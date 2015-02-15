from __future__ import absolute_import, unicode_literals, print_function
try:
    from collections import OrderedDict
except ImportError:  # pragma: no cover
    # some old python 2.6 thing then, eh?
    from ordereddict import OrderedDict
import sys
import threading
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
import warnings

import cssutils
from lxml import etree
from lxml.cssselect import CSSSelector


__all__ = ['PremailerError', 'Premailer', 'transform']


class PremailerError(Exception):
    pass


class ExternalNotFoundError(ValueError):
    pass


grouping_regex = re.compile('([:\-\w]*){([^}]+)}')


def merge_styles(old, new, styles_cache, class_=''):
    """
    if ::
      old = 'font-size:1px; color: red'
    and ::
      new = 'font-size:2px; font-weight: bold'
    then ::
      return 'color: red; font-size:2px; font-weight: bold'

    In other words, the new style bits replace the old ones.

    The @class_ parameter can be something like ':hover' and if that
    is there, you split up the style with '{...} :hover{...}'
    Note: old could be something like '{...} ::first-letter{...}'

    """

    def csstext_to_pairs(csstext):
        try:
            (parsed, variable_value_cache) = styles_cache[csstext]
        except KeyError:
            parsed = cssutils.css.CSSVariablesDeclaration(csstext)
            variable_value_cache = {}
            styles_cache[csstext] = (parsed, variable_value_cache)

        for key in sorted(parsed):
            try:
                variable_value = variable_value_cache[key]
            except KeyError:
                variable_value = parsed.getVariableValue(key)
                variable_value_cache[key] = variable_value

            yield (key, variable_value)

    new_keys = set()
    news = []

    # The code below is wrapped in a critical section implemented via ``RLock``-class lock.
    # The lock is required to avoid ``cssutils`` concurrency issues documented in issue #65
    with merge_styles._lock:
        for k, v in csstext_to_pairs(new):
            news.append((k.strip(), v.strip()))
            new_keys.add(k.strip())

        groups = {}
        grouped_split = grouping_regex.findall(old)
        if grouped_split:
            for old_class, old_content in grouped_split:
                olds = []
                for k, v in csstext_to_pairs(old_content):
                    olds.append((k.strip(), v.strip()))
                groups[old_class] = olds
        else:
            olds = []
            for k, v in csstext_to_pairs(old):
                olds.append((k.strip(), v.strip()))
            groups[''] = olds

    # Perform the merge
    relevant_olds = groups.get(class_, {})
    merged = [style for style in relevant_olds if style[0] not in new_keys] + news
    groups[class_] = merged

    if len(groups) == 1:
        return '; '.join('%s:%s' % (k, v) for
                          (k, v) in sorted(list(groups.values())[0]))
    else:
        all = []
        sorted_groups = sorted(list(groups.items()),
                               key=lambda a: a[0].count(':'))
        for class_, mergeable in sorted_groups:
            all.append('%s{%s}' % (class_,
                                   '; '.join('%s:%s' % (k, v)
                                              for (k, v)
                                              in mergeable)))
        return ' '.join(x for x in all if x != '{}')

# The lock is used in merge_styles function to work around threading concurrency bug of cssutils library.
# The bug is documented in issue #65. The bug's reproduction test in test_premailer.test_multithreading.
merge_styles._lock = threading.RLock()


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
                 exclude_pseudoclasses=True,
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
        self.exclude_pseudoclasses = exclude_pseudoclasses
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
        """ Returns a list of rules to apply to this doc and a list of rules that won't be used
            because e.g. they are pseudoclasses. Rules look like: (specificity, selector, bulk)
            for example: ((0, 1, 0, 0, 0), u'.makeblue', u'color:blue'). The bulk of the rule
            should not end in a semicolon.
        """

        def join_css_properties(properties):
            """ Accepts a list of cssutils Property objects and returns a semicolon delimitted
                string like 'color: red; font-size: 12px'
            """
            return ';'.join(
                u'{0}:{1}'.format(prop.name, prop.value)
                for prop in properties
            )

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

            # normal means it doesn't have "!important"
            normal_properties = [
                prop for prop in rule.style.getProperties()
                if prop.priority != 'important'
            ]
            important_properties = [
                prop for prop in rule.style.getProperties()
                if prop.priority == 'important'
            ]

            # Create three strings that we can use to add to the `rules` list later
            # as ready blocks of css.
            bulk_normal = join_css_properties(normal_properties)
            bulk_important = join_css_properties(important_properties)
            bulk_all = join_css_properties(normal_properties + important_properties)

            selectors = (
                x.strip()
                for x in rule.selectorText.split(',')
                if x.strip() and not x.strip().startswith('@')
            )
            for selector in selectors:
                if (':' in selector and self.exclude_pseudoclasses and
                    ':' + selector.split(':', 1)[1]
                        not in FILTER_PSEUDOSELECTORS):
                    # a pseudoclass
                    leftover.append((selector, bulk_all))
                    continue
                elif '*' in selector and not self.include_star_selectors:
                    continue

                # Crudely calculate specificity
                id_count = selector.count('#')
                class_count = selector.count('.')
                element_count = len(_element_selector_regex.findall(selector))

                # Within one rule individual properties have different priority depending on !important.
                # So we split each rule into two: one that includes all the !important declarations and
                # another that doesn't.
                for is_important, bulk in ((1, bulk_important), (0, bulk_normal)):
                    if not bulk:
                        # don't bother adding empty css rules
                        continue
                    specificity = (
                        is_important,
                        id_count,
                        class_count,
                        element_count,
                        ruleset_index,
                        len(rules) # this is the rule's index number
                    )
                    rules.append((specificity, selector, bulk))

        return rules, leftover

    def transform(self, pretty_print=True, **kwargs):
        """change the self.html and return it with CSS turned into style
        attributes.
        """
        if hasattr(self.html, "getroottree"):
            # skip the next bit
            root = self.html.getroottree()
            page = root
            tree = root
        else:
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

            data_attribute = element.attrib.get('data-premailer')
            if data_attribute == 'ignore':
                del element.attrib['data-premailer']
                continue
            elif data_attribute:
                warnings.warn(
                    'Unrecognized data-premailer attribute (%r)' % (
                        data_attribute,
                    )
                )

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
        styles_cache = {}
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
                    new_style = merge_styles(old_style, style, styles_cache, class_)
                    first_time.append(item)
                    first_time_styles.append((item, old_style))
                else:
                    new_style = merge_styles(old_style, style, styles_cache, class_)
                item.attrib['style'] = new_style
                self._style_to_basic_html_attributes(item, new_style,
                                                     force=True)

        # Re-apply initial inline styles.
        for item, inline_style in first_time_styles:
            old_style = item.attrib.get('style', '')
            if not inline_style:
                continue
            new_style = merge_styles(old_style, inline_style, styles_cache, class_)
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

        if hasattr(self.html, "getroottree"):
            return root
        else:
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
