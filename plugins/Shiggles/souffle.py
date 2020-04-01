import string

vowels = list("aeiou")
consonants = [c for c in string.ascii_lowercase if c not in vowels]


def _conjugate_vowels(word):
    if len(word) <= 3:
        return word, ''

    third, second, last = word[-3:]
    vowel = last
    if second in vowels and last in vowels:
        if second == last and last not in "i":
            return word, last

        if second in "ao" and last in "oai" and third not in vowels:
            if second == "a" and last == "i":
                word = word[:-1]

            return word, last

    word = word[:-1]
    if second in "ioa":
        if third not in vowels:
            word = word[:-1]
            vowel = second

        if second == "i" and third in vowels:
            word = word[:-1]

    return word, vowel

def _conjugate_consonants(word, vowel):
    try:
        second, last = word[-2:]
    except ValueError:
        return word

    if last in vowels:
        return word

    if second == last and vowel == "i":
        word += vowel

    if last in "cg" and second in "aceinrs" and vowel in "aou":
        word += "h"

    return word

def _longest_word(s):
    return max(s.split(), key=lambda x: len(x))

def macchette(text):
    word = _longest_word(text).lower()
    vowel = ""

    if any(word.endswith(v) for v in vowels):
        word, vowel = _conjugate_vowels(word)

    if any(word.endswith(v) for v in consonants):
        word = _conjugate_consonants(word, vowel)

    return "macchette{}iscy :E".format(word)

if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:])
    print(macchette(text))
