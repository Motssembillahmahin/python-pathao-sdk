from typing import TYPE_CHECKING

from src.resources.cache import CacheManager

if TYPE_CHECKING:
    from src.client import PathaoClient

__all__ = ["CacheManager", "BaseResource"]


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
