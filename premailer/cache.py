import functools
import os
import threading

from cachetools import cached, LRUCache

cache = LRUCache(maxsize=int(os.environ.get("PREMAILER_CACHE_MAXSIZE", 128)))

# Lock to prevent multiple threads from accessing the cache at same time.
CACHE_ACCESS_LOCK = threading.RLock()


def function_cache(**options):
    def decorator(func):
        @cached(cache, lock=CACHE_ACCESS_LOCK)
        @functools.wraps(func)
        def inner(*args, **kwargs):
            return func(*args, **kwargs)

        return inner

    return decorator
