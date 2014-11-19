from __future__ import absolute_import, unicode_literals
import sys
import re
import unittest
from contextlib import contextmanager
from lxml import etree
from lxml.cssselect import CSSSelector

if sys.version_info >= (3, ):  # As in, Python 3
    from urllib.request import urlopen
else:  # Python 2
    #lint:disable
    from urllib2 import urlopen
    #lint:enable
from io import BytesIO, StringIO  # Yes, the is an io lib in py2.x
import gzip

from nose.tools import eq_, ok_, assert_raises
import mock
from lxml.etree import XMLSyntaxError

from premailer.premailer import (
    transform,
    Premailer,
    merge_styles,
    _css_string_to_dict,
    ExternalNotFoundError,
)
from premailer.__main__ import main
import premailer.premailer  # lint:ok


whitespace_between_tags = re.compile('>\s*<')


@contextmanager
def captured_output():
    new_out, new_err = StringIO(), StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout, sys.stderr = new_out, new_err
        yield sys.stdout, sys.stderr
    finally:
        sys.stdout, sys.stderr = old_out, old_err


@contextmanager
def provide_input(content):
    old_stdin = sys.stdin
    sys.stdin = StringIO(content)
    try:
        with captured_output() as (out, err):
            yield out, err
    finally:
        sys.stdin = old_stdin
        sys.stdin = StringIO(content)


class MockResponse:

    def __init__(self, content, gzip=False):
        self.content = content
        self.headers = {}
        self.gzip = gzip

    def info(self):
        if self.gzip:
            return {'Content-Encoding': 'gzip'}
        else:
            return {}

    def read(self):
        if self.gzip:
            out = BytesIO()
            # If we didn't have to support python 2.6 we could instead do:
            #   with gzip.GzipFile(fileobj=out, mode="w") as f:
            #       ...
            f = gzip.GzipFile(fileobj=out, mode="w")
            f.write(self.content)
            f.close()
            return out.getvalue()
        else:
            return self.content


def compare_html(one, two):
    one = one.strip()
    two = two.strip()
    one = whitespace_between_tags.sub('>\n<', one)
    two = whitespace_between_tags.sub('>\n<', two)
    one = one.replace('><', '>\n<')
    two = two.replace('><', '>\n<')
    for i, line in enumerate(one.splitlines()):
        other = two.splitlines()[i]
        if line.lstrip() != other.lstrip():
            eq_(line.lstrip(), other.lstrip())


def query_selector(html, query):
    parser = etree.HTMLParser()
    page = etree.fromstring(html, parser).getroottree().getroot()
    return CSSSelector(query)(page)


