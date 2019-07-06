import functools
import os
import threading

import cachetools


# Available cache options.
CACHE_IMPLEMENTATIONS = {
    "LFU": cachetools.LFUCache,
    "LRU": cachetools.LRUCache,
    "RR": cachetools.RRCache,
    "TTL": cachetools.TTLCache,
}

# Time to live (seconds) for entries in TTL cache. Defaults to 1 hour.
TTL_CACHE_TIMEOUT = 1 * 60 * 60

# Lock to prevent multiple threads from accessing the cache at same time.
CACHE_ACCESS_LOCK = threading.RLock()

cache_type = os.environ.get("PREMAILER_CACHE", "LRU")
if cache_type not in CACHE_IMPLEMENTATIONS:
    raise Exception(
        "Unsupported cache implementation. Available options: %s"
        % "/".join(CACHE_IMPLEMENTATIONS.keys())
    )

cache_init_options = {"maxsize": int(os.environ.get("PREMAILER_CACHE_MAXSIZE", 128))}
if cache_type == "TTL":
    cache_init_options["ttl"] = int(
        os.environ.get("PREMAILER_CACHE_TTL", TTL_CACHE_TIMEOUT)
    )

cache = CACHE_IMPLEMENTATIONS[cache_type](**cache_init_options)


def function_cache(**options):
    def decorator(func):
        @cachetools.cached(cache, lock=CACHE_ACCESS_LOCK)
        @functools.wraps(func)
        def inner(*args, **kwargs):
            return func(*args, **kwargs)

        return inner

    return decorator
