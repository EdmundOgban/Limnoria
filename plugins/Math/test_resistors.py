import unittest
import resistors as r

class Testv2c(unittest.TestCase):

    def test_fourbands(self):
        self.assertEqual(r.value_to_colors("4"), "4Ω, 4-Band resistor: Yellow Black Gold")
        self.assertEqual(r.value_to_colors("4.2"), "4.2Ω, 4-Band resistor: Yellow Red Gold")
        self.assertEqual(r.value_to_colors("42"), "42Ω, 4-Band resistor: Yellow Red Black")
        self.assertEqual(r.value_to_colors("420.5"), "420Ω, 4-Band resistor: Yellow Red Brown")

    def test_fivebands(self):
        self.assertEqual(r.value_to_colors("4.25"), "4.25Ω, 5-Band resistor: Yellow Red Green Silver")
        self.assertEqual(r.value_to_colors("42.5"), "42.5Ω, 5-Band resistor: Yellow Red Green Gold")
        self.assertEqual(r.value_to_colors("425"), "425Ω, 5-Band resistor: Yellow Red Green Black")
        self.assertEqual(r.value_to_colors("4250"), "4.25kΩ, 5-Band resistor: Yellow Red Green Brown")

    def test_multiples(self):
        self.assertEqual(r.value_to_colors("420k"), "420kΩ, 4-Band resistor: Yellow Red Yellow")
        self.assertEqual(r.value_to_colors("420M"), "420MΩ, 4-Band resistor: Yellow Red Violet")
        self.assertEqual(r.value_to_colors("99G"), "99GΩ, 4-Band resistor: White White White")

    def test_parsing(self):
        suffixes = ["ohm", "ohms", " ohm", "  ohm", "   ohm"]
        for suffix in suffixes:
            self.assertEqual(r.value_to_colors("4{}".format(suffix)), r.value_to_colors("4"))

        suffixes = ["kohm", "kohms", "k ohm", " k ohm", " k ohms", "  k ohms", "  k  ohms"]
        for suffix in suffixes:
            self.assertEqual(r.value_to_colors("4{}".format(suffix)), r.value_to_colors("4000"))

    def test_idempotence(self):
        self.assertEqual(r.value_to_colors("4200"), r.value_to_colors("4.2k"))
        self.assertEqual(r.value_to_colors("4200000"), r.value_to_colors("4.2M"))
        self.assertEqual(r.value_to_colors("4200k"), r.value_to_colors("4.2M"))
        self.assertEqual(r.value_to_colors("4200000000"), r.value_to_colors("4.2G"))
        self.assertEqual(r.value_to_colors("4200M"), r.value_to_colors("4.2G"))

    def test_identity(self):
        self.assertEqual(r.value_to_colors("04"), r.value_to_colors("4.0"))
        self.assertEqual(r.value_to_colors("04.2"), r.value_to_colors("4.2"))
        self.assertEqual(r.value_to_colors("4,2"), r.value_to_colors("4.2"))
        self.assertEqual(r.value_to_colors("4.20"), r.value_to_colors("4.2"))
        self.assertEqual(r.value_to_colors("42.0"), r.value_to_colors("42"))

    def test_exceptions(self):
        invalid_str = "4.2.2"
        with self.assertRaises(ValueError, msg="Invalid input: '{}'".format(invalid_str)):
            r.value_to_colors(invalid_str)

        invalid_str = "4foo2bar"
        with self.assertRaises(ValueError, msg="Invalid input: '{}'".format(invalid_str)):
            r.value_to_colors(invalid_str)

        with self.assertRaises(ValueError, msg="Out of range"):
            r.value_to_colors("100G")

class Testc2v(unittest.TestCase):

    def test_fourbands(self):
        self.assertEqual(r.colors_to_value("Yellow", "Black", "Gold"), "Yellow Black Gold, 4-Band resistor: 4Ω")
        self.assertEqual(r.colors_to_value("Yellow", "Red", "Gold"), "Yellow Red Gold, 4-Band resistor: 4.2Ω")
        self.assertEqual(r.colors_to_value("Yellow", "Red", "Black"), "Yellow Red Black, 4-Band resistor: 42Ω")
        self.assertEqual(r.colors_to_value("Yellow", "Red", "Brown"), "Yellow Red Brown, 4-Band resistor: 420Ω")

    def test_fivebands(self):
        self.assertEqual(r.colors_to_value("Yellow", "Red", "Green", "Silver"), "Yellow Red Green Silver, 5-Band resistor: 4.25Ω")
        self.assertEqual(r.colors_to_value("Yellow", "Red", "Green", "Gold"), "Yellow Red Green Gold, 5-Band resistor: 42.5Ω")
        self.assertEqual(r.colors_to_value("Yellow", "Red", "Green", "Black"), "Yellow Red Green Black, 5-Band resistor: 425Ω")
        self.assertEqual(r.colors_to_value("Yellow", "Red", "Green", "Brown"), "Yellow Red Green Brown, 5-Band resistor: 4.25kΩ")

    def test_multiples(self):
        self.assertEqual(r.colors_to_value("Yellow", "Red", "Yellow"), "Yellow Red Yellow, 4-Band resistor: 420kΩ")
        self.assertEqual(r.colors_to_value("Yellow", "Red", "Violet"), "Yellow Red Violet, 4-Band resistor: 420MΩ")
        self.assertEqual(r.colors_to_value("White", "White", "White"), "White White White, 4-Band resistor: 99GΩ")

    def test_exceptions(self):
        invalid_color = "Foo"
        with self.assertRaises(ValueError, msg="'{}' is not a valid resistor color".format(invalid_color)):
            r.colors_to_value("Yellow", "Red", invalid_color)

        invalid_color = None
        with self.assertRaises(TypeError, msg="must provide at least 3 not None arguments"):
            r.colors_to_value("Yellow", "Red", invalid_color)

class Testtolerance(unittest.TestCase):
    def test_tolerances(self):
        self.assertEqual(r.tolerance("Silver"), "color: Silver, resistor tolerance: 10%")
        self.assertEqual(r.tolerance("Green"), "color: Green, resistor tolerance: 0.5%")
        self.assertEqual(r.tolerance("Grey"), "color: Grey, resistor tolerance: 0.05%")
    
    def test_exceptions(self):
        invalid_tolerances = ("Black", "Yellow", "White", "Orange", "Foo")
        for tol in invalid_tolerances:
            with self.assertRaises(ValueError, msg="'{}' is not a valid tolerance color".format(tol)):
                r.tolerance(tol)

if __name__ == '__main__':
    unittest.main()


