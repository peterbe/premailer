import unittest
from premailer.merge_style import csstext_to_pairs, merge_styles


class TestMergeStyle(unittest.TestCase):
    # test what is not cover in test_premailer
    # should move them here
    # smaller files are easier to work with
    def test_csstext_to_pairs(self):
        csstext = "font-size:1px"
        parsed_csstext = csstext_to_pairs(csstext)
        self.assertEqual(("font-size", "1px"), parsed_csstext[0])

    def test_inline_invalid_syntax(self):
        # Invalid syntax does not raise
        inline = "{color:pink} :hover{color:purple} :active{color:red}"
        merge_styles(inline, [], [])

    def test_constituent_styles(self):
        # "constituent": `margin-bottom` is a constituent style of `margin`
        new_styles = [[("margin", "5px"), ("margin-bottom", "10px")]]
        classes = [""]
        inline_style = "margin: 0"
        csstext = merge_styles(inline_style, new_styles, classes)
        self.assertEqual(
            # ideally premailer could eliminate margin-bottom altogether
            [("margin-bottom", "10px"), ("margin", "0")], csstext_to_pairs(csstext)
        )
