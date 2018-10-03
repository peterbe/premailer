import functools


class _HashedSeq(list):
    # # From CPython
    __slots__ = 'hashvalue'

    def __init__(self, tup, hash=hash):
        self[:] = tup
        self.hashvalue = hash(tup)

    def __hash__(self):
        return self.hashvalue


def function_cache():
    """
        function_cache is a decorator for caching function call.
        The argument to the wrapped function must be hashable else
        it will not work

        Function wrapper accepts max_cache_entries argument which specifies
        the maximum number of different data to cache. Specifying None will not
        limit the size of the cache at all.

        Returns:
            function

    """

    # indicator of cache missed
    sentinel = object()

    def decorator(func):
        cache = {}

        @functools.wraps(func)
        def inner(*args, **kwargs):
            max_cache_entries = kwargs.pop('max_cache_entries', 1000)

            if (
                max_cache_entries is not None and
                not isinstance(max_cache_entries, int)
            ):
                raise TypeError(
                    'Expected max_cache_entries to be an integer or None'
                )

            if max_cache_entries == 0:
                return func(*args, **kwargs)

            keys = args
            if kwargs:
                sorted_items = sorted(kwargs.items())
                for item in sorted_items:
                    keys += item

            hashed = hash(_HashedSeq(keys))
            result = cache.get(hashed, sentinel)
            if result is sentinel:
                result = func(*args, **kwargs)

                if max_cache_entries is None or len(cache) < max_cache_entries:
                    cache[hashed] = result

            return result

        return inner
    return decorator
