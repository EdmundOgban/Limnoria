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

import logging
import re
import string
import time

from collections import defaultdict
from datetime import datetime, timedelta
from functools import partial
from math import floor

import supybot.schedule as schedule

from supybot import callbacks, ircmsgs, ircdb
from supybot.commands import wrap, optional
try:
    from supybot.i18n import PluginInternationalization
    _ = PluginInternationalization('UnoGame')
except ImportError:
    # Placeholder that allows to run the plugin on a bot
    # without the i18n module
    _ = lambda x: x

from . import unoengine
from .unoengine import PlayState, GameState, Card


UNO_LOGO = "-~- \x02Uno!\x02 -~-"

STRINGS = {
    PlayState.INVALID_PLAY: ["->$ply Non puoi giocare $card su ${curcard}."],
    PlayState.INVALID_DOUBLE_PLAY: ["->$ply $card e $card2 non possono"
        " essere giocate insieme."],
    PlayState.CARD_NOT_IN_DECK: ["->$ply Non possiedi ${card}."],
    PlayState.CARD_NOT_EXIST: ["->$ply La carta $card_bw non esiste."],
    PlayState.VALID_PLAY: ["$ply gioca $card a $nextply"],
    PlayState.VALID_DOUBLE: ["$ply gioca doppio: $card $card2 a $nextply"],
    PlayState.PICKED_CARD: ["->$ply Peschi $card"],
    PlayState.ALREADY_PICKED: ["->$ply Hai già pescato."],
    PlayState.MUST_PICK: ["->$ply Devi pescare prima di poter passare il turno."],
    PlayState.SKIPPED_TURN: ["$ply passa il turno a $nextply"],
    PlayState.MUST_CHOOSE_COLOR: ["->$ply Devi prima scegliere un colore."],
    PlayState.COLOR_CHOSEN: ["$ply ha scelto $card_dcolor"],
    PlayState.INVALID_COLOR: ["->$ply Colore $card_icolor non valido."],
    PlayState.CANT_PICK: ["->$ply Non puoi pescare ora."],
    PlayState.ADVISE_CARDS: ["->$ply Carte: $plycards -~- In gioco: $curcard"],
    # TODO
    #PlayState.ADVISE_CURCARD: ["Carta in gioco: $card"],
    #"current_card": ["Carta in gioco: $curcard"],
    #PlayState.ADVISE_PLAYER: ["$ply è di mano."],
    #"card_cnt": ["$ply: $n cart$plur"],
    #"player_order": ["Ordine giocatori: $players"],

    PlayState.SKIPPED_TURN_AFTER_DRAW: [
        "$ply pesca $picked_cnt carte e passa il turno a $nextply",
        "->$ply Hai pescato: $picked_cards",
        #"Carta in gioco: $curcard"
    ],
    PlayState.JUST_STARTED: [
        "{} Modalità $playtype".format(UNO_LOGO),
        "Ordine giocatori: $players",
        "Carta in gioco: $curcard"
    ],
    PlayState.GAME_WON: [
        ("$ply gioca $curcard e vince Uno, guadagnando $win_points punti"
        " in questa partita!"),
        "\x0304*\x03** Top 5 della partita"
    ],
    PlayState.GAME_ENDED: ["* Top 5 della partita"],

    PlayState.PLAYER_REMOVED: ["$ply è stato rimosso."],
    PlayState.NOT_ENOUGH_PLAYERS: ["Non ci sono sufficienti giocatori per proseguire."],

    "session_init": ("{} Sessione avviata. Per partecipare, scrivere jo"
        " in canale.".format(UNO_LOGO)),
    "session_stopped": "Sessione di Uno terminata.",
    "cards_nextply": ["->$nextply Carte: $nextplycards -~- In gioco: $curcard"],
    "scoreboard_entry": ["$n) $ply, con $plypoints punti rimanenti"],
    "attr_pick_unreplyable": ["$ply pesca $picked_cnt carte e salta il turno,"
        " segue $nextply"],
    "attr_pick_replyable": ["$nextply dovrà pescare $picked_cnt carte e saltare"
        " il turno, a meno che non risponda con un'altra carta Pesca!"],
    "attr_colchange": ["$ply deve scegliere un colore"],
    "attr_reverse": ["nuovo ordine giocatori: $players, partendo da $ply"],
    "attr_skip": ["$ply salta il turno"],
    "votekick_issued": ["Attenzione $players",
        "$issuedby ha richiesto l'espulsione di $target, votate con il comando ki. La richiesta scadrà tra $timeout secondi."],
    "votekick_alreadyissued": ["Un'altra richiesta di espulsione è attualmente attiva."],
}


