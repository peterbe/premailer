import logging
import re
import sys
import os
import unittest
from contextlib import contextmanager
from io import StringIO
import tempfile

from lxml.etree import XMLSyntaxError, fromstring
from requests.exceptions import HTTPError
import mock
import premailer.premailer  # lint:ok
from nose.tools import assert_raises, eq_, ok_
from premailer.__main__ import main
from premailer.premailer import (
    ExternalNotFoundError,
    ExternalFileLoadingError,
    Premailer,
    csstext_to_pairs,
    merge_styles,
    transform,
)


whitespace_between_tags = re.compile(r">\s*<")


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


class MockResponse(object):
    def __init__(self, content, status_code=200):
        self.text = content
        self.status_code = status_code

    def raise_for_status(self):
        http_error_msg = ""

        if 400 <= self.status_code < 500:
            http_error_msg = "Client Error: %s" % (self.status_code,)

        elif 500 <= self.status_code < 600:
            http_error_msg = "Server Error: %s" % (self.status_code,)

        if http_error_msg:
            raise HTTPError(http_error_msg, response=self)


def compare_html(one, two):
    one = one.strip()
    two = two.strip()
    one = whitespace_between_tags.sub(">\n<", one)
    two = whitespace_between_tags.sub(">\n<", two)
    one = one.replace("><", ">\n<")
    two = two.replace("><", ">\n<")
    for i, line in enumerate(one.splitlines()):
        other = two.splitlines()[i]
        if line.lstrip() != other.lstrip():
            eq_(line.lstrip(), other.lstrip())


