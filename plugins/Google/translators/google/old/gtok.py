import re
import requests
from time import time, sleep

TRANSLATE_URL = "translate.google.it"
TKK = [0, 0]
TKK_IAT = 0
COOKIEJAR = None

#import logging
#log = logging.getLogger("supybot")


def JS_charCodeAt(s, idx):
    return s[idx]


def JS_length(s):
    return len(s)


def uShr(a, b):
    if b >= 32 or b < -32:
        m = b // 32
        b -= m * 32

    if b < 0:
        b += 32

    if b == 0:
        return ((a >> 1) & 0x7fffffff) * 2 + ((a >> b) & 1)

    if a < 0:
        a >>= 1
        a &= 2147483647
        a |= 0x40000000
        a >>= b - 1
    else:
        a >>= b

    return a


def RL(a, b):
    for c in range(0, len(b) - 2, 3):
        d = b[c + 2]
        d = ord(d[0]) - 87 if ord('a') <= ord(d) else int(d)
        d = uShr(a, d) if '+' == b[c + 1] else a << d
        a = a + d & 4294967295 if '+' == b[c] else a ^ d

    return a


def TL(a):
    b = TKK[0];
    d = []
    f = 0
    while f < JS_length(a):
        g = JS_charCodeAt(a, f)
        if g < 128:
            d.append(g)
        else:
            if g < 2048:
                d.append(g >> 6 | 192)
            else:
                if (g & 64512 == 55296
                    and f + 1 < JS_length(a)
                    and JS_charCodeAt(a, f + 1) & 64512 == 56320):
                    f += 1
                    g = 65536 + ((g & 1023) << 10) + (JS_charCodeAt(a, f) & 1023)
                    d.append(g >> 18 | 240)
                    d.append(g >> 12 & 63 | 128)
                else:
                    d.append(g >> 12 | 224)

                d.append(g >> 6 & 63 | 128)

            d.append(g & 63 | 128)

        f += 1

    a = b;
    for e in d:
        a += e
        a = RL(a, '+-a^+6')

    a = RL(a, '+-3^+b+-f')
    a ^= TKK[1]
    if a < 0:
        a = (a & 2147483647) + 2147483648

    a %= 10 ** 6
    return "{}.{}".format(a, a ^ b)


def javascriptify_text(s):
    encoded = s.encode("utf-16-be")
    return [encoded[i] * 256 + encoded[i + 1] for i in range(0, len(encoded), 2)]


from pathlib import Path
def reissue_tkk(tries=0):
    global TKK, TKK_IAT, COOKIEJAR

    hdrs = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:73.0) Gecko/20100101"}
    urlh = requests.get("https://{}".format(TRANSLATE_URL), headers=hdrs)

    tkk = re.search("tkk:'([^']+)'", urlh.text)
    if tkk is None:
        if tries < 10:
            sleep(0.5)
            return reissue_tkk(tries+1)

        with open(Path(__file__).parent.joinpath("googletr.html"), "wb") as f:
            f.write(urlh.text.encode())
        raise ValueError("Can't grasp tkk from {}.".format(TRANSLATE_URL))
    else:
        TKK = [int(x) for x in tkk.group(1).split('.')]
        TKK_IAT = time()
        #log.warn("gtok: Reissued tkk: {} {}".format(TKK, TKK_IAT))

    COOKIEJAR = urlh.cookies


def gen_token(text, *, reissue=False):
    if TKK_IAT == 0 or reissue is True or time() - TKK_IAT > 3600:
        reissue_tkk()

    token = TL(javascriptify_text(text))
    return token