log = logging.getLogger("supybot")


def _prepare_mapping(r):
    mapping = r.outcome
    mapping.update({
        "ply": r.player.name,
        "plycards": "\x02{}\x02".format("  ".join(r.player.cards)),
        "nextply": r.nextplayer.name,
        "nextplycards": "\x02{}\x02".format("  ".join(r.nextplayer.cards)),
        "curcard": r.currentcard.name()
    })

    if r.card:
        o = r.card
        mapping.update({
            "card": o.name(),
            "card_bw": o.name(colored=False),
            "card_icolor": o.color,
            "card_dcolor": o.dispcolor
        })

    if r.additionalcard:
        o = r.additionalcard
        mapping.update({
            "card2": o.name(),
            "card2_bw": o.name(colored=False),
            "card2_icolor": o.color,
            "card2_dcolor": o.dispcolor
        })

    if r.playstate is PlayState.CARD_NOT_IN_DECK:
        o = r.additionalcard or r.card
        mapping.update({
            "card": o.name(),
            "card_bw": o.name(colored=False)
        })


    #elif r.playstate is PlayState.SKIPPED_TURN_AFTER_DRAW:
    #    mapping.update({
    #        "picked_cards": " ".join(map(str, r.outcome["picked_cards"])),
    #        "picked_cnt": r.outcome["picked_cnt"]
    #    })
    #if r.playstate is PlayState.JUST_STARTED:
    #    mapping.update({
    #        "playtype": r.outcome["playtype"],
    #        "players": " ".join(map(str, r.outcome["players"]))
    #    })
    #
    #elif r.playstate in PlayState.GAME_WON:
    #    mapping["win_points"] = r.outcome["win_points"]

    return mapping


def _parse_outcome(outcome, mapping):
    affected = outcome["affected"]
    attribs = outcome["affected_attribs"]
    flipped = outcome.get("deck_flipped")
    mapping["ply"] = affected.name
    tmpl = []

    if attribs & Card.ATTRIB_REV:
        tmpl.extend(STRINGS["attr_reverse"])

    if attribs & Card.ATTRIB_CCH:
        tmpl.extend(STRINGS["attr_colchange"])

    if attribs & Card.ATTRIB_PKC:
        if attribs & Card.ATTRIB_SKP:
            tmpl.extend(STRINGS["attr_pick_unreplyable"])
        else:
            tmpl.extend(STRINGS["attr_pick_replyable"])

    if attribs == Card.ATTRIB_SKP:
        tmpl.extend(STRINGS["attr_skip"])

    return [string.Template(t).safe_substitute(mapping) for t in tmpl]


def _response_gamewon(r):
    tmpl = STRINGS["scoreboard_entry"][0]
    mapping = {}
    out = []

    start = 2 if r.playstate is PlayState.GAME_WON else 1

    for pos, (player, points) in enumerate(r.outcome["scoreboard"], start):
        mapping.update({
            "n": pos,
            "ply": player.name,
            "plypoints": points,
        })
        s = string.Template(tmpl).safe_substitute(mapping)
        out.append(s)

    return out

def response2text(r, oo=[]):
    mapping = _prepare_mapping(r)

    tmpl = STRINGS.get(r.playstate)
    if tmpl is not None:
        for line in tmpl:
            oo.append(string.Template(line).safe_substitute(mapping))

        if r.playstate in (PlayState.PLAYER_REMOVED, PlayState.NOT_ENOUGH_PLAYERS):
            if r.playstate is PlayState.PLAYER_REMOVED:
                playstate = PlayState.VALID_PLAY
            elif r.playstate is PlayState.NOT_ENOUGH_PLAYERS:
                playstate = PlayState.GAME_ENDED

            kwargs = r._asdict()
            kwargs.pop("playstate", None)
            r2 = unoengine.UnoResponse(playstate=playstate, **kwargs)
            oo.extend(response2text(r2))

        if r.playstate in (PlayState.GAME_WON, PlayState.GAME_ENDED):
            oo.extend(_response_gamewon(r))
    else:
        oo.append("Unknown response: {}".format(r))

    # FIXME: I don't know if it's ok to check r.playstate here
    if (r.outcome.get("affected") is not None
        and r.playstate is not PlayState.SKIPPED_TURN_AFTER_DRAW):
        oo[-1] = ", ".join([oo[-1], *_parse_outcome(r.outcome, mapping)])

    advise_cards = r.playstate in (
        PlayState.VALID_PLAY,
        PlayState.VALID_DOUBLE,
        PlayState.SKIPPED_TURN,
        PlayState.SKIPPED_TURN_AFTER_DRAW,
        PlayState.COLOR_CHOSEN,
        PlayState.JUST_STARTED
    )
    if advise_cards is True:
        # FIXME: this shouldn't be necessary
        if (r.gamestate in (
            GameState.WAITING_COLOR_COLCARD, GameState.WAITING_COLOR_COLDRAWCARD)
            or r.playstate is PlayState.JUST_STARTED):
            t = STRINGS[PlayState.ADVISE_CARDS][0]
        else:
            t = STRINGS["cards_nextply"][0]

        log.warning(f"advising cards: playstate:{r.playstate} ply:{r.player}"
            f"nextply:{r.nextplayer} {t}")
        oo.append(string.Template(t).safe_substitute(mapping))

    o = oo[:]
    oo.clear()
    return o

