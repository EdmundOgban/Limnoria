import logging
import random
import string

from collections import defaultdict, namedtuple
from enum import Enum, unique
from itertools import chain, repeat, cycle, tee, islice

#NAME_RED = "{b}{k}1,4 {k} Rosso{b}"
#NAME_YELLOW = "{b}{k}1,8 {k} Giallo{b}"
#NAME_GREEN = "{b}{k}1,9 {k} Verde{b}"
#NAME_BLUE = "{b}{k}1,12 {k} Blu{b}"
NAME_RED = "Rosso"
NAME_YELLOW = "Giallo"
NAME_GREEN = "Verde"
NAME_BLUE = "Blu"
NAME_SKIP = "Skip"
NAME_REVERSE = "Rvrs"
NAME_P2 = "+2"
NAME_BLACKP4 = "Jolly +4"
NAME_BLACKCC = "Jolly"
FMT_COLORCARD = "{prefix} {suffix}"

CONSONANTS = set(string.ascii_letters) - set('aeiou')

UnoResponse = namedtuple("UnoResponse", ["player", "nextplayer", "currentcard",
    "card", "additionalcard", "outcome", "gamestate", "playstate"])


log = logging.getLogger("supybot")


@unique
class PlayState(Enum):
    NOT_JOINED = -2
    NOT_YOUR_TURN = -1
    JUST_STARTED = 0
    VALID_PLAY = 1
    VALID_DOUBLE = 2
    INVALID_PLAY = 3
    INVALID_DOUBLE_PLAY = 4
    CARD_NOT_IN_DECK = 5
    CARD_NOT_EXIST = 6
    MUST_PICK = 7
    PICKED_CARD = 8
    ALREADY_PICKED = 9
    CANT_PICK = 10
    MUST_CHOOSE_COLOR = 11
    INVALID_COLOR = 12
    COLOR_CHOSEN = 13
    COLOR_ALREADY_CHOSEN = 14
    SKIPPED_TURN = 15
    SKIPPED_TURN_AFTER_DRAW = 16
    ADVISE_CARDS = 17
    GAME_WON = 18
    GAME_ENDED = 19
    NOT_ENOUGH_PLAYERS = 20
    PLAYER_REMOVED = 21


@unique
class GameState(Enum):
    WAITING_PLAYERS = 0
    PLAYING = 1
    WAITING_COLOR_COLCARD = 2
    WAITING_COLOR_COLDRAWCARD = 3
    WAITING_COLOR_COLDRAWSKIPCARD = 4
    WAITING_ANSWER_DRAWCARD = 5
    GAME_ENDED = 6


@unique
class GameInput(Enum):
    JOIN_TIMED_OUT = 0
    PLAYED_COLCARD = 1
    PLAYED_COLDRAWCARD = 2
    PLAYED_COLDRAWSKIPCARD = 3
    PLAYED_DRAWCARD = 4
    PLAYED_DRAWSKIPCARD = 5
    COLOR_SET = 6
    PLAYER_SKIP = 7
    GAME_WON = 8
    GAME_ENDED = 9


STATES = {
    GameState.WAITING_PLAYERS: {
        GameInput.JOIN_TIMED_OUT: GameState.PLAYING,
        GameInput.PLAYED_COLCARD: GameState.WAITING_COLOR_COLCARD,
        GameInput.PLAYED_DRAWCARD: GameState.WAITING_ANSWER_DRAWCARD,
        GameInput.PLAYED_DRAWSKIPCARD: GameState.PLAYING,
        GameInput.GAME_ENDED: GameState.GAME_ENDED
    },

    GameState.PLAYING: {
        GameInput.PLAYED_COLCARD: GameState.WAITING_COLOR_COLCARD,
        GameInput.PLAYED_COLDRAWCARD: GameState.WAITING_COLOR_COLDRAWCARD,
        GameInput.PLAYED_COLDRAWSKIPCARD: GameState.WAITING_COLOR_COLDRAWSKIPCARD,
        GameInput.PLAYED_DRAWCARD: GameState.WAITING_ANSWER_DRAWCARD,
        GameInput.PLAYED_DRAWSKIPCARD: GameState.PLAYING,
        GameInput.GAME_ENDED: GameState.GAME_ENDED
    },

    GameState.WAITING_COLOR_COLCARD: {
        GameInput.COLOR_SET: GameState.PLAYING,
        GameInput.GAME_ENDED: GameState.GAME_ENDED
    },

    GameState.WAITING_COLOR_COLDRAWCARD: {
        GameInput.COLOR_SET: GameState.WAITING_ANSWER_DRAWCARD,
        GameInput.GAME_ENDED: GameState.GAME_ENDED
    },

    GameState.WAITING_COLOR_COLDRAWSKIPCARD: {
        GameInput.COLOR_SET: GameState.PLAYING,
        GameInput.GAME_ENDED: GameState.GAME_ENDED
    },

    GameState.WAITING_ANSWER_DRAWCARD: {
        GameInput.PLAYER_SKIP: GameState.PLAYING,
        GameInput.PLAYED_COLDRAWCARD: GameState.WAITING_COLOR_COLDRAWCARD,
        GameInput.PLAYED_DRAWCARD: GameState.WAITING_ANSWER_DRAWCARD,
        GameInput.GAME_ENDED: GameState.GAME_ENDED
    },

    GameState.GAME_ENDED: {
    }
}


