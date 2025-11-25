from typing import Optional

from src.exceptions import ValidationError, APIError
from src.resources import BaseResource
from src.resources.decorators import (
    cache_result,
    retry,
    timeout,
    log_execution,
    handle_errors,
    measure_time,
)
import logging

from src.resources.schemas import StoreCreate, Store
from src.resources.utils import suggest_name, validate_address, get_area, get_zone

logger = logging.getLogger(__name__)


class StoresResource(BaseResource):
    """Manage stores and cities with comprehensive decorator usage"""

    @cache_result(ttl=3600, key_params=["city_name"])
    @retry(max_attempts=3, delay=1.0, backoff=2.0)
    @timeout(10.0)
    @log_execution(level="INFO")
    @handle_errors(raise_errors=(ValidationError,))
    async def _get_city_id(self, city_name: str) -> int:
        """
        Get city ID by city name with caching and retry logic.

        Args:
            city_name: Name of the city

        Returns:
            City ID

        Raises:
            ValidationError: If city not found
            APIError: If API request fails
        """
        try:
            data = await self._request("GET", "/aladdin/api/v1/city-list")

            if "data" not in data or "data" not in data["data"]:
                raise APIError("Invalid API response format for city list")

            cities = data["data"]["data"]
            city_name_upper = city_name.upper()

            for city in cities:
                if city.get("city_name", "").upper() == city_name_upper:
                    logger.info(f"Found city_id={city['id']} for {city_name}")
                    return city["id"]

            available_cities = {c["city_name"] for c in cities if "city_name" in c}
            suggestion = suggest_name(city_name, available_cities)

            if suggestion:
                raise ValidationError(
                    f"City '{city_name}' not found. Did you mean '{suggestion}'?"
                )
            else:
                available = ", ".join(sorted(available_cities)[:10])
                raise ValidationError(
                    f"City '{city_name}' not found. Available: {available}"
                )

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error fetching city ID for '{city_name}': {e}")
            raise APIError(f"Failed to fetch city ID: {str(e)}")

    @cache_result(ttl=1800, key_params=["city_id", "zone_name"])
    @retry(max_attempts=3, delay=1.0, backoff=2.0)
    @timeout(10.0)
    @log_execution(level="INFO")
    async def _get_zone_id(self, city_id: int, zone_name: str) -> int:
        """
        Get zone ID for a specific city with caching.

        Args:
            city_id: ID of the city
            zone_name: Name of the zone

        Returns:
            Zone ID

        Raises:
            ValidationError: If zone not found
            APIError: If API request fails
        """
        try:
            data = await self._request(
                "GET", f"/aladdin/api/v1/cities/{city_id}/zone-list"
            )

            if "data" not in data or "data" not in data["data"]:
                raise APIError("Invalid API response format for zone list")

            zones = data["data"]["data"]
            zone_name_upper = zone_name.upper()

            for zone in zones:
                if zone.get("zone_name", "").upper() == zone_name_upper:
                    logger.info(f"Found zone_id={zone['id']} for {zone_name}")
                    return zone["id"]

            available_zones = {z["zone_name"] for z in zones if "zone_name" in z}
            suggestion = suggest_name(zone_name, available_zones)

            if suggestion:
                raise ValidationError(
                    f"Zone '{zone_name}' not found. Did you mean '{suggestion}'?"
                )
            else:
                available = ", ".join(sorted(available_zones))
                raise ValidationError(
                    f"Zone '{zone_name}' not found. Available: {available}"
                )

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error fetching zone ID for '{zone_name}': {e}")
            raise APIError(f"Failed to fetch zone ID: {str(e)}")

    @cache_result(ttl=1800, key_params=["zone_id", "area_name"])
    @retry(max_attempts=3, delay=1.0, backoff=2.0)
    @timeout(10.0)
    @log_execution(level="INFO")
    async def _get_area_id(self, zone_id: int, area_name: str) -> int:
        """
        Get area ID for a specific zone with caching.

        Args:
            zone_id: ID of the zone
            area_name: Name of the area

        Returns:
            Area ID

        Raises:
            ValidationError: If area not found
            APIError: If API request fails
        """
        try:
            data = await self._request(
                "GET", f"/aladdin/api/v1/zones/{zone_id}/area-list"
            )

            if "data" not in data or "data" not in data["data"]:
                raise APIError("Invalid API response format for area list")

            areas = data["data"]["data"]
            area_name_upper = area_name.upper()

            for area in areas:
                if area.get("area_name", "").upper() == area_name_upper:
                    logger.info(f"Found area_id={area['id']} for {area_name}")
                    return area["id"]

            # Suggest similar area names
            available_areas = {a["area_name"] for a in areas if "area_name" in a}
            suggestion = suggest_name(area_name, available_areas)

            if suggestion:
                raise ValidationError(
                    f"Area '{area_name}' not found. Did you mean '{suggestion}'?"
                )
            else:
                available = ", ".join(sorted(available_areas)[:20])
                raise ValidationError(
                    f"Area '{area_name}' not found. Available: {available}"
                )

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error fetching area ID for '{area_name}': {e}")
            raise APIError(f"Failed to fetch area ID: {str(e)}")

    @measure_time
    @log_execution(level="INFO")
    @handle_errors(raise_errors=(ValidationError, APIError))
    async def create_store(self, store_data: StoreCreate) -> Store:
        """
        Create a new store with comprehensive validation and error handling.

        All decorators work together to provide:
        - Execution time measurement
        - Detailed logging
        - Automatic retries on API failures
        - Caching of city/zone/area lookups
        - Rate limiting
        - Timeout protection

        Args:
            store_data: StoreCreate model containing all store information

        Returns:
            Created Store object

        Raises:
            ValidationError: If validation fails
            APIError: If API request fails after retries
        """
        try:
            validate_address(store_data.address)

            area_name = get_area(store_data.address)
            zone_name = get_zone(store_data.address)

            logger.info(
                f"Creating store '{store_data.name}' in {area_name}, {zone_name}",
                extra={
                    "store_name": store_data.name,
                    "area": area_name,
                    "zone": zone_name,
                    "city": store_data.city_name,
                },
            )

            city_id = await self._get_city_id(store_data.city_name)
            zone_id = await self._get_zone_id(city_id=city_id, zone_name=zone_name)
            area_id = await self._get_area_id(zone_id=zone_id, area_name=area_name)

            payload = {
                "name": store_data.name,
                "contact_name": store_data.contact_name,
                "contact_number": store_data.contact_number,
                "secondary_contact": store_data.secondary_contact,
                "otp_number": store_data.otp_number,
                "address": store_data.address,
                "city_id": city_id,
                "zone_id": zone_id,
                "area_id": area_id,
            }

            payload = {k: v for k, v in payload.items() if v is not None}

            data = await self._request("POST", "/aladdin/api/v1/stores", json=payload)

            if "data" not in data or "store" not in data["data"]:
                raise APIError("Invalid API response format for store creation")

            store = Store(**data["data"]["store"])

            logger.info(
                "Successfully created store",
                extra={
                    "store_id": store.id,
                    "store_name": store.name,
                    "city_id": city_id,
                    "zone_id": zone_id,
                    "area_id": area_id,
                },
            )

            return store

        except (ValidationError, APIError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating store: {e}", exc_info=True)
            raise APIError(f"Failed to create store: {str(e)}")

    @cache_result(ttl=60, key_params=["limit"])  # Cache list for 1 minute
    @retry(max_attempts=2, delay=0.5, backoff=2.0)
    @timeout(15.0)
    @log_execution(level="INFO")
    @handle_errors(default_return=[], raise_errors=(APIError,))
    async def list_stores(self, limit: Optional[int] = None) -> list[Store]:
        """
        List all stores with caching and error handling.

        Args:
            limit: Maximum number of stores to return

        Returns:
            List of Store objects (empty list on non-critical errors)

        Raises:
            APIError: If API request fails critically
        """
        try:
            params = {"limit": limit} if limit else {}
            data = await self._request("GET", "/aladdin/api/v1/stores", params=params)

            if "data" not in data or "stores" not in data["data"]:
                raise APIError("Invalid API response format for store list")

            stores = data["data"]["stores"]
            logger.info(f"Retrieved {len(stores)} stores")

            return [Store(**store) for store in stores]

        except Exception as e:
            logger.error(f"Error listing stores: {e}", exc_info=True)
            raise APIError(f"Failed to list stores: {str(e)}")
