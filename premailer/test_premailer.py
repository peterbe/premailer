import re
import nose.tools

from premailer import Premailer, etree, _merge_styles, transform

    
def test_merge_styles_basic():
    old = 'font-size:1px; color: red'
    new = 'font-size:2px; font-weight: bold'
    expect = 'color:red;', 'font-size:2px;', 'font-weight:bold'
    result = _merge_styles(old, new)
    for each in expect:
        assert each in result
        
        
def test_merge_styles_with_class():
    old = 'color:red; font-size:1px;'
    new, class_ = 'font-size:2px; font-weight: bold', ':hover'
    
    # because we're dealing with dicts (random order) we have to 
    # test carefully.
    # We expect something like this:
    #  {color:red; font-size:1px} :hover{font-size:2px; font-weight:bold}
    
    result = _merge_styles(old, new, class_)
    assert result.startswith('{')
    assert result.endswith('}')
    assert ' :hover{' in result
    split_regex = re.compile('{([^}]+)}')
    assert len(split_regex.findall(result)) == 2
    expect_first = 'color:red', 'font-size:1px'
    expect_second = 'font-weight:bold', 'font-size:2px'
    for each in expect_first:
        assert each in split_regex.findall(result)[0]
    for each in expect_second:
        assert each in split_regex.findall(result)[1]
        

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
    
    p = Premailer('html') # won't need the html
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

    p = Premailer('html', exclude_pseudoclasses=True) # won't need the html
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
    assert (k, v) == ('a:hover', 'text-decoration:underline'), (k,v)
    
    
def test_base_url_fixer():
    """if you leave some URLS as /foo and set base_url to 
    'http://www.google.com' the URLS become 'http://www.google.com/foo'
    """
    if not etree:
        # can't test it
        return
    
    html = """<html>
    <head>
    <title>Title</title>
    </head>
    <body>
    <img src="/images/foo.jpg"/>
    <img src="/images/bar.gif"/>
    <img src="http://www.googe.com/photos/foo.jpg">
    <a href="/home">Home</a>
    <a href="http://www.peterbe.com">External</a>
    <a href="subpage">Subpage</a>
    <a href="#internal_link">Internal Link</a>    
    </body>
    </html>"""
    
    expect_html = """<html>
    <head>
    <title>Title</title>
    </head>
    <body>
    <img src="http://kungfupeople.com/images/foo.jpg"/>
    <img src="http://kungfupeople.com/images/bar.gif"/>
    <img src="http://www.googe.com/photos/foo.jpg"/>
    <a href="http://kungfupeople.com/home">Home</a>
    <a href="http://www.peterbe.com">External</a>
    <a href="http://kungfupeople.com/subpage">Subpage</a>
    <a href="#internal_link">Internal Link</a>    
    </body>
    </html>"""
    
    p = Premailer(html, base_url='http://kungfupeople.com',
                  preserve_internal_links=True)
    result_html = p.transform()
    
    whitespace_between_tags = re.compile('>\s*<',)
    
    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()
    
    assert expect_html == result_html
    
    
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
    
    expect_html = """<html>
    <head>
    <title>Title</title>
    </head>
    <body style="color:#123; font-family:Omerta; background:url(http://example.com/bg.png)">
    <h1>Hi!</h1>
    </body>
    </html>""" #"
    
    p = Premailer(html)
    result_html = p.transform()
    
    whitespace_between_tags = re.compile('>\s*<',)
    
    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()
    #print result_html
    #print expect_html
    
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
    
    html = """<html>
    <head>
    <style type="text/css">h1{color:#123}</style>
    </head>
    <body>
    <h1>Hi!</h1>
    </body>
    </html>"""
    
    expect_html = """<html>
    <head></head>
    <body>
    <h1 style="color:#123">Hi!</h1>
    </body>
    </html>""" #"
    
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
    
    expect_html = """<html>
    <head>
    </head>
    <body>
    <a href="#" style="color:red;text-decoration:none">Special!</a>
    <a href="#" style="{color:red; border:1px solid green} :hover{text-decoration:none; border:1px solid green} :visited{border:1px solid green}">Page</a>
    <p style="::first-letter{float: left; font-size: 300%}">Paragraph</p>
    </body>
    </html>""" #"
    
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
    #assert 0


def test_css_with_pseudoclasses_excluded():
    "Skip things like `a:hover{}` and keep them in the style block"
    if not etree:
        # can't test it
        return
    
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
    </html>""" #"
    
    p = Premailer(html, exclude_pseudoclasses=True)
    result_html = p.transform()
    
    whitespace_between_tags = re.compile('>\s*<',)
    
    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()
    
    expect_html = re.sub('}\s+', '}', expect_html)
    result_html = result_html.replace('}\n','}')
    
    print ""
    print "EXPECT"
    print expect_html
    print "--"
    print "RESULT"
    print result_html
    
    assert expect_html == result_html, result_html


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
    </html>""" #"
    
    p = Premailer(html, exclude_pseudoclasses=True)
    result_html = p.transform()
    
    whitespace_between_tags = re.compile('>\s*<',)
    
    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()
    
    expect_html = re.sub('}\s+', '}', expect_html)
    result_html = result_html.replace('}\n','}')
    
    print ""
    print "EXPECT"
    print expect_html
    print "--"
    print "RESULT"
    print result_html
    
    assert expect_html == result_html, result_html


def test_apple_newsletter_example():
    # stupidity test
    import os
    html_file = os.path.join(os.path.dirname(__file__),
                             'test-apple-newsletter.html')
    html = open(html_file).read()
    
    p = Premailer(html, exclude_pseudoclasses=False,
                  keep_style_tags=True)
    result_html = p.transform()
    assert '<html>' in result_html
    assert """<style media="only screen and (max-device-width: 480px)" type="text/css">
* {line-height: normal !important; -webkit-text-size-adjust: 125%}
</style>""" in result_html
    _p = result_html.find('Add this to your calendar')
    assert '''style="{color:#5b7ab3; font-size:11px; font-family:Lucida Grande, Arial, Helvetica, Geneva, Verdana, sans-serif} :link{color:#5b7ab3; text-decoration:none} :visited{color:#5b7ab3; text-decoration:none} :hover{color:#5b7ab3; text-decoration:underline} :active{color:#5b7ab3; text-decoration:none}">Add this to your calendar''' in result_html
                      
    assert 1
    
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