class Tests(unittest.TestCase):
    def shortDescription(self):
        # most annoying thing in the world about nose
        pass

    def test_merge_styles_basic(self):
        inline_style = "font-size:1px; color: red"
        new = "font-size:2px; font-weight: bold"
        expect = "font-size:1px;", "font-weight:bold;", "color:red"
        result = merge_styles(inline_style, [csstext_to_pairs(new)], [""])
        for each in expect:
            ok_(each in result)

    def test_merge_styles_with_class(self):
        inline_style = "color:red; font-size:1px;"
        new, class_ = "font-size:2px; font-weight: bold", ":hover"

        # because we're dealing with dicts (random order) we have to
        # test carefully.
        # We expect something like this:
        #  {color:red; font-size:1px} :hover{font-size:2px; font-weight:bold}

        result = merge_styles(inline_style, [csstext_to_pairs(new)], [class_])
        ok_(result.startswith("{"))
        ok_(result.endswith("}"))
        ok_(" :hover{" in result)
        split_regex = re.compile("{([^}]+)}")
        eq_(len(split_regex.findall(result)), 2)
        expect_first = "color:red", "font-size:1px"
        expect_second = "font-weight:bold", "font-size:2px"
        for each in expect_first:
            ok_(each in split_regex.findall(result)[0])
        for each in expect_second:
            ok_(each in split_regex.findall(result)[1])

    def test_merge_styles_non_trivial(self):
        inline_style = 'background-image:url("data:image/png;base64,iVBORw0KGg")'
        new = "font-size:2px; font-weight: bold"
        expect = (
            'background-image:url("data:image/png;base64,iVBORw0KGg")',
            "font-size:2px;",
            "font-weight:bold",
        )
        result = merge_styles(inline_style, [csstext_to_pairs(new)], [""])
        for each in expect:
            ok_(each in result)

    def test_merge_styles_with_unset(self):
        inline_style = "color: red"
        new = "font-size: 10px; font-size: unset; font-weight: bold"
        expect = "font-weight:bold;", "color:red"
        css_new = csstext_to_pairs(new)
        result = merge_styles(
            inline_style, [css_new], [""], remove_unset_properties=True
        )
        for each in expect:
            ok_(each in result)
        ok_("font-size" not in result)

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

        p = Premailer()
        result_html = p.transform(html)

        compare_html(expect_html, result_html)

    def test_basic_html_argument_wrong(self):
        """It used to be that you'd do:

            instance = Premailer(html, **options)
            print(instance.transform())

        But the new way is:

            instance = Premailer(**options)
            print(instance.transform(html))

        This test checks the handling for the backwards compatability checks.
        """

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

        p = Premailer(html)
        assert_raises(TypeError, p.transform, html)

        p = Premailer()
        assert_raises(TypeError, p.transform)

    def test_instance_reuse(self):
        """test whether the premailer instance can be reused"""

        html_1 = """<html>
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

        html_2 = """<html>
        <head>
        <title>Another Title</title>
        <style type="text/css">
        h1, h2 { color:blue; }
        strong {
            text-decoration:underline
            }
        </style>
        </head>
        <body>
        <h1>Hello!</h1>
        <p><strong>Nope!</strong></p>
        </body>
        </html>"""

        expect_html_1 = """<html>
        <head>
        <title>Title</title>
        </head>
        <body>
        <h1 style="color:red">Hi!</h1>
        <p><strong style="text-decoration:none">Yes!</strong></p>
        </body>
        </html>"""

        expect_html_2 = """<html>
        <head>
        <title>Another Title</title>
        </head>
        <body>
        <h1 style="color:blue">Hello!</h1>
        <p><strong style="text-decoration:underline">Nope!</strong></p>
        </body>
        </html>"""

        p = Premailer()
        result_html_1 = p.transform(html_1)
        result_html_2 = p.transform(html_2)

        compare_html(expect_html_1, result_html_1)
        compare_html(expect_html_2, result_html_2)

    def test_remove_classes(self):
        """test the simplest case"""

        html = """<html>
        <head>
        <title>Title</title>
        <style type="text/css">
        .stuff {
            color: red;
        }
        </style>
        </head>
        <body>
        <p class="stuff"><strong>Yes!</strong></p>
        </body>
        </html>"""

        expect_html = """<html>
        <head>
        <title>Title</title>
        </head>
        <body>
        <p style="color:red"><strong>Yes!</strong></p>
        </body>
        </html>"""

        p = Premailer(html, remove_classes=True)
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

    def test_kwargs_html_shortcut_function(self):
        """test the transform function with kwargs passed"""
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
        <style type="text/css">
        h1, h2 { color:red; }
        strong {
            text-decoration:none
            }
        </style>
        </head>
        <body>
        <h1 style="color:red">Hi!</h1>
        <p><strong style="text-decoration:none">Yes!</strong></p>
        </body>
        </html>"""

        result_html = transform(html, keep_style_tags=True)
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
        p = Premailer("html")  # won't need the html
        func = p._parse_style_rules
        rules, leftover = func(
            """
        h1, h2 { color:red; }
        /* ignore
            this */
        strong {
            text-decoration:none
            }
        ul li {  list-style: 2px; }
        a:hover { text-decoration: underline }
        """,
            0,
        )

        # 'rules' is a list, turn it into a dict for
        # easier assertion testing
        rules_dict = {}
        rules_specificity = {}
        for specificity, k, v in rules:
            rules_dict[k] = v
            rules_specificity[k] = specificity

        ok_("h1" in rules_dict)
        ok_("h2" in rules_dict)
        ok_("strong" in rules_dict)
        ok_("ul li" in rules_dict)

        eq_(rules_dict["h1"], "color:red")
        eq_(rules_dict["h2"], "color:red")
        eq_(rules_dict["strong"], "text-decoration:none")
        eq_(rules_dict["ul li"], "list-style:2px")
        ok_("a:hover" not in rules_dict)

        # won't need the html
        p = Premailer("html", exclude_pseudoclasses=True)
        func = p._parse_style_rules
        rules, leftover = func(
            """
        ul li {  list-style: 2px; }
        a:hover { text-decoration: underline }
        """,
            0,
        )

        eq_(len(rules), 1)
        specificity, k, v = rules[0]
        eq_(k, "ul li")
        eq_(v, "list-style:2px")

        eq_(len(leftover), 1)
        k, v = leftover[0]
        eq_((k, v), ("a:hover", "text-decoration:underline"), (k, v))

    def test_precedence_comparison(self):
        p = Premailer("html")  # won't need the html
        rules, leftover = p._parse_style_rules(
            """
        #identified { color:blue; }
        h1, h2 { color:red; }
        ul li {  list-style: 2px; }
        li.example { color:green; }
        strong { text-decoration:none }
        div li.example p.sample { color:black; }
        """,
            0,
        )

        # 'rules' is a list, turn it into a dict for
        # easier assertion testing
        rules_specificity = {}
        for specificity, k, v in rules:
            rules_specificity[k] = specificity

        # Last in file wins
        ok_(rules_specificity["h1"] < rules_specificity["h2"])
        # More elements wins
        ok_(rules_specificity["strong"] < rules_specificity["ul li"])
        # IDs trump everything
        ok_(
            rules_specificity["div li.example p.sample"]
            < rules_specificity["#identified"]
        )

        # Classes trump multiple elements
        ok_(rules_specificity["ul li"] < rules_specificity["li.example"])

    def test_base_url_fixer(self):
        """if you leave some URLS as /foo and set base_url to
        'http://www.google.com' the URLS become 'http://www.google.com/foo'
        """
        html = """<html>
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
        """

        expect_html = """<html>
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
        </html>"""

        p = Premailer(
            html, base_url="http://kungfupeople.com", preserve_internal_links=True
        )
        result_html = p.transform()

        compare_html(expect_html, result_html)

    def test_base_url_with_path(self):
        """if you leave some URLS as /foo and set base_url to
        'http://www.google.com' the URLS become 'http://www.google.com/foo'
        """

        html = """<html>
        <head>
        <title>Title</title>
        </head>
        <body>
        <img src="/images/foo.jpg">
        <img src="http://www.googe.com/photos/foo.jpg">
        <a href="/home">Home</a>
        <a href="http://www.peterbe.com">External</a>
        <a href="http://www.peterbe.com/base/">External 2</a>
        <a href="subpage">Subpage</a>
        <a href="#internal_link">Internal Link</a>
        </body>
        </html>
        """

        expect_html = """<html>
        <head>
        <title>Title</title>
        </head>
        <body>
        <img src="http://kungfupeople.com/images/foo.jpg">
        <img src="http://www.googe.com/photos/foo.jpg">
        <a href="http://kungfupeople.com/home">Home</a>
        <a href="http://www.peterbe.com">External</a>
        <a href="http://www.peterbe.com/base/">External 2</a>
        <a href="http://kungfupeople.com/base/subpage">Subpage</a>
        <a href="#internal_link">Internal Link</a>
        </body>
        </html>"""

        p = Premailer(
            html, base_url="http://kungfupeople.com/base/", preserve_internal_links=True
        )
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

        expect_html = """<html>
        <head>
        <title>Title</title>
        </head>
        <body style="color:#123; background:url(http://exam
ple.com/bg.png); font-family:Omerta">
        <h1>Hi!</h1>
        </body>
        </html>""".replace(
            "exam\nple", "example"
        )

        p = Premailer(html)
        result_html = p.transform()

        compare_html(expect_html, result_html)

    def test_base_url_ignore_links(self):
        """if you leave some URLS as /foo, set base_url to
        'http://www.google.com' and set disable_link_rewrites to True, the URLS
        should not be changed.
        """

        html = """<html>
        <head>
        <title>Title</title>
        </head>
        <body>
        <img src="/images/foo.jpg">
        <img src="http://www.googe.com/photos/foo.jpg">
        <a href="/home">Home</a>
        <a href="http://www.peterbe.com">External</a>
        <a href="http://www.peterbe.com/base/">External 2</a>
        <a href="subpage">Subpage</a>
        <a href="#internal_link">Internal Link</a>
        </body>
        </html>
        """

        expect_html = """<html>
        <head>
        <title>Title</title>
        </head>
        <body>
        <img src="/images/foo.jpg">
        <img src="http://www.googe.com/photos/foo.jpg">
        <a href="/home">Home</a>
        <a href="http://www.peterbe.com">External</a>
        <a href="http://www.peterbe.com/base/">External 2</a>
        <a href="subpage">Subpage</a>
        <a href="#internal_link">Internal Link</a>
        </body>
        </html>"""

        p = Premailer(
            html, base_url="http://kungfupeople.com/base/", disable_link_rewrites=True
        )
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

        html = """<html>
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
        </html>"""

        p = Premailer(html, exclude_pseudoclasses=False)
        result_html = p.transform()
        # because we're dealing with random dicts here we can't predict what
        # order the style attribute will be written in so we'll look for
        # things manually.
        e = '<p style="::first-letter{float:left; font-size:300%}">' "Paragraph</p>"
        self.fragment_in_html(e, result_html, True)

        e = 'style="{color:red; border:1px solid green}'
        self.fragment_in_html(e, result_html)
        e = " :visited{border:1px solid green}"
        self.fragment_in_html(e, result_html)
        e = " :hover{text-decoration:none; border:1px solid green}"
        self.fragment_in_html(e, result_html)

    def test_css_with_pseudoclasses_excluded(self):
        "Skip things like `a:hover{}` and keep them in the style block"

        html = """<html>
        <head>
        <style type="text/css">
        a { color:red; }
        a:hover { text-decoration:none; }
        a,a:hover,
        a:visited { border:1px solid green; }
        p::first-letter {float: left; font-size: 300%}
        </style>
        </head>
        <body>
        <a href="#">Page</a>
        <p>Paragraph</p>
        </body>
        </html>"""

        expect_html = """<html>
<head>
<style type="text/css">a:hover {text-decoration:none}
a:hover {border:1px solid green}
a:visited {border:1px solid green}p::first-letter {float:left;font-size:300%}
</style>
</head>
<body>
<a href="#" style="color:red; border:1px solid green">Page</a>
<p>Paragraph</p>
</body>
</html>"""

        p = Premailer(html, exclude_pseudoclasses=True)
        result_html = p.transform()

        expect_html = whitespace_between_tags.sub("><", expect_html).strip()
        result_html = whitespace_between_tags.sub("><", result_html).strip()

        expect_html = re.sub(r"}\s+", "}", expect_html)
        result_html = result_html.replace("}\n", "}")

        eq_(expect_html, result_html)
        # XXX

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
            <td style="background-color:red; vert