# ##############################################################################
# ##############################################################################

def _split_cards(s):
    mtch = re.match(r"([a-zA-Z]{1,2}(?:\+?\d+)?)([a-zA-Z]{1,2}(?:\+?\d+)?)?", s)
    if mtch:
        c1, c2 = mtch.groups()
    else:
        c1, c2 = None, None

    return c1, c2

# ##############################################################################
# ##############################################################################

def uno_jo(sess, irc, nick, arg, **kwargs):
    r = sess.add_player(nick)
    if r is True:
        irc.reply("{} parteciperà alla partita!".format(nick))
    elif r is False:
        irc.reply("La sessione è piena!")


def uno_ca(sess, irc, nick, arg, **kwargs):
    if nick not in sess.players:
        return

    return sess.advise_cards(nick)


def uno_tu(sess, irc, nick, arg, **kwargs):
    if nick not in sess.players:
        return

    irc.reply("\x0304*\x03 {} è di mano.".format(sess.current_player.name))
    # TODO:
    # return {"playstate": PlayState.ADVISE_TURN}


def uno_cd(sess, irc, nick, arg, **kwargs):
    if nick not in sess.players:
        return

    irc.reply("\x0304*\x03 Carta in gioco: {}".format(sess.current_card.name()))
    # TODO:
    # return {"playstate": PlayState.ADVISE_CURCARD}


def uno_ct(sess, irc, nick, arg, **kwargs):
    if nick not in sess.players:
        return

    pls = ("{}: {b}{} carte{b}".format(pl.name, len(pl.deck), b="\x02")
        for pl in sess.players)
    irc.reply("\x0304*\x03 " + ", ".join(pls))


def uno_od(sess, irc, nick, arg, **kwargs):
    if nick not in sess.players:
        return

    pls = " ".join(pl.name for pl in sess.players)
    irc.reply("\x0304*\x03 Ordine giocatori: {}".format(pls))


def uno_ki(sess, irc, nick, arg, **kwargs):
    poll = kwargs.get("poll")
    if poll is None or poll.valid is False or nick not in sess.players:
        return

    response = None
    verdict = poll.vote(nick)
    if verdict is True:
        try:
            schedule.removeEvent(poll.pollid)
        except KeyError:
            pass

        irc.reply("È stato raggiunto il quorum, {} verrà espulso.".format(
            poll.target))
        response = sess.remove_player(poll.target)
        poll.close()
    elif verdict is False:
        irc.reply("{} ha espresso il suo voto.".format(nick))

    return response


def uno_cl(sess, irc, nick, arg, **kwargs):
    # TODO: claim a player that hasn't said uno
    pass

def uno_de(sess, irc, nick, arg, **kwargs):
    irc.reply("Mazzo pesca: {} carte, Mazzo scarti: {} carte".format(
        len(sess.draw_deck), len(sess.discard_deck)))

# ##############################################################################
# ##############################################################################

def uno_pl(sess, irc, nick, arg, **kwargs):
    if arg is None:
        return

    ca1, ca2 = _split_cards(arg)
    return sess.play(ca1, ca2)


def uno_co(sess, irc, nick, arg, **kwargs):
    if arg is None:
        return

    return sess.setcolor(arg)


def uno_pa(sess, irc, nick, arg, **kwargs):
    return sess.skip()


def uno_pe(sess, irc, nick, arg, **kwargs):
    return sess.pick()


def uno_bl(sess, irc, nick, arg, **kwargs):
    # TODO: call the j+4 bluff
    pass


def uno_dummy(sess, irc, nick, arg, **kwargs):
    pass

# ##############################################################################
# ##############################################################################

