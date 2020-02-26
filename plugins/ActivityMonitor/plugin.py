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

import supybot.utils as utils
from supybot.commands import *
import supybot.plugins as plugins
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks

try:
    from supybot.i18n import PluginInternationalization
    _ = PluginInternationalization('ActivityMonitor')
except ImportError:
    # Placeholder that allows to run the plugin on a bot
    # without the i18n module
    _ = lambda x: x

from . import actmon


class ActivityMonitor(callbacks.Plugin):
    """Channels activity monitor"""

    def __init__(self, irc):
        self.__parent = super()
        self.__parent.__init__(irc)
        self.am = {}
    
    def _monitor(self, channel):
        try:
            am = self.am[channel]
        except KeyError:
            am = self.am[channel] = actmon.ActivityMonitor(base_level=20)
    
        return am

    @wrap(['channeldb'])
    def activity(self, irc, msg, args, channel):
        """[<channel>]

        Returns the channel activity. <channel> is only necessary if the command
        isn't used in the channel itself.
        """

        am = self._monitor(channel)

        irc.reply("Activity of %s: %.4f, %.4f msg/min, %.4f msg/sec" % (
            channel, am.activity(),
            am.frequency()*60, am.frequency()))

    def doPrivmsg(self, irc, msg):
        if not irc.isChannel(msg.args[0]):
            return

        channel = msg.args[0]
        self._monitor(channel).on_message()


Class = ActivityMonitor


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
