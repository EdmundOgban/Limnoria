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

from supybot import callbacks
from supybot import conf, registry, irclib, drivers, world
from supybot.commands import wrap
try:
    from supybot.i18n import PluginInternationalization
    _ = PluginInternationalization('Telegram')
except ImportError:
    # Placeholder that allows to run the plugin on a bot
    # without the i18n module
    _ = lambda x: x


class Telegram(callbacks.Plugin):
    """Telegram to IRC management commands"""

    @wrap(['owner'])
    def tconnect(self, irc, msg, args):
        """ """
        network = "TelegramIRC"
        for irc in world.ircs:
            if irc.network == network:
                break
        else:
            self._connect(irc, network)
            if network not in conf.supybot.networks():
                conf.supybot.networks().add(network)

    def _connect(self, irc, network, serverPort=None, password='', ssl=False):
        try:
            group = conf.supybot.networks.get(network)
        except (registry.NonExistentRegistryEntry, IndexError):
            conf.registerNetwork(network, password, ssl)
            serverS = 'bridge.telegram.irc:6667'
            conf.supybot.networks.get(network).servers.append(serverS)
            assert conf.supybot.networks.get(network).servers(), \
                   'No servers are set for the %s network.' % network

        self.log.debug('Creating new Irc for %s.', network)
        newIrc = irclib.Irc(network)
        driver = drivers.newDriver(newIrc, moduleName="Telegram")
        irc.getCallback('Owner')._loadPlugins(newIrc)
        return newIrc

Class = Telegram


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
