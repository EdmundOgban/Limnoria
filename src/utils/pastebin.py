# -*- coding: utf-8 -*-
import urllib.request, urllib.parse, urllib.error
import time

VIS_PUBLIC, VIS_UNLISTED, VIS_PRIVATE = range(3)

class YouShallNotPasteError(Exception):
    pass
class APIError(Exception):
    pass
class BadAPIRequestError(APIError):
    pass
class PostLimitError(APIError):
    pass

class PasteBin(object):
    __instance = None

    def __init__(self):
        self._apikey = "67944cad07ebe69f70d6035b89ce97d1"
        self._lastpaste = 0
        self._expire_codes = ("10M", "1H", "1D", "1W", "2W", "1M", "N")
        self._visibilities = (VIS_PUBLIC, VIS_UNLISTED, VIS_PRIVATE)

    def __new__(cls):
        if PasteBin.__instance is None:
            PasteBin.__instance = object.__new__(cls)
        return PasteBin.__instance

    def paste(self, text, title="", visibility=VIS_UNLISTED, expire_in="10M", format="text"):
        if time.time()-self._lastpaste < 30:
            raise YouShallNotPasteError
        if expire_in not in self._expire_codes:
            expire_in = "10M"
        if visibility not in self._visibilities:
            visibility = VIS_UNLISTED

        res = urllib.request.urlopen(
            "http://pastebin.com/api/api_post.php",
            data=urllib.parse.urlencode([
                ("api_option", "paste"),
                ("api_dev_key", self._apikey),
                ("api_paste_private", visibility),
                ("api_paste_name", title),
                ("api_paste_expire_date", expire_in),
                ("api_paste_format", format),
                ("api_paste_code", text),
                ("api_user_key", ""),
            ]).encode()
        ).read()

        if res.lower().startswith(b"bad api request"):
            raise BadAPIRequestError(res)
        elif res.lower().startswith(b"post limit"):
            raise PostLimitError(res)

        self._lastpaste = time.time()
        return res.decode()
