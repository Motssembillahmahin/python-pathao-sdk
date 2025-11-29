from datetime import datetime, timedelta
from typing import Optional, Dict
import httpx
from pydantic import BaseModel

from src.cache import PersistentCache


class TokenData(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: datetime
    token_type: str = "Bearer"

    def is_expired(self) -> bool:
        return datetime.now() >= (self.expires_at - timedelta(seconds=60))


class AuthManager:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        username: str,
        password: str,
        base_url: str,
        cache_backend: PersistentCache = None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.username = username
        self.password = password
        self.base_url = base_url
        self.cache_backend = cache_backend
        self._token_data: Optional[TokenData] = None
        self._http_client = httpx.AsyncClient()

        if self.cache_backend is None:
            self.cache_backend = PersistentCache()

    async def get_access_token(self) -> str:
        """Get valid access token, refreshing if needed"""
        if self._token_data is None or self._token_data.is_expired():
            await self._refresh_or_authenticate()
        return self._token_data.access_token

    async def _refresh_or_authenticate(self):
        """Refresh existing token or get new one"""
        if self._token_data and self._token_data.refresh_token:
            await self._refresh_token()
        else:
            await self._authenticate()

    async def _authenticate(self):
        """Initial authentication to get tokens"""
        response = await self._http_client.post(
            f"{self.base_url}/aladdin/api/v1/issue-token",
            json={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "username": self.username,
                "password": self.password,
                "grant_type": "password",
            },
        )
        response.raise_for_status()
        await self._store_token(response.json())

    async def _refresh_token(self):
        """Refresh access token using refresh token"""
        response = await self._http_client.post(
            f"{self.base_url}/aladdin/api/v1/issue-token",
            json={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self._token_data.refresh_token,
                "grant_type": "refresh_token",
            },
        )
        response.raise_for_status()
        await self._store_token(response.json())

    async def _store_token(self, token_response: Dict):
        """Store token in memory and database"""
        expires_in = token_response.get("expires_in", 3600)
        expires_at = datetime.now() + timedelta(seconds=expires_in)

        self._token_data = TokenData(
            access_token=token_response["access_token"],
            refresh_token=token_response.get("refresh_token"),
            expires_at=expires_at,
            token_type=token_response.get("token_type", "Bearer"),
        )

        token_data_dict = {
            "access_token": token_response["access_token"],
            "refresh_token": token_response.get("refresh_token"),
            "expires_at": expires_at.isoformat(),
            "token_type": token_response.get("token_type", "Bearer"),
        }

        await self.cache_backend.save_token(self.client_id, token_data_dict)


class PathaoAuth(httpx.Auth):
    requires_response_body = False

    def __init__(self, auth_manager: AuthManager):
        self.auth_manager = auth_manager
        self._retry_count = 0
        self._max_retries = 1

    async def async_auth_flow(self, request):
        token = await self.auth_manager.get_access_token()
        request.headers["Authorization"] = f"Bearer {token}"

        response = yield request

        if response.status_code == 401 and self._retry_count < self._max_retries:
            self._retry_count += 1

            await self.auth_manager._refresh_or_authenticate()
            token = await self.auth_manager.get_access_token()
            request.headers["Authorization"] = f"Bearer {token}"

            yield request