def _parse_line(response, line):
    pvt = line.startswith("->")
    if pvt is True:
        recipient, line = line[2:].split(" ", 1)
        line = "-> {}".format(line)
    else:
        recipient = None
        if response.playstate not in (PlayState.GAME_WON, PlayState.GAME_ENDED):
            line = "\x0304*\x03 " + line

    return pvt, recipient, line


def unomsg(irc, response):
    if isinstance(response, unoengine.UnoResponse):
        for line in response2text(response):
            pvt, recipient, line = _parse_line(response, line)
            irc.reply(line, notice=pvt, private=pvt, to=recipient)
    elif isinstance(response, str):
        pvt, recipient, line = _parse_line(line)
        irc.reply(response, notice=pvt, private=pvt, to=recipient)


uno_globcmds = {
    "jo": uno_jo,
    "ca": uno_ca,
    "tu": uno_tu,
    "cd": uno_cd,
    "ct": uno_ct,
    "od": uno_od,
    "ki": uno_ki,
    "de": uno_de
}


uno_playcmds = {
    "pl": uno_pl,
    "co": uno_co,
    "pa": uno_pa,
    "pe": uno_pe,
    "cl": uno_cl,
    "bl": uno_bl
}

# ##############################################################################
# ##############################################################################

class Poll:
    def __init__(self, *, issuedby, target, voters_cnt, pollid, timeout=60):
        self.issuedby = issuedby
        self.target = target
        self.voters_cnt = voters_cnt
        self.pollid = pollid
        self.timeout = timeout
        self.voted_ppl = []
        self.voted_cnt = 0
        self.issuedat = datetime.now()
        self.closed = False

    @property
    def verdict(self):
        return self.voted_cnt >= floor(self.voters_cnt / 2) + 1

    @property
    def expired(self):
        log.warning("Poll.expired {}".format(datetime.now() - self.issuedat > timedelta(seconds=self.timeout)))
        return datetime.now() - self.issuedat > timedelta(seconds=self.timeout)

    @property
    def valid(self):
        return not any([self.expired, self.closed])

    def vote(self, nick):
        if nick in self.voted_ppl or any([self.closed, self.expired]):
            return

        self.voted_ppl.append(nick)
        self.voted_cnt += 1
        return self.verdict

    def close(self):
        log.warning("Poll.close()")
        self.closed = True

    def doNick(self, oldnick, newnick):
        for idx, ppl in enumerate(self.voted_ppl):
            if oldnick == ppl:
                self.voted_ppl[idx] = newnick


def uno_decidekick(irc, poll):
    if poll.verdict is True:
        response = sess.remove_player(poll.target)
        #irc.reply("È stato raggiunto il quorum, {} verrà espulso.".format(
        #    poll.target))
        unomsg(irc, response)
    else:
        irc.reply("Quorum non raggiunto, voto fallito.")

    poll.close()


