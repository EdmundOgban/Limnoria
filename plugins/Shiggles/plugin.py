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

from random import randint

from supybot import utils, plugins, ircutils, callbacks
from supybot.commands import *
try:
    from supybot.i18n import PluginInternationalization
    _ = PluginInternationalization('Shiggles')
except ImportError:
    # Placeholder that allows to run the plugin on a bot
    # without the i18n module
    _ = lambda x: x


class Shiggles(callbacks.Plugin):
    """Shits and giggles"""
    threaded = True

    @wrap([('checkCapability', 'owner'), 'channelDb', 'text'])
    def say(self, irc, msg, args, dest, message):
        """ [dest] <message> """
        irc.reply(message, to=dest)

    def ifelse(self, irc, msg, args, text):
        """ 'conda' [eq|neq] 'condb' 'if-true' 'if-false' """
        m = re.match(r"^'([^']*)'\s([a-z]+)\s'([^']*)'\s'([^']*)'\s'([^']*)'$", text)

        if m:
            cond1, op, cond2, ift, elset = m.groups()
            if op == "eq":
                ret = ift if cond1 == cond2 else elset
            elif op == "neq":
                ret = ift if cond1 != cond2 else elset
            else:
                ret = "invalid operation: %s" % op

            irc.reply(ret)
        else:
            irc.error("invalid parameters.")
    ifelse = wrap(ifelse, ['text'])


    @wrap([optional('somethingWithoutSpaces')])
    def fu(self, irc, msg, args, f):
        " [F]: ffffuuuuuu-"
        s = "%s%s-" % ('f'*randint(3, 32), 'u'*randint(3, 32))

        if f == "F":
            s = s.upper()

        irc.reply(s)
        
    def doPrivmsg(self, irc, msg):
        if not callbacks.addressed(irc.nick, msg):
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

Class = Shiggles


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
