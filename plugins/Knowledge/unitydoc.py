from difflib import SequenceMatcher
import urllib.request
import urllib.parse as urlparse
import json
import sys
import time
import re


UNITY_MANUAL_URL = "https://docs.unity3d.com/Manual"
UNITY_SAPI_URL = "https://docs.unity3d.com/ScriptReference"
UNITY_DOCDATA_URL = "{}/docdata/toc.js?ts={}"


_cached = dict()


# Thanks il_ratto <3
def similarity(a, b):    
    s = SequenceMatcher(a=a, b=b)
    match_a, match_b, size = s.find_longest_match(0, len(a), 0, len(b))
    scaled_size = float(size) / float(min(len(a), len(b)))
    return (s.ratio() + scaled_size) / 2


def _search(content, text, prevcat='', *, scores):
    title = content["title"].strip()
    score = similarity(text.lower(), title.lower())
    path = "/".join([prevcat, title])
    link = content["link"]
    if link not in (None, "null"):
        scores.append([score, path, link])

    for child in (content.get("children") or []):
        _search(child, text, title, scores=scores)

    return max(scores, key=lambda x: x[0])


def _urlget(url, headers={}):
    urlsplt = list(urlparse.urlsplit(url))
    urlsplt[3] = ""
    urlnoquery = urlparse.urlunsplit(urlsplt)
    if urlnoquery not in _cached:
        request = urllib.request.Request(url, headers=headers)
        opener = urllib.request.build_opener()
        _cached[urlnoquery] = opener.open(request).read()

    return _cached[urlnoquery]


def search(q, max_results=100):
    results = []
    for baseurl in (UNITY_MANUAL_URL, UNITY_SAPI_URL):
        hdrs = {
            "Referer": baseurl
        }
        query_url = UNITY_DOCDATA_URL.format(baseurl, int(time.time()))
        page = _urlget(query_url, headers=hdrs)
        mtch = re.match(rb"(?:var )?toc = ({.+})", page, re.DOTALL)
        if mtch:
            content = json.loads(mtch.group(1))
            score, path, link = _search(content, q, scores=[])
            link = "{}/{}.html".format(baseurl, link)
            results.append([score, path, link])

    return sorted(results[:max_results], key=lambda x: x[0], reverse=True)

def main(q):
    confidence, *match = search(q)
    if confidence < 0.6:
        return "Nothing found for ''.".format(q)
    else:
        return "{} => {}".format(*match)


if __name__ == "__main__":
    print(main(sys.argv[1]))