class Tests(unittest.TestCase):

    def shortDescription(self):
        # most annoying thing in the world about nose
        pass

    def test_merge_styles_basic(self):
        old = 'color:red; font-size:1px; background-image: url("data:image/png;base64,iVBORw0KGg")'
        new = 'font-size:2px; font-weight: bold'

        result = merge_styles(old, new)
        result_dict = _css_string_to_dict(result)
        ok_(result_dict['color'] == 'red')
        ok_(result_dict['font-size'] == '2px')
        ok_(result_dict['font-weight'] == 'bold')
        ok_(result_dict['background-image'] == 'url("data:image/png;base64,iVBORw0KGg")')

    def test_basic_html(self):
        """test the simplest case"""

        html = """<html>
        <head>
        <title>Title</title>
        <style type="text/css">
        h1, h2 { color:red; }
        strong {
            text-decoration:none
            }
        </style>
        </head>
        <body>
        <h1>Hi!</h1>
        <p><strong>Yes!</strong></p>
        </body>
        </html>"""

        expect_html = """<html>
        <head>
        <title>Title</title>
        </head>
        <body>
        <h1 style="color:red">Hi!</h1>
        <p><strong style="text-decoration:none">Yes!</strong></p>
        </body>
        </html>"""

        p = Premailer(html)
        result_html = p.transform()

        compare_html(expect_html, result_html)

    def test_basic_html_shortcut_function(self):
        """test the plain transform function"""
        html = """<html>
        <head>
        <title>Title</title>
        <style type="text/css">
        h1, h2 { color:red; }
        strong {
            text-decoration:none
            }
        </style>
        </head>
        <body>
        <h1>Hi!</h1>
        <p><strong>Yes!</strong></p>
        </body>
        </html>"""

        expect_html = """<html>
        <head>
        <title>Title</title>
        </head>
        <body>
        <h1 style="color:red">Hi!</h1>
        <p><strong style="text-decoration:none">Yes!</strong></p>
        </body>
        </html>"""

        result_html = transform(html)
        compare_html(expect_html, result_html)

    def test_empty_style_tag(self):
        """empty style tag"""

        html = """<html>
        <head>
        <title></title>
        <style type="text/css"></style>
        </head>
        <body>
        </body>
        </html>"""

        expect_html = """<html>
        <head>
        <title></title>
        </head>
        <body>
        </body>
        </html>"""

        p = Premailer(html)
        result_html = p.transform()

        compare_html(expect_html, result_html)

    def test_include_star_selector(self):
        """test the simplest case"""

        html = """<html>
        <head>
        <title>Title</title>
        <style type="text/css">
        p * { color: red }
        </style>
        </head>
        <body>
        <h1>Hi!</h1>
        <p><strong>Yes!</strong></p>
        </body>
        </html>"""

        expect_html_not_included = """<html>
        <head>
        <title>Title</title>
        </head>
        <body>
        <h1>Hi!</h1>
        <p><strong>Yes!</strong></p>
        </body>
        </html>"""

        p = Premailer(html)
        result_html = p.transform()

        compare_html(expect_html_not_included, result_html)

        expect_html_star_included = """<html>
        <head>
        <title>Title</title>
        </head>
        <body>
        <h1>Hi!</h1>
        <p><strong style="color:red">Yes!</strong></p>
        </body>
        </html>"""

        p = Premailer(html, include_star_selectors=True)
        result_html = p.transform()

        compare_html(expect_html_star_included, result_html)

    def test_mixed_pseudo_selectors(self):
        """mixing pseudo selectors with straight forward selectors"""

        html = """<html>
        <head>
        <title>Title</title>
        <style type="text/css">
        p { color: yellow }
        a { color: blue }
        a:hover { color: pink }
        </style>
        </head>
        <body>
        <p>
          <a href="#">Page</a>
        </p>
        </body>
        </html>"""

        expect_html = """<html>
        <head>
        <title>Title</title>
        <style type="text/css">a:hover {color:pink}</style>
        </head>
        <body>
        <p style="color:yellow"><a href="#" style="color:blue">Page</a></p>
        </body>
        </html>"""

        p = Premailer(html)
        result_html = p.transform()

        compare_html(expect_html, result_html)

    def test_basic_html_with_pseudo_selector(self):
        """test the simplest case"""

        html = """
        <html>
        <style type="text/css">
        h1 { border:1px solid black }
        p { color:red;}
        p::first-letter { float:left; }
        </style>
        <h1 style="font-weight:bolder">Peter</h1>
        <p>Hej</p>
        </html>
        """

        expect_html = """<html>
        <head>
        <style type="text/css">p::first-letter {float:left}</style>
        </head>
        <body>
        <h1 style="border:1px solid black; font-weight:bolder">Peter</h1>
        <p style="color:red">Hej</p>
        </body>
        </html>"""

        p = Premailer(html)
        result_html = p.transform()

        compare_html(expect_html, result_html)

    def test_parse_style_rules(self):
        p = Premailer('html')  # won't need the html
        func = p._parse_style_rules
        rules, leftover = func("""
        h1, h2 { color:red; }
        /* ignore
            this */
        strong {
            text-decoration:none
            }
        ul li {  list-style: 2px; }
        a:hover { text-decoration: underline }
        """, 0)

        # 'rules' is a list, turn it into a dict for
        # easier assertion testing
        rules_dict = {}
        rules_specificity = {}
        for specificity, k, v in rules:
            rules_dict[k] = v
            rules_specificity[k] = specificity

        ok_('h1' in rules_dict)
        ok_('h2' in rules_dict)
        ok_('strong' in rules_dict)
        ok_('ul li' in rules_dict)

        eq_(rules_dict['h1'], 'color:red')
        eq_(rules_dict['h2'], 'color:red')
        eq_(rules_dict['strong'], 'text-decoration:none')
        eq_(rules_dict['ul li'], 'list-style:2px')
        ok_('a:hover' not in rules_dict)

        p = Premailer('html')  # won't need the html
        func = p._parse_style_rules
        rules, leftover = func("""
        ul li {  list-style: 2px; }
        a:hover { text-decoration: underline }
        """, 0)

        eq_(len(rules), 1)
        specificity, k, v = rules[0]
        eq_(k, 'ul li')
        eq_(v, 'list-style:2px')

        eq_(len(leftover), 1)
        k, v = leftover[0]
        eq_((k, v), ('a:hover', 'text-decoration:underline'), (k, v))

    def test_precedence_comparison(self):
        p = Premailer('html')  # won't need the html
        rules, leftover = p._parse_style_rules("""
        #identified { color:blue; }
        h1, h2 { color:red; }
        ul li {  list-style: 2px; }
        li.example { color:green; }
        strong { text-decoration:none }
        div li.example p.sample { color:black; }
        """, 0)

        # 'rules' is a list, turn it into a dict for
        # easier assertion testing
        rules_specificity = {}
        for specificity, k, v in rules:
            rules_specificity[k] = specificity

        # Last in file wins
        ok_(rules_specificity['h1'] < rules_specificity['h2'])
        # More elements wins
        ok_(rules_specificity['strong'] < rules_specificity['ul li'])
        # IDs trump everything
        ok_(rules_specificity['div li.example p.sample'] <
            rules_specificity['#identified'])

        # Classes trump multiple elements
        ok_(rules_specificity['ul li'] <
            rules_specificity['li.example'])

    def test_base_url_fixer(self):
        """if you leave some URLS as /foo and set base_url to
        'http://www.google.com' the URLS become 'http://www.google.com/foo'
        """
        html = '''<html>
        <head>
        <title>Title</title>
        </head>
        <body>
        <img src="/images/foo.jpg">
        <img src="/images/bar.gif">
        <img src="cid:images/baz.gif">
        <img src="http://www.googe.com/photos/foo.jpg">
        <a href="/home">Home</a>
        <a href="http://www.peterbe.com">External</a>
        <a href="subpage">Subpage</a>
        <a href="#internal_link">Internal Link</a>
        </body>
        </html>
        '''

        expect_html = '''<html>
        <head>
        <title>Title</title>
        </head>
        <body>
        <img src="http://kungfupeople.com/images/foo.jpg">
        <img src="http://kungfupeople.com/images/bar.gif">
        <img src="cid:images/baz.gif">
        <img src="http://www.googe.com/photos/foo.jpg">
        <a href="http://kungfupeople.com/home">Home</a>
        <a href="http://www.peterbe.com">External</a>
        <a href="http://kungfupeople.com/subpage">Subpage</a>
        <a href="#internal_link">Internal Link</a>
        </body>
        </html>'''

        p = Premailer(
            html,
            base_url='http://kungfupeople.com',
            preserve_internal_links=True
        )
        result_html = p.transform()

        compare_html(expect_html, result_html)

    def test_base_url_with_path(self):
        """if you leave some URLS as /foo and set base_url to
        'http://www.google.com' the URLS become 'http://www.google.com/foo'
        """

        html = '''<html>
        <head>
        <title>Title</title>
        </head>
        <body>
        <img src="/images/foo.jpg">
        <img src="/images/bar.gif">
        <img src="http://www.googe.com/photos/foo.jpg">
        <a href="/home">Home</a>
        <a href="http://www.peterbe.com">External</a>
        <a href="http://www.peterbe.com/base/">External 2</a>
        <a href="subpage">Subpage</a>
        <a href="#internal_link">Internal Link</a>
        </body>
        </html>
        '''

        expect_html = '''<html>
        <head>
        <title>Title</title>
        </head>
        <body>
        <img src="http://kungfupeople.com/base/images/foo.jpg">
        <img src="http://kungfupeople.com/base/images/bar.gif">
        <img src="http://www.googe.com/photos/foo.jpg">
        <a href="http://kungfupeople.com/base/home">Home</a>
        <a href="http://www.peterbe.com">External</a>
        <a href="http://www.peterbe.com/base/">External 2</a>
        <a href="http://kungfupeople.com/base/subpage">Subpage</a>
        <a href="#internal_link">Internal Link</a>
        </body>
        </html>'''

        p = Premailer(html, base_url='http://kungfupeople.com/base',
                      preserve_internal_links=True)
        result_html = p.transform()

        compare_html(expect_html, result_html)

    def test_style_block_with_external_urls(self):
        """
        From http://github.com/peterbe/premailer/issues/#issue/2

        If you have
          body { background:url(http://example.com/bg.png); }
        the ':' inside '://' is causing a problem
        """

        html = """<html>
        <head>
        <title>Title</title>
        <style type="text/css">
        body {
          color:#123;
          background: url(http://example.com/bg.png);
          font-family: Omerta;
        }
        </style>
        </head>
        <body>
        <h1>Hi!</h1>
        </body>
        </html>"""

        expect_html = '''<html>
        <head>
        <title>Title</title>
        </head>
        <body style="background:url(http://example.com/bg.png); color:#123; font-family:Omerta">
        <h1>Hi!</h1>
        </body>
        </html>'''

        p = Premailer(html)
        result_html = p.transform()

        compare_html(expect_html, result_html)

    def test_shortcut_function(self):
        # you don't have to use this approach:
        #   from premailer import Premailer
        #   p = Premailer(html, base_url=base_url)
        #   print p.transform()
        # You can do it this way:
        #   from premailer import transform
        #   print transform(html, base_url=base_url)

        html = '''<html>
        <head>
        <style type="text/css">h1{color:#123}</style>
        </head>
        <body>
        <h1>Hi!</h1>
        </body>
        </html>'''

        expect_html = '''<html>
        <head></head>
        <body>
        <h1 style="color:#123">Hi!</h1>
        </body>
        </html>'''

        p = Premailer(html)
        result_html = p.transform()

        compare_html(expect_html, result_html)

    def fragment_in_html(self, fragment, html, fullMessage=False):
        if fullMessage:
            message = '"{0}" not in\n{1}'.format(fragment, html)
        else:
            message = '"{0}" not in HTML'.format(fragment)
        ok_(fragment in html, message)

    def test_css_with_pseudoclasses_included(self):
        "Pick up the pseudoclasses too and include them"

        html = '''<html>
        <head>
        <style type="text/css">
        a.special:link { text-decoration:none; }
        a { color:red; }
        a:hover { text-decoration:none; }
        a,a:hover,
        a:visited { border:1px solid green; }
        p::first-letter {float: left; font-size: 300%}
        </style>
        </head>
        <body>
        <a href="#" class="special">Special!</a>
        <a href="#">Page</a>
        <p>Paragraph</p>
        </body>
        </html>'''

        p = Premailer(html)
        result_html = p.transform()

        elements = query_selector(result_html, 'a')
        eq_(elements[0].attrib['style'], 'border:1px solid green; color:red')

        elements = query_selector(result_html, 'p')
        eq_('style' not in elements[0].attrib, True)

    def test_css_with_html_attributes(self):
        """Some CSS styles can be applied as normal HTML attribute like
        'background-color' can be turned into 'bgcolor'
        """

        html = """<html>
        <head>
        <style type="text/css">
        td { background-color:red; vertical-align:middle;}
        p { text-align:center;}
        table { width:200px; }
        </style>
        </head>
        <body>
        <p>Text</p>
        <table>
          <tr>
            <td>Cell 1</td>
            <td>Cell 2</td>
          </tr>
        </table>
        </body>
        </html>"""

        expect_html = """<html>
        <head>
        </head>
        <body>
        <p style="text-align:center" align="center">Text</p>
        <table style="width:200px" width="200">
          <tr>
            <td style="background-color:red; vertical-align:middle" bgcolor="red" valign="middle">Cell 1</td>
            <td style="background-color:red; vertical-align:middle" bgcolor="red" valign="middle">Cell 2</td>
          </tr>
        </table>
        </body>
        </html>"""

        p = Premailer(html)
        result_html = p.transform()

        expect_html = re.sub('}\s+', '}', expect_html)
        result_html = result_html.replace('}\n', '}')

        compare_html(expect_html, result_html)

    def test_css_disable_basic_html_attributes(self):
        """Some CSS styles can be applied as normal HTML attribute like
        'background-color' can be turned into 'bgcolor'
        """

        html = """<html>
        <head>
        <style type="text/css">
        td { background-color:red; }
        p { text-align:center; }
        table { width:200px; height: 300px; }
        </style>
        </head>
        <body>
        <p>Text</p>
        <table>
          <tr>
            <td>Cell 1</td>
            <td>Cell 2</td>
          </tr>
        </table>
        </body>
        </html>"""

        expect_html = """<html>
        <head>
        </head>
        <body>
        <p style="text-align:center">Text</p>
        <table style="height:300px; width:200px">
          <tr>
            <td style="background-color:red" bgcolor="red">Cell 1</td>
            <td style="background-color:red" bgcolor="red">Cell 2</td>
          </tr>
        </table>
        </body>
        </html>"""

        p = Premailer(
            html,
            disable_basic_attributes=['align', 'width', 'height']
        )
        result_html = p.transform()

        expect_html = re.sub('}\s+', '}', expect_html)
        result_html = result_html.replace('}\n', '}')

        compare_html(expect_html, result_html)

    def test_apple_newsletter_example(self):
        # stupidity test
        import os

        html_file = os.path.join('premailer', 'tests',
                                 'test-apple-newsletter.html')
        html = open(html_file).read()

        p = Premailer(html,
                      keep_style_tags=True,
                      strip_important=False)
        result_html = p.transform()
        ok_('<html>' in result_html)
        ok_('<style media="only screen and (max-device-width: 480px)" '
            'type="text/css">\n'
            '* {line-height: normal !important; -webkit-text-size-adjust: 125%}\n'
            '</style>' in result_html)

    def test_mailto_url(self):
        """if you use URL with mailto: protocol, they should stay as mailto:
        when baseurl is used
        """

        html = """<html>
        <head>
        <title>Title</title>
        </head>
        <body>
        <a href="mailto:e-mail@example.com">e-mail@example.com</a>
        </body>
        </html>"""

        expect_html = """<html>
        <head>
        <title>Title</title>
        </head>
        <body>
        <a href="mailto:e-mail@example.com">e-mail@example.com</a>
        </body>
        </html>"""

        p = Premailer(html, base_url='http://kungfupeople.com')
        result_html = p.transform()

        compare_html(expect_html, result_html)

    def test_strip_important(self):
        """Get rid of !important. Makes no sense inline."""
        html = """<html>
        <head>
        <style type="text/css">
        p {
            height:100% !important;
            width:100% !important;
        }
        </style>
        </head>
        <body>
        <p>Paragraph</p>
        </body>
        </html>
        """
        expect_html = """<html>
        <head>
        </head>
        <body>
        <p style="height:100%; width:100%" height="100%" width="100%">Paragraph</p>
        </body>
        </html>"""

        p = Premailer(html, strip_important=True)
        result_html = p.transform()

        compare_html(expect_html, result_html)

    def test_inline_wins_over_external(self):
        html = """<html>
        <head>
        <style type="text/css">
        div {
            text-align: left;
        }
        /* This tests that a second loop for the same style still doesn't
         * overwrite it. */
        div {
            text-align: left;
        }
        </style>
        </head>
        <body>
        <div style="text-align:right">Some text</div>
        </body>
        </html>"""

        expect_html = """<html>
        <head>
        </head>
        <body>
        <div style="text-align:right" align="right">Some text</div>
        </body>
        </html>"""

        p = Premailer(html)
        result_html = p.transform()

        compare_html(expect_html, result_html)

    def test_last_child(self):
        html = """<html>
        <head>
        <style type="text/css">
        div {
            text-align: right;
        }
        div:last-child {
            text-align: left;
        }
        </style>
        </head>
        <body>
        <div>First child</div>
        <div>Last child</div>
        </body>
        </html>"""

        expect_html = """<html>
        <head>
        </head>
        <body>
        <div style="text-align:right" align="right">First child</div>
        <div style="text-align:left" align="left">Last child</div>
        </body>
        </html>"""

        p = Premailer(html)
        result_html = p.transform()

        compare_html(expect_html, result_html)

    def test_last_child_exclude_pseudo(self):
        html = """<html>
        <head>
        <style type="text/css">
        div {
            text-align: right;
        }
        div:last-child {
            text-align: left;
        }
        </style>
        </head>
        <body>
        <div>First child</div>
        <div>Last child</div>
        </body>
        </html>"""

        expect_html = """<html>
        <head>
        </head>
        <body>
        <div style="text-align:right" align="right">First child</div>
        <div style="text-align:left" align="left">Last child</div>
        </body>
        </html>"""

        p = Premailer(html)
        result_html = p.transform()

        compare_html(expect_html, result_html)

    def test_mediaquery(self):
        html = """<html>
        <head>
        <style type="text/css">
        div {
            text-align: right;
        }
        @media print{
            div {
                text-align: center;
                color: white;
            }
            div {
                font-size: 999px;
            }
        }
        </style>
        </head>
        <body>
        <div>First div</div>
        </body>
        </html>"""

        expect_html = """<html>
        <head>
        <style type="text/css">@media print {
        div {
            text-align: center !important;
            color: white !important
            }
        div {
            font-size: 999px !important
            }
        }</style>
        </head>
        <body>
        <div style="text-align:right" align="right">First div</div>
        </body>
        </html>"""

        p = Premailer(html, strip_important=False)
        result_html = p.transform()

        compare_html(expect_html, result_html)

    def test_child_selector(self):
        html = """<html>
        <head>
        <style type="text/css">
        body > div {
            text-align: right;
        }
        </style>
        </head>
        <body>
        <div>First div</div>
        </body>
        </html>"""

        expect_html = """<html>
        <head>
        </head>
        <body>
        <div style="text-align:right" align="right">First div</div>
        </body>
        </html>"""

        p = Premailer(html)
        result_html = p.transform()

        compare_html(expect_html, result_html)

    def test_doctype(self):
        html = (
            '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" '
            '"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">'
            """<html>
            <head>
            </head>
            <body>
            </body>
            </html>"""
        )

        expect_html = (
            '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" '
            '"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">'
            """<html>
            <head>
            </head>
            <body>
            </body>
            </html>"""
        )

        p = Premailer(html)
        result_html = p.transform()

        compare_html(expect_html, result_html)

    def test_prefer_inline_to_class(self):
        html = """<html>
        <head>
        <style>
        .example {
            color: black;
        }
        </style>
        </head>
        <body>
        <div class="example" style="color:red"></div>
        </body>
        </html>"""

        expect_html = """<html>
        <head>
        </head>
        <body>
        <div style="color:red"></div>
        </body>
        </html>"""

        p = Premailer(html)
        result_html = p.transform()

        compare_html(expect_html, result_html)

    def test_favour_rule_with_element_over_generic(self):
        html = """<html>
        <head>
        <style>
        div.example {
            color: green;
        }
        .example {
            color: black;
        }
        </style>
        </head>
        <body>
        <div class="example"></div>
        </body>
        </html>"""

        expect_html = """<html>
        <head>
        </head>
        <body>
        <div style="color:green"></div>
        </body>
        </html>"""

        p = Premailer(html)
        result_html = p.transform()

        compare_html(expect_html, result_html)

    def test_favour_rule_with_class_over_generic(self):
        html = """<html>
        <head>
        <style>
        div.example {
            color: green;
        }
        div {
            color: black;
        }
        </style>
        </head>
        <body>
        <div class="example"></div>
        </body>
        </html>"""

        expect_html = """<html>
        <head>
        </head>
        <body>
        <div style="color:green"></div>
        </body>
        </html>"""

        p = Premailer(html)
        result_html = p.transform()

        compare_html(expect_html, result_html)

    def test_favour_rule_with_id_over_others(self):
        html = """<html>
        <head>
        <style>
        #identified {
            color: green;
        }
        div.example {
            color: black;
        }
        </style>
        </head>
        <body>
        <div class="example" id="identified"></div>
        </body>
        </html>"""

        expect_html = """<html>
        <head>
        </head>
        <body>
        <div id="identified" style="color:green"></div>
        </body>
        </html>"""

        p = Premailer(html)
        result_html = p.transform()

        compare_html(expect_html, result_html)

    def test_multiple_style_elements(self):
        """Asserts that rules from multiple style elements are inlined correctly."""

        html = """<html>
        <head>
        <title>Title</title>
        <style type="text/css">
        h1, h2 { color:red; }
        strong {
            text-decoration:none
            }
        </style>
        <style type="text/css">
        h1, h2 { color:green; }
        p {
            font-size:120%
            }
        </style>
        </head>
        <body>
        <h1>Hi!</h1>
        <p><strong>Yes!</strong></p>
        </body>
        </html>"""

        expect_html = """<html>
        <head>
        <title>Title</title>
        </head>
        <body>
        <h1 style="color:green">Hi!</h1>
        <p style="font-size:120%"><strong style="text-decoration:none">Yes!</strong></p>
        </body>
        </html>"""

        p = Premailer(html)
        result_html = p.transform()

        compare_html(expect_html, result_html)

    def test_style_attribute_specificity(self):
        """Stuff already in style attributes beats style tags."""

        html = """<html>
        <head>
        <title>Title</title>
        <style type="text/css">
        h1 { color: pink }
        h1.foo { color: blue }
        </style>
        </head>
        <body>
        <h1 class="foo" style="color: green">Hi!</h1>
        </body>
        </html>"""

        expect_html = """<html>
        <head>
        <title>Title</title>
        </head>
        <body>
        <h1 style="color:green">Hi!</h1>
        </body>
        </html>"""

        p = Premailer(html)
        result_html = p.transform()

        compare_html(expect_html, result_html)

    def test_ignore_style_elements_with_media_attribute(self):
        """Asserts that style elements with media attributes other than
        'screen' are ignored."""

        html = """<html>
        <head>
        <title>Title</title>
        <style type="text/css">
            h1, h2 { color:red; }
            strong {
                text-decoration:none
            }
        </style>
        <style type="text/css" media="screen">
            h1, h2 { color:green; }
            p {
                font-size:16px;
                }
        </style>
        <style type="text/css" media="only screen and (max-width: 480px)">
            h1, h2 { color:orange; }
            p {
                font-size:120%;
            }
        </style>
        </head>
        <body>
        <h1>Hi!</h1>
        <p><strong>Yes!</strong></p>
        </body>
        </html>"""

        expect_html = """<html>
        <head>
        <title>Title</title>
        <style type="text/css" media="only screen and (max-width: 480px)">
            h1, h2 { color:orange; }
            p {
                font-size:120%;
            }
        </style>
        </head>
        <body>
        <h1 style="color:green">Hi!</h1>
        <p style="font-size:16px"><strong style="text-decoration:none">Yes!</strong></p>
        </body>
        </html>"""

        p = Premailer(html)
        result_html = p.transform()

        compare_html(expect_html, result_html)

    def test_leftover_important(self):
        """Asserts that leftover styles should be marked as !important."""

        html = """<html>
        <head>
        <title>Title</title>
        <style type="text/css">
        a { color: red; }
        a:hover { color: green; }
        a:focus { color: blue !important; }
        </style>
        </head>
        <body>
        <a href="#">Hi!</a>
        </body>
        </html>"""

        expect_html = """<html>
        <head>
        <title>Title</title>
        <style type="text/css">
        a { color: red; }
        a:hover { color: green; }
        a:focus { color: blue !important; }
        </style>
        </head>
        <body>
        <a href="#" style="color:red">Hi!</a>
        </body>
        </html>"""

        p = Premailer(html,
                      keep_style_tags=True,
                      strip_important=False)
        result_html = p.transform()

        compare_html(expect_html, result_html)

    def test_basic_xml(self):
        """Test the simplest case with xml"""

        html = """<html>
        <head>
        <title>Title</title>
        <style type="text/css">
        img { border: none; }
        </style>
        </head>
        <body>
        <img src="test.png" alt="test"/>
        </body>
        </html>
        """

        expect_html = """<html>
        <head>
        <title>Title</title>
        </head>
        <body>
        <img src="test.png" alt="test" style="border:none"/>
        </body>
        </html>
        """

        p = Premailer(html, method="xml")
        result_html = p.transform()

        compare_html(expect_html, result_html)

    def test_broken_xml(self):
        """Test the simplest case with xml"""

        html = """<html>
        <head>
        <title>Title
        <style type="text/css">
        img { border: none; }
        </style>
        </head>
        <body>
        <img src="test.png" alt="test"/>
        </body>
        """

        p = Premailer(html, method="xml")
        assert_raises(
            XMLSyntaxError,
            p.transform,
        )

    def test_xml_cdata(self):
        """Test that CDATA is set correctly on remaining styles"""

        html = """<html>
        <head>
        <title>Title</title>
        <style type="text/css">
        span:hover > a { background: red; }
        </style>
        </head>
        <body>
        <span><a>Test</a></span>
        </body>
        </html>
        """

        expect_html = """<html>
        <head>
        <title>Title</title>
        <style type="text/css">/*<![CDATA[*/span:hover > a {background:red}/*]]>*/</style>
        </head>
        <body>
        <span><a>Test</a></span>
        </body>
        </html>
        """

        p = Premailer(html, method="xml")
        result_html = p.transform()

        compare_html(expect_html, result_html)

    def test_command_line_fileinput_from_stdin(self):
        html = '<style>h1 { color:red; }</style><h1>Title</h1>'
        expect_html = """
        <html>
        <head></head>
        <body><h1 style="color:red">Title</h1></body>
        </html>
        """

        with provide_input(html) as (out, err):
            main([])
        result_html = out.getvalue().strip()

        compare_html(expect_html, result_html)

    def test_command_line_fileinput_from_argument(self):
        with captured_output() as (out, err):
            main([
                '-f',
                'premailer/tests/test-apple-newsletter.html',
                '--disable-basic-attributes=bgcolor'
            ])

        result_html = out.getvalue().strip()

        ok_('<html>' in result_html)
        ok_('<style media="only screen and (max-device-width: 480px)" '
            'type="text/css">\n'
            '* {line-height: normal !important; -webkit-text-size-adjust: 125%}\n'
            '</style>' in result_html)

    def test_command_line_preserve_style_tags(self):
        with captured_output() as (out, err):
            main([
                '-f',
                'premailer/tests/test-issue78.html',
                '--preserve-style-tags',
                '--external-style=premailer/tests/test-external-styles.css',
            ])

        result_html = out.getvalue().strip()

        expect_html = """
        <html>
        <head>
        <style type="text/css">h1 {
          color: blue;
        }
        h2 {
          color: green;
        }
        a {
          color: pink;
        }
        a:hover {
          color: purple;
        }
        </style>
        <link rel="alternate" type="application/rss+xml" title="RSS" href="/rss.xml">
        <style type="text/css">
        .yshortcuts a {border-bottom: none !important;}
        @media screen and (max-width: 600px) {
            table[class="container"] {
                width: 100% !important;
            }
        }
        /* Even comments should be preserved when the keep_style_tags flag is set */
        p {font-size:12px;}
        </style>
        <style type="text/css">h1 {
          color: brown;
        }
        h2::after {
          content: "";
          display: block;
        }
        @media all and (max-width: 320px) {
            h1 {
                font-size: 12px;
            }
        }
        </style>
        </head>
        <body>
        <h1 style="color:brown">h1</h1>
        <p style="font-size:12px"><a href="" style="color:pink">html</a></p>
        </body>
        </html>
        """

        compare_html(expect_html, result_html)

        # for completeness, test it once without
        with captured_output() as (out, err):
            main([
                '-f',
                'premailer/tests/test-issue78.html',
                '--external-style=premailer/tests/test-external-styles.css',
            ])

        result_html = out.getvalue().strip()
        expect_html = """
        <html>
        <head>
        <style type="text/css">a:hover {color:purple !important}</style>
        <link rel="alternate" type="application/rss+xml" title="RSS" href="/rss.xml">
        <style type="text/css">@media screen and (max-width: 600px) {
            table[class="container"] {
                width: 100% !important
                }
            }</style>
        <style type="text/css">h2::after {content:"" !important;display:block !important}
        @media all and (max-width: 320px) {
            h1 {
                font-size: 12px !important
                }
            }</style>
        </head>
        <body>
        <h1 style="color:brown">h1</h1>
        <p style="font-size:12px"><a href="" style="color:pink">html</a></p>
        </body>
        </html>
        """

        compare_html(expect_html, result_html)

    def test_multithreading(self):
        """The test tests thread safety of merge_styles function which employs
        thread non-safe cssutils calls.
        The test would fail if merge_styles would have not been thread-safe """

        import threading
        import logging
        THREADS = 30
        REPEATS = 100

        class RepeatMergeStylesThread(threading.Thread):
            """The thread is instantiated by test and run multiple times in parallel."""
            exc = None

            def __init__(self, old, new, class_):
                """The constructor just stores merge_styles parameters"""
                super(RepeatMergeStylesThread, self).__init__()
                self.old, self.new, self.class_ = old, new, class_

            def run(self):
                """Calls merge_styles in a loop and sets exc attribute if merge_styles raises an exception."""
                for i in range(0, REPEATS):
                    try:
                        merge_styles(self.old, self.new, self.class_)
                    except Exception as e:
                        logging.exception("Exception in thread %s", self.name)
                        self.exc = e

        old = 'background-color:#ffffff;'
        new = 'background-color:#dddddd;'
        class_ = ''

        # start multiple threads concurrently; each calls merge_styles many times
        threads = [
            RepeatMergeStylesThread(old, new, class_)
            for i in range(0, THREADS)
        ]
        for t in threads:
            t.start()

        # wait until all threads are done
        for t in threads:
            t.join()

        # check if any thread raised exception while in merge_styles call
        exceptions = [t.exc for t in threads if t.exc is not None]
        eq_(exceptions, [])

    def test_external_links(self):
        """Test loading stylesheets via link tags"""

        html = """<html>
        <head>
        <title>Title</title>
        <style type="text/css">
        h1 { color:red; }
        h3 { color:yellow; }
        </style>
        <link href="premailer/tests/test-external-links.css" rel="stylesheet" type="text/css">
        <link rel="alternate" type="application/rss+xml" title="RSS" href="/rss.xml">
        <style type="text/css">
        h1 { color:orange; }
        </style>
        </head>
        <body>
        <h1>Hello</h1>
        <h2>World</h2>
        <h3>Test</h3>
        <a href="#">Link</a>
        </body>
        </html>"""

        expect_html = """<html>
        <head>
        <title>Title</title>
        <style type="text/css">a:hover {color:purple !important}</style>
        <link rel="alternate" type="application/rss+xml" title="RSS" href="/rss.xml">
        </head>
        <body>
        <h1 style="color:orange">Hello</h1>
        <h2 style="color:green">World</h2>
        <h3 style="color:yellow">Test</h3>
        <a href="#" style="color:pink">Link</a>
        </body>
        </html>"""

        p = Premailer(
            html,
            strip_important=False
        )
        result_html = p.transform()

        compare_html(expect_html, result_html)

    def test_external_links_unfindable(self):
        """Test loading stylesheets that can't be found"""

        html = """<html>
        <head>
        <title>Title</title>
        <style type="text/css">
        h1 { color:red; }
        h3 { color:yellow; }
        </style>
        <link href="premailer/xxxx.css" rel="stylesheet" type="text/css">
        <style type="text/css">
        h1 { color:orange; }
        </style>
        </head>
        <body>
        <h1>Hello</h1>
        <h2>World</h2>
        <h3>Test</h3>
        <a href="#">Link</a>
        </body>
        </html>"""

        p = Premailer(
            html,
            strip_important=False
        )
        assert_raises(
            ExternalNotFoundError,
            p.transform,
        )

    def test_external_styles_and_links(self):
        """Test loading stylesheets via both the 'external_styles' argument and link tags"""

        html = """<html>
        <head>
        <link href="test-external-links.css" rel="stylesheet" type="text/css">
        <style type="text/css">
        h1 { color: red; }
        </style>
        </head>
        <body>
        <h1>Hello</h1>
        <h2>Hello</h2>
        <a href="">Hello</a>
        </body>
        </html>"""

        expect_html = """<html>
        <head>
        <style type="text/css">a:hover {color:purple !important}</style>
        <style type="text/css">h2::after {content:"" !important;display:block !important}
        @media all and (max-width: 320px) {
            h1 {
                font-size: 12px !important
                }
            }</style>
        </head>
        <body>
        <h1 style="color:brown">Hello</h1>
        <h2 style="color:green">Hello</h2>
        <a href="" style="color:pink">Hello</a>
        </body>
        </html>"""

        p = Premailer(
            html,
            strip_important=False,
            external_styles='test-external-styles.css',
            base_path='premailer/tests/')
        result_html = p.transform()

        compare_html(expect_html, result_html)

    @mock.patch('premailer.premailer.urlopen')
    def test_load_external_url(self, mocked_url_open):
        'Test premailer.premailer.Premailer._load_external_url'
        faux_response = b'This is not a response'
        faux_uri = 'https://example.com/site.css'
        mocked_url_open.return_value = MockResponse(faux_response)
        p = premailer.premailer.Premailer('<p>A paragraph</p>')
        r = p._load_external_url(faux_uri)

        mocked_url_open.assert_called_once_with(faux_uri)
        self.assertEqual(faux_response.decode('utf-8'), r)

    @mock.patch('premailer.premailer.urlopen')
    def test_load_external_url_gzip(self, mocked_url_open):
        'Test premailer.premailer.Premailer._load_external_url with gzip'
        faux_response = b'This is not a response'
        faux_uri = 'http://example.com/site.css'
        mocked_url_open.return_value = MockResponse(faux_response, True)
        p = premailer.premailer.Premailer('<p>A paragraph</p>')
        r = p._load_external_url(faux_uri)

        mocked_url_open.assert_called_once_with(faux_uri)
        self.assertEqual(faux_response.decode('utf-8'), r)

    def test_css_text(self):
        """Test handling css_text passed as a string"""

        html = """<html>
        <head>
        </head>
        <body>
        <h1>Hello</h1>
        <h2>Hello</h2>
        <a href="">Hello</a>
        </body>
        </html>"""

        expect_html = """<html>
        <head>
        <style type="text/css">@media all and (max-width: 320px) {
            h1 {
                color: black !important
                }
            }</style>
        </head>
        <body>
        <h1 style="color:brown">Hello</h1>
        <h2 style="color:green">Hello</h2>
        <a href="" style="color:pink">Hello</a>
        </body>
        </html>"""

        css_text = """
        h1 {
            color: brown;
        }
        h2 {
            color: green;
        }
        a {
            color: pink;
        }
        @media all and (max-width: 320px) {
            h1 {
                color: black;
            }
        }

        """

        p = Premailer(
            html,
            strip_important=False,
            css_text=[css_text])
        result_html = p.transform()

        compare_html(expect_html, result_html)

    def test_css_text_with_only_body_present(self):
        """Test handling css_text passed as a string when no <html> or <head> is present"""

        html = """<body>
        <h1>Hello</h1>
        <h2>Hello</h2>
        <a href="">Hello</a>
        </body>"""

        expect_html = """<html>
        <head>
        <style type="text/css">@media all and (max-width: 320px) {
            h1 {
                color: black !important
                }
            }</style>
        </head>
        <body>
        <h1 style="color:brown">Hello</h1>
        <h2 style="color:green">Hello</h2>
        <a href="" style="color:pink">Hello</a>
        </body>
        </html>"""

        css_text = """
        h1 {
            color: brown;
        }
        h2 {
            color: green;
        }
        a {
            color: pink;
        }
        @media all and (max-width: 320px) {
            h1 {
                color: black;
            }
        }
        """

        p = Premailer(
            html,
            strip_important=False,
            css_text=css_text)
        result_html = p.transform()

        compare_html(expect_html, result_html)

    @staticmethod
    def mocked_urlopen(url):
        'The standard "response" from the "server".'
        retval = ''
        if 'style1.css' in url:
            retval = "h1 { color: brown }"
        elif 'style2.css' in url:
            retval = "h2 { color: pink }"
        elif 'style3.css' in url:
            retval = "h3 { color: red }"
        return retval

    @mock.patch.object(Premailer, '_load_external_url')
    def test_external_styles_on_http(self, mocked_pleu):
        """Test loading styles that are genuinely external"""

        html = """<html>
        <head>
        <link href="https://www.com/style1.css" rel="stylesheet" type="text/css">
        <link href="//www.com/style2.css" rel="stylesheet" type="text/css">
        <link href="//www.com/style3.css" rel="stylesheet" type="text/css">
        </head>
        <body>
        <h1>Hello</h1>
        <h2>World</h2>
        <h3>World</h3>
        </body>
        </html>"""
        mocked_pleu.side_effect = self.mocked_urlopen
        p = Premailer(html)
        result_html = p.transform()

        # Expected values are tuples of the positional values (as another
        # tuple) and the ketword arguments (which are all null), hence the
        # following Lisp-like explosion of brackets and commas.
        expected_args = [(('https://www.com/style1.css',),),
                         (('http://www.com/style2.css',),),
                         (('http://www.com/style3.css',),)]
        eq_(expected_args, mocked_pleu.call_args_list)

        expect_html = """<html>
        <head>
        </head>
        <body>
        <h1 style="color:brown">Hello</h1>
        <h2 style="color:pink">World</h2>
        <h3 style="color:red">World</h3>
        </body>
        </html>"""
        compare_html(expect_html, result_html)

    @mock.patch.object(Premailer, '_load_external_url')
    def test_external_styles_on_https(self, mocked_pleu):
        """Test loading styles that are genuinely external"""

        html = """<html>
        <head>
        <link href="https://www.com/style1.css" rel="stylesheet" type="text/css">
        <link href="//www.com/style2.css" rel="stylesheet" type="text/css">
        <link href="/style3.css" rel="stylesheet" type="text/css">
        </head>
        <body>
        <h1>Hello</h1>
        <h2>World</h2>
        <h3>World</h3>
        </body>
        </html>"""

        mocked_pleu.side_effect = self.mocked_urlopen
        p = Premailer(html, base_url='https://www.peterbe.com')
        result_html = p.transform()

        expected_args = [(('https://www.com/style1.css',),),
                         (('https://www.com/style2.css',),),
                         (('https://www.peterbe.com/style3.css',),)]
        self.assertEqual(expected_args, mocked_pleu.call_args_list)
        expect_html = """<html>
        <head>
        </head>
        <body>
        <h1 style="color:brown">Hello</h1>
        <h2 style="color:pink">World</h2>
        <h3 style="color:red">World</h3>
        </body>
        </html>"""
        compare_html(expect_html, result_html)

    @mock.patch.object(Premailer, '_load_external_url')
    def test_external_styles_with_base_url(self, mocked_pleu):
        """Test loading styles that are genuinely external if you use
        the base_url"""

        html = """<html>
        <head>
        <link href="style.css" rel="stylesheet" type="text/css">
        </head>
        <body>
        <h1>Hello</h1>
        </body>
        </html>"""
        mocked_pleu.return_value = "h1 { color: brown }"
        p = Premailer(html, base_url='http://www.peterbe.com/')
        result_html = p.transform()
        expected_args = [(('http://www.peterbe.com/style.css',),), ]
        self.assertEqual(expected_args, mocked_pleu.call_args_list)

        expect_html = """<html>
        <head>
        </head>
        <body>
        <h1 style="color:brown">Hello</h1>
        </body>
        </html>"""
        compare_html(expect_html, result_html)

    def test_disabled_validator(self):
        """test disabled_validator"""

        html = """<html>
        <head>
        <title>Title</title>
        <style type="text/css">
        h1, h2 { fo:bar; }
        strong {
            color:baz;
            text-decoration:none;
            }
        </style>
        </head>
        <body>
        <h1>Hi!</h1>
        <p><strong>Yes!</strong></p>
        </body>
        </html>"""

        expect_html = """<html>
        <head>
        <title>Title</title>
        </head>
        <body>
        <h1 style="fo:bar">Hi!</h1>
        <p><strong style="color:baz; text-decoration:none">Yes!</strong></p>
        </body>
        </html>"""

        p = Premailer(html, disable_validation=True)
        result_html = p.transform()

        compare_html(expect_html, result_html)

    def test_comments_in_media_queries(self):
        """CSS comments inside a media query block should not be a problem"""
        html = """<!doctype html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Document</title>
            <style>
            @media screen {
                /* comment */
            }
            </style>
        </head>
        <body></body>
        </html>"""

        p = Premailer(html, disable_validation=True)
        result_html = p.transform()
        ok_('/* comment */' in result_html)

    def test_fontface_selectors_with_no_selectortext(self):
        """
        @font-face selectors are weird.
        This is a fix for https://github.com/peterbe/premailer/issues/71
        """
        html = """<!doctype html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Document</title>
            <style>
            @font-face {
                font-family: 'Garamond';
                src:
                    local('Garamond'),
                    local('Garamond-Regular'),
                    url('Garamond.ttf') format('truetype'); /* Safari, Android, iOS */
                    font-weight: normal;
                    font-style: normal;
            }
            </style>
        </head>
        <body></body>
        </html>"""

        p = Premailer(html, disable_validation=True)
        p.transform()  # it should just work

    def test_keyframe_selectors(self):
        """
        keyframes shouldn't be a problem.
        """
        html = """<!doctype html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Document</title>
            <style>
            @keyframes fadein {
                from { opacity: 0; }
                to   { opacity: 1; }
            }

            /* Firefox */
            @-moz-keyframes fadein {
                from { opacity: 0; }
                to   { opacity: 1; }
            }

            /* Safari and Chrome */
            @-webkit-keyframes fadein {
                from { opacity: 0; }
                to   { opacity: 1; }
            }

            /* Internet Explorer */
            @-ms-keyframes fadein {
                from { opacity: 0; }
                to   { opacity: 1; }
            }

            /* Opera */
            @-o-keyframes fadein {
                from { opacity: 0; }
                to   { opacity: 1; }
            }
            </style>
        </head>
        <body></body>
        </html>"""

        p = Premailer(html, disable_validation=True)
        p.transform()  # it should just work
