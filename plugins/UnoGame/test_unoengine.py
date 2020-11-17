import unittest

import unoengine as uno
from unoengine import Card, Deck, PlayState, GameState


class TestUnoEngineTwoPlClassicMode(unittest.TestCase):
    RULES = "classic"

    def _init_session(self):
        s = uno.Session(self.RULES)
        self._add_players(s)
        return s

    def _start_session(self, s, **kwargs):
        #shand = kwargs.get("card_shand")
        #if shand is not None:
        #    kwargs["start_card"] = self._card_fromshand(s, shand)

        return s.start(**kwargs)

    def testStart(self):
        s = self._init_session()
        card = self._card_fromshand(s, "r0")
        r = self._start_session(s, start_card=card)

        self.assertIs(r.player, s.current_player)
        self.assertIs(r.nextplayer, s.next_player)
        self.assertIs(r.currentcard, s.current_card)
        self.assertIs(r.currentcard, card)
        self.assertIs(r.card, None)
        self.assertIs(r.additionalcard, None)
        self.assertDictEqual(r.outcome, {
            "playtype": s.playtype,
            "players": " ".join(player.name for player in s.players)
        })
        self.assertIs(r.playstate, PlayState.JUST_STARTED)
        self.assertIs(r.gamestate, GameState.PLAYING)
        self.assertEqual(len(s.master_deck), 108)
        self.assertEqual(len(s.discard_deck), 0)
        self.assertEqual(len(s.draw_deck), 108-7-7-1)
        self.assertEqual(len(r.player.deck), 7)
        self.assertEqual(len(r.nextplayer.deck), 7)

    def testStartWithColorCard(self):
        s = self._init_session()
        card = self._card_fromshand(s, "j")
        r = self._start_session(s, start_card=card)

        self.assertEqual(r.currentcard.attribs, Card.ATTRIB_CCH)
        self.assertIs(r.player, s.current_player)
        self.assertIs(r.nextplayer, s.next_player)
        self.assertIs(r.currentcard, s.current_card)
        self.assertIs(r.currentcard, card)
        self.assertIs(r.card, None)
        self.assertIs(r.additionalcard, None)
        self.assertDictEqual(r.outcome, {
            "affected": r.player,
            "affected_attribs": Card.ATTRIB_CCH,
            "picked_cnt": 0,
            "deck_flipped": False,
            "playtype": s.playtype,
            "players": " ".join(player.name for player in s.players)
        })
        self.assertIs(r.playstate, PlayState.JUST_STARTED)
        self.assertIs(r.gamestate, GameState.WAITING_COLOR_COLCARD)

    def testStartWithPickCard(self):
        s = self._init_session()
        card = self._card_fromshand(s, "r+2")
        cards = s.draw_deck.cards[-16:-14]
        cards.sort(key=lambda x: (x.dispcolor, x.points))        
        picked_cards = "\x02{}\x02".format("  ".join(map(lambda c: c.name(bold=False), cards)))
        r = self._start_session(s, start_card=card)
        attribs = Card.ATTRIB_PKC | Card.ATTRIB_SKP
        p1, p2 = s.players

        self.assertEqual(r.currentcard.attribs, attribs)
        self.assertIs(r.player, p2)
        self.assertIs(r.player, s.current_player)
        self.assertIs(r.nextplayer, p1)
        self.assertIs(r.nextplayer, s.next_player)
        self.assertIs(r.currentcard, s.current_card)
        self.assertIs(r.currentcard, card)
        self.assertIs(r.card, None)
        self.assertIs(r.additionalcard, None)
        self.assertDictEqual(r.outcome, {
            "affected": p1,
            "affected_attribs": attribs,
            "picked_cards": picked_cards,
            "picked_cnt": 2,
            "deck_flipped": False,
            "playtype": s.playtype,
            "players": " ".join(player.name for player in s.players)
        })
        self.assertIs(r.playstate, PlayState.JUST_STARTED)
        self.assertIs(r.gamestate, GameState.PLAYING)
        self.assertEqual(len(p1.deck), 9)

    def testStartWithSkipCard(self):
        s = self._init_session()
        card = self._card_fromshand(s, "rs")
        r = self._start_session(s, start_card=card)

        self.assertEqual(r.currentcard.attribs, Card.ATTRIB_SKP)
        self.assertIs(r.player, s.current_player)
        self.assertIs(r.nextplayer, s.next_player)
        self.assertIs(r.currentcard, s.current_card)
        self.assertIs(r.currentcard, card)
        self.assertIs(r.card, None)
        self.assertIs(r.additionalcard, None)
        self.assertDictEqual(r.outcome, {
            "affected": r.nextplayer,
            "affected_attribs": Card.ATTRIB_SKP,
            "picked_cnt": 0,
            "deck_flipped": False,
            "playtype": s.playtype,
            "players": " ".join(player.name for player in s.players)
        })
        self.assertIs(r.playstate, PlayState.JUST_STARTED)
        self.assertIs(r.gamestate, GameState.PLAYING)

    def testStartWithReverseCard(self):
        s = self._init_session()
        players = s.players
        # FIXME: ensure that reverse card really reverses player order
        card = self._card_fromshand(s, "rr")
        r = self._start_session(s, start_card=card, shuffle_players=True)

        self.assertEqual(r.currentcard.attribs, Card.ATTRIB_REV)
        self.assertIs(r.player, s.current_player)
        self.assertIs(r.nextplayer, s.next_player)
        self.assertIs(r.currentcard, card)
        self.assertIs(r.currentcard, s.current_card)
        self.assertIs(r.card, None)
        self.assertIs(r.additionalcard, None)
        self.assertDictEqual(r.outcome, {
            "affected": None,
            "affected_attribs": Card.ATTRIB_REV,
            "picked_cnt": 0,
            "deck_flipped": False,
            "playtype": s.playtype,
            "players": " ".join(player.name for player in s.players)
        })
        self.assertEqual(s.players, players)
        self.assertIs(r.playstate, PlayState.JUST_STARTED)
        self.assertIs(r.gamestate, GameState.PLAYING)

    def testPlaySkip(self):
        s = self._init_session()
        r = self._start_session(s, start_card=self._card_fromshand(s, "r2"))
        ply = s.current_player
        nextply = s.next_player
        if "rs" not in ply.deck:
            card = self._givecard(s, ply, "rs")
        else:
            card, _ = ply.deck.card_from_shorthand("rs")

        self._test_mustpick(s, ply)
        r = s.play("rs")

        self.assertIs(r.player, ply)
        self.assertIs(r.nextplayer, ply)
        self.assertIs(r.currentcard, card)
        self.assertIs(r.card, card)
        self.assertIs(r.additionalcard, None)
        self.assertEqual(r.outcome,  {
            "affected": nextply,
            "affected_attribs": Card.ATTRIB_SKP,
            "picked_cnt": 0,
            "deck_flipped": False
        })
        self.assertIs(s.current_player, ply)
        self.assertIs(s.next_player, nextply)
        self.assertIs(r.playstate, PlayState.VALID_PLAY)

    def testPlayDrawTwo(self):
        s = self._init_session()
        r = self._start_session(s)

        # TODO
        # s.current_card = self._card_fromshand(s, "r0")
        # ply = s.current_player
        # nextply = s.next_player
        
        # card = self._givecard(s, ply, "r+2")
        # self._test_mustpick(s, ply)
        # r = s.play("r+2")

        # self.assertIs(r.player, ply)
        # self.assertIs(r.nextplayer, ply)
        # self.assertIs(r.currentcard, card)
        # self.assertIs(r.card, card)
        # self.assertIs(r.additionalcard, None)
        # self.assertEqual(r.outcome, {})
        # self.assertIs(r.playstate, PlayState.VALID_PLAY)

    def testDeckFlip(self):
        pass

    def _test_mustpick(self, s, ply):
        r = s.skip()
        self.assertIs(r.player, ply)
        self.assertIs(r.nextplayer, s.next_player)
        self.assertIs(r.currentcard, s.current_card)
        self.assertIs(r.card, None)
        self.assertIs(r.additionalcard, None)
        self.assertEqual(r.outcome, {})
        self.assertIs(r.playstate, PlayState.MUST_PICK)

    def _add_players(self, s):
        s.add_player("P1Chewbacca")
        s.add_player("P2HanSolo")

    def _card_fromshand(self, s, shand):
        card, _ = s.master_deck.card_from_shorthand(shand)
        return card

    def _givecard(self, s, ply, shand):
        card = self._card_fromshand(s, shand)
        ply.pick(card)
        s.draw_deck.remove_card(card)
        return card



#class TestUnoEngineNoskipMode(unittest.TestCase):
#
#
#
#class TestUnoEngineExplicitNoneMode(TestUnoEngineTwoPlClassicMode):
#
#
#class TestUnoEngineImplicitNoneMode(TestUnoEngineTwoPlClassicMode):
#