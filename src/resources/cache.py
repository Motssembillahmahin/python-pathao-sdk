"""
Cache implementation for storing and retrieving reference data.

This module provides persistent and in-memory caching capabilities for
rarely-changing reference data like cities, zones, and areas.
"""

import json
import sqlite3
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Any, Dict, Callable
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CacheBackend(ABC):
    """
    Abstract interface for cache storage backends.

    Implementations can use different storage mechanisms (SQLite, Redis, etc.)
    while providing a consistent interface.
    """

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """
        Retrieve a value from cache.

        Args:
            key: Cache key to lookup

        Returns:
            Cached value if found and not expired, None otherwise
        """
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        Store a value in cache with optional TTL.

        Args:
            key: Cache key
            value: Value to cache (must be JSON-serializable)
            ttl: Time-to-live in seconds (None for default)
        """
        pass

    @abstractmethod
    async def delete(self, key: str):
        """
        Remove a value from cache.

        Args:
            key: Cache key to delete
        """
        pass

    @abstractmethod
    async def clear(self):
        """Remove all values from cache."""
        pass


class PersistentCache(CacheBackend):
    """
    File-based persistent cache using SQLite.

    This cache survives application restarts and uses only Python's standard
    library. No external dependencies required.

    Features:
        - Automatic expiration of stale entries
        - Thread-safe SQLite operations
        - Efficient indexing for fast lookups
        - Supports in-memory mode for testing

    Attributes:
        storage_path: Path to SQLite database file
        default_ttl_seconds: Default time-to-live for cached items

    Examples:
        File-based persistent cache:
            >>> cache = PersistentCache(storage_path=".cache/data.db")
            >>> await cache.set("key", "value", ttl=3600)
            >>> value = await cache.get("key")

        In-memory cache (for testing):
            >>> cache = PersistentCache(storage_path=":memory:")
            >>> await cache.set("key", "value")
    """

    def __init__(
        self,
        storage_path: str = ".cache/store_cache.db",
        default_ttl_seconds: int = 604800,  # 7 days
    ):
        """
        Initialize persistent cache with SQLite backend.

        Args:
            storage_path: Path to SQLite database file.
                Use ":memory:" for in-memory (non-persistent) cache.
                Default: ".cache/store_cache.db"
            default_ttl_seconds: Default time-to-live in seconds.
                Default: 604800 (7 days)
        """
        self.storage_path = (
            Path(storage_path) if storage_path != ":memory:" else storage_path
        )
        self.default_ttl_seconds = default_ttl_seconds

        if self.storage_path != ":memory:":
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            logger.info(f"Initialized persistent cache at {self.storage_path}")
        else:
            logger.info("Initialized in-memory cache")

        self._initialize_database()

    def _initialize_database(self):
        """Create database schema if it doesn't exist."""
        db_path = (
            str(self.storage_path) if self.storage_path != ":memory:" else ":memory:"
        )

        with sqlite3.connect(db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_entries (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_expiration ON cache_entries(expires_at)"
            )
            conn.commit()

    def _get_connection(self):
        """Get database connection."""
        db_path = (
            str(self.storage_path) if self.storage_path != ":memory:" else ":memory:"
        )
        return sqlite3.connect(db_path)

    async def get(self, key: str) -> Optional[Any]:
        """
        Retrieve value from cache if not expired.

        Args:
            key: Cache key to lookup

        Returns:
            Cached value (deserialized from JSON) or None if not found/expired
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT value FROM cache_entries
                WHERE key = ? AND expires_at > datetime('now')
                """,
                (key,),
            )
            result = cursor.fetchone()

            if result:
                logger.debug(f"Cache HIT: {key}")
                return json.loads(result[0])

            logger.debug(f"Cache MISS: {key}")
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        Store value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache (must be JSON-serializable)
            ttl: Time-to-live in seconds (uses default if None)
        """
        ttl = ttl or self.default_ttl_seconds
        expires_at = datetime.now() + timedelta(seconds=ttl)

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO cache_entries (key, value, expires_at)
                VALUES (?, ?, ?)
                """,
                (key, json.dumps(value), expires_at),
            )
            conn.commit()

        logger.debug(f"Cache SET: {key} (TTL: {ttl}s)")

    async def delete(self, key: str):
        """
        Remove entry from cache.

        Args:
            key: Cache key to delete
        """
        with self._get_connection() as conn:
            conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
            conn.commit()

        logger.debug(f"Cache DELETE: {key}")

    async def clear(self):
        """Remove all entries from cache."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM cache_entries")
            conn.commit()

        logger.info("Cache cleared (all entries removed)")

    def cleanup_expired(self):
        """
        Remove expired entries from database.

        This is a maintenance operation that can be called periodically
        to reclaim disk space. Not required for normal operation as
        expired entries are automatically ignored during reads.

        Returns:
            Number of entries removed
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM cache_entries WHERE expires_at <= datetime('now')"
            )
            conn.commit()
            deleted = cursor.rowcount

            if deleted > 0:
                logger.info(f"Cleaned up {deleted} expired cache entries")

            return deleted


