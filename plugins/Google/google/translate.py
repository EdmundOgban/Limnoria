import urllib.parse as urlparse
import requests

from time import sleep
from urllib.error import HTTPError

from . import gtok

TRANSLATE_API_URL = "https://translate.google.it/translate_a/single"

import logging
log = logging.getLogger("supybot")


def build_query(from_lang, to_lang, *, q, reissue=False):
    # left out: otf=1 ssel=0 tsel=0
    token = gtok.gen_token(q, reissue=reissue)
    query_params = [
        ("client", "webapp"),
        ("sl", from_lang),
        ("tl", to_lang),
        ("hl", "it"),
        ("tk", token),
        ("q", q)
    ]
    features = "at bd ex ld md qca rw rm ss t".split(" ")
    for feature in features:
        query_params.append(("dt", feature))

    encoded_params = urlparse.urlencode(query_params)
    return "{}?{}".format(TRANSLATE_API_URL, encoded_params)


def tr(from_lang, to_lang, *, q, reissue=False):
    url = build_query(from_lang, to_lang, q=q, reissue=reissue)
    hdrs = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:73.0) Gecko/20100101"}
    data = requests.get(url, headers=hdrs, cookies=gtok.COOKIEJAR)
    if data.status_code == 429:
        return tr(from_lang, to_lang, q=q, reissue=True)
    elif data.status_code != 200:
        raise HTTPError(code=data.status_code, msg=data.reason, url=url, hdrs=hdrs, fp=None)

    if not data:
        raise IOError("No data received")

    data = data.json()
    from_lang = data[2]
    tr_data = data[5]
    if tr_data is None or len(tr_data) == 0:
        tr_data = data[0]
        tr_sentences = [tr[0] for tr in tr_data[:-1]]
        if len(tr_sentences) == 0:
            translations = [q]
        else:
            translations = [''.join(tr_sentences)]
    elif len(tr_data) == 1:
        tr_sentence = [tr[2] for tr in tr_data][0]
        translations = [tr[0] for tr in tr_sentence]
    else:
        tr_sentences =  [tr[2] for tr in tr_data]
        translations = [' '.join(tr[0][0] for tr in tr_sentences)]

    return from_lang, to_lang, translations
