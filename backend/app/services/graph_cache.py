import json
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("gamemind.cache")

class InMemoryRedisMock:
    """An in-memory dictionary simulating Redis key-value store operations."""
    def __init__(self):
        self._store: Dict[str, bytes] = {}

    def get(self, key: str) -> Optional[bytes]:
        return self._store.get(key)

    def set(self, key: str, value: bytes, ex: Optional[int] = None) -> bool:
        self._store[key] = value
        return True

    def mget(self, keys: List[str]) -> List[Optional[bytes]]:
        return [self._store.get(key) for key in keys]

    def incrby(self, key: str, amount: int = 1) -> int:
        current = self._store.get(key)
        val = 0
        if current is not None:
            try:
                val = int(current)
            except ValueError:
                val = 0
        new_val = val + amount
        self._store[key] = str(new_val).encode("utf-8")
        return new_val

    def exists(self, key: str) -> bool:
        return key in self._store


class GraphCache:
    def __init__(self):
        self.redis = None
        self.is_mock = True
        
        # Try importing and using redis
        try:
            import redis
            from app.config import settings
            
            # Extract host and port from configuration if available
            redis_host = getattr(settings, "REDIS_HOST", "localhost")
            redis_port = getattr(settings, "REDIS_PORT", 6379)
            
            self.redis = redis.Redis(host=redis_host, port=redis_port, socket_timeout=1.0)
            # Ping to verify connection
            self.redis.ping()
            self.is_mock = False
            logger.info(f"Connected to Redis cache at {redis_host}:{redis_port}")
        except Exception as e:
            logger.warning(f"Could not connect to Redis: {e}. Falling back to in-memory cache mock.")
            self.redis = InMemoryRedisMock()
            self.is_mock = True

    # Stamp generation keys
    def _entity_stamp_key(self, slug: str) -> str:
        return f"graph:version:entity:{slug}"

    def _relationship_stamp_key(self, source: str, target: str, rel_type: str) -> str:
        return f"graph:version:relationship:{source}:{target}:{rel_type}"

    # Invalidation increments
    def increment_entity_stamp(self, slug: str) -> int:
        """Increment the version stamp for an entity."""
        key = self._entity_stamp_key(slug)
        try:
            if isinstance(self.redis, InMemoryRedisMock):
                return self.redis.incrby(key, 1)
            else:
                return self.redis.incr(key)
        except Exception as e:
            logger.error(f"Redis increment_entity_stamp failed: {e}")
            return 1

    def increment_relationship_stamp(self, source: str, target: str, rel_type: str) -> int:
        """Increment the version stamp for a relationship."""
        key = self._relationship_stamp_key(source, target, rel_type)
        try:
            if isinstance(self.redis, InMemoryRedisMock):
                return self.redis.incrby(key, 1)
            else:
                return self.redis.incr(key)
        except Exception as e:
            logger.error(f"Redis increment_relationship_stamp failed: {e}")
            return 1

    def get_stamps(self, keys: List[str]) -> List[int]:
        """Fetch current version stamps for multiple keys."""
        if not keys:
            return []
        try:
            raw_vals = self.redis.mget(keys)
            results = []
            for val in raw_vals:
                if val is None:
                    results.append(0)
                else:
                    try:
                        results.append(int(val))
                    except ValueError:
                        results.append(0)
            return results
        except Exception as e:
            logger.error(f"Redis mget failed for stamps: {e}")
            return [0] * len(keys)

    # Cache Traversal Methods
    def get_cached_traversal(
        self, query_prefix: str
    ) -> Tuple[Optional[Any], bool]:
        """
        Check traversal cache.
        Returns:
            Tuple[Optional[Any], bool]: (cached_data, is_hit)
        """
        meta_key = f"{query_prefix}:meta"
        try:
            meta_raw = self.redis.get(meta_key)
            if not meta_raw:
                return None, False

            meta = json.loads(meta_raw.decode("utf-8"))
            stored_stamp = meta.get("stamp")
            elements = meta.get("elements", []) # List of dicts: {"type": "entity"/"relationship", "key": str, "stored_stamp": int}

            if not elements:
                # If there are no elements, we just compare the stored stamp itself (or look up query parameters)
                return None, False

            # Get current stamps for all involved elements
            stamp_keys = [el["key"] for el in elements]
            current_stamps = self.get_stamps(stamp_keys)

            # Validate stamps
            for el, curr_stamp in zip(elements, current_stamps):
                if el["stored_stamp"] != curr_stamp:
                    # Stamp mismatch -> cache is invalid
                    return None, False

            # All stamps match! Retrieve the actual traversal result using the stored stamp
            cache_key = f"{query_prefix}:{stored_stamp}"
            result_raw = self.redis.get(cache_key)
            if not result_raw:
                return None, False

            return json.loads(result_raw.decode("utf-8")), True

        except Exception as e:
            logger.error(f"Error checking traversal cache: {e}")
            return None, False

    def set_cached_traversal(
        self,
        query_prefix: str,
        result_data: Any,
        involved_entities: List[str],
        involved_relationships: List[Tuple[str, str, str]],
        ttl: int = 3600
    ) -> None:
        """
        Cache traversal result along with version-stamp metadata.
        No wildcard eviction is used.
        """
        try:
            # Construct the list of elements and their current stamps
            elements = []
            
            # Map involved entities to stamp keys
            entity_keys = [self._entity_stamp_key(slug) for slug in involved_entities]
            entity_stamps = self.get_stamps(entity_keys)
            for slug, key, stamp in zip(involved_entities, entity_keys, entity_stamps):
                elements.append({
                    "type": "entity",
                    "slug": slug,
                    "key": key,
                    "stored_stamp": stamp
                })

            # Map involved relationships to stamp keys
            rel_keys = [self._relationship_stamp_key(s, t, ty) for s, t, ty in involved_relationships]
            rel_stamps = self.get_stamps(rel_keys)
            for (s, t, ty), key, stamp in zip(involved_relationships, rel_keys, rel_stamps):
                elements.append({
                    "type": "relationship",
                    "source": s,
                    "target": t,
                    "rel_type": ty,
                    "key": key,
                    "stored_stamp": stamp
                })

            # Compute composite stamp (hash or simple sum/join of all version stamps)
            # If no elements are involved (e.g. empty traversal), we can use a stamp of "empty"
            if not elements:
                composite_stamp = "empty"
            else:
                stamp_str = "-".join(f"{el['key']}:{el['stored_stamp']}" for el in elements)
                composite_stamp = str(hash(stamp_str))

            # Store the main cached result
            cache_key = f"{query_prefix}:{composite_stamp}"
            self.redis.set(cache_key, json.dumps(result_data).encode("utf-8"), ex=ttl)

            # Store metadata
            meta_data = {
                "stamp": composite_stamp,
                "elements": elements
            }
            meta_key = f"{query_prefix}:meta"
            self.redis.set(meta_key, json.dumps(meta_data).encode("utf-8"), ex=ttl)

        except Exception as e:
            logger.error(f"Error caching traversal result: {e}")

    # Prompt Fragment Caching methods
    def get_cached_fragment(self, fragment_id: str) -> Tuple[Optional[Dict[str, Any]], bool]:
        """
        Retrieve a cached prompt fragment using version-stamp validation.
        """
        meta_key = f"graph:fragment_meta:{fragment_id}"
        content_key = f"graph:fragment:{fragment_id}"
        try:
            meta_raw = self.redis.get(meta_key)
            if not meta_raw:
                return None, False

            meta = json.loads(meta_raw.decode("utf-8"))
            involved_keys = meta.get("involved_keys", [])
            stored_stamps = meta.get("stored_stamps", [])

            if not involved_keys:
                return None, False

            # Query current stamps
            current_stamps = self.get_stamps(involved_keys)
            for idx, curr_stamp in enumerate(current_stamps):
                if stored_stamps[idx] != curr_stamp:
                    # Mismatch found -> stale fragment
                    return None, False

            # Cache is valid, fetch the content
            content_raw = self.redis.get(content_key)
            if not content_raw:
                return None, False

            return {
                "fragment_id": fragment_id,
                "fragment_type": meta.get("fragment_type"),
                "version_stamp": meta.get("version_stamp"),
                "source_entities": meta.get("source_entities"),
                "content": content_raw.decode("utf-8"),
                "token_estimate": meta.get("token_estimate")
            }, True

        except Exception as e:
            logger.error(f"Error reading cached fragment {fragment_id}: {e}")
            return None, False

    def set_cached_fragment(
        self,
        fragment_id: str,
        fragment_type: str,
        version_stamp: str,
        source_entities: List[str],
        content: str,
        token_estimate: int,
        involved_keys: List[str],
        stored_stamps: List[int],
        ttl: int = 3600
    ) -> None:
        """
        Cache a prompt fragment and its metadata version stamps.
        """
        meta_key = f"graph:fragment_meta:{fragment_id}"
        content_key = f"graph:fragment:{fragment_id}"
        try:
            meta_data = {
                "fragment_type": fragment_type,
                "version_stamp": version_stamp,
                "source_entities": source_entities,
                "token_estimate": token_estimate,
                "involved_keys": involved_keys,
                "stored_stamps": stored_stamps
            }
            self.redis.set(content_key, content.encode("utf-8"), ex=ttl)
            self.redis.set(meta_key, json.dumps(meta_data).encode("utf-8"), ex=ttl)
        except Exception as e:
            logger.error(f"Error caching fragment {fragment_id}: {e}")

graph_cache = GraphCache()

