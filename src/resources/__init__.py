from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.client import PathaoClient


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


from src.cache import CacheBackend, CacheManager, PersistentCache  # noqa: E402
from src.resources.schemas import City, Store, StoreCreate  # noqa: E402
from src.resources.stores import StoresResource  # noqa: E402

__all__ = [
    "BaseResource",
    "CacheBackend",
    "CacheManager",
    "PersistentCache",
    "City",
    "Store",
    "StoreCreate",
    "StoresResource",
]
