import time


class TtlCache:
    """In-process TTL cache. CPython's GIL makes dict get/set safe under concurrency."""

    def __init__(self, ttl: int = 3600):
        self._store: dict[str, tuple] = {}
        self._ttl = ttl

    def get(self, key: str):
        entry = self._store.get(key)
        if entry is None:
            return None
        data, ts = entry
        return data if time.time() - ts < self._ttl else None

    def set(self, key: str, data):
        self._store[key] = (data, time.time())
        return data

    def get_or_set(self, key: str, fetcher):
        """Return cached value, or call fetcher(), cache its result, and return it."""
        cached = self.get(key)
        if cached is not None:
            return cached
        return self.set(key, fetcher())
