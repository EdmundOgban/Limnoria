###
# Copyright (c) 2002-2004, Jeremiah Fincher
# Copyright (c) 2008-2009, James McCoy
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

from __future__ import division

import re
import math
import cmath
import types
import string

import supybot.utils as utils
from supybot.commands import *
import supybot.utils.minisix as minisix
import supybot.callbacks as callbacks
from supybot.i18n import PluginInternationalization, internationalizeDocstring
_ = PluginInternationalization('Math')

from .local import convertcore
from supybot.utils.math_evaluator import safe_eval, InvalidNode, SAFE_ENV

baseArg = ('int', 'base', lambda i: i <= 36)

def _toSubscript(number):
    unirange = [chr(0x2080+i) for i in range(10)]
    number = abs(number)
    out = []

    while number > 0:
        idx = number % 10
        out.append(unirange[idx])
        number //= 10

    return "".join(reversed(out))

class Math(callbacks.Plugin):
    """Provides commands to work with math, such as a calculator and
    a unit converter."""
    @internationalizeDocstring
    @wrap([getopts({'to': ('int', 'base', lambda i: 2 <= i <= 36)}), 'text'])
    def base(self, irc, msg, args, optlist, numbers):
        """[--to <base>] <[0x|0o|0b]number[\<fromBase>]> [<[0x|0o|0b]number[\<fromBase>]> ...]

        Converts number (or numbers, separated by space) to base <base>.
        If <base> is left out, it converts to decimal.
        You can prefix the number with 0x, 0o or 0b,
        or specify a nonstandard base suffixing \fromBase to the number.
        """
        L = []

        try:
            k, v = optlist[0]
        except IndexError:
            to = 10
        else:
            if k == "to":
                to = v

        try:
            for number, norm, frm in utils.gen.normalizeBase(*numbers.split()):
                conv = self._convertDecimalToBase(norm, to)
                subsfrm = _toSubscript(frm)
                substo = _toSubscript(to)
                L.append("{}{} = {}{}".format(number, subsfrm, conv, substo))
        except ValueError as e:
            irc.error(_(str(e)))
        else:
            irc.reply(", ".join(L))

    def _convertDecimalToBase(self, number, base):
        """Convert a decimal number to another base; returns a string."""
        if base == 10:
            return str(number)
        if number == 0:
            return '0'
        elif number < 0:
            negative = True
            number = -number
        else:
            negative = False
        digits = []
        while number != 0:
            digit = number % base
            if digit >= 10:
                digit = string.ascii_uppercase[digit - 10]
            else:
                digit = str(digit)
            digits.append(digit)
            number = number // base
        digits.reverse()
        return '-'*negative + ''.join(digits)

    def _floatToString(self, x):
        if -1e-10 < x < 1e-10:
            return '0'
        elif -1e-10 < int(x) - x < 1e-10:
            return str(int(x))
        else:
            return str(x)

    def _complexToString(self, x):
        realS = self._floatToString(x.real)
        imagS = self._floatToString(x.imag)
        if imagS == '0':
            return realS
        elif imagS == '1':
            imagS = '+i'
        elif imagS == '-1':
            imagS = '-i'
        elif x.imag < 0:
            imagS = '%si' % imagS
        else:
            imagS = '+%si' % imagS
        if realS == '0' and imagS == '0':
            return '0'
        elif realS == '0':
            return imagS.lstrip('+')
        elif imagS == '0':
            return realS
        else:
            return '%s%s' % (realS, imagS)

    @internationalizeDocstring
    def calc(self, irc, msg, args, text):
        """<math expression>

        Returns the value of the evaluated <math expression>.  The syntax is
        Python syntax; the type of arithmetic is floating point.  Floating
        point arithmetic is used in order to prevent a user from being able to
        crash to the bot with something like '10**10**10**10'.  One consequence
        is that large values such as '10**24' might not be exact.
        """
        try:
            self.log.info('evaluating %q from %s', text, msg.prefix)
            x = complex(safe_eval(text, allow_ints=False))
            irc.reply(self._complexToString(x))
        except OverflowError:
            maxFloat = math.ldexp(0.9999999999999999, 1024)
            irc.error(_('The answer exceeded %s or so.') % maxFloat)
        except InvalidNode as e:
            irc.error(_('Invalid syntax: %s') % e.args[0])
        except NameError as e:
            irc.error(_('%s is not a defined function.') % e.args[0])
        except MemoryError:
            irc.error(_('Memory error (too much recursion?)'))
        except Exception as e:
            irc.error(str(e))
    calc = wrap(calc, ['text'])

    @internationalizeDocstring
    def icalc(self, irc, msg, args, text):
        """<math expression>

        This is the same as the calc command except that it allows integer
        math, and can thus cause the bot to suck up CPU.  Hence it requires
        the 'trusted' capability to use.
        """
        try:
            self.log.info('evaluating %q from %s', text, msg.prefix)
            x = safe_eval(text, allow_ints=True)
            irc.reply(str(x))
        except OverflowError:
            maxFloat = math.ldexp(0.9999999999999999, 1024)
            irc.error(_('The answer exceeded %s or so.') % maxFloat)
        except InvalidNode as e:
            irc.error(_('Invalid syntax: %s') % e.args[0])
        except NameError as e:
            irc.error(_('%s is not a defined function.') % str(e).split()[1])
        except Exception as e:
            irc.error(utils.exnToString(e))
    icalc = wrap(icalc, [('checkCapability', 'trusted'), 'text'])

    _rpnEnv = {
        'dup': lambda s: s.extend([s.pop()]*2),
        'swap': lambda s: s.extend([s.pop(), s.pop()])
        }
    def rpn(self, irc, msg, args):
        """<rpn math expression>

        Returns the value of an RPN expression.
        """
        stack = []
        for arg in args:
            try:
                x = complex(arg)
                if x == abs(x):
                    x = abs(x)
                stack.append(x)
            except ValueError: # Not a float.
                if arg in SAFE_ENV:
                    f = SAFE_ENV[arg]
                    if callable(f):
                        called = False
                        arguments = []
                        while not called and stack:
                            arguments.append(stack.pop())
                            try:
                                stack.append(f(*arguments))
                                called = True
                            except TypeError:
                                pass
                        if not called:
                            irc.error(_('Not enough arguments for %s') % arg)
                            return
                    else:
                        stack.append(f)
                elif arg in self._rpnEnv:
                    self._rpnEnv[arg](stack)
                else:
                    arg2 = stack.pop()
                    arg1 = stack.pop()
                    s = '%s%s%s' % (arg1, arg, arg2)
                    try:
                        stack.append(safe_eval(s, allow_ints=False))
                    except SyntaxError:
                        irc.error(format(_('%q is not a defined function.'),
                                         arg))
                        return
        if len(stack) == 1:
            irc.reply(str(self._complexToString(complex(stack[0]))))
        else:
            s = ', '.join(map(self._complexToString, list(map(complex, stack))))
            irc.reply(_('Stack: [%s]') % s)

    @internationalizeDocstring
    def convert(self, irc, msg, args, number, unit1, unit2):
        """[<number>] <unit> to <other unit>

        Converts from <unit> to <other unit>. If number isn't given, it
        defaults to 1. For unit information, see 'units' command.
        """
        try:
            digits = len(str(number).split('.')[1])
        except IndexError:
            digits = 0
        try:
            newNum = convertcore.convert(number, unit1, unit2)
            if isinstance(newNum, float):
                zeros = 0
                for char in str(newNum).split('.')[1]:
                    if char != '0':
                        break
                    zeros += 1
                # Let's add one signifiant digit. Physicists would not like
                # that, but common people usually do not give extra zeros...
                # (for example, with '32 C to F', an extra digit would be
                # expected).
                newNum = round(newNum, digits + 1 + zeros)
            newNum = self._floatToString(newNum)
            irc.reply(str(newNum))
        except convertcore.UnitDataError as ude:
            irc.error(str(ude))
    convert = wrap(convert, [optional('float', 1.0),'something','to','text'])

    @internationalizeDocstring
    def units(self, irc, msg, args, type):
        """ [<type>]

        With no arguments, returns a list of measurement types, which can be
        passed as arguments. When called with a type as an argument, returns
        the units of that type.
        """

        irc.reply(convertcore.units(type))
    units = wrap(units, [additional('text')])

    @wrap(['text'])
    def prop(self, irc, msg, args, text):
        """ a:b=c:d """
        text = text.split()[0]
        match = re.match(r'^([\w.]+):([\w.]+)=([\w.]+):([\w.]+)$', text)
        if not match:
            irc.error('Malformed proportion.')
            return

        terms = match.groups()
        unknown = []
        for (x, y) in enumerate(terms, 1):
            try:
                float(y)
            except ValueError:
                unknown.append((x, y))

        if not unknown:
            irc.error('No unknown in that proportion.')
            return
        elif len(unknown) > 1:
            irc.error('Multiple unknowns not allowed.')
            return

        unknown, literal = unknown[0]
        mul = []
        div = None
        pledge = None

        for term in terms:
            if term == literal:
                continue

            term = float(term)

            if unknown == 1:
                if len(mul) < 2:
                    mul.append(term)
                else:
                    div = term
            elif unknown in (2, 3):
                if not pledge:
                    mul.append(term)
                    pledge = True
                else:
                    div = term
                    pledge = False
            elif unknown == 4:
                if not div:
                    div = term
                else:
                    mul.append(term)

        res = mul[0] * mul[1] / div
        irc.reply(f'{literal} = {res:G}')

    @wrap(['float', 'float'])
    def percent(self, irc, msg, args, u1, u2):
        """ <a> <b> """
        try:
            res = (u1 / u2) * 100
            irc.reply(f'{res:.4G}%', prefixNick=True)
        except ZeroDivisionError:
            irc.error('Can\'t divide by zero.')

    vg = 0.6 # Glicerine
    pg = 0.4 # Propylene Glycol
    nicotine_conc = 160.0 # mg/ml

    @wrap(['float', 'percentage', optional('percentage')])
    def juice(self, irc, msg, args, ml, aroma_percentage, lvg):
        """ <ml> <concentration%> [vg%]
        if vg is specified, pg will be calculated automatically """

        vg = self.vg if lvg is None else lvg
        pg = self.pg if lvg is None else 1 - lvg

        base_density = (1.26 * vg + 1.036 * pg)

        base_percentage = 1 - aroma_percentage
        aroma = round(ml * 1.036 * aroma_percentage, 2)
        base = round(ml * base_density * base_percentage, 2)

        irc.reply("base: %.2fg (%d/%d), aroma: %.2fg - total: %.2fg" % (base, vg*100, pg*100, aroma, base+aroma))

    @wrap(['float', 'float', optional('percentage')])
    def baseweight(self, irc, msg, args, ml, conc, lvg):
        """ <ml> <nicotine_concentration> [vg%]
        if vg is specified, pg will be calculated automatically """
        nconc = self.nicotine_conc

        vg = self.vg if lvg is None else lvg
        pg = self.pg if lvg is None else 1 - lvg

        nicotine = ml * conc / nconc
        ml -= nicotine
        vg_ml = ml * vg * 1.26
        pg_ml = ml * pg * 1.036
        total = vg_ml + pg_ml + nicotine

        s = ("vg: %.2fg (%d%%) - pg: %.2fg (%d%%) - nicotine: %.2fg "
             "(%dmg/ml bottle) - total: %.2fg") % (
            vg_ml, vg*100, pg_ml, pg*100, nicotine, nconc, total)
        irc.reply(s)

Class = Math

# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
