import functools

class _HashedSeq(list):
    # # From CPython
    __slots__ = 'hashvalue'

    def __init__(self, tup, hash=hash):
        self[:] = tup
        self.hashvalue = hash(tup)

    def __hash__(self):
        return self.hashvalue

## if we only have nonlocal
class _Cache(object):
    def __init__(self):
        self.off = False
        self.missed = 0
        self.cache = {}

def function_cache(expected_max_entries=1000):
    
    if expected_max_entries is not None and not isinstance(expected_max_entries, int):
        raise TypeError('Expected expected_max_entries to be an integer or None')
    
    # indicator of cache missed
    sentinel = object() 
    
    def decorator(func):
        cached = _Cache()
    
        @functools.wraps(func)
        def inner(*args, **kwargs):
            if cached.off:
                return func(*args, **kwargs)
            
            keys = args
            if kwargs:
                sorted_items = sorted(kwargs.items())   
                for item in sorted_items:
                    keys += item
                    
            hashed = hash(_HashedSeq(keys))
            result = cached.cache.get(hashed, sentinel)
            if result is sentinel:
                cached.missed += 1
                result = func(*args, **kwargs)
                cached.cache[hashed] = result
                # # something is wrong if we are here more than expected
                # # empty and turn it off
                if expected_max_entries is not None and cached.missed > expected_max_entries:
                    cached.off = True
                    cached.cache.clear()
                    
            return result
            
        return inner
    return decorator
