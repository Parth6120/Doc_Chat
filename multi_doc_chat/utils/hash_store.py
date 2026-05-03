import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import redis


class HashStore:
    """
    Persists SHA-256 hashes of ingested files in Redis so the same
    content is never chunked and upserted twice.
    """
    _KEY_PREFIX = "ingested:"

    def __init__(self, redis_url: str):
        self._client = redis.Redis.from_url(redis_url, decode_responses=True)

    def is_ingested(self, file_hash: str) -> bool:
        return bool(self._client.exists(self._KEY_PREFIX + file_hash))

    def register(self, file_hash: str, filename: str, namespace: str) -> None:
        value = json.dumps({
            "filename": filename,
            "namespace": namespace,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        })
        self._client.set(self._KEY_PREFIX + file_hash, value)

    @staticmethod
    def hash_file(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(8192), b""):
                h.update(block)
        return h.hexdigest()
