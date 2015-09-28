from __future__ import absolute_import, unicode_literals
import unittest
from premailer.merge_style import csstext_to_pairs, merge_styles


class TestMergeStyle(unittest.TestCase):
    # test what is not cover in test_premailer
    # should move them here
    # smaller files are easier to work with
    def test_csstext_to_pairs(self):
        csstext = 'font-size:1px'
        parsed_csstext = csstext_to_pairs(csstext)
        self.assertEqual(('font-size', '1px'), parsed_csstext[0])

    def test_inline_invalid_syntax(self):
        # Invalid syntax does not raise
        inline = '{color:pink} :hover{color:purple} :active{color:red}'
        merge_styles(inline, [], [])

    def test_important_rule(self):
        # No exception after #133
        csstext = 'font-size:1px !important'
        parsed_csstext = csstext_to_pairs(csstext)
        self.assertEqual(('font-size', '1px'), parsed_csstext[0])