class UnoGame(callbacks.Plugin):
    """Uno game for Limnoria \\o/"""
    threaded = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sessions = defaultdict(dict)
        self.votekick = None

    @wrap([optional("text")])
    def uno(self, irc, msg, args, mode):
        """ <gamemode>

        Initialize a Uno session on the current channel.
        """
        channel = msg.args[0].lower()
        if not irc.isChannel(channel):
            return

        sess = self.sessions[irc.network].get(channel)
        if sess is None:
            self.sessions[irc.network][channel] = unoengine.Session(mode)
            irc.reply(STRINGS["session_init"])
        else:
            irc.error("Sessione di Uno già avviata in {}".format(channel))

    @wrap
    def unostart(self, irc, msg, args):
        """ <no arguments>

        Starts a Uno session on the current channel.
        """
        channel = msg.args[0].lower()
        if not irc.isChannel(channel):
            return

        sess = self.sessions[irc.network].get(channel)
        if sess is None or msg.nick not in sess.players:
            return

        card = None
        response = sess.start(start_card=card)
        if response:
            unomsg(irc, response)
        elif response is False:
            irc.error(STRINGS[PlayState.NOT_ENOUGH_PLAYERS])
            del self.sessions[irc.network][channel]

    @wrap
    def unostop(self, irc, msg, args):
        """ <no arguments>

        Stops a Uno session on the current channel.
        """
        channel = msg.args[0].lower()
        if not irc.isChannel(channel):
            return

        sess = self.sessions[irc.network].get(channel)
        if sess is None or msg.nick not in sess.players:
            return

        irc.reply(STRINGS["session_stopped"])
        response = sess.stop()
        if sess.current_player:
            unomsg(irc, response)

        del self.sessions[irc.network][channel]

    @wrap(["somethingWithoutSpaces"])
    def unokick(self, irc, msg, args, nick):
        """ <user>

        Calls a vote to expel <user> from the current Uno session. 
        """
        channel = msg.args[0].lower()
        if not irc.isChannel(channel):
            return

        sess = self.sessions[irc.network].get(channel)
        if sess is None or msg.nick not in sess.players:
            return

        if sess.smac.state is GameState.WAITING_PLAYERS:
            return

        player = sess.player_from_name(nick)
        if player is None: # TODO: or not player.idling:
            return

        response = None
        if (self.votekick is None
            or any([self.votekick.closed, self.votekick.expired])):
            self.votekick = Poll(issuedby=msg.nick, target=player.name,
                voters_cnt=len(sess.players)-1,
                pollid="{}-{}:{}".format(irc.network, channel, nick))
            func = partial(uno_decidekick, irc, self.votekick)
            schedule.addEvent(func, time.time() + self.votekick.timeout,
                self.votekick.pollid)
            # FIXME
            r = uno_globcmds["ki"](sess, irc, msg.nick, None, poll=self.votekick)
            if self.votekick.valid:
                playstate = "votekick_issued"
            else:
                response = r
        else:
            playstate = "votekick_alreadyissued"

        # FIXME
        if response is None:
            response = sess._compile_response(
                playstate=playstate,
                outcome={
                    "players": " ".join(map(str, sess.players)),
                    "playstate": playstate,
                    "issuedby": self.votekick.issuedby,
                    "target": self.votekick.target,
                    "timeout": self.votekick.timeout
                })

        if response is not None:
            unomsg(irc, response)

    @wrap(["owner", "somethingWithoutSpaces", optional("text")])
    def unogive(self, irc, msg, args, user, text):
        """ <user> [card] [cnt]

        cheater!
        """
        shand, cnt = None, None
        if text is not None:
            try:
                a, b = text.split(" ", 1)
            except ValueError:
                try:
                    cnt = int(text)
                except ValueError:
                    shand = text
            else:
                try:
                    cnt, shand = int(a), b
                except ValueError:
                    shand, cnt = a, int(b) if b.isdigit() else None

        channel = msg.args[0].lower()
        if not irc.isChannel(channel):
            return

        sess = self.sessions[irc.network].get(channel)
        if sess is None:
            return

        player = sess.player_from_name(user)
        if player is None:
            return
           
        picked = []
        for _ in range(cnt or 1):
            card = None

            if shand is None:
                card, _ = sess._safe_pickdeck_draw()
            else:
                card = sess.draw_deck_card_from_shorthand(shand)

            if card is None:
                break

            player.pick(card)
            picked.append(card.name())
            sess.draw_deck.remove_card(card)

        if picked:
            #irc.reply("{} pesca {}".format(user, " ".join(picked)))
            irc.reply("{} ti ha fatto pescare {}".format(msg.nick, " ".join(picked)),
                private=True, to=user, notice=True)

    def doNick(self, irc, msg):
        newnick = msg.args[0]
        oldnick = msg.nick
        
        for (channel, _) in ircdb.channels.items():
            channel = channel.lower()
            sess = self.sessions[irc.network].get(channel)
            if sess is not None:
                player = sess.player_from_name(oldnick)
                if player is not None:
                    player.name = newnick
                    if self.votekick is not None:
                        self.votekick.doNick(oldnick, newnick)

    def doPrivmsg(self, irc, msg):
        channel = msg.args[0].lower()
        if not irc.isChannel(channel) or callbacks.addressed(irc.nick, msg):
            return

        if not ircmsgs.isCtcp(msg):
            text = msg.args[1]
        else:
            return

        sess = self.sessions[irc.network].get(channel)
        if sess is None:
            return

        ttkn = text.split()
        try:
            cmd, arg = [s.lower() for s in ttkn[:2]]
        except ValueError:
            cmd, arg = ttkn[0].lower(), None

        response = None
        unocmds = {}
        if sess.current_player and sess.current_player.name == msg.nick:
            ca1, ca2 = _split_cards(cmd)
            if ca1 in sess.current_player.deck or ca2 in sess.current_player.deck:
                response = uno_playcmds["pl"](sess, irc, msg.nick, cmd)
            else:
                unocmds.update(uno_playcmds)

        if response is None:
            unocmds.update(uno_globcmds)
            kwargs = {}
            if self.votekick is not None:
                kwargs["poll"] = self.votekick

            response = unocmds.get(cmd, uno_dummy)(
                sess, irc, msg.nick, arg, **kwargs)

        if response is not None:
            unomsg(irc, response)
            if response.gamestate is GameState.GAME_ENDED:
                del self.sessions[irc.network][channel]

Class = UnoGame


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
