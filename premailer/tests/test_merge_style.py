from __future__ import absolute_import, unicode_literals
import unittest
import xml
from nose.tools import raises
from premailer.merge_style import csstext_to_pairs, merge_styles


class TestMergeStyle(unittest.TestCase):
    # test what is not cover in test_premailer
    # should move them here
    # smaller files are easier to work with
    def test_csstext_to_pairs(self):
        csstext = 'font-size:1px'
        parsed_csstext = csstext_to_pairs(csstext)
        self.assertEqual(('font-size', '1px'), parsed_csstext[0])
        
    @raises(xml.dom.SyntaxErr)
    def test_inline_invalid_syntax(self):
        # inline shouldn't have those as I understand
        # but keep the behaviour
        inline = '{color:pink} :hover{color:purple} :active{color:red}'
        merge_styles(inline, [], [])