import math
import re

tolerances = {
    "Silver": 10,
    "Gold": 5,
    "Red": 2,
    "Brown": 1,
    "Green": 0.5,
    "Blue": 0.25,
    "Violet": 0.1,
    "Grey": 0.05,
}
idx_colors = {
    "-2": "Silver",
    "-1": "Gold",
    "0": "Black",
    "1": "Brown",
    "2": "Red",
    "3": "Orange",
    "4": "Yellow",
    "5": "Green",
    "6": "Blue",
    "7": "Violet",
    "8": "Grey",
    "9": "White"
}
colors_idx = {v: k for k, v in idx_colors.items()}
multipliers = {
    "k": 3,
    "M": 6,
    "G": 9
}
powers = {v: k for k, v in multipliers.items()}
multiplier_max = max(multipliers.values())


def _parse_v2c(s):
    mtch = re.match(r"^([\d.,]+)\s*([kMG])?\s*(?:ohms?)?$", s)
    if not mtch:
        raise ValueError("Invalid input: '{}'".format(s))

    val, mult = mtch.groups()
    try:
        val = float(val.replace(",", "."))
    except ValueError:
        raise ValueError("Invalid input: '{}'".format(s))

    if mult:
        val *= 10 ** multipliers[mult]

    return val


def _calc_pow(n):
    pow = 0
    while n > 1000:
        n /= 1000
        pow += 3

    return n, pow


def _format_output(digits, zeros, *, c2v=False):
    colors = [idx_colors[c] for c in digits]
    colors.append(idx_colors[str(zeros)])
    val = int(digits) * 10 ** zeros
    val, pow = _calc_pow(val)
    decimals = math.fmod(val, 1)
    if decimals > 0:
        strdec = "{:.2f}".format(decimals).lstrip("0.")
        fmt = "{{:.{}f}}".format(sum(1 for c in strdec if c != "0"))
        strval = fmt.format(val)
    else:
        strval = str(int(val))

    ohm_val = "{}{}Ω".format(strval, powers.get(pow, ''))
    if not c2v:
        args = (ohm_val, " ".join(colors))
    else:
        args = (" ".join(colors), ohm_val)

    return "{}, {}-Band resistor: {}".format(
        args[0], len(colors) + 1, args[1])


def colors_to_value(a, b, c, d=None):
    args = [v.title() for v in (a, b, c, d) if v is not None]
    if len(args) < 3:
        raise TypeError("must provide at least 3 not None arguments")

    for arg in args:
        if arg not in colors_idx:
            raise ValueError("'{}' is not a valid resistor color".format(arg))

    *colors, mult = args
    forbidden = [v for k, v in idx_colors.items() if int(k) < 0]
    for color in colors:
        if color in forbidden:
            raise ValueError("'{}' is not a valid digit color".format(color))

    digits = ''.join(colors_idx[color] for color in colors)
    if int(digits) == 0:
        raise ValueError("'{}' is an invalid color combination".format(" ".join(args)))

    zeros = int(colors_idx[mult])
    return _format_output(digits, zeros, c2v=True)


def tolerance(tol):
    tol = tol.title()
    if tol not in tolerances:
        raise ValueError("'{}' is not a valid tolerance color".format(tol))

    return "color: {}, resistor tolerance: {}%".format(tol, tolerances[tol])


def value_to_colors(s):
    val = _parse_v2c(s)

    decimals = math.fmod(val, 1)
    if val < 10 or (val < 100 and decimals > 0):
        if decimals == 0:
            zeros = -1
        else:
            zeros = 0
            for _ in range(2):
                if math.fmod(val, 1) == 0:
                    break
                zeros -= 1
                val *= 10

        strval = str(int(val))
        if val < 10:
            digits = "{}0".format(strval)
        else:
            digits = strval
    else:
        strval = str(int(val))
        try:
            if strval[2] != '0':
                idx = 3
            else:
                idx = 2
        except IndexError:
            idx = 2

        digits = strval[:idx]
        zeros = len(strval[idx:])

    if zeros > multiplier_max:
        raise ValueError("Out of range")

    return _format_output(digits, zeros)
