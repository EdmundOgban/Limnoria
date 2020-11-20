# -*- coding: utf-8 -*-
import urllib.request, urllib.parse, urllib.error
import time


ONETIME = "onetime"
ONE_HOUR = "3600"
ONE_WEEK = "604800"
ONE_MONTH = "2592000"
NEVER = "never"

EXPIRY_TIMES = {ONETIME, ONE_HOUR, ONE_WEEK, ONE_MONTH, NEVER}
PASTEBIN_API = "https://dpaste.org/api/"
DEFAULT_EXPIRY = ONE_HOUR


class YouShallNotPaste(Exception):
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
        gracetime = time.monotonic() - self._lastpaste
        if gracetime < 4:
            time.sleep(4 - gracetime)

        if expiry not in EXPIRY_TIMES:
            expiry = DEFAULT_EXPIRY

        req = urllib.request.Request(
            PASTEBIN_API,
            data=urllib.parse.urlencode({
                "format": "url",
                "expires": expiry,
                "content": text
            }).encode()
        )
        req.add_header("User-Agent", "curl/7.72.0")

        try:
            res = urllib.request.urlopen(req)
        except urllib.error.HTTPError as e:
            raise YouShallNotPaste(str(e))
        else:
            if res.code == 200:
                self._lastpaste = time.monotonic()
                return res.read().decode().strip()
            else:
                raise YouShallNotPaste("HTTP Error {}".format(res.code))
