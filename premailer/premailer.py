from __future__ import absolute_import, unicode_literals, print_function
try:
    from collections import OrderedDict
except ImportError:  # pragma: no cover
    # some old python 2.6 thing then, eh?
    from ordereddict import OrderedDict
import sys
if sys.version_info >= (3, ):  # pragma: no cover
    # As in, Python 3
    from io import StringIO
    from urllib.request import urlopen
    from urllib.parse import urljoin
    STR_TYPE = str
else:  # Python 2
    try:
        from cStringIO import StringIO
    except ImportError:  # pragma: no cover
        from StringIO import StringIO  # lint:ok
    from urllib2 import urlopen
    from urlparse import urljoin
    STR_TYPE = basestring
from io import BytesIO  # Yes, there is an io module in Python 2
import cgi
import codecs
import gzip
import operator
import os
import re
import cssutils
from lxml import etree
from lxml.cssselect import CSSSelector


__all__ = ['PremailerError', 'Premailer', 'transform']


class PremailerError(Exception):
    pass


class ExternalNotFoundError(ValueError):
    pass


grouping_regex = re.compile('([:\-\w]*){([^}]+)}')


def _css_string_to_dict(css):
    """Given a string containing CSS, creates a dictionary out of it, where the keys are CSS
    properties and the values are their corresponding values
    This method assumes that CSS key-value pairs are separated by a semicolon. If this is not true,
    it can return unexpected results or even break
    Arguments:
        - str css: the css text
    Returns:
        a dictionary as described above
    """
    buff = ''
    css_properties = []
    for item in css.split(';'):
        # if we have any buffer, append the current item to the buffer
        if buff:
            item = buff + ';' + item
            buff = ''

        # if this breaks any parenthesis, brakets, buffer it and continue
        if _unbalanced(item):
            buff = item
            continue

        # we are good to add the property
        if item.strip():
            css_properties.append(item.strip())

    # split every property into key, value and store them in a dict
    d = {}
    for css_property in css_properties:
        chunks = css_property.split(':', 1)
        d[chunks[0].strip()] = chunks[1].strip()
    return d


def _unbalanced(text):
    """
    Checks if there is an unbalanced parenthesis or bracket in the provided text. Assumes that
    the text is processed left to right
    Arguments:
        - str text: the text to check
    Returns:
        true if its unbalanced, false otherwise
    """
    if text.count('(') and text.count('(') != text.count(')'):
        return True
    if text.count('{') and text.count('}') != text.count('}'):
        return True
    return False


def merge_styles(old, new, class_=''):
    """
    if ::
      old = 'font-size:1px; color: red'
    and ::
      new = 'font-size:2px; font-weight: bold'
    then ::
      return 'color: red; font-size:2px; font-weight: bold'

    In other words, the new style bits replace the old ones.
    """
    old_style_dict = _css_string_to_dict(old)
    style_dict = _css_string_to_dict(new)
    old_style_dict.update(style_dict)
    return '; '.join(['%s:%s' % (k, v) for k, v in sorted(old_style_dict.items())])


def make_important(bulk):
    """makes every property in a string !important.
    """
    return ';'.join('%s !important' % p if not p.endswith('!important') else p
                    for p in bulk.split(';'))


def get_or_create_head(root):
    """Ensures that `root` contains a <head> element and returns it.
    """
    head = CSSSelector('head')(root)
    if not head:
        head = etree.Element('head')
        body = CSSSelector('body')(root)[0]
        body.getparent().insert(0, head)
        return head
    else:
        return head[0]


_element_selector_regex = re.compile(r'(^|\s)\w')
_cdata_regex = re.compile(r'\<\!\[CDATA\[(.*?)\]\]\>', re.DOTALL)
_importants = re.compile('\s*!important')
# These selectors don't apply to all elements. Rather, they specify
# which elements to apply to.
FILTER_PSEUDOSELECTORS = [':last-child', ':first-child', 'nth-child']


