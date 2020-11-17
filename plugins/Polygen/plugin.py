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

import glob
import html
import os.path
import pathlib
import random
import subprocess
import time
import urllib.request, urllib.parse, urllib.error

from collections import defaultdict
from subprocess import Popen, PIPE

from bs4 import BeautifulSoup as BS

from supybot import utils, plugins, ircutils, callbacks, ircmsgs
from supybot.commands import *
try:
    from supybot.i18n import PluginInternationalization
    _ = PluginInternationalization('Polygen')
except ImportError:
    # Placeholder that allows to run the plugin on a bot
    # without the i18n module
    _ = lambda x: x


LINES_BEFORE_PASTEBIN = 6
LINELEN_BEFORE_PASTEBIN = 800
GRAMMAR_PATH = os.path.expanduser("~/.local/share/polygen/grammars/")
GRAMMAR_EXT = ".grm"


def _get_polygen(path):
    try:
        proc = subprocess.run(["polygen", path], capture_output=True)
    except FileNotFoundError:
        raise FileNotFoundError("Polygen executable was nowhere to be found.")
    else:
        stdout = utils.str.try_coding(proc.stdout)
        stderr = utils.str.try_coding(proc.stderr)
        out = stderr or html.unescape(stdout)
        return [line for line in out.split("\n") if line]


def _get_polygen_fromsite(path):
    urlh = urllib.request.urlopen('https://polygen.org%s' % path)    
    soup = BS(urlh).find("div", {"class": "generation"})
    if not soup:
        irc.error("Cannot retrieve category '%s'." % cat)
        return

    out = []
    for line in soup.renderContents().decode().split("<br/>"):
        line = html.unescape(line.strip())
        if len(line) > 0:
            out.append(line)

    urlh.close()
    return out


def _get_categories(from_):
    categories = {}

    if from_ == "website":
        soup = BS(urllib.request.urlopen("http://polygen.org/it"))
        for elem in soup.findAll("div", {"class": "accordion-grammar"}):
            href = elem.a["href"]
            cat = href.rsplit("/", 1)[1].rsplit(".", 1)[0]
            categories[cat] = href
    elif from_ == "filesystem":
        path = pathlib.PurePath(GRAMMAR_PATH).joinpath("*" + GRAMMAR_EXT)
        for filename in glob.glob(str(path)):
            fname_path = pathlib.PurePath(filename)
            categories[fname_path.stem] = filename               

    return categories


class Polygen(callbacks.Plugin):
    """Polygeb"""
    threaded = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.umodes = defaultdict(list)
        self._got_umodes = False

    def _polygen_help(self, irc, cats):
        sorted_cats = sorted(cats)

        try:
            s = "* Polygen: available categories\n . %s" % "\n . ".join(sorted_cats)
            pasteurl = utils.web.pb_inst.paste(s, title="Polygen help")
        except Exception:
            irc.reply(format('Valid categories are: %L', sorted_cats))
        else:
            irc.reply("available Polygen categories: %s" % pasteurl, prefixNick=True)

    def _pre_command(self, irc, msg, text):
        text = text or ""
        try:
            opt, text = text.split(":", 1)
        except ValueError:
            opt = ""

        if self._got_umodes is False:
            self._ask_modes(irc, msg)

        cat = ircutils.stripFormatting(text.lower())
        return cat, opt

    def _reply(self, irc, msg, out, cat, opt, *, randomcat=False):
        if randomcat is True:
            out.insert(0, "Polygen('%s')" % cat)

        outlen = len(out)
        charcnt = sum(len(line) for line in out)
        should_paste = (outlen > LINES_BEFORE_PASTEBIN
            or charcnt > LINELEN_BEFORE_PASTEBIN)
        bot_isoper = 'o' in self.umodes[irc.network]
        if should_paste and not bot_isoper or opt == 'paste':
            title = "%s - <%s> polygen %s" % (
                time.strftime("%Y/%m/%d %H:%M:%S"), msg.nick, cat)
            s = "\n".join(utils.web.htmlToText(s) for s in out)
            try:
                pasteurl = utils.web.pb_inst.paste(
                    s.encode('utf8'), title=title)
            except Exception:
                irc.error("Refusing to paste %s here." % (
                    ("%d lines" % outlen) if outlen > LINES_BEFORE_PASTEBIN else ("%d chars" % totchars)))
                raise
            else:
                irc.reply("look at %s (%d lines long)" % (pasteurl, outlen), prefixNick=True)
        else:
            for line in out:
                line = utils.web.htmlFormatReplacer(line)
                irc.reply(line)

    def _polygen(self, irc, msg, args, text, *, _from, getter):
        randomcat = False
        cat, opt = self._pre_command(irc, msg, text)
        valid_categories = _get_categories(_from)
        if cat in ("", "help"):
            self._polygen_help(irc, valid_categories)
        else:
            if cat == "random":
                randomcat = True
                cat = random.choice(list(valid_categories.keys()))
            elif cat not in valid_categories:
                irc.error('Invalid category: %s' % cat)
                return

            out = getter(valid_categories[cat])                
            self._reply(irc, msg, out, cat, opt, randomcat=randomcat)

    @wrap([optional("text")])
    def polygen(self, irc, msg, args, text):
        """ [<paste>:]<category>

        Polygen from local polygen executable """

        self._polygen(irc, msg, args, text,
            _from="filesystem", getter=_get_polygen)

    @wrap([optional("text")])
    def polygenweb(self, irc, msg, args, text):
        """ [<paste>:]<category>

        Polygen from polygen.it """

        self._polygen(irc, msg, args, text,
            _from="website", getter=_get_polygen_fromsite)

    def _ask_modes(self, irc, msg):
        m = ircmsgs.IrcMsg(prefix=msg.prefix, command='MODE',
                args=(irc.nick,), msg=msg)
        irc.sendMsg(m)

    def do221(self, irc, msg):
        _, *umodes = msg.args[1]
        self.umodes[irc.network] = umodes
        self._got_umodes = True

    def doMode(self, irc, msg):
        recipient, *rest = msg.args
        if recipient == irc.nick:
            op, *umodes = rest[0]
            for mode in umodes:
                if op == "+":
                    self.umodes[irc.network].append(mode)
                elif op == "-":
                    self.umodes[irc.network].remove(mode)

Class = Polygen


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
