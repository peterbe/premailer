import re
import urlparse
from nose.tools import eq_, ok_

from premailer import Premailer, etree


def test_merge_styles_basic():
    html = """<html>
    <head>
    <style type="text/css">
    p { font-size:2px; font-weight: bold }
    </style>
    </head>
    <body>
    <p style="font-size:1px; color: red">hello</p>
    </body>
    </html>"""

    expect_html = """<html>
    <head>
    </head>
    <body>
    <p style="color:red; font-size:1px; font-weight:bold">hello</p>
    </body>
    </html>"""

    p = Premailer(html)
    result_html = p.transform()

    whitespace_between_tags = re.compile('>\s*<',)

    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()

    assert expect_html == result_html


def test_merge_styles_with_class():
    html = """<html>
    <head>
    <style type="text/css">
    p:hover{font-size:2px; font-weight:bold}
    </style>
    </head>
    <body>
    <p style="font-size:1px; color: red">hello</p>
    </body>
    </html>"""

    expect_html = """<html>
    <head>
    </head>
    <body>
    <p style="{color:red; font-size:1px} :hover{font-size:2px; font-weight:bold}">hello</p>
    </body>
    </html>"""

    p = Premailer(html)
    result_html = p.transform()

    whitespace_between_tags = re.compile('>\s*<',)

    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()

    assert expect_html == result_html


def test_basic_html():
    """test the simplest case"""
    if not etree:
        # can't test it
        return

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

    whitespace_between_tags = re.compile('>\s*<',)

    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()

    assert expect_html == result_html