class CacheManager:
    """
    Manages caching of reference data with bulk prefetch strategy.

    This manager implements an intelligent caching strategy optimized for
    rarely-changing reference data (cities, zones, areas):
    - Bulk prefetch: Fetches all data at once instead of one-by-one
    - Two-tier storage: In-memory index + persistent backend
    - Lazy loading: Only fetches data when needed
    - Long TTL: Caches data for extended periods (default: 7 days)

    The bulk prefetch strategy dramatically reduces API calls:
    - Without caching: 3 API calls per store creation
    - With this manager: 3 API calls total (for all stores)

    Attributes:
        cache: Underlying cache backend (persistent or in-memory)
        prefetch_ttl_seconds: TTL for bulk-prefetched data

    Examples:
        >>> cache = PersistentCache()
        >>> manager = CacheManager(cache_backend=cache)
        >>>
        >>> # Prefetch all cities
        >>> await manager.prefetch_cities(fetch_all_cities_func)
        >>>
        >>> # Quick lookup (from in-memory index)
        >>> city_id = manager.get_city_id("Dhaka")
    """

    def __init__(
        self,
        cache_backend: CacheBackend,
        prefetch_ttl_seconds: int = 604800,  # 7 days
    ):
        """
        Initialize cache manager with backend.

        Args:
            cache_backend: Cache storage implementation
            prefetch_ttl_seconds: TTL for prefetched bulk data in seconds.
                Default: 604800 (7 days)
        """
        self.cache = cache_backend
        self.prefetch_ttl_seconds = prefetch_ttl_seconds

        self._cities: Dict[str, int] = {}
        self._zones: Dict[int, Dict[str, int]] = {}
        self._areas: Dict[int, Dict[str, int]] = {}

        logger.debug("Cache manager initialized")

    async def prefetch_cities(self, fetch_func: Callable) -> Dict[str, int]:
        """
        Prefetch all cities in one API call and cache them.

        This method implements a bulk fetch strategy:
        1. Check if cities are already cached
        2. If not, fetch all cities via the provided function
        3. Build an index for fast lookups
        4. Store in persistent cache for future use

        Args:
            fetch_func: Async function that returns list of city dicts.
                Each dict must have 'id' and 'city_name' keys.

        Returns:
            Dictionary mapping city_name (uppercase) to city_id

        Examples:
            >>> async def fetch_all_cities():
            ...     data = await api_client.request('GET', '/cities')
            ...     return data['data']['cities']
            >>>
            >>> cities = await manager.prefetch_cities(fetch_all_cities)
            >>> print(f"Cached {len(cities)} cities")
        """
        cache_key = "bulk:cities"

        cached = await self.cache.get(cache_key)
        if cached:
            self._cities = cached
            logger.info(f"Loaded {len(cached)} cities from cache")
            return cached

        logger.info("Fetching all cities from API (cache miss)...")
        cities_data = await fetch_func()

        cities_index = {city["city_name"].upper(): city["id"] for city in cities_data}

        await self.cache.set(cache_key, cities_index, ttl=self.prefetch_ttl_seconds)
        self._cities = cities_index

        logger.info(
            f"Cached {len(cities_index)} cities (TTL: {self.prefetch_ttl_seconds}s)"
        )
        return cities_index

    async def prefetch_zones(
        self, city_id: int, fetch_func: Callable
    ) -> Dict[str, int]:
        """
        Prefetch all zones for a city in one API call and cache them.

        Args:
            city_id: ID of the city
            fetch_func: Async function that returns list of zone dicts.
                Each dict must have 'id' and 'zone_name' keys.

        Returns:
            Dictionary mapping zone_name (uppercase) to zone_id
        """
        cache_key = f"bulk:zones:{city_id}"

        cached = await self.cache.get(cache_key)
        if cached:
            if city_id not in self._zones:
                self._zones[city_id] = {}
            self._zones[city_id] = cached
            logger.info(f"Loaded {len(cached)} zones for city {city_id} from cache")
            return cached

        # Cache miss - fetch from API
        logger.info(f"Fetching all zones for city {city_id} from API (cache miss)...")
        zones_data = await fetch_func()

        zones_index = {zone["zone_name"].upper(): zone["id"] for zone in zones_data}

        await self.cache.set(cache_key, zones_index, ttl=self.prefetch_ttl_seconds)

        if city_id not in self._zones:
            self._zones[city_id] = {}
        self._zones[city_id] = zones_index

        logger.info(f"Cached {len(zones_index)} zones for city {city_id}")
        return zones_index

    async def prefetch_areas(
        self, zone_id: int, fetch_func: Callable
    ) -> Dict[str, int]:
        """
        Prefetch all areas for a zone in one API call and cache them.

        Args:
            zone_id: ID of the zone
            fetch_func: Async function that returns list of area dicts.
                Each dict must have 'id' and 'area_name' keys.

        Returns:
            Dictionary mapping area_name (uppercase) to area_id
        """
        cache_key = f"bulk:areas:{zone_id}"

        cached = await self.cache.get(cache_key)
        if cached:
            if zone_id not in self._areas:
                self._areas[zone_id] = {}
            self._areas[zone_id] = cached
            logger.info(f"Loaded {len(cached)} areas for zone {zone_id} from cache")
            return cached

        logger.info(f"Fetching all areas for zone {zone_id} from API (cache miss)...")
        areas_data = await fetch_func()

        areas_index = {area["area_name"].upper(): area["id"] for area in areas_data}

        await self.cache.set(cache_key, areas_index, ttl=self.prefetch_ttl_seconds)

        if zone_id not in self._areas:
            self._areas[zone_id] = {}
        self._areas[zone_id] = areas_index

        logger.info(f"Cached {len(areas_index)} areas for zone {zone_id}")
        return areas_index

    def get_city_id(self, city_name: str) -> Optional[int]:
        """
        Get city ID from in-memory index (instant lookup).

        Args:
            city_name: Name of the city (case-insensitive)

        Returns:
            City ID if found, None otherwise
        """
        return self._cities.get(city_name.upper())

    def get_zone_id(self, city_id: int, zone_name: str) -> Optional[int]:
        """
        Get zone ID from in-memory index (instant lookup).

        Args:
            city_id: ID of the parent city
            zone_name: Name of the zone (case-insensitive)

        Returns:
            Zone ID if found, None otherwise
        """
        zones = self._zones.get(city_id, {})
        return zones.get(zone_name.upper())

    def get_area_id(self, zone_id: int, area_name: str) -> Optional[int]:
        """
        Get area ID from in-memory index (instant lookup).

        Args:
            zone_id: ID of the parent zone
            area_name: Name of the area (case-insensitive)

        Returns:
            Area ID if found, None otherwise
        """
        areas = self._areas.get(zone_id, {})
        return areas.get(area_name.upper())