def pairwise(it):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = map(cycle, tee(it))
    next(b, None)
    return zip(a, b)


def consume(it, n):
    "Advance the iterator n-steps ahead."
    next(islice(it, n, n), None)


class StateMachine:
    def __init__(self, initial_state):
        transitions = STATES.get(initial_state)
        if transitions is None:
            raise ValueError("Invalid state: {}".format(initial_state))

        self._curstate = initial_state
        self._transitions = transitions

    def emit(self, inp):
        next_state = self._transitions.get(inp)
        if next_state is not None:
            self._curstate = next_state
            self._transitions = STATES[next_state]
            return True

        return False

    @property
    def state(self):
        return self._curstate

    def __repr__(self):
        return "{}({})".format(self.__class__.__name__, self._curstate)


class Card:
    ATTRIB_REV = set(["reverse"])
    ATTRIB_SKP = set(["skip"])
    ATTRIB_CCH = set(["colorchange"])
    ATTRIB_PKC = set(["pickcards"])
    ATTRIB_NUL = set()

    def __init__(self, name, *, value=0, points=0, attribs=ATTRIB_NUL,
        color=None, dispcolor=""):
        self._name = name
        self.color = color
        self.dispcolor = dispcolor
        self.value = value
        self.points = points
        self.attribs = attribs

    def play_over(self, card):
        blackcard = card.color is not None and self.color is None
        same_color = card.color is not None and self.color == card.color
        same_value = (card.color is not None and self.value == card.value
            and self.attribs == card.attribs == self.ATTRIB_NUL)
        specialcard = (card.color is not None and self.color is not None
            and self.attribs == card.attribs != self.ATTRIB_NUL)

        return any([blackcard, same_color, same_value, specialcard])

    def double_play(self, card):
        return (self.color == card.color
            and self.value == card.value
            and self.attribs == card.attribs == self.ATTRIB_NUL)

    def name(self, *, colored=True, bold=True):
        if colored is True:
            c = Deck.IRC_CARDCOLORS[self.color]
            fmt = "{b}{k}1,{c} {k} {{}}{b}".format(
                c=c, k="\x03", b="\x02" if bold else "")
        else:
            fmt = "{}"

        return fmt.format(self._name)
        #return fmt.format(self.shorthand).upper()

    @property
    def shorthand(self):
        try:
            pfx, sfx = self._name.split(" ", 1)
        except ValueError:
            pfx, sfx = self._name[0], ""
        else:
            pfx = pfx[0]
            sfx = sfx[0]

        if self.ATTRIB_PKC & self.attribs:
            sfx = "+{}".format(self.value)

        return "{}{}".format(pfx.lower(), sfx.lower())

    def __repr__(self):
        return ("{}(name='{}', value={}, points={}, attribs={}, "
            "color={}, dispcolor={})".format(self.__class__.__name__,
                self._name, self.value, self.points, self.attribs,
                repr(self.color) if self.color is not None else 'None',
                repr(self.dispcolor)))

    def __str__(self):
        return self.name()


