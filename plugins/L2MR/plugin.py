""" Limnoria Plugin file for L2MR """
###
# Copyright (c) 2020, Edmund\
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

from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import json
import logging
import string
import urllib.parse as urlparse

import requests
#from bs4 import BeautifulSoup as BS

from supybot import callbacks, schedule, ircdb
from supybot.commands import wrap, optional
try:
    from supybot.i18n import PluginInternationalization
    _ = PluginInternationalization('L2MR')
except ImportError:
    # Placeholder that allows to run the plugin on a bot
    # without the i18n module
    _ = lambda x: x

VOWELS = set('aeiou')
CONSONANTS = set(string.ascii_lowercase) - VOWELS

RADIOS = {
    "Azzurra": {
        "#worldofmedia": "http://stream.ambroservice.net:8080/wom",
        "#python": "http://stream.ambroservice.net:8080/sync",
        "#unity": "http://stream.ambroservice.net:8080/sync",
        "#supybot": "http://stream.ambroservice.net:8080/wom",
    },
    "TelegramIRC": {
        "#-1001429488860": "http://stream.ambroservice.net:8080/wom",
    }
}

ENDPOINT = "status-json.xsl"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:82.0)"
        " Gecko/20100101 Firefox/82.0"
}


DB_PATH = Path(__file__).parent.joinpath("icecast_radios.json")

log = logging.getLogger("supybot")
# def l2mr_songs(songs_html):
    # """ Convert songs HTML to [artist, name] pairs """
    # songs = []
    # log.warning("songs_html: %s", songs_html)
    # soup = BS(songs_html)
    # for song in soup.findAll("div", class_="list_title"):
        # artist = song.find("label")
        # name = song.find("a")
        # if artist and name:
            # songs.append([artist.text.strip(), name.text.strip()])

    # return songs


# def l2mr_unpack(response):
    # """ Normalize JSON response """
    # status = response["status"]
    # songs_html = []
    # listeners = response.get("current_listeners", None)
    # if status == "success" and response.get("display") == "song_name":
        # listeners = int(utils.web.htmlToText(listeners))
        # songs_html = response["html"].replace("\\", "")

    # return {
        # "status": status,
        # "message": response.get("message"),
        # "listeners": listeners,
        # "songs": l2mr_songs("".join(songs_html))
    # }

class RadioData:
    attrs = set(["baseurl", "endpointurl", "listenurl", "webplayerurl",
        "announced_at", "topic", "event", "online", "streamdata"])
    # TODO
    #live_attrs = set(["online", "streamdata"])

    def __init__(self, **kwargs):
        self.data = {}
        for k, v in kwargs.items():
            if k in self.attrs:
                self.data[k] = v

    def __getattr__(self, attr):
        if attr in self.attrs:
            return self.data.get(attr)

    def __setattr__(self, attr, val):
        if attr in self.attrs:
            self.data[attr] = val
        else:
            return super().__setattr__(attr, val)

    def __delattr__(self, attr):
        if attr in self.attrs and attr in self.data:
            del self.data[attr]
        else:
            return super().__delattr__(attr)

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


