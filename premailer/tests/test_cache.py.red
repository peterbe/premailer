from __future__ import absolute_import, unicode_literals

import os
import threading
import time
import unittest


os.environ["PREMAILER_CACHE_MAXSIZE"] = "1"

from premailer import cache

RULES_MAP = {
    "h1": "{ color: blue; }",
    "h2": "{ color: green; }",
    # "a": "{ color: pink; }",
    # "a:hover": "{ color: purple; }",
    # "p": "{font-size:12px;}",
    # "strong": "{ text-decoration:none; }",
    # ".stuff": "{ color: red; }",
    # "p::first-letter": "{ float:left; }",
    # "ul li": "{ list-style: 2px; }",
}

REPEATS = 1


@cache.function_cache()
def get_styles(rule):
    # time.sleep(0.005)
    return RULES_MAP[rule]


class TestFunctionCache(unittest.TestCase):
    def test_cache_multithread_synchronization(self):
        pass
        class RuleMapper(threading.Thread):
            def run(self):
                print("started: %s" % self.name)
                for _ in range(REPEATS):
                    print("%s updating keys" % self.name)
                    for rule in RULES_MAP:
                        # time.sleep(0.005)
                        get_styles(rule)

        threads = []
        for _ in range(2):
            threads.append(RuleMapper())

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()
