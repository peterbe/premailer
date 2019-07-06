from __future__ import absolute_import, unicode_literals

import os
import unittest
import imp

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
            cache_fd = open("premailer/cache.py", "r")
            imp.load_source("cache.py", "premailer/cache.py", cache_fd)

        self.assertTrue(
            assert_context.exception.args[0].startswith(
                "Unsupported cache implementation"
            )
        )

    def test_default_cache(self):
        cache_fd = open("premailer/cache.py", "r")
        cache_module = imp.load_source("cache.py", "premailer/cache.py", cache_fd)

        self.assertEquals(type(cache_module.cache), cachetools.LRUCache)
        self.assertEquals(cache_module.cache.maxsize, 128)

    def test_ttl_cache(self):
        os.environ["PREMAILER_CACHE"] = "TTL"
        os.environ["PREMAILER_CACHE_TTL"] = "10"
        os.environ["PREMAILER_CACHE_MAXSIZE"] = "50"

        cache_fd = open("premailer/cache.py", "r")
        cache_module = imp.load_source("cache.py", "premailer/cache.py", cache_fd)

        self.assertEquals(type(cache_module.cache), cachetools.TTLCache)
        self.assertEquals(cache_module.cache.maxsize, 50)
        self.assertEquals(cache_module.cache.ttl, 10)
