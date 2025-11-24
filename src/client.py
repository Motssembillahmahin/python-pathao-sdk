import httpx
from .auth import AuthManager, PathaoAuth
from .config import PathaoConfig


class PathaoClient:
    """Framework-agnostic Pathao API client"""

    def __init__(
        self,
        client_id: str = None,
        client_secret: str = None,
        config: PathaoConfig = None,
    ):
        if config is None:
            config = PathaoConfig(
                pathao_client_id=client_id, pathao_client_secret=client_secret
            )

        self.config = config
        self.auth_manager = AuthManager(
            client_id=config.pathao_client_id,
            client_secret=config.pathao_client_secret,
            base_url=config.pathao_base_url,
        )

        self.http_client = httpx.AsyncClient(
            auth=PathaoAuth(self.auth_manager),
            base_url=config.pathao_base_url,
            timeout=30.0,
        )

        # TODO: Initialize resources

    async def close(self):
        """Close HTTP client"""
        await self.http_client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
