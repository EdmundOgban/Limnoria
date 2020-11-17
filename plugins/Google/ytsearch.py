import json
import re
import urllib.request as urlrequest
import urllib.parse as urlparse
import logging

YT_SEARCHURL = "https://www.youtube.com/results"
ytdatare = re.compile(r'var ytInitialData\s*=\s*({.+});')

log = logging.getLogger("supybot")

def ytdenest(data):
    path = [
        "contents",
        "twoColumnSearchResultsRenderer",
        "primaryContents",
        "sectionListRenderer",
        "contents",
    ]

    for item in path:
        data = data[item]

    for contents in data:
        if "itemSectionRenderer" not in contents:
            continue

        yield contents["itemSectionRenderer"]["contents"]


def ytIsVerified(result):
    try:
        badge = result["ownerBadges"][0]["metadataBadgeRenderer"]["style"]
    except (IndexError, KeyError):
        verified = False
    else:
        verified = badge == "BADGE_STYLE_TYPE_VERIFIED"

    return verified


def ytVideoRenderer(data):
    result = data["videoRenderer"]
    url = result["navigationEndpoint"]["commandMetadata"]["webCommandMetadata"]["url"]
    title = result["title"]["runs"][0]["text"]
    uploaded_by = result["ownerText"]["runs"][0]["text"]
    verified = ytIsVerified(result)
    metrics = result["viewCountText"].get("simpleText", "")
    runtime = result.get("lengthText", {"simpleText": ""})["simpleText"]
    return url, "video", title, uploaded_by, verified, metrics, runtime


def ytPlaylistRenderer(data):
    result = data["playlistRenderer"]
    url = result["navigationEndpoint"]["commandMetadata"]["webCommandMetadata"]["url"]
    title = result["title"]["simpleText"]
    uploaded_by = result["shortBylineText"]["runs"][0]["text"]
    verified = ytIsVerified(result)
    metrics = result["videoCount"]
    runtime = result["videos"][0]["childVideoRenderer"]["lengthText"]["simpleText"]
    return url, "playlist", title, uploaded_by, verified, metrics, runtime


def ytChannelRenderer(data):
    result = data["channelRenderer"]
    url = result["navigationEndpoint"]["browseEndpoint"]["canonicalBaseUrl"]
    title = result["title"]["simpleText"]
    uploaded_by = None
    verified = ytIsVerified(result)
    metrics = result["subscriberCountText"]["simpleText"]
    runtime = None
    return url, "channel", title, uploaded_by, verified, metrics, runtime


def ytRadioRenderer(data):
    result = data["radioRenderer"]
    import logging
    log = logging.getLogger("supybot")
    log.warn(str(result))
    url = result["navigationEndpoint"]["commandMetadata"]["webCommandMetadata"]["url"]
    title = result["title"]["simpleText"]
    #uploaded_by = result["shortBylineText"]["simpleText"]
    uploaded_by = "YouTube"
    verified = False
    metrics = result["videoCountText"]["runs"][0]["text"]
    runtime = result["videos"][0]["childVideoRenderer"]["lengthText"]["simpleText"]
    return url, "radio", title, uploaded_by, verified, metrics, runtime


def ytget(query):
    query = urlparse.quote(query)
    url = "{}?search_query={}".format(YT_SEARCHURL, query)
    urlh = urlrequest.urlopen(url)
    return urlh.read().decode()


def constrain(val, lower, upper):
    return max(min(val, upper), lower)


renderers = {
    "videoRenderer": ytVideoRenderer,
    "playlistRenderer": ytPlaylistRenderer,
    "channelRenderer": ytChannelRenderer,
    "radioRenderer": ytRadioRenderer,
}
def search(query, idx=1):
    ytpage = ytget(query)
    ytdatamtch = ytdatare.search(ytpage)
    if not ytdatamtch:
        log.warn("youtube.search: no ytdatamatch.")
        return

    results = []
    ytwhole = json.loads(ytdatamtch.group(1))
    for ytdata in ytdenest(ytwhole):
        for data in ytdata:
            renderer = list(data.keys()).pop()
            f = renderers.get(renderer)
            if f is not None:
                results.append(f(data))

    if results:
        idx = constrain(idx, 1, len(results))
        return results[idx-1]
