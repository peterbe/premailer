import imp
import os
import threading
import time
import unittest

import cachetools


class TestFunctionCache(unittest.TestCase):
    def tearDown(self):
        for key in (
            "PREMAILER_CACHE",
            "PREMAILER_CACHE_MAXSIZE",
            "PREMAILER_CACHE_TTL",
        ):
            try:
                del os.environ[key]
            except KeyError:
                pass

    def test_unknown_cache(self):
        os.environ["PREMAILER_CACHE"] = "UNKNOWN"

        with self.assertRaises(Exception) as assert_context:
            imp.load_source("cache.py", os.path.join("premailer", "cache.py"))

        self.assertTrue(
            assert_context.exception.args[0].startswith(
                "Unsupported cache implementation"
            )
        )

    def test_ttl_cache(self):
        os.environ["PREMAILER_CACHE"] = "TTL"
        os.environ["PREMAILER_CACHE_TTL"] = "10"
        os.environ["PREMAILER_CACHE_MAXSIZE"] = "50"

        cache_module = imp.load_source(
            "cache.py", os.path.join("premailer", "cache.py")
        )

        self.assertEquals(type(cache_module.cache), cachetools.TTLCache)
        self.assertEquals(cache_module.cache.maxsize, 50)
        self.assertEquals(cache_module.cache.ttl, 10)

    def test_cache_multithread_synchronization(self):
        """
        Tests thread safety of internal cache access.

        The test will fail if function_cache would not have been thread safe.
        """
        RULES_MAP = {"h1": "{ color: blue; }", "h2": "{ color: green; }"}

        class RuleMapper(threading.Thread):
            def __init__(self):
                super(RuleMapper, self).__init__()
                self.exception = None

            def run(self):
                try:
                    for rule in RULES_MAP:
                        get_styles(rule)
                except KeyError as e:
                    self.exception = e

        class DelayedDeletionLRUCache(cachetools.LRUCache):
            """
            Overrides base LRU implementation to introduce a small delay when
            removing elements from cache.

            The delay makes sure that multiple threads try to pop same item from
            cache, resulting in KeyError being raised. Reference to exception is
            kept to make assertions afterwards.
            """

            def popitem(self):
                try:
                    key = next(iter(self._LRUCache__order))
                except StopIteration:
                    raise KeyError("%s is empty" % self.__class__.__name__)
                else:
                    time.sleep(0.01)
                    return (key, self.pop(key))

        cache_module = imp.load_source(
            "cache.py", os.path.join("premailer", "cache.py")
        )

        # Set module cache to point to overridden implementation.
        cache_module.cache = DelayedDeletionLRUCache(maxsize=1)

        @cache_module.function_cache()
        def get_styles(rule):
            return RULES_MAP[rule]

        threads = [RuleMapper() for _ in range(2)]
        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        exceptions = [thread.exception for thread in threads if thread.exception]
        self.assertTrue(
            not exceptions, "Unexpected exception when accessing Premailer cache."
        )
