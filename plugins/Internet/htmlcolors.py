class RGBColor:
    def __init__(self, *args, name=None):
        if len(args) == 1:
            arg = args[0]

            if isinstance(arg, str):
                if arg.startswith("#"):
                    arg = arg.lstrip("#")
                    chars = set(arg)
                    if len(arg) == 3 and len(chars) == 1:
                        arg = "{{:{}<6}}".format(chars.pop()).format(arg)
                arg = int(arg, 16)
            elif not isinstance(arg, int):
                raise ValueError("Unsupported argument type.")

            self.r = (arg & 0xFF0000) >> 16
            self.g = (arg & 0xFF00) >> 8
            self.b = (arg & 0xFF)
        elif len(args) == 3:
            if not all(isinstance(arg, int) for arg in args):
                raise ValueError("Values must be integers.")

            self.r = min(args[0], 255)
            self.g = min(args[1], 255)
            self.b = min(args[2], 255)
        else:
            raise ValueError("Too much arguments")
        self.__tohsb()
        self._n = name

    def __tohsb(self):
        r1, g1, b1 = self.r / 255, self.g / 255, self.b / 255
        cmax = max(r1, g1, b1)
        cmin = min(r1, g1, b1)
        delta = cmax - cmin

        if delta != 0:
            if cmax == r1:
                h = (g1 - b1) / delta % 6
            elif cmax == g1:
                h = (b1 - r1) / delta + 2
            else:
                h = (r1 - g1) / delta + 4
            
            s = delta / cmax if cmax != 0 else 0
        else:
            h = s = 0

        self.h = 60 * h
        self.s = s
        self.v = cmax

    def distance(self, val):
        return (val.h - self.h) ** 2 + (val.s - self.s) ** 2 + (val.v - self.v) ** 2

    def __eq__(self, val):
        return self.hsb_int == val.hsb_int

    def __gt__(self, val):
        return self.hsb_int > val.hsb_int

    def __lt__(self, val):
        return self.hsb_int < val.hsb_int

    def __str__(self):
        return "rgb({}, {}, {})".format(self.r, self.g, self.b)

    def __repr__(self):
        return "{}({}, name='{}')".format(self.__class__.__name__, self.hex, self.name)

    @property
    def htmlhex(self):
        return "#{:02X}{:02X}{:02X}".format(self.r, self.g, self.b)

    @property
    def hex(self):
        return "0x{:06X}".format(self.rgb_int)

    @property
    def rgb_int(self):
        return (self.r << 16) + (self.g << 8) + self.b

    @property
    def hsb_int(self):
        return int(self.h * 2 + self.s * 1.8 + self.v * 1.5)

    @property
    def name(self):
        return self._n


