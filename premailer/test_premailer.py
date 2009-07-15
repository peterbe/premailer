import re
import nose.tools

from premailer import Premailer, etree, _merge_styles

    
def test_merge_styles():
    old = 'font-size:1px; color: red'
    new = 'font-size:2px; font-weight: bold'
    expect = 'color:red;', 'font-size:2px;', 'font-weight:bold'
    result = _merge_styles(old, new)
    for each in expect:
        assert each in result

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
    rules = func("""
    h1, h2 { color:red; }
    /* ignore
        this */
    strong { 
        text-decoration:none
        }
    ul li {  list-style: 2px; }
    """)
    
    # 'rules' is a list, turn it into a dict for 
    # easier testing
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
    </body>
    </html>"""
    
    p = Premailer(html, base_url='http://kungfupeople.com')
    result_html = p.transform()
    
    whitespace_between_tags = re.compile('>\s*<',)
    
    expect_html = whitespace_between_tags.sub('><', expect_html).strip()
    result_html = whitespace_between_tags.sub('><', result_html).strip()
    
    assert expect_html == result_html
    
    