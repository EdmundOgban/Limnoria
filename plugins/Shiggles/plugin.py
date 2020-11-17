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

import re
import requests

from math import floor
from random import randint, random, choice
from itertools import chain, cycle
from bs4 import BeautifulSoup as BS

from supybot import utils, plugins, ircutils, ircmsgs, callbacks, world
from supybot.commands import *
try:
    from supybot.i18n import PluginInternationalization
    _ = PluginInternationalization('Shiggles')
except ImportError:
    # Placeholder that allows to run the plugin on a bot
    # without the i18n module
    _ = lambda x: x

from . import souffle

VOWELS = set("aeiou")


# def ratterpolate(s, n):
#     L = list(s)
#     interpolate = n - len(L)
#     while interpolate:
#         for idx, c in enumerate(L):
#             if c in VOWELS:
#                 L.insert(idx+1, "=")
#                 interpolate -= 1
#                 if interpolate == 0:
#                     break
# 
#     return "".join(L).upper()

def ratterpolate(s, n):
    size = max(1, len(s) - 1)
    chars_cnt = max(0, n - size)
    dash_cnt = max(1, chars_cnt / size)
    err = (chars_cnt % round(dash_cnt)) / size
    out = []
    for c in s:
        if chars_cnt > 0:
            out.append(c + "=" * floor(min(dash_cnt, chars_cnt)))
            chars_cnt -= floor(dash_cnt)
            dash_cnt += err
        else:
            out.append(c)

    return "".join(out)