class L2MR(callbacks.Plugin):
    """listen2myradio.com now playing"""
    threaded = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._radios = defaultdict(dict)
        self._load_radios()

    @wrap # [optional('somethingWithoutSpaces')])
    def radio(self, irc, msg, _): # , arg):
        """ [last]

        Show IceCast radio status (if any) for the current channel
        """
        channel = msg.args[0].lower()
        if not irc.isChannel(channel):
            return

        network = str(irc.network)
        radio = self._get_radio(network, channel)
        if radio is None:
            return

        self._radio_poll(network, channel)
        if radio.online is False:
            irc.reply("{}'s radio is Offline right now.".format(channel))
            return

        radio.announced_at = datetime.now().isoformat()
        show_listeners = self.registryValue('showListeners',
            channel, irc.network)
        irc.reply(self._format_output(radio, show_listeners=show_listeners))

    @wrap([optional('text')])
    def radiotopic(self, irc, msg, args, text):
        """ [topic]
        """
        channel = msg.args[0].lower()
        if not irc.isChannel(channel):
            return

        network = str(irc.network)
        radio = self._get_radio(network, channel)
        if radio is None:
            return

        if ircdb.checkChannelCapability(irc, msg, 'radioop'):
            if (text or "").lower() == "unset":
                del radio.topic

            elif text is not None:
                if "\x03" in text:
                    text = "{}\x0f".format(text)

                radio.topic = text

            self._dump_radios()

        irc.reply("<{}> - {}".format(radio.webplayerurl,
            radio.topic or "No topic set."))

    @wrap(['somethingWithoutSpaces'])
    def autoradio(self, irc, msg, args, state):
        """ [on|off]

        Enable or disable automatic radio link announcement when radio
         is found online. """
        channel = msg.args[0].lower()
        if not irc.isChannel(channel):
            return

        network = str(irc.network)
        radio = self._get_radio(network, channel)
        if radio is None:
            return

        if radio.event is None:
            if state == "on":
                radio.event = schedule.addPeriodicEvent(
                    lambda: self.Proxy(irc.irc, msg, ["radioannounce"]),
                    45,
                    "radioAnnounce-{}:{}".format(irc.network, channel))
        elif state == "off":
            schedule.removeEvent(radio.event)

    @wrap([optional('int')])
    def radioannounce(self, irc, msg, args, every):
        """ <no arguments>

        This command is not meant to be called directly. """
        channel = msg.args[0].lower()
        if not irc.isChannel(channel):
            return

        network = str(irc.network)
        radio = self._get_radio(network, channel)
        if radio is None:
            return

        if every is None:
            every = 300

        now = datetime.now()
        delta = timedelta(seconds=every)
        if radio.announced_at is None:
            radio.announced_at = (now - delta).isoformat()

        announced_at = datetime.strptime(radio.announced_at, "%Y-%m-%dT%H:%M:%S.%f")
        if now >= announced_at + delta:
            self._radio_poll(network, channel)
            if radio.online is False:
                return

            radio.announced_at = now.isoformat()
            self._dump_radios()

            show_listeners = self.registryValue('showListeners',
                channel, irc.network)
            out = self._format_output(radio, show_listeners=show_listeners)
            irc.reply(out)

    #def _radio(self, network, channel):
    #    url = None
    #    if network in RADIOS.keys():
    #        url = RADIOS[network].get(channel)
    #        if url is None:
    #            return None
    #
    #    api_url = ENDPOINT.format(url)
    #    jar = self._sessions[network][channel]
    #    response = requests.get(api_url, headers=HEADERS, cookies=jar)
    #    if response.status_code != 200:
    #        self.log.warning("_radio: HTTP Error %d", response.status_code)
    #        return None
    #
    #    infos = l2mr_unpack(response.json())
    #    if infos["message"] == "Error has Occuered":
    #        self._refresh_sessions()
    #        return self._radio(network, channel)
    #
    #    infos["radio_url"] = url
    #    return infos

    # @wrap([optional('somethingWithoutSpaces')])
    # def radio(self, irc, msg, _, arg):
        # """ [last]

        # Show listen2myradio.com radio status (if any) for the current channel
        # """

        # channel = msg.args[0].lower()
        # if not irc.isChannel(channel):
            # return

        # network = str(irc.network)
        # infos = self._radio(network, channel)
        # if infos is None:
            # return

        # if infos["status"] == "success":
            # title = self._titles[network][channel] or "Listen2MyRadio"
            # out = "\x02{}\x02 <{}> - {{}}".format(title, infos["radio_url"])
            # songs = infos["songs"]
            # if songs:
                # idx = 1 if arg == "last" else 0
                # artist, name = songs[idx]
                # out = out.format("{}{} by {}".format(
                        # "" if idx == 0 else "Last played: ",
                        # name,
                        # artist))
            # else:
                # topic = self._topics[network].get(channel)
                # out = out.format(topic or "Now airing!")

            # listeners = infos["listeners"]
            # show_listeners = self.registryValue('showListeners',
                # channel, irc.network)
            # if listeners and show_listeners:
                # out = "{} ({} listener{})".format(
                    # out,
                    # listeners,
                    # "s" if listeners != 1 else "")

            # irc.reply(out)
        # else:
            # irc.error(infos["message"])

    #def _refresh_sessions(self):
    #    for network, channels in RADIOS.items():
    #        for channel, url in channels.items():
    #            jar = self._sessions[network].get(channel)
    #            if jar is None:
    #                resp = requests.get(url, headers=HEADERS)
    #                jar = resp.cookies
    #                self._sessions[network][channel] = jar
    #            else:
    #                resp = requests.get(url, headers=HEADERS, cookies=jar)
    #
    #            soup = BS(resp.text)
    #            radio_title = soup.find(class_="radio_fm_txt")
    #            if radio_title:
    #                radio_title = radio_title.h1.text.strip()
    #
    #            self._titles[network][channel] = radio_title
    #            api_url = ENDPOINT.format(url)
    #            additional = {
    #                "Origin": url,
    #                "Referer": "{}/".format(url),
    #                "X-Requested-With": "XMLHttpRequest"
    #            }
    #            data = {"action": "getRadioRecentSongs"}
    #            HEADERS.update(additional)
    #            requests.post(api_url, data, headers=HEADERS, cookies=jar)

    def _get_radio(self, network, channel):
        channels = self._radios.get(network)
        if channels is None:
            return None

        radio = channels.get(channel)
        if radio is None:
            return None

        return radio

    def _radio_poll(self, network, channel):
        radio = self._get_radio(network, channel)
        if radio is None:
            return None

        response = requests.get(radio.endpointurl)
        if response.status_code != 200:
            self.log.warning("_radio: HTTP Error %s", response.status_code)
            return None

        stats = response.json()
        icestats = stats.get("icestats")
        if icestats is None:
            self.log.warning("_radio: Icecast Error: 'icestats' not present "
                "in JSON Reply", )
            return None

        sources = icestats.get('source')
        if sources is None:
            radio.online = False
            return False

        if not isinstance(sources, list):
            sources = [sources]

        for source in sources:
            if source["listenurl"] == radio.listenurl:
                radio.streamdata = source
                radio.online = True
                break
        else:
            radio.online = False

        return radio.streamdata or False

    def _format_output(self, radio, *, show_listeners=False):
        data = radio.streamdata
        title = data["server_name"] or "Radio"
        out = ["\x02{}\x02 <{}>".format(title, radio.webplayerurl)]
        listeners = data.get("listeners")
        if show_listeners is True and listeners is not None:
            out[0] = "{} ({} listener{})".format(
                out[0], listeners, "s" if listeners != 1 else "")

        topic = radio.topic
        if topic:
            out.append(topic)

        song = data.get("title")
        if song:
            out.append("Now On-air: {}".format(song))

        return " ~ ".join(out)

    def doJoin(self, irc, msg):
        channel = msg.args[0].lower()
        radio = self._get_radio(str(irc.network), channel)
        if msg.nick != irc.nick and radio and radio.event is not None:
            self.radioannounce(irc, msg, ["180"])

    def _load_radios(self):
        if DB_PATH.exists():
            with open(DB_PATH) as f:
                db = json.load(f)
        else:
            db = None

        for network, channels in RADIOS.items():
            for channel, url in channels.items():
                schema, netloc, path, _, _ = urlparse.urlsplit(url)
                baseloc = netloc.split(":", 1)[0]
                data = {
                    "baseurl": "{}://{}".format(schema, baseloc),
                    "endpointurl": "{}://{}/{}".format(schema, netloc, ENDPOINT),
                    "listenurl": "{}://{}{}".format(schema, netloc, path),
                    "webplayerurl": "{}://{}{}".format(schema, baseloc, path)
                }

                if db is not None:
                    fromdb = db.get(network, {}).get(channel)
                    if fromdb is not None:
                        fromdb.update(data)
                        data = fromdb

                self._radios[network][channel] = RadioData.from_dict(data)

    def _dump_radios(self):
        data = {network: {channel: data.data for channel, data in channels.items()}
            for network, channels in self._radios.items()}

        with open(DB_PATH, "w") as f:
            json.dump(data, f)

    def reload(self):
        """ Called when the plugin is reloaded """
        if self._radios is None:
            return

        for channels in self._radios.values():
            for radio in channels.values():
                if radio.event is None:
                    continue

                try:
                    schedule.removeEvent(radio.event)
                except KeyError:
                    self.log.warning("trying to remove non-existent "
                        "event: %s", radio.event)

                radio.event = None

        self._dump_radios()
        del self._radios

    def die(self):
        self.reload()


Class = L2MR


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