rgbcolors = [
    RGBColor(0x000000, name="Black"),
    RGBColor(0x000080, name="Navy"),
    RGBColor(0x00008B, name="DarkBlue"),
    RGBColor(0x0000CD, name="MediumBlue"),
    RGBColor(0x0000FF, name="Blue"),
    RGBColor(0x006400, name="DarkGreen"),
    RGBColor(0x008000, name="Green"),
    RGBColor(0x008080, name="Teal"),
    RGBColor(0x008B8B, name="DarkCyan"),
    RGBColor(0x00BFFF, name="DeepSkyBlue"),
    RGBColor(0x00CED1, name="DarkTurquoise"),
    RGBColor(0x00FA9A, name="MediumSpringGreen"),
    RGBColor(0x00FF00, name="Lime"),
    RGBColor(0x00FF7F, name="SpringGreen"),
    RGBColor(0x00FFFF, name="Cyan"),
    RGBColor(0x191970, name="MidnightBlue"),
    RGBColor(0x1E90FF, name="DodgerBlue"),
    RGBColor(0x20B2AA, name="LightSeaGreen"),
    RGBColor(0x228B22, name="ForestGreen"),
    RGBColor(0x2E8B57, name="SeaGreen"),
    RGBColor(0x2F4F4F, name="DarkSlateGrey"),
    RGBColor(0x32CD32, name="LimeGreen"),
    RGBColor(0x3CB371, name="MediumSeaGreen"),
    RGBColor(0x40E0D0, name="Turquoise"),
    RGBColor(0x4169E1, name="RoyalBlue"),
    RGBColor(0x4682B4, name="SteelBlue"),
    RGBColor(0x483D8B, name="DarkSlateBlue"),
    RGBColor(0x48D1CC, name="MediumTurquoise"),
    RGBColor(0x4B0082, name="Indigo"),
    RGBColor(0x556B2F, name="DarkOliveGreen"),
    RGBColor(0x5F9EA0, name="CadetBlue"),
    RGBColor(0x6495ED, name="CornflowerBlue"),
    RGBColor(0x663399, name="RebeccaPurple"),
    RGBColor(0x66CDAA, name="MediumAquaMarine"),
    RGBColor(0x696969, name="DimGrey"),
    RGBColor(0x6A5ACD, name="SlateBlue"),
    RGBColor(0x6B8E23, name="OliveDrab"),
    RGBColor(0x708090, name="SlateGrey"),
    RGBColor(0x778899, name="LightSlateGrey"),
    RGBColor(0x7B68EE, name="MediumSlateBlue"),
    RGBColor(0x7CFC00, name="LawnGreen"),
    RGBColor(0x7FFF00, name="Chartreuse"),
    RGBColor(0x7FFFD4, name="Aquamarine"),
    RGBColor(0x800000, name="Maroon"),
    RGBColor(0x800080, name="Purple"),
    RGBColor(0x808000, name="Olive"),
    RGBColor(0x808080, name="Grey"),
    RGBColor(0x87CEEB, name="SkyBlue"),
    RGBColor(0x87CEFA, name="LightSkyBlue"),
    RGBColor(0x8A2BE2, name="BlueViolet"),
    RGBColor(0x8B0000, name="DarkRed"),
    RGBColor(0x8B008B, name="DarkMagenta"),
    RGBColor(0x8B4513, name="SaddleBrown"),
    RGBColor(0x8FBC8F, name="DarkSeaGreen"),
    RGBColor(0x90EE90, name="LightGreen"),
    RGBColor(0x9370DB, name="MediumPurple"),
    RGBColor(0x9400D3, name="DarkViolet"),
    RGBColor(0x98FB98, name="PaleGreen"),
    RGBColor(0x9932CC, name="DarkOrchid"),
    RGBColor(0x9ACD32, name="YellowGreen"),
    RGBColor(0xA0522D, name="Sienna"),
    RGBColor(0xA52A2A, name="Brown"),
    RGBColor(0xA9A9A9, name="DarkGrey"),
    RGBColor(0xADD8E6, name="LightBlue"),
    RGBColor(0xADFF2F, name="GreenYellow"),
    RGBColor(0xAFEEEE, name="PaleTurquoise"),
    RGBColor(0xB0C4DE, name="LightSteelBlue"),
    RGBColor(0xB0E0E6, name="PowderBlue"),
    RGBColor(0xB22222, name="FireBrick"),
    RGBColor(0xB8860B, name="DarkGoldenRod"),
    RGBColor(0xBA55D3, name="MediumOrchid"),
    RGBColor(0xBC8F8F, name="RosyBrown"),
    RGBColor(0xBDB76B, name="DarkKhaki"),
    RGBColor(0xC0C0C0, name="Silver"),
    RGBColor(0xC71585, name="MediumVioletRed"),
    RGBColor(0xCD5C5C, name="IndianRed"),
    RGBColor(0xCD853F, name="Peru"),
    RGBColor(0xD2691E, name="Chocolate"),
    RGBColor(0xD2B48C, name="Tan"),
    RGBColor(0xD3D3D3, name="LightGrey"),
    RGBColor(0xD8BFD8, name="Thistle"),
    RGBColor(0xDA70D6, name="Orchid"),
    RGBColor(0xDAA520, name="GoldenRod"),
    RGBColor(0xDB7093, name="PaleVioletRed"),
    RGBColor(0xDC143C, name="Crimson"),
    RGBColor(0xDCDCDC, name="Gainsboro"),
    RGBColor(0xDDA0DD, name="Plum"),
    RGBColor(0xDEB887, name="BurlyWood"),
    RGBColor(0xE0FFFF, name="LightCyan"),
    RGBColor(0xE6E6FA, name="Lavender"),
    RGBColor(0xE9967A, name="DarkSalmon"),
    RGBColor(0xEE82EE, name="Violet"),
    RGBColor(0xEEE8AA, name="PaleGoldenRod"),
    RGBColor(0xF08080, name="LightCoral"),
    RGBColor(0xF0E68C, name="Khaki"),
    RGBColor(0xF0F8FF, name="AliceBlue"),
    RGBColor(0xF0FFF0, name="HoneyDew"),
    RGBColor(0xF0FFFF, name="Azure"),
    RGBColor(0xF4A460, name="SandyBrown"),
    RGBColor(0xF5DEB3, name="Wheat"),
    RGBColor(0xF5F5DC, name="Beige"),
    RGBColor(0xF5F5F5, name="WhiteSmoke"),
    RGBColor(0xF5FFFA, name="MintCream"),
    RGBColor(0xF8F8FF, name="GhostWhite"),
    RGBColor(0xFA8072, name="Salmon"),
    RGBColor(0xFAEBD7, name="AntiqueWhite"),
    RGBColor(0xFAF0E6, name="Linen"),
    RGBColor(0xFAFAD2, name="LightGoldenRodYellow"),
    RGBColor(0xFDF5E6, name="OldLace"),
    RGBColor(0xFF0000, name="Red"),
    RGBColor(0xFF00FF, name="Magenta"),
    RGBColor(0xFF1493, name="DeepPink"),
    RGBColor(0xFF4500, name="OrangeRed"),
    RGBColor(0xFF6347, name="Tomato"),
    RGBColor(0xFF69B4, name="HotPink"),
    RGBColor(0xFF7F50, name="Coral"),
    RGBColor(0xFF8C00, name="DarkOrange"),
    RGBColor(0xFFA07A, name="LightSalmon"),
    RGBColor(0xFFA500, name="Orange"),
    RGBColor(0xFFB6C1, name="LightPink"),
    RGBColor(0xFFC0CB, name="Pink"),
    RGBColor(0xFFD700, name="Gold"),
    RGBColor(0xFFDAB9, name="PeachPuff"),
    RGBColor(0xFFDEAD, name="NavajoWhite"),
    RGBColor(0xFFE4B5, name="Moccasin"),
    RGBColor(0xFFE4C4, name="Bisque"),
    RGBColor(0xFFE4E1, name="MistyRose"),
    RGBColor(0xFFEBCD, name="BlanchedAlmond"),
    RGBColor(0xFFEFD5, name="PapayaWhip"),
    RGBColor(0xFFF0F5, name="LavenderBlush"),
    RGBColor(0xFFF5EE, name="SeaShell"),
    RGBColor(0xFFF8DC, name="Cornsilk"),
    RGBColor(0xFFFACD, name="LemonChiffon"),
    RGBColor(0xFFFAF0, name="FloralWhite"),
    RGBColor(0xFFFAFA, name="Snow"),
    RGBColor(0xFFFF00, name="Yellow"),
    RGBColor(0xFFFFE0, name="LightYellow"),
    RGBColor(0xFFFFF0, name="Ivory"),
    RGBColor(0xFFFFFF, name="White")
]


def bsearch(L, val):
    lo = 0
    hi = len(L) - 1

    while hi - lo > 1:
        mid = (lo + hi) // 2

        if val < L[mid]:
            hi = mid
        elif val > L[mid]:
            lo = mid
        else:
            hi = lo = mid
            break

    return lo, hi


def rgb(*val):
    color = RGBColor(*val)

    hsbcolors = sorted(rgbcolors, key=lambda e: e.hsb_int)

    lo, hi = bsearch(hsbcolors, color)

    lcolor = hsbcolors[lo]
    rcolor = hsbcolors[hi]

    ldist = lcolor.distance(color)
    rdist = rcolor.distance(color)

    s = "{}, {} is ".format(color.htmlhex, color)

    if ldist == 0 or rdist == 0:
        return s + "a {}".format(lcolor.name if ldist == 0 else rcolor.name)
    else:
        return s + "close to {}".format(lcolor.name if ldist < rdist else rcolor.name)

