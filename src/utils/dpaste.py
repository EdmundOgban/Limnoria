# -*- coding: utf-8 -*-
import urllib.request, urllib.parse
import time

PASTEBIN_API = "https://dpaste.com/api/"
DEFAULT_EXPIRY = 1

class YouShallNotPasteError(Exception):
    pass


class PasteBin(object):
    __instance = None

    def __init__(self):
        self._lastpaste = 0

    def __new__(cls):
        if PasteBin.__instance is None:
            PasteBin.__instance = object.__new__(cls)
        return PasteBin.__instance

    def paste(self, text, title="", format="text", expiry=DEFAULT_EXPIRY):
        #if time.time()-self._lastpaste < 30:
        #    raise YouShallNotPasteError

        if not 1 <= expiry <= 365:
            expiry = DEFAULT_EXPIRY

        res = urllib.request.urlopen(
            PASTEBIN_API,
            data=urllib.parse.urlencode({
                "content": text,
                "title": title,
                "syntax": format,
                "expiry_days": expiry
            }).encode()
        ).read()
        self._lastpaste = time.time()
        return res.decode().strip()
