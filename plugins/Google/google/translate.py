import urllib.parse as urlparse
import requests
from . import gtok

TRANSLATE_API_URL = "https://translate.google.it/translate_a/single"

def build_query(from_lang, to_lang, *, q):
    # left out: otf=1 ssel=0 tsel=0
    query_params = [
        ("client", "webapp"),
        ("sl", from_lang),
        ("tl", to_lang),
        ("hl", "it"),
        ("tk", gtok.gen_token(q)),
        ("q", q)
    ]
    features = "at bd ex ld md qca rw rm ss t".split(" ")
    for feature in features:
        query_params.append(("dt", feature))

    encoded_params = urlparse.urlencode(query_params)
    return "{}?{}".format(TRANSLATE_API_URL, encoded_params)

def tr(from_lang, to_lang, *, q):
    url = build_query(from_lang, to_lang, q=q)
    hdrs = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:73.0) Gecko/20100101"}
    data = requests.get(url, headers=hdrs)
    if not data:
        return '', '', []

    data = data.json()
    from_lang = data[2]
    tr_data = data[5]
    if tr_data is None or len(tr_data) == 0:
        translations = [q]
    elif len(tr_data) == 1:
        tr_sentence = [tr[2] for tr in tr_data][0]
        translations = [tr[0] for tr in tr_sentence]
        #translations = [tr[0] for tr in tr_data[0][2]]
    else:
        tr_sentences =  [tr[2] for tr in tr_data]
        translations = [' '.join(tr[0][0] for tr in tr_sentences)]

    return from_lang, to_lang, translations
