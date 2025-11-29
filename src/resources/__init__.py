from src.resources.cache import CacheBackend, CacheManager, PersistentCache
from src.resources.schemas import City, Store, StoreCreate
from src.resources.stores import StoresResource


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.client import PathaoClient

__all__ = [
    "CacheBackend",
    "CacheManager",
    "PersistentCache",
    "BaseResource",
    "City",
    "Store",
    "StoreCreate",
    "StoresResource",
]


class BaseResource:
    """Base class for API resources"""

    def __init__(self, client: "PathaoClient"):
        self._client = client
        self._http = client.http_client

    async def _request(self, method: str, endpoint: str, **kwargs):
        """Make authenticated request"""
        response = await self._http.request(method, endpoint, **kwargs)
        response.raise_for_status()
        return response.json()