ical-align:middle" bgcolor="red" valign="middle">Cell 1</td>
            <td style="background-color:red; vert
ical-align:middle" bgcolor="red" valign="middle">Cell 2</td>
          </tr>
        </table>
        </body>
        </html>""".replace(
            "vert\nical", "vertical"
        )

        p = Premailer(html, exclude_pseudoclasses=True)
        result_html = p.transform()

        expect_html = re.sub(r"}\s+", "}", expect_html)
        result_html = result_html.replace("}\n", "}")

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
        <table style="width:200px; height:300px">
          <tr>
            <td style="background-color:red" bgcolor="red">Cell 1</td>
            <td style="background-color:red" bgcolor="red">Cell 2</td>
          </tr>
        </table>
        </body>
        </html>"""

        p = Premailer(
            html,
            exclude_pseudoclasses=True,
            disable_basic_attributes=["align", "width", "height"],
        )
        result_html = p.transform()

        expect_html = re.sub(r"}\s+", "}", expect_html)
        result_html = result_html.replace("}\n", "}")

        compare_html(expect_html, result_html)

    def test_apple_newsletter_example(self):
        # stupidity test
        import os

        html_file = os.path.join("premailer", "tests", "test-apple-newsletter.html")
        html = open(html_file).read()

        p = Premailer(
            html,
            exclude_pseudoclasses=False,
            keep_style_tags=True,
            strip_important=False,
        )
        result_html = p.transform()
        ok_("<html>" in result_html)
        ok_(
            '<style media="only screen and (max-device-width: 480px)" '
            'type="text/css">\n'
            "* {line-height: normal !important; "
            "-webkit-text-size-adjust: 125%}\n"
            "</style>" in result_html
        )

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

        p = Premailer(html, base_url="http://kungfupeople.com")
        result_html = p.transform()

        compare_html(expect_html, result_html)

    def test_tel_url(self):
        """if you use URL with tel: protocol, it should stay as tel:
        when baseurl is used
        """

        html = """<html>
        <head>
        <title>Title</title>
        </head>
        <body>
        <a href="tel:202-555-0113">202-555-0113</a>
        </body>
        </html>"""

        p = Premailer(html, base_url="http://kungfupeople.com")
        result_html = p.transform()

        compare_html(result_html, html)

    def test_uppercase_margin(self):
        """Option to comply with outlook.com

        https://emailonacid.com/blog/article/email-development/outlook.com-does-support-margins
        """

        html = """<html>
<head>
<title>Title</title>
</head>
<style>
h1 {margin: 0}
h2 {margin-top:0;margin-bottom:0;margin-left:0;margin-right:0}
</style>
<body>
<h1>a</h1>
<h2>
b
</h2>
</body>
</html>"""

        expect_html = """<html>
<head>
<title>Title</title>
</head>
<body>
<h1 style="Margin:0">a</h1>
<h2 style="Margin-top:0; Margin-bottom:0; Margin-left:0; Margin-right:0">
b
</h2>
</body>
</html>"""

        p = Premailer(html, capitalize_float_margin=True)
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

        p = Premailer(html, exclude_pseudoclasses=True)
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

    def test_css_ordering_preserved(self):
        """For cases like these padding rules, it's important that the style that
        should be applied comes last so that premailer follows the same rules that
        browsers use to determine precedence."""

        html = """<html>
        <head>
        <style type="text/css">
        div {
            padding-left: 6px;
            padding-right: 6px;
            padding: 4px;
        }
        </style>
        </head>
        <body>
        <div>Some text</div>
        </body>
        </html>"""

        expect_html = """<html>
        <head>
        </head>
        <body>
        <div style="padding-left:6px; padding-right:6px; padding:4px">Some text</div>
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
        <div class="example" style="color:red"></div>
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
        <div class="example" style="color:green"></div>
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
        <div class="example" style="color:green"></div>
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
        <div class="example" id="identified" style="color:green"></div>
        </body>
        </html>"""

        p = Premailer(html)
        result_html = p.transform()

        compare_html(expect_html, result_html)

    def test_favour_rule_with_important_over_others(self):
        html = """<html>
        <head>
        <style>
        .makeblue {
            color: blue !important;
            font-size: 12px;
        }
        #id {
            color: green;
            font-size: 22px;
        }
        div.example {
            color: black;
        }
        </style>
        </head>
        <body>
        <div class="example makeblue" id="id"></div>
        </body>
        </html>"""

        expect_html = """<html>
<head>
</head>
<body>
<div class="example makeblue" id="id" style="font-size:22px; color:blue"></div>
</body>
</html>"""

        p = Premailer(html)
        result_html = p.transform()

        compare_html(expect_html, result_html)

    def test_multiple_style_elements(self):
        """Asserts that rules from multiple style elements
        are inlined correctly."""

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
        <p style="font-size:120%"><strong style="text-deco
