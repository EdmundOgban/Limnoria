
import random
import sys
import re
import string

from string import ascii_letters as ASCII_L

VOWELS = "AEIOU"

class ScramblerExhaustedError(Exception):
    pass
class UndefinedVariableError(Exception):
    pass
class InvalidVariableTypeError(Exception):
    pass
class BuiltinOverrideError(Exception):
    pass

class VariablesManager(object):
    def __init__(self):
        self._vars = {}
        self._builtins = {
            "$lcon": lambda: random.choice([i for i in string.ascii_lowercase if i not in VOWELS.lower()]),
            "$ucon": lambda: random.choice([i for i in string.ascii_uppercase if i not in VOWELS]),
            "$lvow": lambda: random.choice(VOWELS.lower()),
            "$uvow": lambda: random.choice(VOWELS),
            "$char": lambda: chr(random.randint(32, 127)),
            "$uchar": lambda: chr(random.randint(32, 255))
        }

    def getVar(self, k):
        try:
            v = self._builtins[k]()
        except KeyError:
            try:
                v = self._vars[k]
            except KeyError:
                raise UndefinedVariableError(k)
        """
        try:
            print "bare_choice v='%s'" % v
            sel = bare_choice(v)
            print "chosen '%s'" % sel
            sel = letter_range(sel)
            sel = numeric_range(sel)
        except IndexError:
            raise ScramblerExhaustedError
        else:
            if k.startswith("%"):
                v.remove(sel)
        """
        return v

    def setVar(self, k, v):
        if k[0] not in ("%", "$"):
            raise InvalidVariableTypeError
        if k in self._builtins:
            raise BuiltinOverrideError

        self._vars[k] = v

    def assignment(self, s):
        m = re.match(r"(\$[^\s=]+)(?:\s*=\s*([\S ]+))?", s)

        if m:
            if m.group(2):
                self.setVar(m.group(1), m.group(2))
                ret = ""
            else:
                ret = self.getVar(m.group(1))
        else:
            ret = s
        
        return ret

    def process(self, s):
        ret = self.assignment(s)
        ret = bare_choice(ret)
        ret = letter_range(ret)
        ret = numeric_range(ret)

        return ret


    def __iter__(self):
        for k in self._vars:
            yield k


def letter_range(s):
    m = re.match(r"^(\s+)?([a-zA-Z])\.\.([a-zA-Z])(\s+)?$", s)

    if not m:
        return s

    leading = m.group(1) or ""
    trailing = m.group(4) or ""
    pos_a, pos_b = ASCII_L.index(m.group(2)), ASCII_L.index(m.group(3))

    if pos_a < pos_b:
        letter = ASCII_L[random.randint(pos_a, pos_b)]
    elif pos_a > pos_b:
        letter = ASCII_L[random.randint(pos_a, pos_b+len(ASCII_L)) % len(ASCII_L)]
    else:
        letter = m.group(1)

    return leading + letter + trailing

def numeric_range(s):
    m = re.match(r"^(\s+)?(-?\d+)\.\.(-?\d+)(\s+)?$", s)

    if not m:
        return s

    leading = m.group(1) or ""
    trailing = m.group(4) or ""
    
    mg1, mg2 = int(m.group(2)), int(m.group(3))
    
    if mg1 <= mg2:
        a, b = mg1, mg2
    else:
        a, b = mg2, mg1

    fmt = "%%s%%0%sd%%s" % (len(m.group(2)))
    return fmt % (leading, random.randint(a, b), trailing)
 
def bare_choice(s):
    return random.choice(s.split(";" if ";" in s else " "))



def rand(s, *, zero_depth=True):
    g_stack = []
    g_curbuffer = ""
    g_maxdepth = 0
    g_curdepth = 0
    _escaping = False
    mgr = VariablesManager()
    random.seed(random.getrandbits(256))

    for c in s:
        if c == "<" and not _escaping:
            g_curdepth += 1
            g_maxdepth += 1
            g_stack.append(g_curbuffer)
            g_curbuffer = ""
        elif c == ">" and not _escaping:
            g_curdepth -= 1
            try:
                tmp = g_stack.pop()
            except IndexError:
                pass
            else:
                g_curbuffer = tmp + mgr.process(g_curbuffer)
        else:
            if c == "\\" and not _escaping:
                _escaping = True
                continue
            elif _escaping:
                _escaping = False

            g_curbuffer += c

    if g_curdepth > 0:
        return "Missing %d closing parenthesis." % g_curdepth
    elif g_curdepth < 0:
        return "Missing %d opening parenthesis." % -g_curdepth
    else:
        if g_maxdepth == 0 and zero_depth:
            g_curbuffer = bare_choice(g_curbuffer)
            g_curbuffer = letter_range(g_curbuffer)
            g_curbuffer = numeric_range(g_curbuffer)

        return g_curbuffer

