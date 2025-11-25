import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Any
from datetime import datetime, timedelta
import sqlite3

logger = logging.getLogger(__name__)


class CacheBackend(ABC):
    """
    Abstract cache interface. Users can implement their own backends.
    Package provides SQLite built-in implementations SQLite.
    """

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set value in cache with optional TTL"""
        pass

    @abstractmethod
    async def delete(self, key: str):
        """Delete cache entry"""
        pass

    @abstractmethod
    async def clear(self):
        """Clear all cache entries"""
        pass


class SQLiteCache(CacheBackend):
    """SQLite-based persistent cache. Uses only stdlib, survives restarts."""

    def __init__(
        self, db_path: str = ".cache/store_cache.db", default_ttl: int = 86400 * 7
    ):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.default_ttl = default_ttl
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    expires_at TIMESTAMP NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_expires ON cache(expires_at)")
            conn.commit()

    async def get(self, key: str) -> Optional[Any]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT value FROM cache WHERE key = ? AND expires_at > datetime('now')",
                (key,),
            )
            result = cursor.fetchone()
            return json.loads(result[0]) if result else None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        ttl = ttl or self.default_ttl
        expires_at = datetime.now() + timedelta(seconds=ttl)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache (key, value, expires_at) VALUES (?, ?, ?)",
                (key, json.dumps(value), expires_at),
            )
            conn.commit()

    async def delete(self, key: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            conn.commit()

    async def clear(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM cache")
            conn.commit()
