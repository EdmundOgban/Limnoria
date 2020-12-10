###
# Copyright (c) 2003-2005, Jeremiah Fincher
# Copyright (c) 2010-2011, James McCoy
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
###

import fnmatch
import gzip
import time
import socket
import telnetlib

import re
import urllib.request
import urllib.error
import urllib.parse as urlparse
import html
from bs4 import BeautifulSoup as BS, SoupStrainer

import supybot.conf as conf
import supybot.utils as utils
import supybot.ircmsgs as ircmsgs
import supybot.ircutils as ircutils
import supybot.plugins as plugins
import supybot.callbacks as callbacks
from supybot.commands import *
from supybot.utils.iter import any as supyany
from supybot.utils import minisix
from supybot.i18n import PluginInternationalization, internationalizeDocstring
_ = PluginInternationalization('Internet')

if minisix.PY2:
    builtins = __builtins__
else:
    import builtins

from . import htmlcolors


TITLEABLE_URLS = set([
    "?*.reddit.com", "redd.it", "?*.redd.it",
    "spotify.com", "*.spotify.com",
    "stackoverflow.com", "serverfault.com",
])
YOUTUBE_URLS = set([
    "?*.youtube.com", "youtube.com", "youtu.be"
])


class Internet(callbacks.Plugin):
    """Provides commands to query DNS, search WHOIS databases,
    and convert IPs to hex."""
    threaded = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        #URL_SAFECHARS = r"A-Za-z0-9_~.\-;/?:@=&%()#"
        HOST_SAFECHARS = r"\w~.\-;/?:@=&%()#"
        TLD_SAFECHARS = r"A-Za-z0-9{2,}"
        PATH_SAFECHARS = r"\S"

        self._urlsnarf_re = re.compile("(https?://[{}]+\.[{}]{{2,}})([{}]*)".format(
            HOST_SAFECHARS, TLD_SAFECHARS, PATH_SAFECHARS))
        self._supported_content = ["text/html"]
        self._last_url = dict()
        self._last_tweet_url = dict()
        self._http_codes = dict()
        self._fill_http_codes()

    def _urlget(self, url, *, data=None, browser_ua=False):
        req = urllib.request.Request(url)
        if browser_ua is True:
            req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; WOW64; rv:51.0) Gecko/20100101 Firefox/51.0")
            #req.add_header("User-Agent", "Lynx/2.8.7rel.1 libwww-FM/2.14 SSL-MM/1.4.1 OpenSSL/1.0.2a")
        else:
            req.add_header("User-Agent", "curl/7.70.0")

        urlh = urllib.request.urlopen(req, data)
        if urlh.code != 200:
            desc, _ = self._http_codes[urlh.code]
            raise urllib.error.HTTPError(url=url, code=urlh.code, msg=desc, hdrs=data, fp=urlh)
        else:
            return urlh

    def _fill_http_codes(self):
        urlh = self._urlget("https://www.w3.org/Protocols/rfc2616/rfc2616-sec10.html")
        soup = BS(urlh, "html.parser", parse_only=SoupStrainer("h3"))

        category = "Unknown"
        for entity in soup.findAll("h3"):
            content = entity.contents[1].strip()
            code, desc = content.split(" ", 1)
            try:
                code = int(code)
            except ValueError:
                category = content
            else:
                self._http_codes[code] = (desc, category)

    @internationalizeDocstring
    def dns(self, irc, msg, args, host):
        """<host|ip>

        Returns the ip of <host> or the reverse DNS hostname of <ip>.
        """
        banned_octets = ('192', '172', '127', '10')
        if utils.net.isIP(host):
            hostname = socket.getfqdn(host)
            host8 = host.split('.')[0]
            if hostname == host or host8 in banned_octets:
                irc.reply(_('Host not found.'))
            else:
                irc.reply(hostname)
        else:
            try:
                ips = socket.getaddrinfo(host, None)
                ips = map(lambda x:x[4][0], ips)
                ordered_unique_ips = []
                unique_ips = set()
                for ip in ips:
                    if ip not in unique_ips:
                        ordered_unique_ips.append(ip)
                        unique_ips.add(ip)
                irc.reply(format('%L', ordered_unique_ips))
            except socket.error:
                irc.reply(_('Host not found.'))
    dns = wrap(dns, ['something'])

    _domain = ['Domain Name', 'Server Name', 'domain']
    _netrange = ['NetRange', 'inetnum']
    _registrar = ['Sponsoring Registrar', 'Registrar', 'source']
    _netname = ['NetName', 'inetname']
    _updated = ['Last Updated On', 'Domain Last Updated Date', 'Updated Date',
                'Last Modified', 'changed', 'last-modified']
    _created = ['Created On', 'Domain Registration Date', 'Creation Date',
                'created', 'RegDate']
    _expires = ['Expiration Date', 'Domain Expiration Date']
    _status = ['Status', 'Domain Status', 'status']
    @internationalizeDocstring
    def whois(self, irc, msg, args, domain):
        """<domain>

        Returns WHOIS information on the registration of <domain>.
        """
        if utils.net.isIP(domain):
            whois_server = 'whois.arin.net'
            usertld = 'ipaddress'
        elif '.' in domain:
            usertld = domain.split('.')[-1]
            whois_server = '%s.whois-servers.net' % usertld
        else:
            usertld = None
            whois_server = 'whois.iana.org'
        try:
            sock = utils.net.getSocket(whois_server,
                    vhost=conf.supybot.protocols.irc.vhost(),
                    vhostv6=conf.supybot.protocols.irc.vhostv6(),
                    )
            sock.connect((whois_server, 43))
        except socket.error as e:
            irc.error(str(e))
            return
        sock.settimeout(5)
        if usertld == 'com':
            sock.send(b'=')
        elif usertld == 'ipaddress':
            sock.send(b'n + ')
        sock.send(domain.encode('ascii'))
        sock.send(b'\r\n')

        s = b''
        end_time = time.time() + 5
        try:
            while end_time>time.time():
                time.sleep(0.1)
                s += sock.recv(4096)
        except socket.error:
            pass
        sock.close()
        server = netrange = netname = registrar = updated = created = expires = status = ''
        for line in s.splitlines():
            line = line.decode('utf8').strip()
            if not line or ':' not in line:
                continue
            if not server and supyany(line.startswith, self._domain):
                server = ':'.join(line.split(':')[1:]).strip().lower()
                # Let's add this check so that we don't respond with info for
                # a different domain. E.g., doing a whois for microsoft.com
                # and replying with the info for microsoft.com.wanadoodoo.com
                if server != domain:
                    server = ''
                    continue
            if not netrange and supyany(line.startswith, self._netrange):
                netrange = ':'.join(line.split(':')[1:]).strip()
            if not server and not netrange:
                continue
            if not registrar and supyany(line.startswith, self._registrar):
                registrar = ':'.join(line.split(':')[1:]).strip()
            elif not netname and supyany(line.startswith, self._netname):
                netname = ':'.join(line.split(':')[1:]).strip()
            elif not updated and supyany(line.startswith, self._updated):
                s = ':'.join(line.split(':')[1:]).strip()
                updated = _('updated %s') % s
            elif not created and supyany(line.startswith, self._created):
                s = ':'.join(line.split(':')[1:]).strip()
                created = _('registered %s') % s
            elif not expires and supyany(line.startswith, self._expires):
                s = ':'.join(line.split(':')[1:]).strip()
                expires = _('expires %s') % s
            elif not status and supyany(line.startswith, self._status):
                status = ':'.join(line.split(':')[1:]).strip().lower()
        if not status:
            status = 'unknown'
        try:
            t = telnetlib.Telnet('whois.pir.org', 43)
        except socket.error as e:
            irc.error(str(e))
            return
        t.write(b'registrar ')
        t.write(registrar.split('(')[0].strip().encode('ascii'))
        t.write(b'\n')
        s = t.read_all()
        url = ''
        for line in s.splitlines():
            line = line.decode('ascii').strip()
            if not line:
                continue
            if line.startswith('Email'):
                url = _(' <registered at %s>') % line.split('@')[-1]
            elif line.startswith('Registrar Organization:'):
                url = _(' <registered by %s>') % line.split(':')[1].strip()
            elif line == 'Not a valid ID pattern':
                url = ''
        if (server or netrange) and status:
            entity = server or 'Net range %s%s' % \
                    (netrange, ' (%s)' % netname if netname else '')
            info = filter(None, [status, created, updated, expires])
            s = format(_('%s%s is %L.'), entity, url, info)
            irc.reply(s)
        else:
            irc.error(_('I couldn\'t find such a domain.'))
    whois = wrap(whois, ['lowered'])

    @internationalizeDocstring
    def hexip(self, irc, msg, args, ip):
        """<ip>

        Returns the hexadecimal IP for that IP.
        """
        ret = ""
        if utils.net.isIPV4(ip):
            quads = ip.split('.')
            for quad in quads:
                i = int(quad)
                ret += '%02X' % i
        else:
            octets = ip.split(':')
            for octet in octets:
                if octet:
                    i = int(octet, 16)
                    ret += '%04X' % i
                else:
                    missing = (8 - len(octets)) * 4
                    ret += '0' * missing
        irc.reply(ret)
    hexip = wrap(hexip, ['ip'])

    def _address_or_lasturl(self, address, last_url):
        if not address and not last_url:
            return

        if address:
            for prefix in ("", "https://", "http://"):
                s = prefix + address
                res = self._urlsnarf_re.match(ircutils.stripFormatting(s))
                if res:
                    address, query = map(utils.str.try_coding, res.groups())
                    address = "".join([address, urlparse.quote(query)])
                    break
            else:
                raise urllib.error.URLError(reason="invalid url: '%s'" % address)

        return address or last_url

    @staticmethod
    def _read_chunked(urlh, chunksize=8192):
        buf = b''
        tries = 0
        while True:
            if chunksize * tries > 2 ** 23: # 1 Meg
                break

            data = urlh.read(chunksize)
            if data == b'':
                break

            buf += data
            tries += 1
            if buf[0] == 0x1F and buf[1] == 0x8B:
                buf += urlh.read()
                buf = gzip.decompress(buf)

            yield buf

    def _title(self, url, *, youtube=False, autotitle=False):
        L = list(urlparse.urlsplit(url))
        L[1] = L[1].encode('idna').decode('ascii')
        url = urlparse.urlunsplit(L)

        try:
            urlh = self._urlget(url)
        except urllib.error.HTTPError as e:
            if e.code in (403, 404, 502, 503):
                urlh = self._urlget(url, browser_ua=True)
            else:
                raise

        info = urlh.info()
        if info.get_content_type() not in self._supported_content:
            if autotitle:
                return
            s = "<%s>: Content-Type: %s - Content-Length: %s"
            return s % (url, info["Content-Type"], info["Content-Length"])

        try:
            charset = info.get_charsets()[0] or "utf8"
        except IndexError:
            charset = "ascii"

        title = None
        ogtitle = None
        match_text = ""
        for webpage in self._read_chunked(urlh):
            if not title:
                title = re.search(b"<title[^>]*>(.+?(?=</title>))", webpage, re.DOTALL | re.I)
            if not ogtitle:
                ogtitle = re.search(b"<meta property=['\"]og:title['\"] content=['\"]([^'\"]+)['\"]", webpage, re.DOTALL | re.I)

            if youtube:
                if ogtitle:
                    match_text = ogtitle.group(1)
            elif title or ogtitle:
                if title and ogtitle:
                    match_text = title.group(1)
                elif ogtitle:
                    match_text = ogtitle.group(1)
                else:
                    match_text = (ogtitle or title).group(1)

            if match_text:
                title_text = html.unescape(match_text.strip().decode(charset))
                return "Title <%s>: %s" % (utils.str.shorten(url, 45), title_text)

    def _checkpoint(self):
        t = time.monotonic() - self._t
        self._t = time.monotonic()

        return t

    @wrap(['channeldb', optional('text')])
    def title(self, irc, msg, args, channel, address):
        """ [url] """
        channel = channel.lower()
        last_url = self._last_url.get(channel)
        url = self._address_or_lasturl(address, last_url)
        if url is None:
            return

        title = self._title(url)
        if title:
            irc.reply(title)

    ## Test cases
    ##https://twitter.com/parcesepulto/status/1243664062300504070
    ##https://twitter.com/LucaCellamare/status/1243682458698223617
    ##https://twitter.com/emmevilla/status/1245463860909346824/photo/1
    ##https://twitter.com/ThingsWork/status/1243648203884388352
    ##https://twitter.com/GDGC240977/status/1267546417473748992
    ##https://twitter.com/PlayStation/status/1267525525825900549
    ##https://twitter.com/Dark_Tesla/status/1267551166864461826
    ## FAIL: https://twitter.com/nick_kapur/status/1283261781008437248
    ## FAIL: https://twitter.com/jasonschreier/status/1285527461300711424
    def _tweet(self, url):
        # Replace *twitter.com with mobile.twitter.com
        urlsplt = list(urlparse.urlsplit(url))
        urlsplt[1] = "mobile.twitter.com"
        url = urlparse.urlunsplit(urlsplt)

        soup = BS(self._urlget(url))
        topdoc = soup.find("table", class_="main-tweet")
        if topdoc is None:
            return

        header = topdoc.find("tr")
        tweet_content = topdoc.find("td", class_="tweet-content")
        try:
            name = header.find("strong").text
        except AttributeError:
            name = None
        else:
            name = name.strip()

        try:
            account = header.find("span", class_="username").text
        except AttributeError:
            account = None
        else:
            verified = "\u2713 " if header.find("a", class_="badge") else ""
            account = "{}{}".format(verified, account.strip())

        tweet_text = tweet_content.find("div", class_="tweet-text")
        if tweet_text and tweet_text.text.strip():
            content = []
            has_video = False
            for child in tweet_text.div:
                text = ""
                try:
                    if "twitter_external_link" in child.attrs["class"]:
                        url = child.attrs["data-url"]
                        if "/video/" in url:
                            has_video = True
                            text = url
                    else:
                        text = child.text
                except AttributeError:
                    text = child

                text = text.strip()
                if text:
                    content.append(text)

            if has_video is False:
                for img in tweet_content.findAll("img"):
                    url = img["src"]
                    if url.count(":") > 1:
                        url = url.rsplit(":", 1)[0]

                    content.append(url.strip())

            return name, account, " ".join(content)

    def _tweet_format(self, name, account, tweet):
        tweet = re.sub(r"\s*\n+\s*", " | ", tweet)

        if name is None and account is None:
            s = "Tweet ({}): {}".format(utils.str.shorten(url, 50), tweet)
        elif name is None or account is None:
            s = "Tweeted by {}: {}".format(name or account, tweet)
        else:
            s = "Tweeted by {} ({}): {}".format(name, account, tweet)

        return s

    @wrap(['channeldb', optional('text')])
    def tweet(self, irc, msg, args, channel, address):
        """ [url] """
        channel = channel.lower()
        last_url = self._last_tweet_url.get(channel)
        url = self._address_or_lasturl(address, last_url)
        if url is None:
            return

        res = self._tweet(url)
        if res:
            irc.reply(self._tweet_format(*res))


    @wrap(['channeldb'])
    def lasturl(self, irc, msg, args, channel):
        """ """
        channel = channel.lower()
        if channel in self._last_url:
            irc.reply(self._last_url[channel], prefixNick=True)

    @wrap(['channeldb'])
    def lasttweet(self, irc, msg, args, channel):
        """ """
        channel = channel.lower()
        if channel in self._last_tweet_url:
            irc.reply(self._last_tweet_url[channel], prefixNick=True)

    @wrap(['long'])
    def http(self, irc, msg, args, code):
        """<http_code> """
        try:
            desc, category = self._http_codes[code]
            irc.reply("%s, HTTP %d %s" % (category, code, desc), prefixNick=True)
        except KeyError:
            irc.error("unknown HTTP code: %d" % code)

    @wrap(["text"])
    def rgb(self, irc, msg, args, text):
        """<[#]xxxxxx>|<r, g, b>
        
        Returns the HTML color name or the closest color.
        """
        args = []
        color = text.split()
        try:
           if len(color) == 3:
                args = [int(c) for c in color]
           elif len(color) == 1:
                args = color
           else:
                raise ValueError
        except ValueError:
            irc.error("Invalid input: {}".format(color))
        else:
            irc.reply(htmlcolors.rgb(*args), prefixNick=True)

    def _snarfUrl(self, network, channel, text):
        channel = channel.lower()
        res = self._urlsnarf_re.search(ircutils.stripFormatting(text))
        if res:
            url, query = map(utils.str.try_coding, res.groups())
            url = "".join([url, query])
            scheme, netloc, path, query, fragment = list(urlparse.urlsplit(url))
            path = urlparse.quote(path)
            qsl_quoted = [(urlparse.quote(a), urlparse.quote(b))
                for a, b in urlparse.parse_qsl(query)]
            query = urlparse.urlencode(qsl_quoted)
            url = urlparse.urlunsplit([scheme, netloc, path, query, fragment])
            splitresult = urlparse.urlsplit(url)

            if splitresult.netloc.endswith("twitter.com"):
                self._last_tweet_url[channel] = url
            else:
                self._last_url[channel] = url

            return url, splitresult

    def _autotitle_snarf(self, irc, msg, text):
        channel = plugins.getChannel(msg.args[0]).lower()
        splitresult = self._snarfUrl(irc.network, channel, text)
        botNicks = self.registryValue("botNames", channel).split()
        if supyany(msg.nick.startswith, botNicks):
            return

        if splitresult:
            text = None
            url, urlsplt = splitresult
            isYtUrl = builtins.any(fnmatch.fnmatch(urlsplt.netloc, url_wcard)
                for url_wcard in YOUTUBE_URLS)
            isTitleableUrl = builtins.any(fnmatch.fnmatch(urlsplt.netloc, url_wcard)
                for url_wcard in TITLEABLE_URLS)
            isTweetUrl = urlsplt.netloc.endswith("twitter.com")
            if ((urlsplt.path.lstrip("/") or urlsplt.query)
                and self.registryValue("ytAutoTitle", channel)):
                if isYtUrl:
                    text = self._title(url, youtube=True, autotitle=True)
                elif isTitleableUrl:
                    text = self._title(url, autotitle=True)
                elif isTweetUrl: # and self.registryValue("autoTweet", channel):
                    res = self._tweet(url)
                    if res:
                        text = self._tweet_format(*res)

            return text

    # This is needed in case of a message containing an HTTP link which starts with
    # someone's nick that incidentally begins with the selected bot commands prefix.
    def invalidCommand(self, irc, msg, tokens):
        if not irc.isChannel(msg.args[0]):
            return

        text = " ".join(tokens)
        title = self._autotitle_snarf(irc, msg, text)
        if title is not None:
            irc.reply(title)

    def doPrivmsg(self, irc, msg):
        if not irc.isChannel(msg.args[0]):
            return

        if callbacks.addressed(irc.nick, msg):
            return

        if ircmsgs.isAction(msg):
            text = ircmsgs.unAction(msg)
        elif not ircmsgs.isCtcp(msg):
            text = msg.args[1]
        else:
            return

        title = self._autotitle_snarf(irc, msg, text)
        if title is not None:
            irc.reply(title)

    _ddgSearchUrl = 'https://duckduckgo.com/html/?q={}'
    def _ddg(self, text):
        searchurl = self._ddgSearchUrl.format(utils.web.urlquote_plus(text))
        page = BS(self._urlget(searchurl, browser_ua=True))

        dym = page.find("div", id="did_you_mean")
        if dym is not None:
            return self._ddg(dym.find_all("a")[-1].text)

        results = page.find_all("div", class_="result__body")
        if len(results) == 1:
            return []

        r = []
        for result in results:
            anchor = result.find("a", class_="result__a")
            ad = result.find("a", class_="badge--ad")
            if anchor is None or ad:
                continue

            description = result.find("a", class_="result__snippet")
            r.append({
                "title": anchor.text.strip(),
                "url": anchor["href"],
                "description": description.text.strip() if description else '',
            })

        return r

    def _pre_command(self, text):
        text = text or ""
        try:
            opt, text = text.split(":", 1)
            opt = int(opt)
        except ValueError:
            opt = 0

        text = ircutils.stripFormatting(text.lower().strip())
        return text, opt

    @wrap(["text"])
    def ddg(self, irc, msg, args, text):
        """<search>

        Searches duckduckgo.com for the given string.
        """
        text, idx = self._pre_command(text)

        try:
            result = self._ddg(text)[idx]
        except IndexError:
            irc.reply("Can't find what you are looking for.")
        else:
            
            text = utils.str.shorten(text, 30)
            title = ircutils.bold(result["title"])
            url = result["url"]
            irc.reply("DuckDuckGo ({}): {} <{}>".format(text, title, url))

Internet = internationalizeDocstring(Internet)

Class = Internet


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
