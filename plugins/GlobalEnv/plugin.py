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

from collections import defaultdict

from supybot import utils, plugins, ircutils, callbacks, ircmsgs
from supybot.commands import *
try:
    from supybot.i18n import PluginInternationalization
    _ = PluginInternationalization('GlobalEnv')
except ImportError:
    # Placeholder that allows to run the plugin on a bot
    # without the i18n module
    _ = lambda x: x

URL_SAFECHARS = r"A-Za-z0-9_~.\-;/?:@=&%()#"
TLD_SAFECHARS = r"A-Za-z0-9{2,}"
urlsnarf_re = re.compile("(https?://[{0}]+\.[{1}]{{2,}}[{0}]*)".format(
    URL_SAFECHARS, TLD_SAFECHARS))


def env_set_lasturl(env, irc, msg, text):
    mtch = urlsnarf_re.search(text)
    if mtch:
        return mtch.group(1)


def env_set_lastspoke(env, irc, msg, text):
    return msg.nick


def env_set_prevmsg(env, irc, msg, args):
    if callbacks.addressed(irc.nick, msg):
        return

    return env.get("lastmsg")


def env_set_lastmsg(env, irc, msg, text):
    if callbacks.addressed(irc.nick, msg):
        return

    if ircmsgs.isAction(msg):
        text = "{} {}".format(msg.nick, ircmsgs.unAction(msg))

    return text


VARIABLES = {
    "lasturl": env_set_lasturl,
    "lastspoke": env_set_lastspoke,
    # DO NOT change order of the following two vars.
    "prevmsg": env_set_prevmsg,
    "lastmsg": env_set_lastmsg,
}


class GlobalEnv(callbacks.Plugin):
    """Global environment meant to hold substitution values
        for ircutils.standardSubstitute"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.genv = defaultdict(dict)

    def _env(self, network, channel):
        channel = channel.lower()
        return self.genv[network].get(channel)

    @wrap
    def env(self, irc, msg, args):
        """ <no arguments>

        prints current global env values for this channel.
        """
        channel = msg.args[0].lower()
        if not irc.isChannel(channel):
            return

        _env = self._env(irc.network, channel)
        if _env is None:
            return

        out = []
        for var, val in _env.items():
            out.append("${} = {}".format(var, val))

        irc.reply(utils.str.commaAndify(out))

    def doPrivmsg(self, irc, msg):
        channel = msg.args[0].lower()
        if not irc.isChannel(channel):
            return

        if (callbacks.addressed(irc.nick, msg)
            or ircmsgs.isCtcp(msg) and not ircmsgs.isAction(msg)):
            return

        text = ircutils.stripFormatting(msg.args[1])
        text = utils.str.try_coding(text)
        env = self.genv[irc.network].get(channel)
        if env is None:
            env = dict()
            self.genv[irc.network][channel] = env

        for var, func in VARIABLES.items():
            value = func(env, irc, msg, text)
            if value is not None:
                env[var] = value

Class = GlobalEnv


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