class Premailer(object):

    def __init__(self, html, base_url=None,
                 preserve_internal_links=False,
                 preserve_inline_attachments=True,
                 keep_style_tags=False,
                 include_star_selectors=False,
                 remove_classes=True,
                 strip_important=True,
                 external_styles=None,
                 css_text=None,
                 method="html",
                 base_path=None,
                 disable_basic_attributes=None,
                 disable_validation=False):
        self.html = html
        self.base_url = base_url
        self.preserve_internal_links = preserve_internal_links
        self.preserve_inline_attachments = preserve_inline_attachments
        # whether to delete the <style> tag once it's been processed
        # this will always preserve the original css
        self.keep_style_tags = keep_style_tags
        self.remove_classes = remove_classes
        # whether to process or ignore selectors like '* { foo:bar; }'
        self.include_star_selectors = include_star_selectors
        if isinstance(external_styles, STR_TYPE):
            external_styles = [external_styles]
        self.external_styles = external_styles
        if isinstance(css_text, STR_TYPE):
            css_text = [css_text]
        self.css_text = css_text
        self.strip_important = strip_important
        self.method = method
        self.base_path = base_path
        if disable_basic_attributes is None:
            disable_basic_attributes = []
        self.disable_basic_attributes = disable_basic_attributes
        self.disable_validation = disable_validation

    def _parse_style_rules(self, css_body, ruleset_index):
        leftover = []
        rules = []
        rule_index = 0
        # empty string
        if not css_body:
            return rules, leftover
        sheet = cssutils.parseString(css_body, validate=not self.disable_validation)
        for rule in sheet:
            # handle media rule
            if rule.type == rule.MEDIA_RULE:
                leftover.append(rule)
                continue
            # only proceed for things we recognize
            if rule.type != rule.STYLE_RULE:
                continue
            bulk = ';'.join(
                u'{0}:{1}'.format(key, rule.style[key])
                for key in rule.style.keys()
            )
            selectors = (
                x.strip()
                for x in rule.selectorText.split(',')
                if x.strip() and not x.strip().startswith('@')
            )
            for selector in selectors:
                if (':' in selector and
                    ':' + selector.split(':', 1)[1]
                        not in FILTER_PSEUDOSELECTORS):
                    # a pseudoclass
                    leftover.append((selector, bulk))
                    continue
                elif '*' in selector and not self.include_star_selectors:
                    continue

                # Crudely calculate specificity
                id_count = selector.count('#')
                class_count = selector.count('.')
                element_count = len(_element_selector_regex.findall(selector))

                specificity = (id_count, class_count, element_count, ruleset_index, rule_index)

                rules.append((specificity, selector, bulk))
                rule_index += 1

        return rules, leftover

    def transform(self, pretty_print=True, **kwargs):
        """change the self.html and return it with CSS turned into style
        attributes.
        """
        if self.method == 'xml':
            parser = etree.XMLParser(ns_clean=False, resolve_entities=False)
        else:
            parser = etree.HTMLParser()
        stripped = self.html.strip()
        tree = etree.fromstring(stripped, parser).getroottree()
        page = tree.getroot()
        # lxml inserts a doctype if none exists, so only include it in
        # the root if it was in the original html.
        root = tree if stripped.startswith(tree.docinfo.doctype) else page

        assert page is not None

        head = get_or_create_head(tree)

        ##
        ## style selectors
        ##

        rules = []
        index = 0

        for element in CSSSelector('style,link[rel~=stylesheet]')(page):
            # If we have a media attribute whose value is anything other than
            # 'screen', ignore the ruleset.
            media = element.attrib.get('media')
            if media and media != 'screen':
                continue

            is_style = element.tag == 'style'
            if is_style:
                css_body = element.text
            else:
                href = element.attrib.get('href')
                css_body = self._load_external(href)

            these_rules, these_leftover = self._parse_style_rules(css_body, index)
            index += 1
            rules.extend(these_rules)

            parent_of_element = element.getparent()
            if these_leftover or self.keep_style_tags:
                if is_style:
                    style = element
                else:
                    style = etree.Element('style')
                    style.attrib['type'] = 'text/css'
                if self.keep_style_tags:
                    style.text = css_body
                else:
                    style.text = self._css_rules_to_string(these_leftover)
                if self.method == 'xml':
                    style.text = etree.CDATA(style.text)

                if not is_style:
                    element.addprevious(style)
                    parent_of_element.remove(element)

            elif not self.keep_style_tags or not is_style:
                parent_of_element.remove(element)

        # external style files
        if self.external_styles:
            for stylefile in self.external_styles:
                css_body = self._load_external(stylefile)
                self._process_css_text(css_body, index, rules, head)
                index += 1

        # css text
        if self.css_text:
            for css_body in self.css_text:
                self._process_css_text(css_body, index, rules, head)
                index += 1

        # rules is a tuple of (specificity, selector, styles), where specificity is a tuple
        # ordered such that more specific rules sort larger.
        rules.sort(key=operator.itemgetter(0))

        first_time = []
        first_time_styles = []
        for __, selector, style in rules:
            new_selector = selector
            class_ = ''
            if ':' in selector:
                new_selector, class_ = re.split(':', selector, 1)
                class_ = ':%s' % class_
            # Keep filter-type selectors untouched.
            if class_ in FILTER_PSEUDOSELECTORS:
                class_ = ''
            else:
                selector = new_selector

            sel = CSSSelector(selector)
            for item in sel(page):
                old_style = item.attrib.get('style', '')
                if not item in first_time:
                    new_style = merge_styles(old_style, style, class_)
                    first_time.append(item)
                    first_time_styles.append((item, old_style))
                else:
                    new_style = merge_styles(old_style, style, class_)
                item.attrib['style'] = new_style
                self._style_to_basic_html_attributes(item, new_style,
                                                     force=True)

        # Re-apply initial inline styles.
        for item, inline_style in first_time_styles:
            old_style = item.attrib.get('style', '')
            if not inline_style:
                continue
            new_style = merge_styles(old_style, inline_style, class_)
            item.attrib['style'] = new_style
            self._style_to_basic_html_attributes(item, new_style, force=True)

        if self.remove_classes:
            # now we can delete all 'class' attributes
            for item in page.xpath('//@class'):
                parent = item.getparent()
                del parent.attrib['class']

        ##
        ## URLs
        ##
        if self.base_url:
            for attr in ('href', 'src'):
                for item in page.xpath("//@%s" % attr):
                    parent = item.getparent()
                    if attr == 'href' and self.preserve_internal_links and parent.attrib[attr].startswith('#'):
                        continue
                    if attr == 'src' and self.preserve_inline_attachments and parent.attrib[attr].startswith('cid:'):
                        continue
                    if not self.base_url.endswith('/'):
                        self.base_url += '/'
                    parent.attrib[attr] = urljoin(self.base_url, parent.attrib[attr].lstrip('/'))

        kwargs.setdefault('method', self.method)
        kwargs.setdefault('pretty_print', pretty_print)
        kwargs.setdefault('encoding', 'utf-8')  # As Ken Thompson intended
        out = etree.tostring(root, **kwargs).decode(kwargs['encoding'])
        if self.method == 'xml':
            out = _cdata_regex.sub(lambda m: '/*<![CDATA[*/%s/*]]>*/' % m.group(1), out)
        if self.strip_important:
            out = _importants.sub('', out)
        return out

    def _load_external_url(self, url):
        r = urlopen(url)
        _, params = cgi.parse_header(r.headers.get('Content-Type', ''))
        encoding = params.get('charset', 'utf-8')
        if 'gzip' in r.info().get('Content-Encoding', ''):
            buf = BytesIO(r.read())
            f = gzip.GzipFile(fileobj=buf)
            out = f.read().decode(encoding)
        else:
            out = r.read().decode(encoding)
        return out

    def _load_external(self, url):
        """loads an external stylesheet from a remote url or local path
        """
        if url.startswith('//'):
            # then we have to rely on the base_url
            if self.base_url and 'https://' in self.base_url:
                url = 'https:' + url
            else:
                url = 'http:' + url

        if url.startswith('http://') or url.startswith('https://'):
            css_body = self._load_external_url(url)
        else:
            stylefile = url
            if not os.path.isabs(stylefile):
                stylefile = os.path.abspath(
                    os.path.join(self.base_path or '', stylefile)
                )
            if os.path.exists(stylefile):
                with codecs.open(stylefile, encoding='utf-8') as f:
                    css_body = f.read()
            elif self.base_url:
                url = urljoin(self.base_url, url)
                return self._load_external(url)
            else:
                raise ExternalNotFoundError(stylefile)

        return css_body

    def _style_to_basic_html_attributes(self, element, style_content,
                                        force=False):
        """given an element and styles like
        'background-color:red; font-family:Arial' turn some of that into HTML
        attributes. like 'bgcolor', etc.

        Note, the style_content can contain pseudoclasses like:
        '{color:red; border:1px solid green} :visited{border:1px solid green}'
        """
        if style_content.count('}') and style_content.count('{') == style_content.count('{'):
            style_content = style_content.split('}')[0][1:]

        attributes = OrderedDict()
        for key, value in [x.split(':') for x in style_content.split(';')
                           if len(x.split(':')) == 2]:
            key = key.strip()

            if key == 'text-align':
                attributes['align'] = value.strip()
            elif key == 'vertical-align':
                attributes['valign'] = value.strip()
            elif key == 'background-color':
                attributes['bgcolor'] = value.strip()
            elif key == 'width' or key == 'height':
                value = value.strip()
                if value.endswith('px'):
                    value = value[:-2]
                attributes[key] = value

        for key, value in attributes.items():
            if key in element.attrib and not force or key in self.disable_basic_attributes:
                # already set, don't dare to overwrite
                continue
            element.attrib[key] = value

    def _css_rules_to_string(self, rules):
        """given a list of css rules returns a css string
        """
        lines = []
        for item in rules:
            if isinstance(item, tuple):
                k, v = item
                lines.append('%s {%s}' % (k, make_important(v)))
            # media rule
            else:
                for rule in item.cssRules:
                    if isinstance(rule, cssutils.css.csscomment.CSSComment):
                        continue
                    for key in rule.style.keys():
                        rule.style[key] = (
                            rule.style.getPropertyValue(key, False),
                            '!important'
                        )
                lines.append(item.cssText)
        return '\n'.join(lines)

    def _process_css_text(self, css_text, index, rules, head):
        """processes the given css_text by adding rules that can be in-lined to the given rules list and
        adding any that cannot be in-lined to the given `<head>` element
        """
        these_rules, these_leftover = self._parse_style_rules(css_text, index)
        rules.extend(these_rules)
        if these_leftover or self.keep_style_tags:
            style = etree.Element('style')
            style.attrib['type'] = 'text/css'
            if self.keep_style_tags:
                style.text = css_text
            else:
                style.text = self._css_rules_to_string(these_leftover)
            head.append(style)


def transform(html, base_url=None):
    return Premailer(html, base_url=base_url).transform()


if __name__ == '__main__':  # pragma: no cover
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
    print (p.transform())
