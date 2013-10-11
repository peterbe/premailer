import re
from nose.tools import eq_, ok_

from premailer import Premailer, etree, merge_styles


def test_merge_styles_basic():
    old = 'font-size:1px; color: red'
    new = 'font-size:2px; font-weight: bold'
    expect = 'color:red;', 'font-size:2px;', 'font-weight:bold'
    result = merge_styles(old, new)
    for each in expect:
        assert each in result


def test_merge_styles_with_class():
    old = 'color:red; font-size:1px;'
    new, class_ = 'font-size:2px; font-weight: bold', ':hover'

    # because we're dealing with dicts (random order) we have to
    # test carefully.
    # We expect something like this:
    #  {color:red; font-size:1px} :hover{font-size:2px; font-weight:bold}

    result = merge_styles(old, new, class_)
    ok_(result.startswith('{'))
    ok_(result.endswith('}'))
    ok_(' :hover{' in result)
    split_regex = re.compile('{([^}]+)}')
    eq_(len(split_regex.findall(result)), 2)
    expect_first = 'color:red', 'font-size:1px'
    expect_second = 'font-weight:bold', 'font-size:2px'
    for each in expect_first:
        ok_(each in split_regex.findall(result)[0])
    for each in expect_second:
        ok_(each in split_regex.findall(result)[1])


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

    eq_(expect_html, result_html)


def test_empty_style_tag():
    """empty style tag"""
    if not etree:
        # can't test it
        return

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

    whitespace_between_tags = re.compile('>\s*<',)

    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()

    eq_(expect_html, result_html)


def test_mixed_pseudo_selectors():
    """mixing pseudo selectors with straight forward selectors"""
    if not etree:
        # can't test it
        return

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

    whitespace_between_tags = re.compile('>\s*<',)

    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()

    eq_(expect_html, result_html)