ration:none">Yes!</strong></p>
        </body>
        </html>""".replace(
            "deco\nration", "decoration"
        )

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
        <h1 class="foo" style="color:green">Hi!</h1>
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
        <p style="font-size:16px"><strong style="text-deco
ration:none">Yes!</strong></p>
        </body>
        </html>""".replace(
            "deco\nration", "decoration"
        )

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

        p = Premailer(html, keep_style_tags=True, strip_important=False)
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
        assert_raises(XMLSyntaxError, p.transform)

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
        <style type="text/css">/*<![CDATA[*/span:hover > a {back
ground:red}/*]]>*/</style>
        </head>
        <body>
        <span><a>Test</a></span>
        </body>
        </html>
        """.replace(
            "back\nground", "background"
        )

        p = Premailer(html, method="xml")
        result_html = p.transform()

        compare_html(expect_html, result_html)

    def test_command_line_fileinput_from_stdin(self):
        html = "<style>h1 { color:red; }</style><h1>Title</h1>"
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
            main(
                [
                    "-f",
                    "premailer/tests/test-apple-newsletter.html",
                    "--disable-basic-attributes=bgcolor",
                ]
            )

        result_html = out.getvalue().strip()

        ok_("<html>" in result_html)
        ok_(
            '<style media="only screen and (max-device-width: 480px)" '
            'type="text/css">\n'
            "* {line-height: normal !important; "
            "-webkit-text-size-adjust: 125%}\n"
            "</style>" in result_html
        )

    def test_command_line_preserve_style_tags(self):
        with captured_output() as (out, err):
            main(
                [
                    "-f",
                    "premailer/tests/test-issue78.html",
                    "--preserve-style-tags",
                    "--external-style=premailer/tests/test-external-styles.css",
                    "--allow-loading-external-files",
                ]
            )

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
        <link rel="alternate" type="applic
ation/rss+xml" title="RSS" href="/rss.xml">
        <style type="text/css">
        .yshortcuts a {border-bottom: none !important;}
        @media screen and (max-width: 600px) {
            table[class="container"] {
                width: 100% !important;
            }
        }
        /* Even comments should be preserved when the
           keep_style_tags flag is set */
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
        <p style="font-size:12px"><a href="" style="{color:pink} :hover{col
or:purple}">html</a></p>
        </body>
        </html>
        """.replace(
            "col\nor", "color"
        ).replace(
            "applic\nation", "application"
        )

        compare_html(expect_html, result_html)

        # for completeness, test it once without
        with captured_output() as (out, err):
            main(
                [
                    "-f",
                    "premailer/tests/test-issue78.html",
                    "--external-style=premailer/tests/test-external-styles.css",
                    "--allow-loading-external-files",
                ]
            )

        result_html = out.getvalue().strip()
        expect_html = """
        <html>
        <head>
        <link rel="alternate" type="applic
ation/rss+xml" title="RSS" href="/rss.xml">
        <style type="text/css">@media screen and (max-width: 600px) {
            table[class="container"] {
                width: 100% !important
                }
            }</style>
        <style type="text/css">@media all and (max-width: 320px) {
            h1 {
                font-size: 12px !important
                }
            }</style>
        </head>
        <body>
        <h1 style="color:brown">h1</h1>
        <p style="font-size:12px"><a href="" style="{color:pink} :hover{co
lor:purple}">html</a></p>
        </body>
        </html>
        """.replace(
            "co\nlor", "color"
        ).replace(
            "applic\nation", "application"
        )

        compare_html(expect_html, result_html)

    def test_multithreading(self):
        """The test tests thread safety of merge_styles function which employs
        thread non-safe cssutils calls.
        The test would fail if merge_styles would have not been thread-safe"""

        import threading
        import logging

        THREADS = 30
        REPEATS = 100

        class RepeatMergeStylesThread(threading.Thread):
            """The thread is instantiated by test and run multiple
            times in parallel."""

            exc = None

            def __init__(self, old, new, class_):
                """The constructor just stores merge_styles parameters"""
                super(RepeatMergeStylesThread, self).__init__()
                self.old, self.new, self.class_ = old, new, class_

            def run(self):
                """Calls merge_styles in a loop and sets exc attribute
                if merge_styles raises an exception."""
                for _ in range(0, REPEATS):
                    try:
                        merge_styles(self.old, self.new, self.class_)
                    except Exception as e:
                        logging.exception("Exception in thread %s", self.name)
                        self.exc = e

        inline_style = "background-color:#ffffff;"
        new = "background-color:#dddddd;"
        class_ = ""

        # start multiple threads concurrently; each
        # calls merge_styles many times
        threads = [
            RepeatMergeStylesThread(inline_style, [csstext_to_pairs(new)], [class_])
            for _ in range(0, THREADS)
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
        <link href="premailer/tests/test-external-links.css" rel="style
sheet" type="text/css">
        <link rel="alternate" type="applic
ation/rss+xml" title="RSS" href="/rss.xml">
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
        </html>""".replace(
            "applic\naction", "application"
        ).replace(
            "style\nsheet", "stylesheet"
        )

        expect_html = """<html>
        <head>
        <title>Title</title>
        <style type="text/css">a:hover {color:purple !important}</style>
        <link rel="alternate" type="applic
ation/rss+xml" title="RSS" href="/rss.xml">
        </head>
        <body>
        <h1 style="color:orange">Hello</h1>
        <h2 style="color:green">World</h2>
        <h3 style="color:yellow">Test</h3>
        <a href="#" style="color:pink">Link</a>
        </body>
        </html>""".replace(
            "applic\naction", "application"
        )

        p = Premailer(html, strip_important=False, allow_loading_external_files=True)
        result_html = p.transform()

        compare_html(expect_html, result_html)

    def test_external_links_disallow_network(self):
        """Test loading stylesheets via link tags with disallowed network access"""

        html = """<html>
            <head>
            <title>Title</title>
            <style type="text/css">
            h1 { color:red; }
            h3 { color:yellow; }
            </style>
            <link href="premailer/tests/test-external-links.css" rel="style
    sheet" type="text/css">
            <link rel="alternate" type="applic
    ation/rss+xml" title="RSS" href="/rss.xml">
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
            </html>""".replace(
            "applic\naction", "application"
        ).replace(
            "style\nsheet", "stylesheet"
        )

        expect_html = """<html>
            <head>
            <title>Title</title>
            <link href="premailer/tests/test-external-links.css" rel="style
    sheet" type="text/css">
            <link rel="alternate" type="applic
    ation/rss+xml" title="RSS" href="/rss.xml">
            </head>
            <body>
            <h1 style="color:orange">Hello</h1>
            <h2>World</h2>
            <h3 style="color:yellow">Test</h3>
            <a href="#">Link</a>
            </body>
            </html>""".replace(
            "applic\naction", "application"
        )

        p = Premailer(html, strip_important=False, allow_network=False)
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

        p = Premailer(html, strip_important=False, allow_loading_external_files=True)
        assert_raises(ExternalNotFoundError, p.transform)

    def test_external_styles_and_links(self):
        """Test loading stylesheets via both the 'external_styles'
        argument and link tags"""

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
        <style type="text/css">h2::after {cont
ent:"" !important;display:block !important}
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
        </html>""".replace(
            "cont\nent", "content"
        )

        p = Premailer(
            html,
            strip_important=False,
            external_styles="test-external-styles.css",
            base_path="premailer/tests/",
            allow_loading_external_files=True,
        )
        result_html = p.transform()

        compare_html(expect_html, result_html)

    @mock.patch("premailer.premailer.requests")
    def test_load_external_url(self, mocked_requests):
        "Test premailer.premailer.Premailer._load_external_url"
        faux_response = "This is not a response"
        faux_uri = "https://example.com/site.css"
        mocked_requests.get.return_value = MockResponse(faux_response)
        p = premailer.premailer.Premailer("<p>A paragraph</p>")
        r = p._load_external_url(faux_uri)

        mocked_requests.get.assert_called_once_with(faux_uri, verify=True)
        eq_(faux_response, r)

    def test_load_external_url_with_custom_session(self):
        mocked_session = mock.MagicMock()
        faux_response = "This is not a response"
        faux_uri = "https://example.com/site.css"
        mocked_session.get.return_value = MockResponse(faux_response)
        p = premailer.premailer.Premailer("<p>A paragraph</p>", session=mocked_session)
        r = p._load_external_url(faux_uri)

        mocked_session.get.assert_called_once_with(faux_uri, verify=True)
        eq_(faux_response, r)

    @mock.patch("premailer.premailer.requests")
    def test_load_external_url_no_insecure_ssl(self, mocked_requests):
        "Test premailer.premailer.Premailer._load_external_url"
        faux_response = "This is not a response"
        faux_uri = "https://example.com/site.css"
        mocked_requests.get.return_value = MockResponse(faux_response)
        p = premailer.premailer.Premailer(
            "<p>A paragraph</p>", allow_insecure_ssl=False
        )
        r = p._load_external_url(faux_uri)

        mocked_requests.get.assert_called_once_with(faux_uri, verify=True)
        eq_(faux_response, r)

    @mock.patch("premailer.premailer.requests")
    def test_load_external_url_with_insecure_ssl(self, mocked_requests):
        "Test premailer.premailer.Premailer._load_external_url"
        faux_response = "This is not a response"
        faux_uri = "https://example.com/site.css"
        mocked_requests.get.return_value = MockResponse(faux_response)
        p = premailer.premailer.Premailer("<p>A paragraph</p>", allow_insecure_ssl=True)
        r = p._load_external_url(faux_uri)

        mocked_requests.get.assert_called_once_with(faux_uri, verify=False)
        eq_(faux_response, r)

    @mock.patch("premailer.premailer.requests")
    def test_load_external_url_404(self, mocked_requests):
        "Test premailer.premailer.Premailer._load_external_url"
        faux_response = "This is not a response"
        faux_uri = "https://example.com/site.css"
        mocked_requests.get.return_value = MockResponse(faux_response, status_code=404)
        p = premailer.premailer.Premailer("<p>A paragraph</p>")
        assert_raises(HTTPError, p._load_external_url, faux_uri)

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

        p = Premailer(html, strip_important=False, css_text=[css_text])
        result_html = p.transform()

        compare_html(expect_html, result_html)

    def test_css_text_with_only_body_present(self):
        """Test handling css_text passed as a string when no <html> or
        <head> is present"""

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

        p = Premailer(html, strip_important=False, css_text=css_text)
        result_html = p.transform()

        compare_html(expect_html, result_html)

    def test_css_disable_leftover_css(self):
        """Test handling css_text passed as a string when no <html> or
        <head> is present"""

        html = """<body>
        <h1>Hello</h1>
        <h2>Hello</h2>
        <a href="">Hello</a>
        </body>"""

        expect_html = """<html>
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
            html, strip_important=False, css_text=css_text, disable_leftover_css=True
        )
        result_html = p.transform()

        compare_html(expect_html, result_html)

    @staticmethod
    def mocked_urlopen(url):
        'The standard "response" from the "server".'
        retval = ""
        if "style1.css" in url:
            retval = "h1 { color: brown }"
        elif "style2.css" in url:
            retval = "h2 { color: pink }"
        elif "style3.css" in url:
            retval = "h3 { color: red }"
        return retval

    @mock.patch.object(Premailer, "_load_external_url")
    def test_external_styles_on_http(self, mocked_pleu):
        """Test loading styles that are genuinely external"""

        html = """<html>
        <head>
        <link href="https://www.com/style1.css" rel="stylesheet">
        <link href="//www.com/style2.css" rel="stylesheet">
        <link href="//www.com/style3.css" rel="stylesheet">
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
        expected_args = [
            (("https://www.com/style1.css",),),
            (("http://www.com/style2.css",),),
            (("http://www.com/style3.css",),),
        ]
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

    @mock.patch.object(Premailer, "_load_external_url")
    def test_external_styles_on_https(self, mocked_pleu):
        """Test loading styles that are genuinely external"""

        html = """<html>
        <head>
        <link href="https://www.com/style1.css" rel="stylesheet">
        <link href="//www.com/style2.css" rel="stylesheet">
        <link href="/style3.css" rel="stylesheet">
        </head>
        <body>
        <h1>Hello</h1>
        <h2>World</h2>
        <h3>World</h3>
        </body>
        </html>"""

        mocked_pleu.side_effect = self.mocked_urlopen
        p = Premailer(
            html, base_url="https://www.peterbe.com", allow_loading_external_files=True
        )
        result_html = p.transform()

        expected_args = [
            (("https://www.com/style1.css",),),
            (("https://www.com/style2.css",),),
            (("https://www.peterbe.com/style3.css",),),
        ]
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

    @mock.patch.object(Premailer, "_load_external_url")
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
        p = Premailer(
            html, base_url="http://www.peterbe.com/", allow_loading_external_files=True
        )
        result_html = p.transform()
        expected_args = [(("http://www.peterbe.com/style.css",),)]
        eq_(expected_args, mocked_pleu.call_args_list)

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
        ok_("/* comment */" in result_html)

    def test_unknown_in_media_queries(self):
        """CSS unknown rule inside a media query block should not be a problem"""
        html = """<!doctype html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Document</title>
            <style>
                @media screen {
                    @unknownrule {
                        /* unknown rule */
                    }
                }
            </style>
        </head>
        <body></body>
        </html>"""

        p = Premailer(html, disable_validation=True)
        result_html = p.transform()
        ok_("/* unknown rule */" in result_html)

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
                    url('Garamond.ttf') format('truetype');
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

    def test_capture_cssutils_logging(self):
        """you can capture all the warnings, errors etc. from cssutils
        with your own logging."""
        html = """<!doctype html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Document</title>
            <style>
            @keyframes fadein {
                from { opacity: 0; }
                to   { opacity: 1; }
            }
            </style>
        </head>
        <body></body>
        </html>"""

        mylog = StringIO()
        myhandler = logging.StreamHandler(mylog)
        p = Premailer(html, cssutils_logging_handler=myhandler)
        p.transform()  # it should work
        eq_(
            mylog.getvalue(), "CSSStylesheet: Unknown @rule found. [2:13: @keyframes]\n"
        )

        # only log errors now
        mylog = StringIO()
        myhandler = logging.StreamHandler(mylog)
        p = Premailer(
            html,
            cssutils_logging_handler=myhandler,
            cssutils_logging_level=logging.ERROR,
        )
        p.transform()  # it should work
        eq_(mylog.getvalue(), "")

    def test_type_test(self):
        """test the correct type is returned"""

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

        p = Premailer(html)
        result = p.transform()
        eq_(type(result), type(""))

        html = fromstring(html)
        etree_type = type(html)

        p = Premailer(html)
        result = p.transform()
        ok_(type(result) != etree_type)

    def test_ignore_some_inline_stylesheets(self):
        """test that it's possible to put a `data-premailer="ignore"`
        attribute on a <style> tag and it gets left alone (except that
        the attribute gets removed)"""

        html = """<html>
        <head>
        <title>Title</title>
        <style type="text/css">
        h1 { color:red; }
        </style>
        <style type="text/css" data-premailer="ignore">
        h1 { color:blue; }
        </style>
        </head>
        <body>
        <h1>Hello</h1>
        <h2>World</h2>
        </body>
        </html>"""

        expect_html = """<html>
        <head>
        <title>Title</title>
        <style type="text/css">
        h1 { color:blue; }
        </style>
        </head>
        <body>
        <h1 style="color:red">Hello</h1>
        <h2>World</h2>
        </body>
        </html>"""

        p = Premailer(html, disable_validation=True)
        result_html = p.transform()
        compare_html(expect_html, result_html)

    def test_ignore_does_not_strip_importants(self):
        """test that it's possible to put a `data-premailer="ignore"`
        attribute on a <style> tag and important tags do not get stripped."""

        html = """<html>
        <head>
        <title>Title</title>
        <style type="text/css">
        h1 { color:red; }
        </style>
        <style type="text/css" data-premailer="ignore">
        h1 { color:blue !important; }
        </style>
        </head>
        <body>
        <h1>Hello</h1>
        <h2>World</h2>
        </body>
        </html>"""

        expect_html = """<html>
        <head>
        <title>Title</title>
        <style type="text/css">
        h1 { color:blue !important; }
        </style>
        </head>
        <body>
        <h1 style="color:red">Hello</h1>
        <h2>World</h2>
        </body>
        </html>"""

        p = Premailer(html, disable_validation=True)
        result_html = p.transform()
        compare_html(expect_html, result_html)

    @mock.patch("premailer.premailer.warnings")
    def test_ignore_some_incorrectly(self, warnings_mock):
        """You can put `data-premailer="ignore"` but if the attribute value
        is something we don't recognize you get a warning"""

        html = """<html>
        <head>
        <title>Title</title>
        <style type="text/css" data-premailer="blah">
        h1 { color:blue; }
        </style>
        </head>
        <body>
        <h1>Hello</h1>
        <h2>World</h2>
        </body>
        </html>"""

        expect_html = """<html>
        <head>
        <title>Title</title>
        </head>
        <body>
        <h1 style="color:blue">Hello</h1>
        <h2>World</h2>
        </body>
        </html>"""

        p = Premailer(html, disable_validation=True)
        result_html = p.transform()
        warnings_mock.warn.assert_called_with(
            "Unrecognized data-premailer attribute ('blah')"
        )

        compare_html(expect_html, result_html)

    def test_ignore_some_external_stylesheets(self):
        """test that it's possible to put a `data-premailer="ignore"`
        attribute on a <link> tag and it gets left alone (except that
        the attribute gets removed)"""

        # Know thy fixtures!
        # The test-external-links.css has a `h1{color:blue}`
        # And the test-external-styles.css has a `h1{color:brown}`
        html = """<html>
        <head>
        <title>Title</title>
        <link href="premailer/tests/test-external-links.css"
         rel="stylesheet" type="text/css">
        <link data-premailer="ignore"
          href="premailer/tests/test-external-styles.css"
          rel="stylesheet" type="text/css">
        </head>
        <body>
        <h1>Hello</h1>
        </body>
        </html>"""

        # Note that the `test-external-links.css` gets converted to a inline
        # style sheet.
        expect_html = """<html>
<head>
<title>Title</title>
<style type="text/css">a:hover {color:purple}</style>
<link href="premailer/tests/test-external-styles.css" rel="style
sheet" type="text/css">
</head>
<body>
<h1 style="color:blue">Hello</h1>
</body>
</html>""".replace(
            "style\nsheet", "stylesheet"
        )

        p = Premailer(html, disable_validation=True, allow_loading_external_files=True)
        result_html = p.transform()
        compare_html(expect_html, result_html)

    def test_turnoff_cache_works_as_expected(self):
        html = """<html>
        <head>
        <style>
        .color {
            color: green;
        }
        div.example {
            font-size: 10px;
        }
        </style>
        </head>
        <body>
        <div class="color example"></div>
        </body>
        </html>"""

        expect_html = """<html>
        <head>
        </head>
        <body>
        <div class="color example" style="color:green; font-size:10px"></div>
        </body>
        </html>"""

        p = Premailer(html, cache_css_parsing=False)
        self.assertFalse(p.cache_css_parsing)
        # run one time first
        p.transform()
        result_html = p.transform()

        compare_html(expect_html, result_html)

    def test_links_without_protocol(self):
        """If you the base URL is set to https://example.com and your html
        contains <img src="//otherdomain.com/">... then the URL to point to
        is "https://otherdomain.com/" not "https://example.com/file.css"
        """
        html = """<html>
        <head>
        </head>
        <body>
        <img src="//example.com">
        </body>
        </html>"""

        expect_html = """<html>
        <head>
        </head>
        <body>
        <img src="{protocol}://example.com">
        </body>
        </html>"""

        p = Premailer(html, base_url="https://www.peterbe.com")
        result_html = p.transform()
        compare_html(expect_html.format(protocol="https"), result_html)

        p = Premailer(html, base_url="http://www.peterbe.com")
        result_html = p.transform()
        compare_html(expect_html.format(protocol="http"), result_html)

        # Because you can't set a base_url without a full protocol
        p = Premailer(html, base_url="www.peterbe.com")
        assert_raises(ValueError, p.transform)

    def test_align_float_images(self):

        html = """<html>
        <head>
        <title>Title</title>
        <style>
        .floatright {
            float: right;
        }
        </style>
        </head>
        <body>
        <p><img src="/images/left.jpg" style="float: left"> text
           <img src="/r.png" class="floatright"> text
           <img src="/images/nofloat.gif"> text
        </body>
        </html>"""

        expect_html = """<html>
<head>
<title>Title</title>
</head>
<body>
<p><img src="/images/left.jpg" style="float: left" align="left"> text
   <img src="/r.png" class="floatright" style="float:right" align="right"> text
   <img src="/images/nofloat.gif"> text
</p>
</body>
</html>"""

        p = Premailer(html, align_floating_images=True)
        result_html = p.transform()
        compare_html(expect_html, result_html)

    def test_remove_unset_properties(self):
        html = """<html>
        <head>
        <style>
        div {
            color: green;
        }
        span {
            color: blue;
        }
        span.nocolor {
            color: unset;
        }
        </style>
        </head>
        <body>
        <div class="color"><span class="nocolor"></span></div>
        </body>
        </html>"""

        expect_html = """<html>
        <head>
        </head>
        <body>
        <div class="color" style="color:green"><span class="nocolor"></span>
        </div>
        </body>
        </html>"""

        p = Premailer(html, remove_unset_properties=True)
        self.assertTrue(p.remove_unset_properties)
        result_html = p.transform()
        compare_html(expect_html, result_html)

    def test_six_color(self):
        r = Premailer.six_color("#cde")
        e = "#ccddee"
        self.assertEqual(e, r)

    def test_3_digit_color_expand(self):
        "Are 3-digit color values expanded into 6-digits for IBM Notes"
        html = """<html>
    <style>
        body {background-color: #fe5;}
        p {background-color: #123456;}
        h1 {color: #f0df0d;}
    </style>
    <body>
        <h1>color test</h1>
        <p>
            This is a test of color handling.
        </p>
    </body>
</html>"""
        expect_html = """<html>
    <head>
    </head>
    <body style="background-color:#fe5" bgcolor="#ffee55">
        <h1 style="color:#f0df0d">color test</h1>
        <p style="background-color:#123456" bgcolor="#123456">
            This is a test of color handling.
        </p>
    </body>
</html>"""
        p = Premailer(html, remove_unset_properties=True)
        result_html = p.transform()
        compare_html(expect_html, result_html)

    def test_inline_important(self):
        "Are !important tags preserved inline."

        html = """<html>
<head>
  <title></title>
</head>
<body>
  <style type="text/css">.something { display:none !important; }</style>
  <div class="something">blah</div>
</body>
</html>"""

        expect_html = """<html>
<head>
  <title></title>
</head>
<body>
  <style type="text/css">.something { display:none !important; }</style>
  <div class="something" style="display:none !important">blah</div>
</body>
</html>"""
        p = Premailer(
            html, remove_classes=False, keep_style_tags=True, strip_important=False
        )
        result_html = p.transform()
        compare_html(expect_html, result_html)

    def test_pseudo_selectors_without_selector(self):
        """Happens when you have pseudo selectors without an actual selector.
        Which means it's not possible to find it in the DOM.

        For example:

           <style>
           :before{box-sizing:inherit}
           </style>

        Semantic-UI uses this in its normalizer.

        Original issue: https://github.com/peterbe/premailer/issues/184
        """

        html = """
            <html>
            <style>
                 *,:after,:before{box-sizing:inherit}
                h1{ border: 1px solid blue}
                h1:hover {border: 1px solid green}

            </style>
            <h1>Hey</h1>
            </html>
        """

        expect_html = """
<html>
    <head>
    <style>
         *,:after,:before{box-sizing:inherit}
        h1{ border: 1px solid blue}
        h1:hover {border: 1px solid green}

    </style>
    </head>
    <body>
    <h1 style="{border:1px solid blue} :hover{border:1px solid green}">Hey</h1>
    </body>
</html>
        """
        p = Premailer(html, exclude_pseudoclasses=False, keep_style_tags=True)
        result_html = p.transform()
        compare_html(expect_html, result_html)

    def test_preserve_handlebar_syntax(self):
        """Demonstrate encoding of handlebar syntax with preservation.

        Original issue: https://github.com/peterbe/premailer/issues/248
        """

        html = """
            <html>
            <img src="{{ data | default: 'Test & <code>' }}">
            <a href="{{ data | default: "Test & <code>" }}"></a>
            </html>
        """

        expected_preserved_html = """
<html>
    <head>
    </head>
    <body>
    <img src="{{ data | default: 'Test & <code>' }}">
    <a href="{{ data | default: "Test & <code>" }}"></a>
    </body>
</html>
"""

        expected_neglected_html = """
<html>
    <head>
    </head>
    <body>
    <img src="%7B%7B%20data%20%7C%20default:%20'Test%20&amp;%20&lt;code&gt;'%20%7D%7D">
    <a href="%7B%7B%20data%20%7C%20default:%20" test>" }}"&gt;</a>
    </body>
</html>
"""
        p = Premailer(html, preserve_handlebar_syntax=True)
        result_preserved_html = p.transform()
        compare_html(expected_preserved_html, result_preserved_html)

        p = Premailer(html)
        result_neglected_html = p.transform()
        compare_html(expected_neglected_html, result_neglected_html)

    def test_allow_loading_external_files(self):
        """Demonstrate the risks of allow_loading_external_files"""
        external_content = "foo { bar:buz }"
        with tempfile.TemporaryDirectory() as tmpdirname:
            tmp_file = os.path.join(tmpdirname, "external.css")
            with open(tmp_file, "w") as f:
                f.write(external_content)
            html = """
                <html>
                <head>
                <link rel=stylesheet href="{}">
                </head>
                </html>
            """.format(
                tmp_file
            )

            p = Premailer(html)
            assert_raises(ExternalFileLoadingError, p.transform)

            # Imagine if `allow_loading_external_files` and `keep_style_tags` where
            # both on, in some configuration or instance, but the HTML being
            # sent in, this program will read that file unconditionally and include
            # it in the file rendered HTML output.
            # E.g. `<link rel=stylesheet href=/tmp/credentials.txt>`
            p = Premailer(html, allow_loading_external_files=True, keep_style_tags=True)
            out = p.transform()
            assert external_content in out
