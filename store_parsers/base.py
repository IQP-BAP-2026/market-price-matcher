from __future__ import annotations

import json
import sqlite3
import threading
import time
from concurrent.futures import Future
from pathlib import Path

import requests


class BaseStoreParser:
    store_id = "base"
    display_name = "Base Store"

    def __init__(
        self,
        cache_file: Path,
        cache_ttl_hours: float = 12,
        timeout_seconds: int = 25,
        max_retries: int = 3,
        pool_size: int = 24,
    ):
        self.cache_file = Path(cache_file)
        self.cache_ttl_seconds = max(0.0, float(cache_ttl_hours)) * 3600.0
        self.timeout_seconds = int(timeout_seconds)
        self.max_retries = int(max_retries)
        self.pool_size = int(pool_size)
        self.local = threading.local()
        self.cache_lock = threading.Lock()
        self.db_lock = threading.Lock()
        self.page_futures: dict[str, Future] = {}
        self.db = sqlite3.connect(self.cache_file, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS store_search_cache (
                cache_key TEXT PRIMARY KEY,
                fetched_at REAL NOT NULL,
                response_json TEXT NOT NULL
            )
            """
        )
        self.db.commit()

    def close(self):
        with self.db_lock:
            try:
                self.db.commit()
                self.db.close()
            except Exception:
                pass

    def clear_cache(self):
        prefix = f"{self.store_id}|%"
        with self.db_lock:
            self.db.execute("DELETE FROM store_search_cache WHERE cache_key LIKE ?", (prefix,))
            self.db.commit()
        with self.cache_lock:
            self.page_futures = {
                k: v for k, v in self.page_futures.items() if not k.startswith(f"{self.store_id}|")
            }

    def _headers(self) -> dict[str, str]:
        return {
            "accept": "application/json,text/plain,*/*",
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/152 Safari/537.36"
            ),
        }

    def _session(self) -> requests.Session:
        session = getattr(self.local, "session", None)
        if session is None:
            session = requests.Session()
            session.headers.update(self._headers())
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=self.pool_size,
                pool_maxsize=self.pool_size,
                max_retries=0,
            )
            session.mount("https://", adapter)
            session.mount("http://", adapter)
            self.local.session = session
        return session

    def _cache_key(self, query: str, page: int) -> str:
        q = " ".join(str(query).lower().split())
        return f"{self.store_id}|{q}|{page}"

    def _disk_cache_get(self, key: str):
        if self.cache_ttl_seconds <= 0:
            return None
        cutoff = time.time() - self.cache_ttl_seconds
        with self.db_lock:
            row = self.db.execute(
                "SELECT fetched_at, response_json FROM store_search_cache WHERE cache_key = ?",
                (key,),
            ).fetchone()
        if not row or row[0] < cutoff:
            return None
        try:
            return json.loads(row[1])
        except Exception:
            return None

    def _disk_cache_set(self, key: str, result: dict):
        if self.cache_ttl_seconds <= 0:
            return
        payload = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
        with self.db_lock:
            self.db.execute(
                """
                INSERT INTO store_search_cache(cache_key, fetched_at, response_json)
                VALUES (?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    fetched_at = excluded.fetched_at,
                    response_json = excluded.response_json
                """,
                (key, time.time(), payload),
            )
            self.db.commit()

    def _fetch_page(self, query: str, page: int) -> dict:
        raise NotImplementedError

    def _search_page(self, query: str, page: int) -> dict:
        key = self._cache_key(query, page)
        cached = self._disk_cache_get(key)
        if cached is not None:
            return cached

        with self.cache_lock:
            future = self.page_futures.get(key)
            if future is None:
                future = Future()
                self.page_futures[key] = future
                owner = True
            else:
                owner = False

        if not owner:
            return future.result()

        try:
            result = self._fetch_page(query, page)
            self._disk_cache_set(key, result)
            future.set_result(result)
            return result
        except Exception as exc:
            future.set_exception(exc)
            with self.cache_lock:
                if self.page_futures.get(key) is future:
                    del self.page_futures[key]
            raise

    def search_pages(self, query: str):
        page = 1
        while True:
            result = self._search_page(query, page)
            yield result
            if not result.get("has_more"):
                break
            page += 1
            if page > self.max_pages:
                break

    @property
    def max_pages(self) -> int:
        return 1

    @property
    def deep_max_pages(self) -> int:
        """Adapters without deeper pagination stop at their normal page limit."""
        return self.max_pages
