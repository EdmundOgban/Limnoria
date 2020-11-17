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

from . import covidit_stats
from . import unitydoc
from . import wikipedia
from . import wikilangs


class Knowledge(callbacks.Plugin):
    """Knowledge Brings Fear"""
    threaded = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

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
    def pydoc(self, irc, msg, args, text):
        """ <query>
        search inside the Python 3 documentation using Google."""
        s = self._gsite(irc, msg, "docs.python.org/3", text)
        irc.reply(s)

    @wrap([getopts({'pfx': 'text'}), "url", "text"])
    def gsite(self, irc, msg, args, optlist, url, query):
        """ [--pfx prefix] <url> <query>
        search on arbitrary sites using Google."""
        s = self._gsite(irc, msg, url, query)
        if optlist:
            k, v = optlist[0]
            s = "{}: {}".format(v, s)

        irc.reply(s)

    @wrap(["text"])
    def rust(self, irc, msg, args, text):
        """ <query>
        search inside the Rust documentation using Google."""
        s = self._gsite(irc, msg, "doc.rust-lang.org", text)
        irc.reply(s)

    @wrap(["text"])
    def meme(self, irc, msg, args, text):
        """ <query>
        search on knowyourmeme.com using Google."""
        s = self._gsite(irc, msg, "knowyourmeme.com/memes", text)
        irc.reply(s)

    @wrap(["text"])
    def wiki(self, irc, msg, args, query, DEFAULT_LANG="it"):
        """ [lang]:<query>
            Search on it.wikipedia.org."""
        try:
            lang, query = query.split(":", 1)
        except ValueError:
            lang = DEFAULT_LANG
        else:
            if lang not in wikilangs.LANGS:
                lang = DEFAULT_LANG

        s = "Wikipedia ({}): {} <{}>"
        url, title, res = wikipedia.search(query, lang)
        result = res.split("\n")[0]
        irc.reply(s.format(title, result, url))

    def doPrivmsg(self, irc, msg):
        if callbacks.addressed(irc.nick, msg):
            return

        if msg.nick not in ('Svadilfari', 'Edmund\\'):
            return

        out = covidit_stats.feed(msg.args[1])
        if out is False:
            irc.reply("not going back in time, sorry.", prefixNick=True)
        elif out:
            _,_,_, dinfected,_,_, _,_,_, _,_,_, dtested,_,_, *span = out
            *out, _,_,_, _,_ = out
            ratio = dinfected / dtested * 100
            irc.reply(("Italy: New cases: {} ({}{:.1f}%);"
                " Infected: {} ({}{:.1f}%); Deaths: {} ({}{:.1f}%);"
                " Recovered: {} ({}{:.1f}%); Infected/Tested: {:.1f}%; Span: {} day{}").format(*out, ratio, *span))

    def die(self):
        covidit_stats.dump()

Class = Knowledge


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
