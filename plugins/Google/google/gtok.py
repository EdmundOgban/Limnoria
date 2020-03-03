import math

TKK = [406398, (561666268 + 1526272306)]

def JS_charCodeAt(s, idx):
    return ord(s[idx])


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
    tkk = TKK
    b = tkk[0];
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
    a ^= tkk[1]
    if a < 0:
        a = (a & 2147483647) + 2147483648

    a %= 10 ** 6
    return "{}.{}".format(a, a ^ b)


def gen_token(text):
    return TL(text)

