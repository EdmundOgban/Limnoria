###
# Copyright (c) 2018, Edmund_Ogban
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
import supybot.log as log
import supybot.ircdb as ircdb
import supybot.ircmsgs as ircmsgs
try:
    from supybot.i18n import PluginInternationalization
    _ = PluginInternationalization('AntiSpam')
except ImportError:
    # Placeholder that allows to run the plugin on a bot
    # without the i18n module
    _ = lambda x: x

import random


def haveOpState(irc, channel):
    if channel not in irc.state.channels:
        return False

    if not irc.state.channels[channel].isOp(irc.nick):
        return False

    return True


def haveAtLeastHalfOpState(irc, channel):
    if channel not in irc.state.channels:
        return False

    if not irc.state.channels[channel].isHalfopPlus(irc.nick):
        return False

    return True


class AntiSpam(callbacks.Plugin):
    """AntiSpam plugin"""

    REASONS = ["stfu", "get out of my sight", "you are filth", "burn in hell",
               "twisting by the pool", "yo dawg", "gee you stink", "see ya",
               "don't bother", "why so serious"]

    def doPrivmsg(self, irc, msg):
        
        if not irc.isChannel(msg.args[0]):
            return

        channel = plugins.getChannel(msg.args[0])

        def sbambannalo():
            banmasks = ("*!*@%s" % msg.host, "%s!*@*" % msg.nick)
            reason = random.choice(self.REASONS)

            #irc.queueMsg(ircmsgs.bans(channel, banmasks))
            irc.sendMsg(ircmsgs.kick(channel, msg.nick, reason))
            irc.noReply()

        spam = ("/!\ attn: this channel has moved to irc.freenode.net",
                "with our irc ad service you can reach a global audience of entrepreneurs "
                "and fentanyl addicts with extraordinary engagement rates",
                "i thought you guys might be interested in this blog by freenode "
                "staff member bryan kloeri ostergaard",
                "read what irc investigative journalists have uncovered "
                "on the freenode pedophilia scandal",
                "a fascinating blog where freenode staff member matthew mst trout recounts "
                "his experiences of eye-raping young children")

        # Old table with uppercase letters
        #intab  = "ΑᎪɑаᥱеⅰіоοоⲟഠ∪ᥙⵑǃΒⅽϲсϹⲤԁⅾᖴɡһΙιϳⅼⅿΜᎷϺⅯΝⲚᥒⲞоⲣрᎡᏒѕΤᎢ∨ᴠⅴᏔᴡⲭỿу：︓∶⁚․．∕／⁄∖⧵\u202f\u205f"
        #outtab = "aaaaeeiiooooouu!!bcccccddfghiijlmmmmmnnnoopprrsttvvvwwxyy::::..///\\\  "
        intab  =  "αꭺɑаᥱеⅰіоοоⲟഠ∪ᥙⵑǃ！﹗︕βᏼⅽϲсϲꮯⲥԁⅾᖴɡһιιϳјⅼⅿμꮇϻⅿмνᥒⲛⲟоⲣрꭱꮢᖇѕτꭲт∨⋁ᴠⅴꮤᴡꮃⲭⅹхỿу⠆：︓∶⁚˸᛬ː፡﹕։․．᜵∕／⁄⧸∖\⧵＼﹨⧹⎼﹣╴＃﹟\u202f\u205f"
        outtab = r"aaaaeeiiooooouu!!!!!bbccccccddfghiijjlmmmmmmnnnoopprrrstttvvvvwwwxxxyy:::::::::::../////\\\\\\---##  "

        text = " ".join(msg.args[1].split()).lower()
        text = text.translate(str.maketrans(intab, outtab))

        for phrase in spam:
            #log.info("'%s'" % text)
            #log.info("'%s'" % phrase)
            #log.info(str(text.startswith(phrase)))
            #log.info("\n\n")

            if text.strip().startswith(phrase):
                if haveAtLeastHalfOpState(irc, channel):
                    sbambannalo()
                else:
                    irc.reply(random.choice(self.REASONS), to=msg.nick, private=True)
                break

Class = AntiSpam


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