class Deck:
    VALUE_RED = "red"
    VALUE_YELLOW = "yellow"
    VALUE_GREEN = "green"
    VALUE_BLUE = "blue"

    COLORCARDS_COLORS = [
        (NAME_RED, VALUE_RED),
        (NAME_YELLOW, VALUE_YELLOW),
        (NAME_GREEN, VALUE_GREEN),
        (NAME_BLUE, VALUE_BLUE)
    ]

    DISPLAYED_COLORS = {
        VALUE_RED: NAME_RED,
        VALUE_YELLOW: NAME_YELLOW,
        VALUE_GREEN: NAME_GREEN,
        VALUE_BLUE: NAME_BLUE
    }

    IRC_CARDCOLORS = {
        VALUE_RED: 4,
        VALUE_YELLOW: 8,
        VALUE_GREEN: 9,
        VALUE_BLUE: 12,
        None: 0
    }

    def __init__(self):
        self.cards = []
        self._cards_lookup = defaultdict(list)

    def populate(self, *, playtype):
        if playtype in ("classic", None):
            drawcards_skips = Card.ATTRIB_SKP
        elif playtype == "noskip":
            drawcards_skips = Card.ATTRIB_NUL

        colorcards_special = [
            (0, NAME_SKIP, Card.ATTRIB_SKP),
            (0, NAME_REVERSE, Card.ATTRIB_REV),
            (2, NAME_P2, Card.ATTRIB_PKC | drawcards_skips),
        ]
        blackcards = [
            (4, NAME_BLACKP4, Card.ATTRIB_PKC | Card.ATTRIB_CCH | drawcards_skips),
            (0, NAME_BLACKCC, Card.ATTRIB_CCH)
        ]
        for prefix, color in self.COLORCARDS_COLORS:
            dispcolor = self.DISPLAYED_COLORS[color]

            self.cards.append(Card(
                FMT_COLORCARD.format(prefix=prefix, suffix=0),
                color=color,
                dispcolor=dispcolor
            ))

            for value in chain(*repeat(range(1, 10), 2)):
                self.cards.append(Card(
                    FMT_COLORCARD.format(prefix=prefix, suffix=value),
                    color=color,
                    dispcolor=dispcolor,
                    value=value,
                    points=value
                ))

            for value, suffix, attribs in chain(*repeat(colorcards_special, 2)):
                self.cards.append(Card(
                    FMT_COLORCARD.format(prefix=prefix, suffix=suffix),
                    color=color,
                    dispcolor=dispcolor,
                    attribs=attribs,
                    value=value,
                    points=20,
                ))

        for value, name, attribs in chain(*repeat(blackcards, 4)):
            self.cards.append(Card(
                name,
                attribs=attribs,
                value=value,
                points=50,
            ))

        for card in self.cards:
            self._cards_lookup[card.shorthand].append(card)

    def shuffle(self):
        random.shuffle(self.cards)

    def flip(self, deck):
        if len(self.cards) == 0:
            self.cards = deck.cards
            self._cards_lookup = deck._cards_lookup
            self.shuffle()
            deck.purge()

    def purge(self):
        self.cards = []

    def add_card(self, card):
        # This check is unnecessary, but we're playing extra safe.
        if card in self.cards:
            raise RuntimeError("the impossible happened: found a duped"
                " card in a deck")

        self.cards.append(card)
        self._cards_lookup[card.shorthand].append(card)

    def remove_card(self, card):
        try:
            self.cards.remove(card)
        except ValueError:
            return False
        else:
            self._cards_lookup[card.shorthand].remove(card)
            return True

    def draw_card(self):
        try:
            card = self.cards.pop()
        except IndexError:
            return
        else:
            self._cards_lookup[card.shorthand].remove(card)
            return card

    @staticmethod
    def color_from_shortand(shand):
        for prefix, card_color in Deck.COLORCARDS_COLORS:
            prefix_shand = prefix[0].lower()
            if prefix_shand == shand:
                return card_color

        return False

    def card_from_shorthand(self, shand, shand2=None):
        shand = shand.lower()
        if shand2 is not None:
            shand2 = shand2.lower()

        card = self._cards_lookup.get(shand)
        if shand == shand2:
            if len(card) > 1:
                # FIXME
                card2 = [card[1]]
            else:
                card2 = self._cards_lookup.get(shand2)
        else:
            card2 = self._cards_lookup.get(shand2)

        return card[0] if card else None, card2[0] if card2 else None

    def copy(self):
        obj = Deck()
        obj.cards = self.cards[:]
        obj._cards_lookup = self._cards_lookup.copy()
        return obj

    def __contains__(self, other):
        if isinstance(other, Card):
            return other.shorthand in self._cards_lookup
        elif isinstance(other, str):
            return other in self._cards_lookup
        else:
            return False

    def __iter__(self):
        for card in self.cards:
            yield card

    def __len__(self):
        return len(self.cards)


