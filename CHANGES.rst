premailer Changes
=================

Peter's note: Unfortunately, ``premailer`` didn't use to keep a change log. But it's
never too late to start, so let's start here and now.

3.10.0
------

* New option ``session=None`` to provide the session used for making http requests.

* Bug fix: inlined styles are no longer sorted alphabetically. This preserves the input
  rule order so that premailer does not break style precedence where order is significant, e.g.

  .. code-block:: css

    div {
      /* Padding on all sides is 10px. */
      padding-left: 5px;
      padding: 10px;
    }

    div {
      /* Padding on the left side is 5px, on other sides is 10px. */
      padding: 10px;
      padding-left: 5px;
    }

  Prior to this fix premailer would swap the rules in the first example to look like the second.


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
