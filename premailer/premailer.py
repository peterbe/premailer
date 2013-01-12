import codecs
from lxml import etree
from lxml.cssselect import CSSSelector
import cssselect
import os
import re
import urllib
import urlparse
import sys


__all__ = ['PremailerError', 'Premailer', 'transform']


class PremailerError(Exception):
    pass


def _parse_styles(style_text, specificity):
    """Parse a style string into a dictionary {style_key: (style_value, specificity)}."""

    return {k.strip(): (v.strip(), specificity)
            for k, v in [x.strip().split(':', 1)
                         for x in style_text.split(';') if x.strip()]}


def _inline_specificity():
    """Specificity for inlined styles.
    Inlined styles take precedence over selector styles.
    """

    return (sys.maxint, sys.maxint, sys.maxint)


grouping_regex = re.compile('([:\-\w]*){([^}]+)}')


def _parse_style_groups(style_text, specificity):
    """Parse an html element style string into style groups.

    given::
        style_text = '{color:red; font-size:1px} :hover{font-weight:bold}'
        specificity = (0, 1, 1)

    return::
        {
            '' : { 'color': ('red', (0, 1, 1)), 'font-size': ('1px', (0, 1, 1)) }
            'hover' : { 'font-weight': ('bold', (0, 1, 1)) }
        }
    """

    groups = {}

    grouped_split = grouping_regex.findall(style_text)
    if grouped_split:
        for class_, content in grouped_split:
            groups[class_] = _parse_styles(content, specificity)
    else:
        groups[''] = _parse_styles(style_text, specificity)

    return groups


def _merge_styles(item_styles, item, style, specificity, class_=''):
    """Merge selector styles with current item styles.

    :param item_styles: The current computed item styles for the html document
    :param item: An html element who's style we want to merge with the given selector style
    :param style: The selector style to apply
    :param specificity: The selector specificity
    :param class_: An optional selector class
    """
    new_styles = _parse_styles(style, specificity)

    existing_styles = item_styles.get(item)
    if not existing_styles:
        # initialize styles for this item using the inlined style
        existing_styles = _parse_style_groups(item.attrib.get('style', ''), _inline_specificity())
        item_styles[item] = existing_styles

    style_group = existing_styles.get(class_)
    if not style_group:
        style_group = {}
        existing_styles[class_] = style_group

    # Perform the merge
    for style_key, value_and_specificity in new_styles.iteritems():
        old_style = style_group.get(style_key)
        if not old_style:
            style_group[style_key] = value_and_specificity
        else:
            # override if the new style is more specific
            old_value, old_specificity = old_style
            if value_and_specificity[1] > old_specificity:
                style_group[style_key] = value_and_specificity


def _apply_styles(item_styles):
    """Apply the calculated styles in the item_styles dictionary to the html document."""
    
    for item, style_groups in item_styles.iteritems():
        if len(style_groups) == 1:
            new_style = '; '.join(['%s:%s' % (k, v[0]) for
                                  (k, v) in style_groups.values()[0].items()])
        else:
            all = []
            for class_, mergeable in sorted(style_groups.items(),
                                            lambda x, y: cmp(x[0].count(':'),
                                                             y[0].count(':'))):
                all.append('%s{%s}' % (class_,
                                       '; '.join(['%s:%s' % (k, v[0])
                                                  for (k, v) in mergeable.items()])))
            new_style = ' '.join([x for x in all if x != '{}'])

        item.attrib['style'] = new_style
        _style_to_basic_html_attributes(item, new_style, force=True)


_css_comments = re.compile(r'/\*.*?\*/', re.MULTILINE | re.DOTALL)
_regex = re.compile('((.*?){(.*?)})', re.DOTALL | re.M)
_semicolon_regex = re.compile(';(\s+)')
_colon_regex = re.compile(':(\s+)')
_importants = re.compile('\s*!important')
_style_url_regex = re.compile('url\(\s*[\'"]?(?P<url>.*?)[\'"]?\s*\)')
# These selectors don't apply to all elements. Rather, they specify
# which elements to apply to.
FILTER_PSEUDOSELECTORS = [':last-child', ':first-child', 'nth-child']