def test_basic_html_with_pseudo_selector():
    """test the simplest case"""
    if not etree:
        # can't test it
        return

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

    whitespace_between_tags = re.compile('>\s*<',)

    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()

    eq_(expect_html, result_html)


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
    """, 0)

    # 'rules' is a list, turn it into a dict for
    # easier assertion testing
    rules_dict = {}
    rules_specificity = {}
    for specificity, k, v in rules:
        rules_dict[k] = v
        rules_specificity[k] = specificity

    assert 'h1' in rules_dict
    assert 'h2' in rules_dict
    assert 'strong' in rules_dict
    assert 'ul li' in rules_dict

    assert rules_dict['h1'] == 'color:red'
    assert rules_dict['h2'] == 'color:red'
    assert rules_dict['strong'] == 'text-decoration:none'
    assert rules_dict['ul li'] == 'list-style:2px'
    assert 'a:hover' not in rules_dict

    p = Premailer('html', exclude_pseudoclasses=True)  # won't need the html
    func = p._parse_style_rules
    rules, leftover = func("""
    ul li {  list-style: 2px; }
    a:hover { text-decoration: underline }
    """, 0)

    assert len(rules) == 1
    specificity, k, v = rules[0]
    assert k == 'ul li'
    assert v == 'list-style:2px'

    assert len(leftover) == 1
    k, v = leftover[0]
    assert (k, v) == ('a:hover', 'text-decoration:underline'), (k, v)


def test_precedence_comparison():
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
    assert rules_specificity['h1'] < rules_specificity['h2']
    # More elements wins
    assert rules_specificity['strong'] < rules_specificity['ul li']
    # IDs trump everything
    assert (rules_specificity['div li.example p.sample'] <
            rules_specificity['#identified'])

    # Classes trump multiple elements
    assert (rules_specificity['ul li'] <
            rules_specificity['li.example'])


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


def test_base_url_with_path():
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
    <img src="http://kungfupeople.com/base/images/foo.jpg">
    <img src="http://kungfupeople.com/base/images/bar.gif">
    <img src="http://www.googe.com/photos/foo.jpg">
    <a href="http://kungfupeople.com/base/home">Home</a>
    <a href="http://www.peterbe.com">External</a>
    <a href="http://kungfupeople.com/base/subpage">Subpage</a>
    <a href="#internal_link">Internal Link</a>
    </body>
    </html>'''

    p = Premailer(html, base_url='http://kungfupeople.com/base',
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
    <body style="color:#123; background:url(http://example.com/bg.png); font-family:Omerta">
    <h1>Hi!</h1>
    </body>
    </html>'''

    p = Premailer(html)
    result_html = p.transform()

    whitespace_between_tags = re.compile('>\s*<',)

    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()
    eq_(expect_html, result_html)


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

    p = Premailer(html, exclude_pseudoclasses=False)
    result_html = p.transform()

    # because we're dealing with random dicts here we can't predict what
    # order the style attribute will be written in so we'll look for things
    # manually.
    assert '<p style="::first-letter{float:left; font-size:300%}">'\
           'Paragraph</p>' in result_html

    assert 'style="{color:red; border:1px solid green}' in result_html
    assert ' :visited{border:1px solid green}' in result_html
    assert ' :hover{text-decoration:none; border:1px solid green}' in \
        result_html


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
    <p style="height:100%; width:100%" width="100%" height="100%">Paragraph</p>
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


def test_prefer_inline_to_class():
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

    whitespace_between_tags = re.compile('>\s*<',)

    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()

    eq_(expect_html, result_html)


def test_favour_rule_with_element_over_generic():
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

    whitespace_between_tags = re.compile('>\s*<',)

    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()

    eq_(expect_html, result_html)


def test_favour_rule_with_class_over_generic():
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

    whitespace_between_tags = re.compile('>\s*<',)

    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()

    eq_(expect_html, result_html)


def test_favour_rule_with_id_over_others():
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

    whitespace_between_tags = re.compile('>\s*<',)

    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()

    eq_(expect_html, result_html)


def test_multiple_style_elements():
    """Asserts that rules from multiple style elements are inlined correctly."""
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

    whitespace_between_tags = re.compile('>\s*<',)

    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()

    eq_(expect_html, result_html)


def test_ignore_style_elements_with_media_attribute():
    """Asserts that style elements with media attributes other than 'screen' are ignored."""
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

    whitespace_between_tags = re.compile('>\s*<', )

    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()

    eq_(expect_html, result_html)


def test_leftover_important():
    """Asserts that leftover styles should be marked as !important."""
    if not etree:
        # can't test it
        return

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
    <style type="text/css">a:hover {color:green !important}
a:focus {color:blue !important}</style>
    </head>
    <body>
    <a href="#" style="color:red">Hi!</a>
    </body>
    </html>"""

    p = Premailer(html,
        keep_style_tags=True,
        strip_important=False)
    result_html = p.transform()

    whitespace_between_tags = re.compile('>\s*<',)

    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()

    eq_(expect_html, result_html)


def test_basic_xml():
    """Test the simplest case with xml"""
    if not etree:
        # can't test it
        return

    html = """<html>
<head>
<title>Title</title>
<style type="text/css">
img { border: none; }
</style>
</head>
<body>
<img src="test.png" alt="test">
</body>
</html>"""

    expect_html = """<html>
<head>
<title>Title</title>
</head>
<body>
<img src="test.png" alt="test" style="border:none"/>
</body>
</html>"""

    p = Premailer(html, method="xml")
    result_html = p.transform()

    whitespace_between_tags = re.compile('>\s*<',)

    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()

    eq_(expect_html, result_html)


def test_xml_cdata():
    """Test that CDATA is set correctly on remaining styles"""
    if not etree:
        # can't test it
        return

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
</html>"""

    expect_html = """<html>
<head>
<title>Title</title>
<style type="text/css">/*<![CDATA[*/span:hover > a {background:red}/*]]>*/</style>
</head>
<body>
<span><a>Test</a></span>
</body>
</html>"""

    p = Premailer(html, method="xml")
    result_html = p.transform()

    whitespace_between_tags = re.compile('>\s*<',)

    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()

    eq_(expect_html, result_html)


def test_xml_cdata():
    """Test that CDATA is set correctly on remaining styles"""
    if not etree:
        # can't test it
        return

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
    </html>"""

    expect_html = """<html>
    <head>
    <title>Title</title>
    <style type="text/css">/*<![CDATA[*/span:hover > a {background:red}/*]]>*/</style>
    </head>
    <body>
    <span><a>Test</a></span>
    </body>
    </html>"""

    p = Premailer(html, method="xml")
    result_html = p.transform()

    whitespace_between_tags = re.compile('>\s*<',)

    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()

    eq_(expect_html, result_html)
