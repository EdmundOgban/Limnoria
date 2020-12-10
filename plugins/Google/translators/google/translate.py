import json
import re
import urllib.parse as urlparse
from datetime import datetime

import requests

# Data that could possibly change
TRANSLATION_RPCID = "MkEWBc"
WIZDATA_WEBSERVER = "cfb2h"
WIZDATA_API_PATH = "eptZe"
WIZDATA_SID = "FdrFJe"


TRANSLATE_URL = "https://translate.google.it"
TRANSLATE_ENDPOINT = "data/batchexecute"

HDRS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:83.0)"
        " Gecko/20100101 Firefox/83.0",
    "Origin": TRANSLATE_URL,
    "Referer": TRANSLATE_URL + "/"
}

homepage = requests.get(TRANSLATE_URL, headers=HDRS)
wizdata_mtch = re.search(r'window.WIZ_global_data\s*=\s*({.+});', homepage.text)
if wizdata_mtch:
    wizdata = json.loads(wizdata_mtch.group(1))
else:
    raise ValueError("Can't grasp wizdata from {}.".format(TRANSLATE_URL))

cookiejar = homepage.cookies
reqcnt = 0
reqdt = datetime.now()


def gen_reqid():
    global reqcnt
    reqcnt += 1
    return 1 + (3600 * reqdt.hour + 60 * reqdt.minute + reqdt.second) + 10000 * reqcnt


def build_api_url(*, sid=None, reqid=None):
    url = TRANSLATE_URL + wizdata[WIZDATA_API_PATH] + TRANSLATE_ENDPOINT
    return "".join([url, "?", "&".join(
        "{}={}".format(k, v) for k, v in {
            "rpcids": TRANSLATION_RPCID,
            "f.sid": sid or wizdata[WIZDATA_SID],
            "bl": wizdata[WIZDATA_WEBSERVER],
            "_reqid": reqid or gen_reqid(),
            "hl": "it",
            "soc-app": 1,
            "soc-platform": 1,
            "soc-device": 1 ,
            "rt": "c"
        }.items())])


def build_request(from_lang, to_lang, q):
    s = '[[["{}","[[\\"{}\\",\\"{}\\",\\"{}\\",true],[null]]",null,"generic"]]]'
    return {
        "f.req": s.format(TRANSLATION_RPCID, q, from_lang, to_lang)
    }


def gsection(s):
    sectlen, s = s.split("\n", 1)
    sectlen = int(sectlen)-1
    return s[:sectlen], s[sectlen:] 


def gunpack(s):
    hdr, s = s[:6], s[6:]
    trdata, s = gsection(s)
    return json.loads(trdata.replace("\\n", ""))


def translate(from_lang, to_lang, *, q):
    url = build_api_url()
    data = build_request(from_lang, to_lang, q)
    resp = requests.post(url, data=data, headers=HDRS, cookies=cookiejar)
    unpacked = gunpack(resp.text)
    transdata = json.loads(unpacked[0][2])
    try:
        detected_lang = transdata[2]
    except IndexError:
        detected_lang = transdata[1][3]

    translations = transdata[1][0][0][5][0]
    if len(translations) == 2:
        translated, alternatives = translations
        if translated in alternatives:
            translations = alternatives
        else:
            translations = translated + alternatives

    return detected_lang, to_lang, translations

tr = translate
