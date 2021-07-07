premailer Changes
=================

Peter's note: Unfortunately, ``premailer`` didn't use to keep a change log. But it's
never too late to start, so let's start here and now.

Unreleased
----------
* New option ``session=None`` to provide the session used for making http requests.

3.9.0
-----

* New option ``allow_loading_external_files=False`` when loading externally
  referenced file URLs. E.g. ``<link rel=stylesheet href=/path/to/file.css>``
  Be careful to enable this if the HTML loaded isn't trusted. **Big security risk
  otherwise**.

3.8.0
-----

* Add ``preserve_handlebar_syntax`` option.
  See https://github.com/peterbe/premailer/pull/252
  Thanks @CraigRobertWhite

* Switch to GitHub Actions instead of TravisCI
  See https://github.com/peterbe/premailer/pull/253

3.7.0
-----

* Drop support for Python 2.7 and 3.4. Add test support for 3.8

3.6.2
-----

* Don't strip ``!important`` on stylesheets that are ignored
  See https://github.com/peterbe/premailer/pull/242
  Thanks @nshenkman

3.6.1
-----

* The ``disable_validation`` wasn't passed to ``csstest_to_pairs``
  See https://github.com/peterbe/premailer/pull/235
  Thanks @mbenedettini

3.6.0
-----

* Add ``allow_insecure_ssl`` option for external URLs

3.5.0
-----

* Change default ``cachetools`` implementation to ``cachetools.LFUCache``.

* Now possible to change ``cachetools`` implementation with environment variables.
  See README.rst.

* To avoid thread unsafe execution, the function caching decorator now employs a lock.
  See https://github.com/peterbe/premailer/issues/225
