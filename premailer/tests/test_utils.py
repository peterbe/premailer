import unittest

from premailer.premailer import capitalize_float_margin


class UtilsTestCase(unittest.TestCase):
    def testcapitalize_float_margin(self):
        self.assertEqual(capitalize_float_margin("margin:1em"), "Margin:1em")
        self.assertEqual(capitalize_float_margin("margin-left:1em"), "Margin-left:1em")
        self.assertEqual(capitalize_float_margin("float:right;"), "Float:right;")
        self.assertEqual(
            capitalize_float_margin("float:right;color:red;margin:0"),
            "Float:right;color:red;Margin:0",
        )