class Premailer(object):

    def __init__(self, html, base_url=None,
                 preserve_internal_links=False,
                 exclude_pseudoclasses=False,
                 keep_style_tags=False,
                 include_star_selectors=False,
                 remove_classes=True,
                 strip_important=True,
                 external_styles=None,
                 url_transform=None):
        self.html = html
        self.base_url = base_url
        self.preserve_internal_links = preserve_internal_links
        self.exclude_pseudoclasses = exclude_pseudoclasses
        # whether to delete the <style> tag once it's been processed
        self.keep_style_tags = keep_style_tags
        self.remove_classes = remove_classes
        # whether to process or ignore selectors like '* { foo:bar; }'
        self.include_star_selectors = include_star_selectors
        if isinstance(external_styles, basestring):
            external_styles = [external_styles]
        self.external_styles = external_styles
        self.strip_important = strip_important
        self.url_transform = url_transform

    def _parse_style_rules(self, css_body):
        leftover = []
        rules = []
        css_body = _css_comments.sub('', css_body)
        for each in _regex.findall(css_body.strip()):
            __, selectors, bulk = each

            bulk = _semicolon_regex.sub(';', bulk.strip())
            bulk = _colon_regex.sub(':', bulk.strip())
            if bulk.endswith(';'):
                bulk = bulk[:-1]
            for selector in [x.strip() for
                             x in selectors.split(',') if x.strip() and
                             not x.strip().startswith('@')]:
                if (':' in selector and self.exclude_pseudoclasses and
                    ':' + selector.split(':', 1)[1]
                        not in FILTER_PSEUDOSELECTORS):
                    # a pseudoclass
                    leftover.append((selector, bulk))
                    continue
                elif selector == '*' and not self.include_star_selectors:
                    continue

                rules.append((selector, bulk))

        return rules, leftover

    def transform(self, pretty_print=True):
        """change the self.html and return it with CSS turned into style
        attributes.
        """
        if etree is None:
            return self.html

        parser = etree.HTMLParser()
        stripped = self.html.strip()
        tree = etree.fromstring(stripped, parser).getroottree()
        page = tree.getroot()
        # lxml inserts a doctype if none exists, so only include it in
        # the root if it was in the original html.
        root = tree if stripped.startswith(tree.docinfo.doctype) else page

        if page is None:
            print repr(self.html)
            raise PremailerError("Could not parse the html")
        assert page is not None

        ##
        ## style selectors
        ##

        rules = []

        for style in CSSSelector('style')(page):
            these_rules, these_leftover = self._parse_style_rules(style.text)
            rules.extend(these_rules)

            parent_of_style = style.getparent()
            if these_leftover:
                style.text = '\n'.join(['%s {%s}' % (k, v) for
                                        (k, v) in these_leftover])
            elif not self.keep_style_tags:
                parent_of_style.remove(style)

        if self.external_styles:
            for stylefile in self.external_styles:
                if stylefile.startswith('http://'):
                    css_body = urllib.urlopen(stylefile).read()
                elif os.path.exists(stylefile):
                    try:
                        f = codecs.open(stylefile)
                        css_body = f.read()
                    finally:
                        f.close()
                else:
                    raise ValueError(u"Could not find external style: %s" %
                                     stylefile)
                these_rules, these_leftover = self._parse_style_rules(css_body)
                rules.extend(these_rules)

        # calculated styles for html elements that are
        # affected by css selector styles.
        item_styles = {}

        for selector, style in rules:
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

            # get the selector specificity
            specificity = cssselect.parse(selector)[0].specificity()

            sel = CSSSelector(selector)
            for item in sel(page):
                _merge_styles(item_styles, item, style, specificity, class_)

        _apply_styles(item_styles)

        if self.remove_classes:
            # now we can delete all 'class' attributes
            for item in page.xpath('//@class'):
                parent = item.getparent()
                del parent.attrib['class']

        ##
        ## URLs
        ##
        if self.base_url or self.url_transform:
            for attr in ('href', 'src', 'style'):
                for item in page.xpath("//@%s" % attr):
                    parent = item.getparent()
                    if attr == 'href' and self.preserve_internal_links \
                            and parent.attrib[attr].startswith('#'):
                        continue
                    if attr == 'style':
                        parent.attrib[attr] = _style_url_regex.sub(
                            lambda match: "url(\'{url}\')".format(
                                url=self._process_url(match.group('url'))),
                            parent.attrib[attr])
                    else:
                        url = parent.attrib[attr]
                        parent.attrib[attr] = self._process_url(url)

        out = etree.tostring(root, method="html", pretty_print=pretty_print)
        if self.strip_important:
            out = _importants.sub('', out)
        return out

    def _process_url(self, url):
        """given a url apply the base_url and url_transform."""

        if self.url_transform:
            url = self.url_transform(url)
        if self.base_url:
            url = urlparse.urljoin(self.base_url, url)
        return url


def _style_to_basic_html_attributes(element, style_content, force=False):
    """given an element and styles like
    'background-color:red; font-family:Arial' turn some of that into HTML
    attributes. like 'bgcolor', etc.

    Note, the style_content can contain pseudoclasses like:
    '{color:red; border:1px solid green} :visited{border:1px solid green}'
    """
    if style_content.count('}') and style_content.count('{') == style_content.count('{'):
        style_content = style_content.split('}')[0][1:]

    attributes = {}
    for key, value in [x.split(':') for x in style_content.split(';')
                       if len(x.split(':')) == 2]:
        key = key.strip()

        if key == 'text-align':
            attributes['align'] = value.strip()
        elif key == 'background-color':
            attributes['bgcolor'] = value.strip()
        elif key == 'width' or key == 'height':
            value = value.strip()
            if value.endswith('px'):
                value = value[:-2]
            attributes[key] = value
        #else:
        #    print "key", repr(key)
        #    print 'value', repr(value)

    for key, value in attributes.items():
        if key in element.attrib and not force:
            # already set, don't dare to overwrite
            continue
        element.attrib[key] = value


def transform(html, base_url=None):
    return Premailer(html, base_url=base_url).transform()


if __name__ == '__main__':
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
