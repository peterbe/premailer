import functools
import os

from cachetools import cached, LRUCache


cache = LRUCache(maxsize=int(os.environ.get("PREMAILER_CACHE_MAXSIZE", 128)))


def function_cache(**options):
    def decorator(func):
        @cached(cache)
        @functools.wraps(func)
        def inner(*args, **kwargs):
            return func(*args, **kwargs)

        return inner

    return decorator
