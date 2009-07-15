# http://www.peterbe.com/plog/premailer.py
import re, os
from collections import defaultdict
from cStringIO import StringIO
import lxml.html
from lxml.cssselect import CSSSelector
from lxml import etree

__version__ = '1.3'

__all__ = ['PremailerError','Premailer','transform']

class PremailerError(Exception):
    pass

def _merge_styles(old, new):
    """
    if ::
      old = 'font-size:1px; color: red'
    and ::
      new = 'font-size:2px; font-weight: bold'
    then ::
      return 'color: red; font-size:2px; font-weight: bold'
      
    In other words, the new style bits replace the old ones
    """
    news = {}
    for k, v in [x.strip().split(':') for x in new.split(';') if x.strip()]:
        news[k.strip()] = v.strip()

    olds = {}
    for k, v in [x.strip().split(':') for x in old.split(';') if x.strip()]:
        olds[k.strip()] = v.strip()
        
    merged = news
    for k, v in olds.items():
        if k not in merged:
            merged[k] = v
        
    return '; '.join(['%s:%s' % (k, v) for (k, v) in merged.items()])


_css_comments = re.compile(r'/\*.*?\*/', re.MULTILINE|re.DOTALL)
_regex = re.compile('((.*?){(.*?)})', re.DOTALL|re.M)
_semicolon_regex = re.compile(';(\s+)')
_colon_regex = re.compile(':(\s+)')


class Premailer(object):
    
    def __init__(self, html, base_url=None, encoding='utf8'):
        self.html = html
        self.base_url = base_url
        self.encoding = encoding
        
    def _parse_style_rules(self, css_body):
        rules = []        
        css_body = _css_comments.sub('', css_body)
        for each in _regex.findall(css_body.strip()):
            __, selectors, bulk = each
            
            bulk = _semicolon_regex.sub(';', bulk.strip())
            bulk = _colon_regex.sub(':', bulk.strip())
            if bulk.endswith(';'):
                bulk = bulk[:-1]
            for selector in [x.strip() for x in selectors.split(',') if x.strip()]:
                rules.append((selector, bulk))

        return rules
        
    def transform(self, pretty_print=True):
        """change the self.html and return it with CSS turned into style
        attributes.
        """
        if etree is None:
            return self.html
        
        parser = etree.HTMLParser()
        tree = etree.parse(StringIO(self.html.strip().encode(self.encoding)), parser)
        page = tree.getroot()
        
        if page is None:
            print repr(self.html)
            raise PremailerError("Could not parse the html")
        assert page is not None
        
        ##
        ## style selectors
        ##
        
        rules = []
        
        for style in CSSSelector('style')(page):
            css_body = etree.tostring(style)
            css_body = css_body.split('>')[1].split('</')[0]
            rules.extend(self._parse_style_rules(css_body))
            parent_of_style = style.getparent()
            parent_of_style.remove(style)
            
        for selector, style in rules:
            sel = CSSSelector(selector)
            for item in sel(page):
                old_style = item.attrib.get('style','')
                new_style = _merge_styles(old_style, style)
                item.attrib['style'] = new_style
                
        # now we can delete all 'class' attributes
        for item in page.xpath('//@class'):
            parent = item.getparent()
            del parent.attrib['class']
            
                    
        ##
        ## URLs
        ##
        
        if self.base_url:
            
            def make_full_url(rel_url):
                if rel_url.startswith('/'):
                    if self.base_url.endswith('/'):
                        return self.base_url + rel_url[1:]
                    else:
                        return self.base_url + rel_url
                else:
                    # e.g. rel_url = "page.html"
                    if self.base_url.endswith('/'):
                        return self.base_url + rel_url
                    else:
                        return self.base_url + '/' + rel_url
                    
            for attr in ('href', 'src'):
                for item in page.xpath("//@%s" % attr):
                    parent = item.getparent()
                    if '://' not in parent.attrib[attr]:
                        parent.attrib[attr] = make_full_url(parent.attrib[attr])
                        
        
        return etree.tostring(page, pretty_print=pretty_print)
            
                    
def transform(html, base_url=None):
    return PremailerError(html, base_url=base_url).transform()
        
        
if __name__=='__main__':
    
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
    p = Premailer(html)
    print p.transform()
    
    