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

from supybot import utils, plugins, ircutils, callbacks
from supybot.commands import *
try:
    from supybot.i18n import PluginInternationalization
    _ = PluginInternationalization('Knowledge')
except ImportError:
    # Placeholder that allows to run the plugin on a bot
    # without the i18n module
    _ = lambda x: x

import re
from datetime import datetime, timedelta

from . import unitydoc
from . import wikipedia
from collections import namedtuple, deque

Stat = namedtuple("Stat", ["value", "delta"])
DayStat = namedtuple("DayStat", ["total", "infected", "deaths", "recovered", "date"])


class Knowledge(callbacks.Plugin):
    """Knowledge Brings Fear"""
    threaded = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.covidit_stats = deque(maxlen=2)

    @wrap(["text"])
    def unityidx(self, irc, msg, args, text):
        """ <query>
        search inside the Unity User Manual."""

        matches = unitydoc.search(text)
        highest_score, *_ = matches[0]
        if highest_score < 0.6:
            irc.reply("Nothing found for '{}'.".format(text))
        else:
            results = ("{}: {}".format(path, url) for _, path, url in matches)
            irc.reply("\n".join(results))

    def _check_for_google(self, irc):
        callbacks = {callback.name(): callback for callback in irc.callbacks}

        try:
            google = callbacks["Google"]
        except KeyError:
            raise KeyError("Google plugin is not loaded.")
        else:
            return google

    def _gsite(self, irc, msg, site, query):        
        text = "{} site:{}".format(query.strip("| "), site)
        google = self._check_for_google(irc)
        data = google.search(text, msg.channel, irc.network, dict(language="en"))
        ret = google.formatData(data, bold=True, max=1, onetoone=True)
        return ret[0]

    @wrap(["text"])
    def unity(self, irc, msg, args, text):
        """ <query>
        search inside the Unity User Manual using Google."""
        s = self._gsite(irc, msg, "docs.unity3d.com", text)
        irc.reply(s)

    @wrap(["text"])
    def meme(self, irc, msg, args, text):
        """ <query>
        search on knowyourmeme.com using Google."""
        s = self._gsite(irc, msg, "knowyourmeme.com/memes", text)
        irc.reply(s)

    @wrap(["text"])
    def wiki(self, irc, msg, args, query):
        """ <query>
            Search on it.wikipedia.org."""
        lang = "it"
        s = "Wikipedia ({}): {} - {}"
        url, title, res = wikipedia.search(query, lang)
        result = res.split("\n")[0]
        irc.reply(s.format(title, result, url))

    covidit_re = re.compile("Italy: "
                            r"Total cases: (\d+).+"
                            r"Infected: (\d+).+"
                            r"Deaths: (\d+).+"
                            r"Recovered: (\d+).+"
                            r"Date: (.+)$")
    def doPrivmsg(self, irc, msg):
        if callbacks.addressed(irc.nick, msg):
            return

        if msg.nick not in ('Svadilfari', 'Edmund\\'):
            return

        m = self.covidit_re.match(msg.args[1])
        if m:
            *cur_vals, date = m.groups()
            cur_date = datetime.strptime(date, "%Y-%m-%dT%H:%M:%S")
            cur_stat = [*([int(val), 1] for val in cur_vals), cur_date]
            if (len(self.covidit_stats) < 2
                or cur_date - self.covidit_stats[0][-1] >= timedelta(days=2)):
                self.covidit_stats.append(cur_stat)
                if len(self.covidit_stats) == 1:
                    return

            prev_stat = self.covidit_stats[-2]
            out = []
            for prev_val, cur_val in zip(prev_stat, cur_stat[:-1]):
                delta = cur_val[0] - prev_val[0]
                prev_delta = prev_val[1]
                percent = (delta - prev_delta) / abs(prev_delta) * 100
                cur_val[1] = delta
                out.extend([delta, '+' if percent > 0 else '', percent])

            out_s = ("Italy: New cases: {} ({}{:.1f}%);"
                     " Infected: {} ({}{:.1f}%); Deaths: {} ({}{:.1f}%);"
                     " Recovered: {} ({}{:.1f}%)")
            irc.reply(out_s.format(*out))

Class = Knowledge


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