def _shorten(s, n):
    if len(s) <= n:
        return s

    s2 = [c for c in s[1:] if c in CONSONANTS]
    remaining = len(s2) - n + 1
    if remaining > 0:
        d = {}
        for c in s2:
            if c not in d:
                d[c] = s2.count(c)
        for cons, cnt in d.items():
            if cnt > 1:
                s2.remove(cons)

    return s[0] + "".join(s2)


class Player:
    def __init__(self, name):
        self.name = name
        self.deck = Deck()
        self.hand_picked = False
        self.declared_uno = False
        self.bluffed = False

    def play_card(self, current_card, shand, shand2=None, *, pretend=False):
        card, card2 = self.deck.card_from_shorthand(shand, shand2)

        if card is None or (shand2 is not None and card2 is None):
            return [None, None, PlayState.CARD_NOT_IN_DECK]

        # The following two checks are unnecessary, but we're playing extra safe.
        if current_card is card:
            raise RuntimeError("Play against the same card")

        if card is card2:
            raise RuntimeError("Double play against the same card")

        if card.play_over(current_card) is False:
            return [card, None, PlayState.INVALID_PLAY]

        if card2 is not None:
            if card.double_play(card2) is False:
                return [card, card2, PlayState.INVALID_DOUBLE_PLAY]

            if pretend is False:
                self.deck.remove_card(card2)

        if pretend is False:
            self.deck.remove_card(card)

        return [card, card2, PlayState.VALID_DOUBLE if card2
            else PlayState.VALID_PLAY]

    def pick(self, card):
        self.declared_uno = False
        self.deck.add_card(card)

    @property
    def cards(self):
        cards_cnt = len(self.deck)
        if cards_cnt == 0:
            return ""

        #formatted = []
        sorted_cards = sorted(self.deck, key=lambda x: (x.dispcolor, x.points))
        # for card in sorted_cards:
            # shortened = []
            # for token in card.name(colored=False).split(" "):
                # if len(token) > 3 and cards_cnt >= 12:
                    # newtok = _shorten(token, 3)
                # else:
                    # newtok = token

                # shortened.append(newtok)

            # cardname = " ".join(shortened)
            # formatted.append([cardname, Deck.IRC_CARDCOLORS[card.color]])

        return [card.name(bold=False) for card in sorted_cards]

    @property
    def at_uno(self):
        return len(self.deck) == 1

    @property
    def winner(self):
        return len(self.deck) == 0

    def __eq__(self, other):
        return other == self.name

    def __hash__(self):
        return hash(self.name)

    def __str__(self):
        return self.name

    def __repr__(self):
        return "{}('{}')".format(
            self.__class__.__name__, self.name)

