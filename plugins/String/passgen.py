import random
import string
import sys

# tolta qz
consonants = "bcdfglmnprstv"
vowels = "aeiou"
digits = "1234567890"
# tolta z
starters = "abcdefgilmnoprstuv"
# tolta qz
consonants_prevowel = "bdlmnrv"

vows_successors = {
    "a": vowels,
    "b": vowels,
    "c": vowels,
    "d": vowels,
    "e": vowels,
    "f": vowels,
    "g": vowels,
    "h": "ieao",
    "i": vowels,
    "l": vowels,
    "m": vowels,
    "n": vowels,
    "o": vowels,
    "p": vowels,
    "q": "u",
    "r": vowels,
    "s": vowels,
    "t": vowels,
    "u": vowels,
    "v": vowels,
    "z": vowels
}

cons_successors = {
    "a": consonants,
    "b": "dlnr",
    "c": "hlr",
    "d": "r",
    "e": consonants,
    "f": "lr",
    "g": "hlnr",
    "h": "",
    "i": "bcdglmnprstv",
# tolta z
    "l": "gmpstuv",
    "m": "bnp",
    "n": "cdfgt",
    "o": consonants,
    "p": "lnru",
    "q": "",
    "r": "bcdglnpstu",
    "s": "bcdfglmnptuv",
    "t": "r",
    "u": consonants,
    "v": "",
    "z": ""
}


def choice_no_repeat(L, lastc):
    c = random.choice(L)
    while c == lastc:
        c = random.choice(L)
    return c

def passgen(length):
    #digitsqty = int(round(length * 0.25))
    #digitsqty = digitsqty if digitsqty <= 4 else 4
    
    s = ""
    c = ""
    consnum = 0
    vowsnum = 0

    for n in range(length-1):
        if s == "":
            c = random.choice(starters)
        elif consnum > 0:
            successors = cons_successors[c]
            if successors:
                c = choice_no_repeat(successors, c)
            else:
                consnum = 0
                c = choice_no_repeat(vows_successors[c], c)
               
        elif vowsnum > 0:
            successors = vows_successors[c]
            if successors:
                c = choice_no_repeat(successors, c)
            else:
                c = choice_no_repeat(cons_successors[c], c)

        s += c

        if c in consonants:
            consnum -= 1
        else:
            vowsnum -= 1

        if consnum <= 0 and vowsnum <= 0:
            if c in consonants:
                vowsnum = random.randint(1, 2)
            else:
                consnum = random.randint(1, 2)

    s += choice_no_repeat(vows_successors[c], c)

    #for i in xrange(digitsqty):
    #    s += random.choice(digits) 

    return s

