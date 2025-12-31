"""
SQLite-based storage for API usage tracking.

Stores hourly aggregates of token usage per API key and model,
enabling cost tracking and usage analytics.
"""
import sqlite3
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import settings

logger = logging.getLogger(__name__)


class UsageStorage:
    """Manages usage data storage in SQLite with hourly aggregates."""

    def __init__(self, db_file: Optional[str] = None):
        """Initialize usage storage.

        Args:
            db_file: Path to SQLite database. Defaults to settings.USAGE_DB_FILE.
        """
        self.db_file = db_file or settings.USAGE_DB_FILE
        self._ensure_db_directory()
        self._init_db()

    def _ensure_db_directory(self):
        """Ensure the database directory exists with proper permissions."""
        db_path = Path(self.db_file)
        db_dir = db_path.parent

        if not db_dir.exists():
            db_dir.mkdir(parents=True, mode=0o700)
            logger.info(f"Created usage database directory: {db_dir}")

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with row factory enabled."""
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize database schema if not exists."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Create hourly usage table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS usage_hourly (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key_id TEXT NOT NULL,
                    model TEXT NOT NULL,
                    hour_timestamp INTEGER NOT NULL,
                    input_tokens INTEGER DEFAULT 0,
                    output_tokens INTEGER DEFAULT 0,
                    cache_read_tokens INTEGER DEFAULT 0,
                    cache_creation_tokens INTEGER DEFAULT 0,
                    request_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(key_id, model, hour_timestamp)
                )
            """)

            # Create indexes for efficient queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_usage_key_id
                ON usage_hourly(key_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_usage_timestamp
                ON usage_hourly(hour_timestamp)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_usage_key_timestamp
                ON usage_hourly(key_id, hour_timestamp)
            """)

            conn.commit()
            logger.debug(f"Usage database initialized: {self.db_file}")
        finally:
            conn.close()

    @staticmethod
    def _get_hour_timestamp() -> int:
        """Get current Unix timestamp truncated to the hour."""
        now = datetime.now(timezone.utc)
        # Truncate to hour by zeroing minutes, seconds, microseconds
        hour_dt = now.replace(minute=0, second=0, microsecond=0)
        return int(hour_dt.timestamp())

    @staticmethod
    def _get_current_iso() -> str:
        """Get current time as ISO 8601 string."""
        return datetime.now(timezone.utc).isoformat()

    def record_usage(
        self,
        key_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        cache_creation_tokens: int = 0
    ):
        """Record API usage for a request.

        Uses upsert to increment hourly aggregates. Multiple requests
        within the same hour for the same key/model combination will
        be aggregated into a single row.

        Args:
            key_id: The API key ID
            model: The Anthropic model used
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cache_read_tokens: Tokens read from cache
            cache_creation_tokens: Tokens written to cache
        """
        hour_timestamp = self._get_hour_timestamp()
        now = self._get_current_iso()

        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Upsert: insert or update existing row
            cursor.execute("""
                INSERT INTO usage_hourly (
                    key_id, model, hour_timestamp,
                    input_tokens, output_tokens,
                    cache_read_tokens, cache_creation_tokens,
                    request_count, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                ON CONFLICT(key_id, model, hour_timestamp) DO UPDATE SET
                    input_tokens = input_tokens + excluded.input_tokens,
                    output_tokens = output_tokens + excluded.output_tokens,
                    cache_read_tokens = cache_read_tokens + excluded.cache_read_tokens,
                    cache_creation_tokens = cache_creation_tokens + excluded.cache_creation_tokens,
                    request_count = request_count + 1,
                    updated_at = excluded.updated_at
            """, (
                key_id, model, hour_timestamp,
                input_tokens, output_tokens,
                cache_read_tokens, cache_creation_tokens,
                now, now
            ))

            conn.commit()
            logger.debug(
                f"Recorded usage: key={key_id}, model={model}, "
                f"in={input_tokens}, out={output_tokens}, "
                f"cache_read={cache_read_tokens}, cache_create={cache_creation_tokens}"
            )
        except Exception as e:
            logger.error(f"Failed to record usage: {e}")
            raise
        finally:
            conn.close()

    def get_usage_summary(self, key_id: str) -> Dict:
        """Get total usage summary for an API key.

        Args:
            key_id: The API key ID

        Returns:
            Dictionary with total token counts and request count
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    COALESCE(SUM(input_tokens), 0) as total_input_tokens,
                    COALESCE(SUM(output_tokens), 0) as total_output_tokens,
                    COALESCE(SUM(cache_read_tokens), 0) as total_cache_read_tokens,
                    COALESCE(SUM(cache_creation_tokens), 0) as total_cache_creation_tokens,
                    COALESCE(SUM(request_count), 0) as total_requests,
                    MIN(created_at) as first_usage,
                    MAX(updated_at) as last_usage
                FROM usage_hourly
                WHERE key_id = ?
            """, (key_id,))

            row = cursor.fetchone()
            if row:
                return {
                    "key_id": key_id,
                    "total_input_tokens": row["total_input_tokens"],
                    "total_output_tokens": row["total_output_tokens"],
                    "total_cache_read_tokens": row["total_cache_read_tokens"],
                    "total_cache_creation_tokens": row["total_cache_creation_tokens"],
                    "total_requests": row["total_requests"],
                    "first_usage": row["first_usage"],
                    "last_usage": row["last_usage"],
                }
            return {
                "key_id": key_id,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_cache_read_tokens": 0,
                "total_cache_creation_tokens": 0,
                "total_requests": 0,
                "first_usage": None,
                "last_usage": None,
            }
        finally:
            conn.close()

    def get_hourly_usage(self, key_id: str, hours: int = 24) -> List[Dict]:
        """Get hourly usage breakdown for the last N hours.

        Args:
            key_id: The API key ID
            hours: Number of hours to retrieve (default 24)

        Returns:
            List of hourly usage records
        """
        # Calculate cutoff timestamp
        now = datetime.now(timezone.utc)
        cutoff = now.replace(minute=0, second=0, microsecond=0)
        cutoff_ts = int(cutoff.timestamp()) - (hours * 3600)

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    hour_timestamp,
                    SUM(input_tokens) as input_tokens,
                    SUM(output_tokens) as output_tokens,
                    SUM(cache_read_tokens) as cache_read_tokens,
                    SUM(cache_creation_tokens) as cache_creation_tokens,
                    SUM(request_count) as request_count
                FROM usage_hourly
                WHERE key_id = ? AND hour_timestamp >= ?
                GROUP BY hour_timestamp
                ORDER BY hour_timestamp ASC
            """, (key_id, cutoff_ts))

            results = []
            for row in cursor.fetchall():
                ts = datetime.fromtimestamp(row["hour_timestamp"], tz=timezone.utc)
                results.append({
                    "timestamp": ts.isoformat(),
                    "hour": ts.hour,
                    "input_tokens": row["input_tokens"],
                    "output_tokens": row["output_tokens"],
                    "cache_read_tokens": row["cache_read_tokens"],
                    "cache_creation_tokens": row["cache_creation_tokens"],
                    "request_count": row["request_count"],
                })
            return results
        finally:
            conn.close()

    def get_daily_usage(self, key_id: str, days: int = 30) -> List[Dict]:
        """Get daily usage breakdown for the last N days.

        Args:
            key_id: The API key ID
            days: Number of days to retrieve (default 30)

        Returns:
            List of daily usage records
        """
        # Calculate cutoff timestamp (start of day N days ago)
        now = datetime.now(timezone.utc)
        cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff_ts = int(cutoff.timestamp()) - (days * 86400)

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            # Group by date by dividing timestamp by 86400 (seconds per day)
            cursor.execute("""
                SELECT
                    (hour_timestamp / 86400) * 86400 as day_timestamp,
                    SUM(input_tokens) as input_tokens,
                    SUM(output_tokens) as output_tokens,
                    SUM(cache_read_tokens) as cache_read_tokens,
                    SUM(cache_creation_tokens) as cache_creation_tokens,
                    SUM(request_count) as request_count
                FROM usage_hourly
                WHERE key_id = ? AND hour_timestamp >= ?
                GROUP BY day_timestamp
                ORDER BY day_timestamp ASC
            """, (key_id, cutoff_ts))

            results = []
            for row in cursor.fetchall():
                ts = datetime.fromtimestamp(row["day_timestamp"], tz=timezone.utc)
                results.append({
                    "date": ts.strftime("%Y-%m-%d"),
                    "input_tokens": row["input_tokens"],
                    "output_tokens": row["output_tokens"],
                    "cache_read_tokens": row["cache_read_tokens"],
                    "cache_creation_tokens": row["cache_creation_tokens"],
                    "request_count": row["request_count"],
                })
            return results
        finally:
            conn.close()

    def get_usage_by_model(self, key_id: str) -> List[Dict]:
        """Get usage breakdown by model for an API key.

        Args:
            key_id: The API key ID

        Returns:
            List of per-model usage records
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    model,
                    SUM(input_tokens) as input_tokens,
                    SUM(output_tokens) as output_tokens,
                    SUM(cache_read_tokens) as cache_read_tokens,
                    SUM(cache_creation_tokens) as cache_creation_tokens,
                    SUM(request_count) as request_count
                FROM usage_hourly
                WHERE key_id = ?
                GROUP BY model
                ORDER BY request_count DESC
            """, (key_id,))

            results = []
            for row in cursor.fetchall():
                results.append({
                    "model": row["model"],
                    "input_tokens": row["input_tokens"],
                    "output_tokens": row["output_tokens"],
                    "cache_read_tokens": row["cache_read_tokens"],
                    "cache_creation_tokens": row["cache_creation_tokens"],
                    "request_count": row["request_count"],
                })
            return results
        finally:
            conn.close()

    def delete_key_usage(self, key_id: str) -> int:
        """Delete all usage data for an API key.

        Called when an API key is deleted.

        Args:
            key_id: The API key ID

        Returns:
            Number of rows deleted
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM usage_hourly WHERE key_id = ?",
                (key_id,)
            )
            deleted = cursor.rowcount
            conn.commit()
            logger.info(f"Deleted {deleted} usage records for key {key_id}")
            return deleted
        finally:
            conn.close()
