import re
import requests
import urllib.parse as urlparse

import mwparserfromhell
import mwparserfromhell.wikicode as mw_wikicode
import mwparserfromhell.nodes as mw_nodes

import logging
log = logging.getLogger("supybot")

WIKI_URL = "https://{}.wikipedia.org/wiki/{}"
mwlink = re.compile("\[\[([^\]]+)\]\]")
mwfmt = re.compile("'{2,5}([^']+)'{2,5}")
mwtemplate = re.compile("{{([^}]+)}}")


class WikiMultipleDefinitions(Exception):
    pass


def _wiki_urlget(lang, params):
    API_URL = "https://{}.wikipedia.org/w/api.php".format(lang)
    params.update({
        "format": "json",
        "formatversion": "2"
    })
    headers = {"User-Agent": "Sleipnir/1.0"}
    req = requests.get(API_URL, headers=headers, params=params)
    log.info(f"GET {API_URL}?{urlparse.urlencode(params)}")
    return req.json()


def _wiki_redirects(title, lang):
    log.info("Wikipedia ENDPOINT _wiki_redirects")
    params = {
        "action": "query",
        "prop": "redirects",
        "titles": title
    }
    return _wiki_urlget(lang, params)


def _wiki_query(title, lang):
    log.info("Wikipedia ENDPOINT _wiki_query")
    params = {
        "action": "query",
        "prop": "revisions",
        "rvprop": "content",
        "rvslots": "main",
        "rvlimit": 1,
        "titles": title
    }
    return _wiki_urlget(lang, params)


def _wiki_expandtemplate(template, lang):
    params = {
        "action": "expandtemplates",
        "prop": "wikitext",
        "text": template
    }
    return _wiki_urlget(lang, params)


# TODO
def _parse_templates():
    pass


def _parse_nodes(wikidoc, lang, *, periods):
    out = []
    partials = []
    for node in wikidoc.nodes:
        # Skip refs
        if hasattr(node, "tag") and node.tag == "ref":
            continue

        strnode = str(node)
        m = mwlink.match(strnode)
        if m:
            content = m.group(1)
            prefixes = ("File", "Image", "Media")
            if any(content.startswith(prefix) for prefix in prefixes):
                # Image node, don't care about that.
                continue

        m = mwtemplate.match(strnode)
        if m:
            content = m.group(1).lower()
            args = content.split("|")
            if len(args) > 1:
                label, *_ = args
            else:
                label = args[0]

            label = label.strip()
            if label.startswith("disambigua"):
                raise WikiMultipleDefinitions
            elif label == "bio" or label.startswith("ipa"):
                node = _wiki_expandtemplate(strnode, lang)
                template_text = node["expandtemplates"]["wikitext"]
                ret = _parse_nodes(mwparserfromhell.parse(template_text),
                    lang, periods=periods)
                out.extend(ret)
                continue
            elif mwlink.match(label) or mwfmt.match(label):
                wkc = mw_wikicode.Wikicode([])
                wkc.append(label)
                node = mw_nodes.wikilink.Wikilink(wkc)

        node_nomarkup = node.__strip__()
        if not node_nomarkup:
            continue

        strnode_nomarkup = str(node_nomarkup)
        if periods:
            if isinstance(node, mw_nodes.text.Text):
                try:
                    a, b = strnode_nomarkup.split(".", 1)
                except ValueError:
                    partials.append(strnode_nomarkup)
                else:
                    partials.extend([a, ".\n"])
                    out.append("".join(partials))
                    partials = [b]
            else:
                partials.append(strnode_nomarkup)
        else:
            out.append(strnode_nomarkup)

    return out + partials


def _build_return(lang, title, text):
    url = WIKI_URL.format(lang, urlparse.quote(title).replace("%20", "_"))
    return url, title, text


def search(title, lang="en", *, periods=True, endpoint=_wiki_query): #, endpoint=_wiki_redirects):
    res = endpoint(title, lang)
    if "query" not in res:
        return _build_return(lang, title, "Something's wrong :\\")

    query = res["query"]
    page = query["pages"][0]
    #if "redirects" in page:
    #    redirect_title = page["redirects"][0]["title"]
    #    log.info(f"Wikipedia found 'redirects' from {title} to {redirect_title}")
    #    return search(title, lang, periods=periods, endpoint=_wiki_redirects)
    #elif endpoint != _wiki_query:
    if endpoint != _wiki_query:
        log.info(f"Wikipedia no redirect, calling _wiki_query({title})")
        return search(title, lang, periods=periods, endpoint=_wiki_query)

    if "revisions" not in page:
        if "normalized" in query:
            normalized = query["normalized"][0]["to"]
            log.info(f"Wikipedia normalized query from {title} to {normalized}")
            return search(normalized, lang, endpoint=_wiki_query)
        else:
            return _build_return(lang, title, "Not found")

    revision = page["revisions"][0]
    ttitle = page["title"]
    text = revision["slots"]["main"]["content"]
    wikidoc = mwparserfromhell.parse(text)
    try:
        ret = _parse_nodes(wikidoc, lang, periods=periods)
    except WikiMultipleDefinitions:
        return _build_return(lang, ttitle, "Multiple definitions available")
    else:
        s = "".join(ret)
        # FIXME: This should be smarter
        if s.startswith("REDIRECT") or s.startswith("RINVIA"):
            _, to = s.split(" ", 1)
            to = to.strip()
            log.info(f"Wikipedia REDIRECT in page from {title} to {to}")
            return search(to, lang)

        return _build_return(lang, ttitle, s.strip())
