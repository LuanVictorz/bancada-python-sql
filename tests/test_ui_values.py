import unittest

try:
    from app.ui import format_money, parse_integer, parse_money
    HAS_TK = True
except ImportError:
    HAS_TK = False


@unittest.skipUnless(HAS_TK, "Distribuição Python sem Tkinter")
class FormValueTests(unittest.TestCase):
    def test_money_input_preserves_cents_without_float_rounding(self):
        for text, cents in [("0,10", 10), ("1.234,56", 123456), ("125.50", 12550),
                            ("R$ 89,9", 8990), ("0", 0), ("1.000", 100000)]:
            with self.subTest(text=text):
                self.assertEqual(parse_money(text), cents)

    def test_invalid_money_is_rejected(self):
        for text in ["", "-1", "NaN", "inf", "1e5", "1,234", "1.2.3", "R$", "1,00 reais"]:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    parse_money(text)

    def test_integer_input_rejects_fractional_and_negative_quantities(self):
        self.assertEqual(parse_integer(" 12 ", "Quantidade", 1), 12)
        for text in ["1.5", "-1", "0", "abc", ""]:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    parse_integer(text, "Quantidade", 1)

    def test_display_formats_large_and_small_amounts(self):
        self.assertEqual(format_money(1), "R$ 0,01")
        self.assertEqual(format_money(123456789), "R$ 1.234.567,89")
        self.assertEqual(format_money(-123), "R$ -1,23")