def test_parse_style_rules():

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
    """)

    # 'rules' is a list, turn it into a dict for
    # easier assertion testing
    rules_dict = {}
    for k, v in rules:
        rules_dict[k] = v

    assert 'h1' in rules_dict
    assert 'h2' in rules_dict
    assert 'strong' in rules_dict
    assert 'ul li' in rules_dict

    # order is important
    rules_keys = [x[0] for x in rules]
    assert rules_keys.index('h1') < rules_keys.index('h2')
    assert rules_keys.index('strong') < rules_keys.index('ul li')

    assert rules_dict['h1'] == 'color:red'
    assert rules_dict['h2'] == 'color:red'
    assert rules_dict['strong'] == 'text-decoration:none'
    assert rules_dict['ul li'] == 'list-style:2px'
    assert rules_dict['a:hover'] == 'text-decoration:underline'

    p = Premailer('html', exclude_pseudoclasses=True)  # won't need the html
    func = p._parse_style_rules
    rules, leftover = func("""
    ul li {  list-style: 2px; }
    a:hover { text-decoration: underline }
    """)

    assert len(rules) == 1
    k, v = rules[0]
    assert k == 'ul li'
    assert v == 'list-style:2px'

    assert len(leftover) == 1
    k, v = leftover[0]
    assert (k, v) == ('a:hover', 'text-decoration:underline'), (k, v)


def test_base_url_fixer():
    """if you leave some URLS as /foo and set base_url to
    'http://www.google.com' the URLS become 'http://www.google.com/foo'
    """
    if not etree:
        # can't test it
        return

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
    <img src="http://www.googe.com/photos/foo.jpg">
    <a href="http://kungfupeople.com/home">Home</a>
    <a href="http://www.peterbe.com">External</a>
    <a href="http://kungfupeople.com/subpage">Subpage</a>
    <a href="#internal_link">Internal Link</a>
    </body>
    </html>'''

    p = Premailer(html, base_url='http://kungfupeople.com',
                  preserve_internal_links=True)
    result_html = p.transform()

    whitespace_between_tags = re.compile('>\s*<',)

    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()

    eq_(expect_html, result_html)


def test_style_block_with_external_urls():
    """
    From http://github.com/peterbe/premailer/issues/#issue/2

    If you have
      body { background:url(http://example.com/bg.png); }
    the ':' inside '://' is causing a problem
    """
    if not etree:
        # can't test it
        return

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
    <body style="color:#123; font-family:Omerta; background:url(http://example.com/bg.png)">
    <h1>Hi!</h1>
    </body>
    </html>'''

    p = Premailer(html)
    result_html = p.transform()

    whitespace_between_tags = re.compile('>\s*<',)

    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()
    assert expect_html == result_html


def test_base_url_for_style_block_urls():
    """base_url should also fix style block urls.

    If you have
      body { background:url(/images/bg.png); }
    then a transform with a base_url should change the url
    to prepend the base_url.
    """
    if not etree:
        # can't test it
        return

    html = """<html>
    <head>
    <title>Title</title>
    <style type="text/css">
    body {
      color:#123;
      background: url(/images/bg.png);
      fun: url('/images/fun.png');
      extra-fun:  url(  \"/images/extra_fun.png\" );
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
    <body style="color:#123; fun:url('http://example.com/images/fun.png'); """ \
     "font-family:Omerta; background:url('http://example.com/images/bg.png'); " \
     "extra-fun:url('http://example.com/images/extra_fun.png')\">" \
    """<h1>Hi!</h1>
    </body>
    </html>"""

    p = Premailer(html, base_url='http://example.com')
    result_html = p.transform()

    whitespace_between_tags = re.compile('>\s*<',)

    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()
    assert expect_html == result_html


def test_url_transform():

    if not etree:
        # can't test it
        return

    html = """<html>
    <head>
    <title>Title</title>
    <style type="text/css">
    body {
      color:#123;
      background: url(/images/bg.png);
      font-family: Omerta;
    }
    </style>
    </head>
    <body>
    <h1>Hi!</h1>
    <img src="/images/foo.jpg">
    <img src="http://www.googe.com/photos/foo.jpg">
    <a href="/home">Home</a>
    <a href="http://www.peterbe.com">External</a>
    </body>
    </html>"""

    expect_html = """<html>
    <head>
    <title>Title</title>
    </head>
    <body style="color:#123; font-family:Omerta; background:url('http://example.com/static/images/bg.png')">
    <h1>Hi!</h1>
    <img src="http://example.com/static/images/foo.jpg">
    <img src="http://www.googe.com/photos/foo.jpg">
    <a href="http://example.com/home">Home</a>
    <a href="http://www.peterbe.com">External</a>
    </body>
    </html>"""

    def url_transform(url):
        """Add 'static/' before 'example.com' image urls."""

        uscheme, netloc, path, query, fragment = urlparse.urlsplit(url)

        if path.startswith('/images'):
            if not netloc or netloc == 'example.com':
                path = 'static' + path

        return urlparse.urlunsplit((uscheme, netloc, path, query, fragment))

    p = Premailer(html,
                  base_url='http://example.com',
                  url_transform=url_transform)
    result_html = p.transform()

    whitespace_between_tags = re.compile('>\s*<',)

    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()
    assert expect_html == result_html


def test_shortcut_function():
    # you don't have to use this approach:
    #   from premailer import Premailer
    #   p = Premailer(html, base_url=base_url)
    #   print p.transform()
    # You can do it this way:
    #   from premailer import transform
    #   print transform(html, base_url=base_url)

    if not etree:
        # can't test it
        return

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

    whitespace_between_tags = re.compile('>\s*<',)

    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()

    assert expect_html == result_html, result_html


def test_css_with_pseudoclasses_included():
    "Pick up the pseudoclasses too and include them"
    if not etree:
        # can't test it
        return

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

    ''' Unused, for reading purposes.
    expect_html = """<html>
    <head>
    </head>
    <body>
    <a href="#" style="color:red;text-decoration:none">Special!</a>
    <a href="#" style="{color:red; border:1px solid green} :hover{text-decoration:none; border:1px solid green} :visited{border:1px solid green}">Page</a>
    <p style="::first-letter{float: left; font-size: 300%}">Paragraph</p>
    </body>
    </html>"""
    '''

    p = Premailer(html)
    result_html = p.transform()

    # because we're dealing with random dicts here we can't predict what
    # order the style attribute will be written in so we'll look for things
    # manually.
    assert '<head></head>' in result_html
    assert '<p style="::first-letter{font-size:300%; float:left}">'\
           'Paragraph</p>' in result_html

    assert 'style="{color:red; border:1px solid green}' in result_html
    assert ' :visited{border:1px solid green}' in result_html
    assert ' :hover{border:1px solid green; text-decoration:none}' in \
        result_html
    print result_html


def test_css_with_pseudoclasses_excluded():
    "Skip things like `a:hover{}` and keep them in the style block"
    if not etree:
        # can't test it
        return

    html = '''<html>
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
    </html>'''

    expect_html = '''<html>
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
    </html>'''

    p = Premailer(html, exclude_pseudoclasses=True)
    result_html = p.transform()

    whitespace_between_tags = re.compile('>\s*<',)

    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()

    expect_html = re.sub('}\s+', '}', expect_html)
    result_html = result_html.replace('}\n', '}')

    eq_(expect_html, result_html)


def test_css_with_html_attributes():
    """Some CSS styles can be applied as normal HTML attribute like
    'background-color' can be turned into 'bgcolor'
    """
    if not etree:
        # can't test it
        return

    html = """<html>
    <head>
    <style type="text/css">
    td { background-color:red; }
    p { text-align:center; }
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
        <td style="background-color:red" bgcolor="red">Cell 1</td>
        <td style="background-color:red" bgcolor="red">Cell 2</td>
      </tr>
    </table>
    </body>
    </html>"""

    p = Premailer(html, exclude_pseudoclasses=True)
    result_html = p.transform()

    whitespace_between_tags = re.compile('>\s*<',)

    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()

    expect_html = re.sub('}\s+', '}', expect_html)
    result_html = result_html.replace('}\n', '}')

    eq_(expect_html, result_html)


def test_apple_newsletter_example():
    # stupidity test
    import os
    html_file = os.path.join(os.path.dirname(__file__),
                             'test-apple-newsletter.html')
    html = open(html_file).read()

    p = Premailer(html, exclude_pseudoclasses=False,
                  keep_style_tags=True,
                  strip_important=False)
    result_html = p.transform()
    ok_('<html>' in result_html)
    ok_('<style media="only screen and (max-device-width: 480px)" '
        'type="text/css">\n'
        '* {line-height: normal !important; -webkit-text-size-adjust: 125%}\n'
        '</style>' in result_html)


def test_mailto_url():
    """if you use URL with mailto: protocol, they should stay as mailto:
    when baseurl is used
    """
    if not etree:
        # can't test it
        return

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

    whitespace_between_tags = re.compile('>\s*<',)

    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()

    assert expect_html == result_html


def test_strip_important():
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
    <p style="width:100%; height:100%" width="100%" height="100%">Paragraph</p>
    </body>
    </html>"""

    p = Premailer(html, strip_important=True)
    result_html = p.transform()

    whitespace_between_tags = re.compile('>\s*<',)

    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()

    eq_(expect_html, result_html)


def test_inline_wins_over_external():
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

    whitespace_between_tags = re.compile('>\s*<',)

    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()

    eq_(expect_html, result_html)


def test_last_child():
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

    whitespace_between_tags = re.compile('>\s*<',)

    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()

    eq_(expect_html, result_html)


def test_last_child_exclude_pseudo():
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

    whitespace_between_tags = re.compile('>\s*<',)

    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()

    eq_(expect_html, result_html)


def test_mediaquery():
    html = """<html>
    <head>
    <style type="text/css">
    div {
        text-align: right;
    }
    @media print{
        div {
            text-align: center;
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
    </head>
    <body>
    <div style="text-align:right" align="right">First div</div>
    </body>
    </html>"""

    p = Premailer(html)
    result_html = p.transform()

    whitespace_between_tags = re.compile('>\s*<',)

    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()

    eq_(expect_html, result_html)


def test_child_selector():
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

    whitespace_between_tags = re.compile('>\s*<',)

    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()

    eq_(expect_html, result_html)


def test_doctype():
    html = """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
    <html>
    <head>
    </head>
    <body>
    </body>
    </html>"""

    expect_html = """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
    <html>
    <head>
    </head>
    <body>
    </body>
    </html>"""

    p = Premailer(html)
    result_html = p.transform()

    whitespace_between_tags = re.compile('>\s*<',)

    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()

    eq_(expect_html, result_html)


def test_css_specificity():
    html = """<html>
    <head>
    <style type="text/css">
    td.content-inner p {padding-bottom:10px;}
    p {padding-bottom:0;}
    </style>
    </head>
    <body>
    <p>text</p>
    <table>
    <tr>
    <td class="content-inner">
    <p>some text</p>
    </td>
    </tr>
    </table>
    </body>
    </html>"""

    expect_html = """<html>
    <head>
    </head>
    <body>
    <p style="padding-bottom:0">text</p>
    <table>
    <tr>
    <td>
    <p style="padding-bottom:10px">some text</p>
    </td>
    </tr>
    </table>
    </body>
    </html>"""

    p = Premailer(html)
    result_html = p.transform()

    whitespace_between_tags = re.compile('>\s*<',)

    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()

    eq_(expect_html, result_html)


def test_css_selector_grouping():
    html = """<html>
    <head>
    <style type="text/css">
    h1,h2,h3 {color: black}
    h1 {font-size: 24px; color: red}
    h1.major {font-size: 48px}
    h1#title {font-weight: bold}
    h2#subtitle {font-size: 12px}
    </style>
    </head>
    <body>
    <h1 id="title" class="major">h1 title text</h1>
    <h1>h1 text</h1>
    <h2 id="subtitle">h2 text</h2>
    <h3>h3 text</h3>
    </body>
    </html>"""

    expect_html = """<html>
    <head>
    </head>
    <body>
    <h1 id="title" style="color:red; font-size:48px; font-weight:bold">h1 title text</h1>
    <h1 style="color:red; font-size:24px">h1 text</h1>
    <h2 id="subtitle" style="color:black; font-size:12px">h2 text</h2>
    <h3 style="color:black">h3 text</h3>
    </body>
    </html>"""

    p = Premailer(html)
    result_html = p.transform()

    whitespace_between_tags = re.compile('>\s*<',)

    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()

    eq_(expect_html, result_html)


def test_general():
    html = """<html>
        <head>
        <title>Test</title>
        <style>
        h1, h2 { color:red; }
        strong {
          text-decoration:none
          }
        p { font-size:2px }
        p.footer { font-size: 1px}
        </style>
        </head>
        <body>
        <h1>Hi!</h1>
        <p><strong>Yes!</strong></p>
        <p class="footer" style="color:red">Feetnuts</p>
        </body>
        </html>"""

    expect_html = """<html>
    <head>
    <title>Test</title>
    </head>
    <body>
    <h1 style="color:red">Hi!</h1>
    <p style="font-size:2px"><strong style="text-decoration:none">Yes!</strong></p>
    <p style="color:red; font-size:1px">Feetnuts</p>
    </body>
    </html>"""

    p = Premailer(html)
    result_html = p.transform()

    whitespace_between_tags = re.compile('>\s*<',)

    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()

    eq_(expect_html, result_html)