class Session:
    def __init__(self, playtype=None):
        self.master_deck = Deck()
        self.discard_deck = Deck()
        self.smac = StateMachine(GameState.WAITING_PLAYERS)
        self.players = []
        self.current_player = None
        self.current_card = None
        self.next_player = None
        self.firstround = True
        self._player_iter = None
        self._picked_cnt = 0
        self.playtype = playtype or "classic"
        self.master_deck.populate(playtype=self.playtype)
        self.draw_deck = self.master_deck.copy()
        self.draw_deck.shuffle()

    def add_player(self, name):
        if (self.smac.state is not GameState.WAITING_PLAYERS
            or name in self.players):
            return

        if len(self.players) == 10:
            return False

        newp = Player(name)
        self.players.append(newp)
        return True

    def remove_player(self, name):
        if name not in self.players:
            return

        player = self.player_from_name(name)
        top = len(self.draw_deck.cards) - 2
        for card in player.deck:
            pos = random.randint(1, top)
            self.draw_deck.cards.insert(pos, card)            
            top += 1

        self.players.remove(player)
        if len(self.players) == 1:
            outcome, _ = self._end_game()
            playstate = PlayState.NOT_ENOUGH_PLAYERS
        else:
            if self.current_player.name == name:
                self.current_player = self.next_player

            self._refresh_players()
            # Prime the iterator
            self._next_turn()
            # FIXME: re-applying the card effects make the cards with
            #  attributes act twice
            outcome = self._apply_effects()
            outcome["removedply"] = name
            # FIXME: This must repeat the last playstate
            playstate = PlayState.PLAYER_REMOVED

        return self._compile_response(outcome=outcome,
            playstate=playstate)

    def player_from_name(self, name):
        for player in self.players:
            if player.name == name:
                return player

    def advise_cards(self, player_name):
        player = self.player_from_name(player_name)
        if not player:
            return

        return self._compile_response(player=player,
            playstate=PlayState.ADVISE_CARDS)

    def start(self, *, start_card=None, shuffle_players=True):
        if len(self.players) < 2:
            return False

        if self.smac.state is not GameState.WAITING_PLAYERS:
            return

        if shuffle_players is True:
            random.shuffle(self.players)

        # Give 7 cards, one at a time for each player
        for _ in range(7):
            for player in self.players:
                card = self.draw_deck.draw_card()
                player.pick(card)

        self._next_turn()
        if start_card is not None:
            self.current_card = start_card
            self.draw_deck.remove_card(start_card)
        else:
            self.current_card = self._draw_first_card()

        if self.current_card.attribs & Card.ATTRIB_CCH:
            self.smac.emit(GameInput.PLAYED_COLCARD)
        else:
            self.smac.emit(GameInput.JOIN_TIMED_OUT)

        outcome = self._apply_effects()
        outcome.update({
            "playtype": self.playtype,
            "players": " ".join(map(str, self.players))
        })
        return self._compile_response(
            outcome=outcome, playstate=PlayState.JUST_STARTED)

    def setcolor(self, shand):
        card = None
        outcome = {}
        curplayer = self.current_player
        nextplayer = self.next_player

        if self.current_card.color is None:
            color = Deck.color_from_shortand(shand)
            if color is not False:
                card = self.current_card
                card.color = color
                card.dispcolor = Deck.DISPLAYED_COLORS[color]
                if (self.smac.emit(GameInput.COLOR_SET) is True
                    and self.firstround is False):
                    if card.attribs & Card.ATTRIB_SKP:
                        outcome = self._pick_after_drawcard(nextplayer)
                        if len(self.players) > 2:
                            self._next_turn()
                    else:
                        self._next_turn()

                playstate = PlayState.COLOR_CHOSEN
            else:
                # FIXME
                card = Card("", color=shand)
                playstate = PlayState.INVALID_COLOR
        else:
            playstate = PlayState.COLOR_ALREADY_CHOSEN

        return self._compile_response(player=curplayer, nextplayer=nextplayer,
            card=card, outcome=outcome, playstate=playstate)

    def pick(self):
        response = self._check_playing()
        if response is not True:
            return response

        if self.smac.state is GameState.WAITING_ANSWER_DRAWCARD:
            card, flipped = self.current_card, False
            playstate = PlayState.CANT_PICK
        else:
            if self.current_player.hand_picked is False:
                card, flipped = self._safe_pickdeck_draw()
                self.current_player.pick(card)
                self.current_player.hand_picked = True
                playstate = PlayState.PICKED_CARD
            else:
                card, flipped = None, False
                playstate = PlayState.ALREADY_PICKED

        return self._compile_response(card=card,
            outcome={"deck_flipped": flipped},
            playstate=playstate)

    def skip(self):
        curplayer = self.current_player
        nextplayer = self.next_player
        outcome = {}
        response = self._check_playing()
        if response is not True:
            return response

        if curplayer.hand_picked is True:
            playstate = PlayState.SKIPPED_TURN
            self._next_turn()
        elif self.smac.emit(GameInput.PLAYER_SKIP) is True:
            outcome = self._pick_after_drawcard(curplayer)
            playstate = PlayState.SKIPPED_TURN_AFTER_DRAW
            self._next_turn()
        else:
            playstate = PlayState.MUST_PICK

        return self._compile_response(player=curplayer, nextplayer=nextplayer,
            outcome=outcome, playstate=playstate)

    def stop(self):
        outcome, playstate = self._end_game()
        return self._compile_response(outcome=outcome, playstate=playstate)

    def _validate_play(self, shand, shand2):
        outcome = {}

        card, card2, playstate = self.current_player.play_card(
            self.current_card, shand, shand2, pretend=True)

        if (playstate in (PlayState.VALID_PLAY, PlayState.VALID_DOUBLE)
            and self.smac.state is GameState.WAITING_ANSWER_DRAWCARD
            and not card.attribs & Card.ATTRIB_PKC):
            playstate = PlayState.INVALID_PLAY
            card2 = self.current_card
            outcome.update({
                "affected": self.current_player,
                "affected_attribs": Card.ATTRIB_SKP | Card.ATTRIB_PKC,
                "picked_cnt": self._picked_cnt,
                "deck_flipped": False
            })
        elif playstate is PlayState.CARD_NOT_IN_DECK:
            card, card2 = self.master_deck.card_from_shorthand(shand, shand2)
            if card is None:
                card = Card(shand)
                card2 = card2 or Card(shand2)
                playstate = PlayState.CARD_NOT_EXIST

        return card, card2, outcome, playstate

    def play(self, shand, shand2=None):
        response = self._check_playing()
        if response is not True:
            return response

        # FIXME: I don't really like setting firstround = False here...
        self.firstround = False
        playedby = self.current_player
        nextply = self.next_player
        card, card2, outcome, playstate = self._validate_play(shand, shand2)

        if playstate in (PlayState.VALID_PLAY, PlayState.VALID_DOUBLE):
            self.current_player.play_card(self.current_card, shand, shand2)
            self._next_card(card, card2)
            outcome = self._apply_effects()
            if playedby.winner is True:
                outcome, playstate = self._end_game(won=True)

            if self.smac.state in (GameState.PLAYING,
                GameState.WAITING_ANSWER_DRAWCARD):
                self._next_turn()
                nextply = self.current_player

        return self._compile_response(player=playedby,
            nextplayer=nextply,
            card=card, additionalcard=card2,
            outcome=outcome, playstate=playstate)

    def _next_card(self, card, card2):
        self.discard_deck.add_card(self.current_card)
        if card2:
            self.discard_deck.add_card(card2)

        if self.current_card.attribs & Card.ATTRIB_CCH:
            self.current_card.color = None

        self.current_card = card

    def _next_turn(self):
        if self._player_iter is None:
            self._player_iter = pairwise(self.players)

        if self.current_player is not None:
            self.current_player.hand_picked = False

        self.current_player, self.next_player = next(self._player_iter)

    def _refresh_players(self):
        it = pairwise(self.players)
        consume(it, self.players.index(self.current_player))
        self._player_iter = it

    def _reverse_order(self):
        self.players.reverse()
        self._refresh_players()
        # In case of two players, the same player must have another go
        if len(self.players) > 2:
            self._next_turn()

    def _apply_effects(self):
        prev_player = self.current_player
        attribs = self.current_card.attribs
        picked_cnt = self._picked_cnt
        outcome = {}

        if attribs == Card.ATTRIB_CCH:
            self.smac.emit(GameInput.PLAYED_COLCARD)

        if attribs & Card.ATTRIB_PKC:
            self._picked_cnt += self.current_card.value
            if attribs & Card.ATTRIB_CCH and attribs & Card.ATTRIB_SKP:
                self.smac.emit(GameInput.PLAYED_COLDRAWSKIPCARD)
            elif attribs & Card.ATTRIB_CCH:
                self.smac.emit(GameInput.PLAYED_COLDRAWCARD)
            elif attribs & Card.ATTRIB_SKP:
                self.smac.emit(GameInput.PLAYED_DRAWSKIPCARD)
                picked_cnt = self._picked_cnt
                if self.firstround:
                    pl = self.current_player
                else:
                    pl = self.next_player
                outcome_draw = self._pick_after_drawcard(pl)
                outcome.update(outcome_draw)
            else:
                self.smac.emit(GameInput.PLAYED_DRAWCARD)

        if attribs & Card.ATTRIB_REV:
            self._reverse_order()
            if self.firstround is False:
                outcome["players"] = " ".join(map(str, self.players))

        if attribs & Card.ATTRIB_SKP and not attribs & Card.ATTRIB_CCH:
            self._next_turn()

        if attribs:
            if self.firstround is True:
                pl = prev_player
            else:
                pl = self.current_player

            if attribs == Card.ATTRIB_REV:
                pl = None

            outcome.update({
                "affected": pl,
                "affected_attribs": attribs,
                "picked_cnt": picked_cnt,
                "deck_flipped": False
            })

        return outcome

    def _draw_first_card(self):
        card = self.draw_deck.draw_card()
        # Can't start with a blackcard +4
        while (card.value == 4 and card.color is None
            and card.attribs & (Card.ATTRIB_PKC | Card.ATTRIB_CCH)):
            # We put it back in the pick deck in a random spot (but
            # not on top and not at the bottom)
            pos = random.randint(1, len(self.draw_deck.cards) - 2)
            self.draw_deck.cards.insert(pos, card)
            card = self.draw_deck.draw_card()

        return card

    def _compile_response(self, *, player=None, nextplayer=None,
        card=None, additionalcard=None, outcome=None, playstate=None):
        return UnoResponse(
            gamestate=self.smac.state,
            player=player or self.current_player,
            nextplayer=nextplayer or self.next_player,
            currentcard=self.current_card,
            card=card,
            additionalcard=additionalcard,
            outcome=outcome or {},
            playstate=playstate)

    def _check_playing(self):
        if self.smac.state is GameState.WAITING_PLAYERS:
            return

        if self.smac.state in (GameState.WAITING_COLOR_COLCARD,
            GameState.WAITING_COLOR_COLDRAWCARD,
            GameState.WAITING_COLOR_COLDRAWSKIPCARD):
            return self._compile_response(playstate=PlayState.MUST_CHOOSE_COLOR)

        return True

    def _safe_pickdeck_draw(self):
        card = self.draw_deck.draw_card()
        # Deck is signaling that it's done, swap it with the discard
        # deck, shuffle it and go on
        if card is None:
            # FIXME: if everyone picks without playing, this will broke
            # at some point.
            self.draw_deck.flip(self.discard_deck)
            card = self.draw_deck.draw_card()
            flipped = True
        else:
            flipped = False

        return card, flipped

    def _pick_after_drawcard(self, player):
        attribs = self.current_card.attribs - Card.ATTRIB_CCH
        picked_cards = []
        for _ in range(self._picked_cnt):
            card, flipped = self._safe_pickdeck_draw()
            picked_cards.append(card)
            player.pick(card)

        picked_cards.sort(key=lambda x: (x.dispcolor, x.points))

        # FIXME: Duplicated code ######################################
        formatted = []
        for card in picked_cards:
            shortened = []
            for token in card.name(colored=False).split(" "):
                if len(token) > 3 and len(picked_cards) >= 12:
                    newtok = _shorten(token, 3)
                else:
                    newtok = token

                shortened.append(newtok)

            formatted.append([" ".join(shortened), Deck.IRC_CARDCOLORS[card.color]])

        s_picked_cards = "  ".join("{k}1,{c} {k} {n}".format(
            c=color, n=name, k="\x03") for name, color in formatted)
        # ##############################################################

        outcome = {
            "affected": player,
            "affected_attribs": attribs,
            "picked_cards": "\x02{}\x02".format(s_picked_cards),
            "picked_cnt": self._picked_cnt,
            "deck_flipped": flipped,
        }
        self._picked_cnt = 0
        return outcome

    def _scoreboard(self, *, won=False, top=5):
        outcome = {}
        scoreboard = []
        if self.current_player:
            if won is True:
                self.players.remove(self.current_player)

            win_points = 0
            for player in self.players[:top]:
                points = sum(card.points for card in player.deck.cards)
                scoreboard.append([player, points])
                win_points += points

            scoreboard.sort(key=lambda x: x[1])
            outcome.update({
                "scoreboard": scoreboard,
                "win_points": win_points
            })

        return outcome

    def _end_game(self, *, won=False):
        self.smac.emit(GameInput.GAME_ENDED)
        if won is True:
            playstate = PlayState.GAME_WON
        else:
            playstate = PlayState.GAME_ENDED

        return self._scoreboard(won=won), playstate
