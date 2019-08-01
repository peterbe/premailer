premailer Changes
=================

Peter's note: Unfortunately, ``premailer`` has never kept a change log. But it's
never too late to start, so let's start here and now.

dev
-----

* Add ``allow_insecure_ssl`` option for external URLs

3.5.0
-----

* Change default ``cachetools`` implementation to ``cachetools.LFUCache``.

* Now possible to change ``cachetools`` implementation with environment variables.
  See README.rst.

* To avoid thread unsafe execution, the function caching decorator now employs a lock.
  See https://github.com/peterbe/premailer/issues/225
