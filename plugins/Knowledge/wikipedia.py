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


def _wikidata_urlget(lang, params):
    API_URL = "https://www.wikidata.org/w/api.php"
    params.update({
        "format": "json",
        "formatversion": "2"
    })
    headers = {"User-Agent": "Sleipnir/1.0"}
    req = requests.get(API_URL, headers=headers, params=params)
    log.info(f"GET {API_URL}?{urlparse.urlencode(params)}")
    return req.json()


def _wikidata_query(title, lang):
    log.info("Wikipedia ENDPOINT _wikidata_query")
    params = {
        "action": "query",
        "list": "search",
        "srsearch": title,
        "srlimit": 1
    }
    return _wikidata_urlget(lang, params)


def _wikidata_entities(id, lang):
    log.info("Wikipedia ENDPOINT _wikidata_entities")
    params = {
        "action": "wbgetentities",
        "ids": id
    }
    return _wikidata_urlget(lang, params)


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
        "redirects": "",
        "rvprop": "content",
        "rvslots": "main",
        "rvlimit": 1,
        "titles": title
    }
    return _wiki_urlget(lang, params)


def _wiki_opensearch(title, lang):
    log.info("Wikipedia ENDPOINT _wiki_opensearch")
    params = {
        "action": "opensearch",
        "search": title,
        "namespace": 0
    }
    return _wiki_urlget(lang, params)


def _wiki_expandtemplate(template, lang):
    log.info("Wikipedia ENDPOINT _wiki_expandtemplate")
    params = {
        "action": "expandtemplates",
        "prop": "wikitext",
        "text": template
    }
    return _wiki_urlget(lang, params)


# TODO
def _parse_templates():
    pass


def _unwanted_node(node):
    if hasattr(node, "tag") and node.tag == "ref":
        # Skip refs
        return True

    strnode = str(node)
    m = mwlink.match(strnode)
    if m:
        content = m.group(1)
        prefixes = ("File", "Image", "Media")
        if any(content.startswith(prefix) for prefix in prefixes):
            # Image node, don't care about that.
            return True

    return False

def _parse_nodes(wikidoc, lang, *, periods):
    out = []
    partials = []
    for node in wikidoc.nodes:
        if _unwanted_node(node):
            continue

        #if isinstance(node, mw_nodes.template.Template):
        strnode = str(node)
        m = mwtemplate.match(strnode)
        if m:
            #args = node.params
            content = m.group(1).lower()
            args = content.split("|")
            if len(args) > 1:
                label, *_ = args
            else:
                label = args[0]
            #elif len(args) == 1:
            #    label = args[0]
            #else:
            #    continue

            label = label.strip()
            if label.startswith("disambigua"):
                raise WikiMultipleDefinitions
            elif mwlink.match(label) or mwfmt.match(label):
                wkc = mw_wikicode.Wikicode([])
                wkc.append(label)
                node = mw_nodes.wikilink.Wikilink(wkc)
            elif label == "bio": # TODO: or label.startswith("ipa"):
                node = _wiki_expandtemplate(str(node), lang)
                template_text = node["expandtemplates"]["wikitext"]
                ret = _parse_nodes(mwparserfromhell.parse(template_text),
                    lang, periods=periods)
                log.info(f"ret: {ret}")
                out.extend(ret)
                continue

        node_nomarkup = node.__strip__()
        if not node_nomarkup:
            continue

        strnode_nomarkup = str(node_nomarkup)
        if periods:
            # Check that text is not in a markup element
            if isinstance(node, mw_nodes.text.Text):
                # Check if we've encountered the last sentence
                try:
                    a, b = strnode_nomarkup.split(".", 1)
                except ValueError:
                    partials.append(strnode_nomarkup)
                else:
                    # Check that there are at least 3 characters between space and
                    # dot, the word doesn't start with a parenthesis, and it's not
                    # a number.
                    try:
                        x, y = a.rsplit(" ", 1)
                    except ValueError:
                        pass
                    else:
                        if len(y) < 3 or y[0] in "(<[{" or y.isdigit():
                            partials.append(strnode_nomarkup)
                            continue

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


def _wiki_page(title, lang, *, periods):
    res = _wiki_query(title, lang)
    if "query" not in res:
        return _build_return(lang, title, "Something's wrong :\\")

    query = res["query"]
    page = query["pages"][0]
    if "revisions" not in page:
        return _build_return(lang, title, "Not found")

    revision = page["revisions"][0]
    ttitle = page["title"]
    text = revision["slots"]["main"]["content"]
    wikidoc = mwparserfromhell.parse(text)
    try:
        ret = _parse_nodes(wikidoc, lang, periods=periods)
    except WikiMultipleDefinitions:
        # TODO: Better handling of multiple definitions
        return _build_return(lang, ttitle, "Multiple definitions available")
    else:
        return _build_return(lang, ttitle, "".join(ret).strip())


def search(title, lang="en", *, periods=True):
    _, keywords, _, _ = _wiki_opensearch(title, lang)
    if keywords:
        term = keywords[0]
    else:
        res = _wikidata_query(title, lang)
        if "query" not in res:
            return _build_return(lang, title, "Something's wrong :\\")

        searchres = res["query"]["search"]
        if not searchres:
            return _build_return(lang, title, "Not found")

        entity_id = searchres[0]["title"]
        res = _wikidata_entities(entity_id, lang)
        if "error" in res:
            return _build_return(lang, title, "Something's wrong :\\")

        entity = res["entities"][entity_id]
        labels = entity["labels"]
        aliases = entity["aliases"]
        if lang in labels:
            term = labels[lang]["value"]
        elif lang in aliases:
            term = aliases[lang][0]["value"]
        else:
            return _build_return(lang, title, "Not found")

    return _wiki_page(term, lang, periods=periods)
