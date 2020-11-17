###
# Copyright (c) 2002-2004, Jeremiah Fincher
# Copyright (c) 2008, James McCoy
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
###

from __future__ import print_function

from supybot.test import *

class MathTestCase(PluginTestCase):
    plugins = ('Math',)
    def testBase(self):
        self.assertNotRegexp('base asdflkj\\56', 'ValueError')
        self.assertResponse('base --to 2 0xF', 'F₁₆ = 1111₂')
        self.assertResponse('base --to 16 0b1111', '1111₂ = F₁₆')
        self.assertResponse('base BBBB\\20', 'BBBB₂₀ = 92631₁₀')
        self.assertResponse('base --to 20 92631', '92631₁₀ = BBBB₂₀')
        self.assertResponse('base --to 36 0b10', '10₂ = 2₃₆')
        self.assertResponse('base --to 2 10\\36', '10₃₆ = 100100₂')
        self.assertResponse('base 0b1010101', '1010101₂ = 85₁₀')
        self.assertResponse('base --to 2 0b11', '11₂ = 11₂')

        self.assertResponse('base 0\\12', '0₁₂ = 0₁₀')
        self.assertResponse('base --to 2 0\\36', '0₃₆ = 0₂')


        # self.assertNotError("base " +\
            # "ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ"\
            # "ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ"\
            # "ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ"\
            # "ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ"\
            # "ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ"\
            # "ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ"\
            # "ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ\\36")

        # self.assertResponse("base --to 36 [base " +\
            # "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"\
            # "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"\
            # "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"\
            # "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"\
            # "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"\
            # "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"\
            # "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz\\36]",

            # "ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ"\
            # "ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ"\
            # "ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ"\
            # "ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ"\
            # "ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ"\
            # "ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ"\
            # "ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ")

        # self.assertResponse('base 2 10 [base --to 2 12]', '12')
        # self.assertResponse('base 16 2 [base --to 16 0b110101]', '110101')
        # self.assertResponse('base 10 8 [base 0o76532]', '76532')
        # self.assertResponse('base 10 36 [base csalnwea\\36]', 'CSALNWEA')
        # self.assertResponse('base 5 4 [base --to 5 212231\\4]', '212231')

        self.assertError('base 1\\37')
        self.assertError('base 1\\37')
        self.assertError('base --to 1 1\\12')
        self.assertError('base --to 12 1\\1')
        self.assertError('base --to 12 1\\1.0')
        self.assertError('base 1\\A')

        self.assertError('base 4\\4')
        self.assertError('base --to 12 A\\10')

        # self.assertRegexp('base 2 10 [base 10 2 -12]', '-12')
        # self.assertRegexp('base 16 2 [base 2 16 -110101]', '-110101')

    def testCalc(self):
        self.assertResponse('calc 5*0.06', str(5*0.06))
        self.assertResponse('calc 2.0-7.0', str(2-7))
        self.assertResponse('calc e**(i*pi)+1', '0')
        if minisix.PY3:
            # Python 2 has bad handling of exponentiation of negative numbers
            self.assertResponse('calc (-1)**.5', 'i')
            self.assertRegexp('calc (-5)**.5', '2.236067977[0-9]+i')
            self.assertRegexp('calc -((-5)**.5)', '-2.236067977[0-9]+i')
        self.assertNotRegexp('calc [9, 5] + [9, 10]', 'TypeError')
        self.assertError('calc [9, 5] + [9, 10]')
        self.assertNotError('calc degrees(2)')
        self.assertNotError('calc (2 * 3) - 2*(3*4)')
        self.assertNotError('calc (3) - 2*(3*4)')
        self.assertNotError('calc (1600 * 1200) - 2*(1024*1280)')
        self.assertNotError('calc 3-2*4')
        self.assertNotError('calc (1600 * 1200)-2*(1024*1280)')
        self.assertError('calc factorial(20000)')

    def testCalcNoNameError(self):
        self.assertRegexp('calc foobar(x)', 'foobar is not a defined function')

    def testCalcInvalidNode(self):
        self.assertRegexp('calc {"foo": "bar"}', 'Illegal construct Dict')

    def testCalcImaginary(self):
        self.assertResponse('calc 3 + sqrt(-1)', '3+i')

    def testCalcFloorWorksWithSqrt(self):
        self.assertNotError('calc floor(sqrt(5))')

    def testCaseInsensitive(self):
        self.assertNotError('calc PI**PI')

    def testCalcMaxMin(self):
        self.assertResponse('calc max(1,2)', '2')
        self.assertResponse('calc min(1,2)', '1')

    def testCalcStrFloat(self):
        self.assertResponse('calc 3+33333333333333', '33333333333336')

    def testCalcMemoryError(self):
        self.assertRegexp('calc ' + '('*10000,
            '(too much recursion'  # cpython < 3.10
            '|too many nested parentheses'  # cpython >= 3.10
            '|parenthesis is never closed)'  # pypy
        )

    def testICalc(self):
        self.assertResponse('icalc 1^1', '0')
        self.assertResponse('icalc 10**24', '1' + '0'*24)
        self.assertRegexp('icalc 49/6', '8.16')
        self.assertNotError('icalc factorial(20000)')

    def testRpn(self):
        self.assertResponse('rpn 5 2 +', '7')
        self.assertResponse('rpn 1 2 3 +', 'Stack: [1, 5]')
        self.assertResponse('rpn 1 dup', 'Stack: [1, 1]')
        self.assertResponse('rpn 2 3 4 + -', str(2-7))
        self.assertNotError('rpn 2 degrees')

    def testRpnSwap(self):
        self.assertResponse('rpn 1 2 swap', 'Stack: [2, 1]')

    def testRpmNoSyntaxError(self):
        self.assertNotRegexp('rpn 2 3 foobar', 'SyntaxError')

    def testConvert(self):
        self.assertResponse('convert 1 m to cm', '100')
        self.assertResponse('convert m to cm', '100')
        self.assertResponse('convert 3 metres to km', '0.003')
        self.assertResponse('convert 32 F to C', '0')
        self.assertResponse('convert 32 C to F', '89.6')
        self.assertResponse('convert [calc 2*pi] rad to degree', '360')
        self.assertResponse('convert amu to atomic mass unit',
                            '1')
        self.assertResponse('convert [calc 2*pi] rad to circle', '1')
        self.assertError('convert 1 meatball to bananas')
        self.assertError('convert 1 gram to meatballs')
        self.assertError('convert 1 mol to grams')
        self.assertError('convert 1 m to kpa')

    def testConvertSingularPlural(self):
        self.assertResponse('convert [calc 2*pi] rads to degrees', '360')
        self.assertResponse('convert 1 carat to grams', '0.2')
        self.assertResponse('convert 10 lbs to oz', '160')
        self.assertResponse('convert mA to amps', '0.001')

    def testConvertCaseSensitivity(self):
        self.assertError('convert MA to amps')
        self.assertError('convert M to amps')
        self.assertError('convert Radians to rev')

    def testUnits(self):
        self.assertNotError('units')
        self.assertNotError('units mass')
        self.assertNotError('units flux density')

    def testAbs(self):
        self.assertResponse('calc abs(2)', '2')
        self.assertResponse('calc abs(-2)', '2')
        self.assertResponse('calc abs(2.0)', '2')
        self.assertResponse('calc abs(-2.0)', '2')

    def testV2cFourbands(self):
        self.assertResponse("resbands 4", "4Ω, 4-Band resistor: Yellow Black Gold")
        self.assertResponse("resbands 4.2", "4.2Ω, 4-Band resistor: Yellow Red Gold")
        self.assertResponse("resbands 42", "42Ω, 4-Band resistor: Yellow Red Black")
        self.assertResponse("resbands 420.5", "420Ω, 4-Band resistor: Yellow Red Brown")

    def testV2cFivebands(self):
        self.assertResponse("resbands 4.25", "4.25Ω, 5-Band resistor: Yellow Red Green Silver")
        self.assertResponse("resbands 42.5", "42.5Ω, 5-Band resistor: Yellow Red Green Gold")
        self.assertResponse("resbands 425", "425Ω, 5-Band resistor: Yellow Red Green Black")
        self.assertResponse("resbands 4250", "4.25kΩ, 5-Band resistor: Yellow Red Green Brown")

    def testV2cMultiples(self):
        self.assertResponse("resbands 420k", "420kΩ, 4-Band resistor: Yellow Red Yellow")
        self.assertResponse("resbands 420M", "420MΩ, 4-Band resistor: Yellow Red Violet")
        self.assertResponse("resbands 99G", "99GΩ, 4-Band resistor: White White White")

    def testParsing(self):
        suffixes = ["ohm", "ohms", " ohm", "  ohm", "   ohm"]
        for suffix in suffixes:
            self.assertResponse("resbands 4{}".format(suffix),
                "4Ω, 4-Band resistor: Yellow Black Gold")

        suffixes = ["kohm", "kohms", "k ohm", " k ohm", " k ohms", "  k ohms", "  k  ohms"]
        for suffix in suffixes:
            self.assertResponse("resbands 4{}".format(suffix),
                "4kΩ, 4-Band resistor: Yellow Black Red")

    def testIdempotence(self):
        self.assertResponse("resbands 4200", self.getMsg("resbands 4.2k").args[1])
        self.assertResponse("resbands 4200000", self.getMsg("resbands 4.2M").args[1])
        self.assertResponse("resbands 4200k", self.getMsg("resbands 4.2M").args[1])
        self.assertResponse("resbands 4200000000", self.getMsg("resbands 4.2G").args[1])
        self.assertResponse("resbands 4200M", self.getMsg("resbands 4.2G").args[1])

    def testIdentity(self):
        self.assertResponse("resbands 04", self.getMsg("resbands 4.0").args[1])
        self.assertResponse("resbands 04.2", self.getMsg("resbands 4.2").args[1])
        self.assertResponse("resbands 4,2", self.getMsg("resbands 4.2").args[1])
        self.assertResponse("resbands 4.20", self.getMsg("resbands 4.2").args[1])
        self.assertResponse("resbands 42.0", self.getMsg("resbands 42").args[1])

    def testV2cExceptions(self):
        self.assertError("resbands 4.2.2")
        self.assertError("resbands 4foo2bar")
        self.assertError("resbands 100G")

    def testC2vFourbands(self):
        self.assertResponse("resbands Yellow Black Gold", "Yellow Black Gold, 4-Band resistor: 4Ω")
        self.assertResponse("resbands Yellow Red Gold", "Yellow Red Gold, 4-Band resistor: 4.2Ω")
        self.assertResponse("resbands Yellow Red Black", "Yellow Red Black, 4-Band resistor: 42Ω")
        self.assertResponse("resbands Yellow Red Brown", "Yellow Red Brown, 4-Band resistor: 420Ω")

    def testC2vivebands(self):
        self.assertResponse("resbands Yellow Red Green Silver", "Yellow Red Green Silver, 5-Band resistor: 4.25Ω")
        self.assertResponse("resbands Yellow Red Green Gold", "Yellow Red Green Gold, 5-Band resistor: 42.5Ω")
        self.assertResponse("resbands Yellow Red Green Black", "Yellow Red Green Black, 5-Band resistor: 425Ω")
        self.assertResponse("resbands Yellow Red Green Brown", "Yellow Red Green Brown, 5-Band resistor: 4.25kΩ")

    def testC2vMultiples(self):
        self.assertResponse("resbands Yellow Red Yellow", "Yellow Red Yellow, 4-Band resistor: 420kΩ")
        self.assertResponse("resbands Yellow Red Violet", "Yellow Red Violet, 4-Band resistor: 420MΩ")
        self.assertResponse("resbands White White White", "White White White, 4-Band resistor: 99GΩ")

    def testC2vExceptions(self):
        self.assertError("resbands Yellow Red Foo")
        self.assertError("resbands Black Black Gold")
        self.assertError("resbands Gold Gold Gold")
        self.assertError("resbands Gold Gold Gold Silver")
        self.assertError("resbands Gold Gold Silver Silver")

    def testTolerances(self):
        self.assertResponse("restol Silver", "color: Silver, resistor tolerance: 10%")
        self.assertResponse("restol Green", "color: Green, resistor tolerance: 0.5%")
        self.assertResponse("restol Grey", "color: Grey, resistor tolerance: 0.05%")
    
    def testRestolExceptions(self):
        invalid_tolerances = ("Black", "Yellow", "White", "Orange", "Foo")
        for tol in invalid_tolerances:
            self.assertError("restol {}".format(tol))

# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