class Shiggles(callbacks.Plugin):
    """Shits and giggles"""
    threaded = True
    
    def __init__(self, irc):
        self.__parent = super()
        self.__parent.__init__(irc)
        self._germanos = []

    @wrap([('checkCapability', 'owner'), 'somethingWithoutSpaces', 'text'])
    def say(self, irc, msg, args, dest, message):
        """ [dest] <message> """
        
        irc.reply(message, to=dest, private=not irc.isChannel(dest))

    @wrap(['channelDb', 'text'])
    def act(self, irc, msg, args, dest, message):
        """ [dest] <message> """
        irc.reply(message, to=dest, action=True)

    # def ifelse(self, irc, msg, args, text):
        # """ 'conda' [eq|neq] 'condb' 'if-true' 'if-false' """
        # m = re.match(r"^'([^']*)'\s([a-z]+)\s'([^']*)'\s'([^']*)'\s'([^']*)'$", text)

        # if m:
            # cond1, op, cond2, ift, elset = m.groups()
            # if op == "eq":
                # ret = ift if cond1 == cond2 else elset
            # elif op == "neq":
                # ret = ift if cond1 != cond2 else elset
            # else:
                # ret = "invalid operation: %s" % op

            # irc.reply(ret)
        # else:
            # irc.error("invalid parameters.")
    # ifelse = wrap(ifelse, ['text'])

    @wrap([optional('somethingWithoutSpaces')])
    def fu(self, irc, msg, args, f):
        " [F]: ffffuuuuuu-"
        s = "%s%s-" % ('f'*randint(3, 32), 'u'*randint(3, 32))

        if f == "F":
            s = s.upper()

        irc.reply(s)

    def greetz(self, irc, msg, args, opt, text):
        """ Greets someone """
        #opt = dict(opt)
        #dst = opt['dst'] if 'dst' in opt else None
        dst = None
        if text:
            text = text.split()
            r = '%s ' % text[0][:30]
        else:
            r = ''
        r += '%s' % (''.join(('ò' if randint(0, 1) else '\\') for i in range(randint(2, 15))))
        if dst: irc.reply(r, to=dst, private=True)
        else: irc.reply(r)
    greetz = wrap(greetz, [optional(getopts({'dst': 'something'})), optional('text')])

    @wrap(['text'])
    def klindize(self, irc, msg, args, text):
        """ <text> """
        chanenv = ircutils.channel_env(irc, msg.args[0])
        text = ircutils.standardSubstitute(irc, msg, text, env=chanenv)
        irc.reply(''.join(c if random() > 0.3 or c == ' ' else '\ufffd' for c in text))

    @wrap([optional('text')])
    def souffle(self, irc, msg, args, text):
        """ [text]
        macchettehelpiscy :E
        """
        if text is None:
            out = choice("sesese sesesesesese sesesesesesesesese seseseseessesesse ebbasta".split())
            if random() <= 0.33:
                out += " :E"
        else:
            out = souffle.macchette(text)

        irc.reply(out)

    def _get_germanos(self):
        req = requests.get("https://nonciclopedia.org/wiki/Nonquote:Germano_Mosconi")
        soup = BS(req.text, features="html.parser")
        parserout = soup.find("div", class_="mw-parser-output")
        for quotes in parserout.findAll("div"):
            quote = quotes.findAll("div")
            if not quote:
                continue

            cit, aut = [o.text for o in quote]
            if aut.lower().startswith("(germano mosconi"):
                self._germanos.append(cit.strip("«»").strip())

    @wrap([optional('text')])
    def mosconi(self, irc, msg, args, query):
        """ [query]
        se mi chiedi l'help ancora ti do un pugno! """
        germanos = []
        if not self._germanos:
            self._get_germanos()

        if query:
            for germano in self._germanos:
                if query.lower() in germano.lower():
                    germanos.append(germano)

        if not germanos:
            germanos = self._germanos

        germano = choice(germanos)
        irc.reply("« {} »".format(germano))

    def _advratto(self, size, nick):
        if size is None:
            mult = 1
        elif "giga" in size or "iper" in size:
            mult = 4 if random() > 1/9 else 8
        elif "mega" in size or "maxi" in size:
            mult = 3
        elif "super" in size:
            mult = 2
        else:
            mult = 1

        fmt = "8={}==D"
        if nick == "amelierose":
            mast = choice(["=", "=", "==", "==="])
        else:
            mast = choice(["==", "===", "====", "======", "=================="])

        ratto = fmt.format(mast*mult)
        if random() < 1/7:
            ratto += "O:"

        return ratto

    @wrap([optional('text')])
    def rattobaleno(self, irc, msg, args, size):
        """ <no arguments>
        {ratto}
        """
        ratto = self._advratto(size, msg.nick)
        irc.reply(''.join(f'\x03{n%16:02}{c}'
            for c, n in zip(ratto, cycle(chain(
                range(3, 16),range(14, 3, -1))))))   

    @wrap([optional('text')])
    def rattozaker(self, irc, msg, args, text):
        """ <nick>

        {ratto}ize nick
        """
        fmt = "8=={}==D"
        if text is None:
            text = "Mezmerize"

        textlen = len(text)
        mastlen = randint(textlen*2, textlen*5)
        mast = ratterpolate(text, mastlen)
        irc.reply(fmt.format(mast).upper())

    @wrap
    def rattamituttah(self, irc, msg, args):
        """ :E """
        rattone = lambda: "(!{}8".format("="*randint(35,120))
        ctcpratto = "\x01RATTO {}\x01".format(rattone())
        messages = [
            ircmsgs.privmsg(msg.nick, ctcpratto),
            ircmsgs.privmsg(msg.nick, rattone()),
            ircmsgs.privmsg(msg.args[0], rattone()),
            ircmsgs.notice(msg.nick, rattone())
        ]
        for message in messages:
            irc.queueMsg(message)

    # * to Roygbiv bridge
    def doIrcBridge(self, irc, msg):
        channel = msg.args[0].lower()
        if not irc.isChannel(channel):
            return

        nick_fmt = "{b}{k}10{}{k}{b}@{b}{k}15{}{k}{b}".format(
            msg.nick, irc.network, b="\x02", k="\x03")

        if ircmsgs.isAction(msg):
            text = ircmsgs.unAction(msg)
            fmt = "* {} {{}}".format(nick_fmt)
        elif ircmsgs.isCtcp(msg):
            return
        else:
            text = msg.args[1]
            fmt = "<{}> {{}}".format(nick_fmt)

        roygbirc = world.getIrc("Roygbiv")
        if roygbirc is not None and irc.network != "Roygbiv":
            if channel in roygbirc.state.channels:
                s = fmt.format(text)
                m = ircmsgs.privmsg(channel, s)
                #roygbirc.sendMsg(m)

    def doShigglesReply(self, irc, msg):
        if not callbacks.addressed(irc.nick, msg):
            try:
                head, tail = msg.args[1].split(irc.nick)
            except ValueError:
                pass
            else:
                if head == "" and set(tail) == set("!"):
                    irc.reply(msg.nick + tail)
                    return

        replies = {
            "doraemon": "babbo natale",
            "jesoo": "babbo natale",
            "il tuo padrone": "Edmund_Ogban",
            "scucchiarone": "una testa di minchia"
        }
        try:
            text = msg.args[1].lower().split(" ", 1)[1]
        except IndexError:
            pass
        else:
            if text.startswith("chi \xe8 ") and text.endswith("?"):
                rest = ' '.join(text.strip("?").split()[2:])
                reply = replies.get(rest, None)
                if not reply:
                    reply = "stocazzo"
                irc.reply(reply, prefixNick=True)

    def doPrivmsg(self, irc, msg):
        self.doIrcBridge(irc, msg)
        self.doShigglesReply(irc, msg)

    def doNotice(self, irc, msg):
        self.log.info("Notice from {}@{}: {}".format(
            msg.nick, irc.network, str(msg.args[1])))

Class = Shiggles

# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
