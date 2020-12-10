###
# Copyright (c) 2017, Edmund Ogban
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
import supybot.world as world
from supybot.commands import *
import supybot.plugins as plugins
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks
import supybot.schedule as schedule
import supybot.ircmsgs as ircmsgs
import supybot.ircdb as ircdb
import supybot.log as logger
import supybot.plugins.Google.translators.google.langs as tr_langs
try:
    from supybot.i18n import PluginInternationalization
    _ = PluginInternationalization('Random')
except ImportError:
    # Placeholder that allows to run the plugin on a bot
    # without the i18n module
    _ = lambda x: x

import supybot.conf as conf

import kyotocabinet
import os
import random
import re
import string
import threading
import time
from collections import defaultdict, deque
from time import sleep, monotonic, gmtime, strftime
from functools import partial
from supybot.plugins.Google.translators.deepl import translate as deepl, langs as deeplangs

from . import rand
from . import randre
from . import wordsdbmgr


DEFAULT_JAMU_LANG = "it"
JAMU_CACHE_SIZE = 10


class TranslationError(ValueError):
    pass


class MyVisitor(kyotocabinet.Visitor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.content = []

    def visit_full(self, k, v):
        self.content.append((k.decode(), v.decode()))


class KeysVisitor(MyVisitor):
    def visit_full(self, k, v):
        self.content.append(k.decode())


class ValuesVisitor(MyVisitor):
    def visit_full(self, k, v):
        self.content.append(v.decode())


def _db_get_content(db, visitor):
    db.iterate(visitor)
    return visitor.content


def db_get_keys(db):
    return _db_get_content(db, KeysVisitor())


def db_get_values(db):
    return _db_get_content(db, ValuesVisitor())


def _sanitize_nick(nick):
    return ''.join(c for c in nick.lower()
        if c in string.ascii_lowercase or c.isdigit())


class JamuFactory():
    def _pre_validator(self, text, *, to_lang):
        return True

    def _pre_filter(self, text):
        return text

    def _post_validator(self, text, *, to_lang):
        return True

    def _post_filter(self, text):
        return text

    def jamu(self, to_lang):
        raise NotImplementedError


class JamuSupyGetter():
    def _check_for_google(self):
        callbacks = {callback.name(): callback for callback in self.irc.callbacks}

        try:
            google = callbacks["Google"]
        except KeyError:
            raise KeyError("Google Translate plugin is not loaded.")
        else:
            return google

    def _translate_jamu(self, to_lang, text):
        google = self._check_for_google()
        text, _ = google._translate('ja', to_lang, text, allTranslations=True)
        return text


def _build_alphabet():
    hira = "あいうえおかがくぐけげこごさざすずせぜそぞただぢつづてでとどなぬねのはばぱふぶぷへべぺほぼぽまむめもやゆよらるれろわをんゔ"
    yoon_roots = 'きぎき゚ひびぴしじちにみり'
    # (this used to include "き゚" too)
    smalls = "ゃゅょ"
    yoons = [root + s for root in yoon_roots for s in smalls]
    return [*hira, *yoon_roots, *yoons] # , "っ"]

HIRAGANA_ALPHABET = _build_alphabet()


def ratto_hiragana(min_length=6, max_length=50):
    text = "".join(
        random.choices(HIRAGANA_ALPHABET, k=random.randint(min_length, max_length))
    )
    return text


class JamuManager(JamuFactory, JamuSupyGetter):
    def __init__(self):
        self.wdbmgr = wordsdbmgr.WordsDBManager()
        self.log = logger.getPluginLogger("Random")
        self._exit = False

    def _generate_hiras(self):
        hira = ('あいうえおかがきぎくぐけげこごさざしじすずせぜそぞ'
                'ただちぢつづてでとどなにぬねのはばぱひびぴふぶぷへべぺほ'
                'ぼぽまみむめもゃやゅゆょよらりるれろわをんゔ')
        regex = '[{}]{{6,50}}'.format(hira)
        return "{}".format(randre.randre(regex))

    def _pre_filter(self, text):
        yoons = 'きぎき゚ひびぴしじちにみり'
        smalls = 'ゃゅょ'

        return re.sub(
            u'(.)[{}]'.format(smalls),
            lambda m: m.group(0) if m.group(1) in yoons else m.group(1),
            text)

    def _post_filter(self, text):
        text = text.strip(",;:'\"")
        text = ''.join(c for c in text if ord(c) < 0x0500 and c not in {'0', '_'})

        return text

    def _post_validator(self, text, *, to_lang=DEFAULT_JAMU_LANG):
        acceptable_score = 0.65
        words = set(text.split())
        word_cnt = len(set(word.lower() for word in words))
        score = 0.0
        valid_jamu = False

        if to_lang == "it":
            score = self.wdbmgr.calculate_score(text)
            if score > acceptable_score and word_cnt >= 4:
                valid_jamu = True
        else:
            if (word_cnt > 2 and
                sum(1 for word in words if word.istitle()) <= len(words) / 2.):
                valid_jamu = True

        return valid_jamu

    def exit(self):
        self._exit = True

    def jamu(self, to_lang):

        #self.log.warning("JamuManager.jamu() _exit:%s" % self._exit)
        max_tries = 50
        tries = 0
        valid_jamu = False
        while not self._exit and tries < max_tries:
            hiras = self._generate_hiras()

            if not self._pre_validator(hiras, to_lang=to_lang):
                tries += 1
                continue

            prefiltered = self._pre_filter(hiras)
            #self.log.warning(f"try:{tries} prefiltered: {prefiltered}")
            translations = self._translate_jamu(to_lang, prefiltered)
            for translated in translations:
                text = self._post_filter(translated)
                if self._post_validator(text, to_lang=to_lang):
                    valid_jamu = True
                    break
            else:
                tries += 1

            if valid_jamu:
                break

        if tries == max_tries:
            raise TranslationError("Translation not passing validators"
                " after {} tries".format(tries))

        return ' '.join(text.split())


class UpdaterThread(threading.Thread):
    def __init__(self, jamumgr, *args, **kwargs):
        name = 'Thread #%s (JamuUpdaterThread)' % world.threadsSpawned
        world.threadsSpawned += 1
        super().__init__(*args, **kwargs, name=name)

        self.jamus = defaultdict(deque)
        self.jamumgr = jamumgr
        self._requested_lang = DEFAULT_JAMU_LANG
        self._request = threading.Event()
        self._ready = threading.Event()
        self._updater_free = threading.Event()
        self._updater_free.set()
        self._exc_queue = []
        self._exit = False

    def request_jamu(self, to_lang):
        if self._requested_lang != to_lang:
            self._updater_free.wait()

        self._requested_lang = to_lang

        if len(self.jamus[to_lang]) == 0:
            self._ready.clear()
            self._request.set()

        #self.jamumgr.log.warning("Requested {}, deque len {}, waiting for _ready".format(to_lang, len(self.jamus[to_lang])))
        self._ready.wait()

        if len(self._exc_queue) > 0:
            if len(self.jamus[to_lang]) == 0:
                self._ready.clear()
                raise self._exc_queue.pop()
            else:
                self._exc_queue.pop()

        #self.jamumgr.log.warning("Thread is _ready")

        jamu = self.jamus[to_lang].popleft()
        self._request.set()

        return jamu

    def exit(self):
        self._exit = True
        self.jamumgr.exit()
        self._request.set()

    def _update_jamus(self, to_lang):
        #self.jamumgr.log.warning("updating jamus")

        while len(self.jamus[to_lang]) < JAMU_CACHE_SIZE:
            #self.jamumgr.log.warning("jamus %s: %d" % (to_lang, len(self.jamus[to_lang])))
            jamu = self.jamumgr.jamu(to_lang)
            if self._exit:
                break
            self.jamus[to_lang].append(jamu)
            self._ready.set()

    def run(self):
        #self.jamumgr.log.info("UpdaterThread.run()")
        while not self._exit:
            self._request.wait()

            if self._exit:
                break

            try:
                self._updater_free.clear()
                self._update_jamus(self._requested_lang)
            except Exception as e:
                self._exc_queue.append(e)
                self._ready.set()
            finally:
                self._updater_free.set()
                self._request.clear()

        #self.jamumgr.log.info("UpdaterThread dying")


class Random(callbacks.Plugin):
    """Add the help for "@plugin help Random" here
    This should describe *how* to use this plugin."""
    threaded = True

    def __init__(self, *args, **kwargs):
        super(Random, self).__init__(*args, **kwargs)
        db_path = conf.supybot.directories.data.dirize('rnick.db.kch')

        self.kdb = kyotocabinet.DB()
        if not self.kdb.open(db_path, kyotocabinet.DB.OWRITER | kyotocabinet.DB.OCREATE):
            e_str = "Unable to open KyotoCabinet DB ('%s')" % db_path
            log.error(e_str)
            raise IOException(e_str)

        self._events = defaultdict(dict)
        self._last_jamu = defaultdict(dict)
        self.jamumgr = JamuManager()
        self.updater = UpdaterThread(self.jamumgr)
        self.updater.start()

    @wrap(["text"])
    def randre(self, irc, msg, args, text):
        """ <regex> """
        irc.reply(randre.randre(text))

    def jamure(self, irc, msg, args):
        # randre.randre("[\u3041-\u3096]+")
        hiras = self.jamumgr._generate_hiras()
        text = self.jamumgr._pre_filter(hiras)
        irc.reply(text)

    @wrap(["text"])
    def rand(self, irc, msg, args, text):
        """ <Rscript>
    
        TODO: write the grammar definition. """
        irc.reply(rand.rand(text))

    @wrap([('checkcapability', 'trusted'),
        'somethingWithoutSpaces', 'text'])
    def rnadd(self, irc, msg, args, nick, text):
        """ <nick> <Rscript> """
        nick = _sanitize_nick(nick)
        if nick:
            self.kdb.set(nick, text)
            self.kdb.synchronize(True)
            irc.reply(rand.rand(text))

    @wrap([('checkcapability', 'trusted'), 'somethingWithoutSpaces'])
    def rndel(self, irc, msg, args, nick):
        """ <nick> """
        nick = _sanitize_nick(nick)
        if self.kdb.check(nick) != -1:
            self.kdb.remove(nick)
            self.kdb.synchronize(True)
        else:
            irc.error(("No '%s' found." % nick))

    @wrap([optional('text')])
    def rnick(self, irc, msg, args, text):
        """ <nick> """
        rest = ""
        if text:
            text = rand.rand(text, zero_depth=False)

            try:
                nick, rest = text.strip().split(" ", 1)
            except ValueError:
                nick, rest = text, ""

            nick = _sanitize_nick(nick)
            if self.kdb.check(nick):
                rstring = self.kdb.get_str(nick)
        elif self.kdb.count() > 0:
            rstring = random.choice(db_get_values(self.kdb))
        else:
            rstring = None

        if rstring:
            irc.reply(("%s%s!" % (rand.rand(rstring), rest)))

    def rnlist(self, irc, msg, args):
       rnicks = db_get_keys(self.kdb)
       if rnicks:
           irc.reply(utils.str.commaAndify(rnicks))
       else:
           irc.reply("No randnicks available.", prefixNick=True)

    @wrap(['somethingWithoutSpaces'])
    def rnshow(self, irc, msg, args, nick):
        """ <nick> """
        sanitized_nick = _sanitize_nick(nick)
        rstring = self.kdb.get_str(sanitized_nick)
        if rstring:
            irc.reply(("Rscript for %s: %s" % (nick, rstring)))

    def entropy(self, irc, msg, args):
        """: shows how many entropy bits the system has available. """
        with open("/proc/sys/kernel/random/entropy_avail") as f:
            irc.reply(f.read().strip())

    def _activity_monitor(self, irc, channel):
        callbacks = {callback.name(): callback for callback in irc.callbacks}

        try:
            actmon = callbacks["ActivityMonitor"]
        except KeyError:
            raise KeyError("ActivityMonitor plugin is not loaded.")
        else:
            return actmon._monitor(channel)

    @wrap(["channeldb"])
    def autojamu2(self, irc, msg, args, channel):
        """ """
        actmon = self._activity_monitor(irc, channel)
        activity = actmon.activity()
        threshold = self.registryValue('autoJamuThreshold', channel)
        period = self.registryValue('autoJamuPeriod', channel)
        lang = self.registryValue('autoJamuLang', channel)

        if activity < threshold:
            last_jamu = self._last_jamu[irc.network][channel]

            if monotonic() - last_jamu > period:
                if lang not in tr_langs.langs:
                    lang = 'it'

                self.jamumgr.irc = irc
                try:
                    text = self.updater.request_jamu(lang)
                except utils.web.Error:
                    pass
                else:
                    irc.sendMsg(ircmsgs.privmsg(channel, text))

                self._last_jamu[irc.network][channel] = monotonic()

    def _stats(self, irc, channel):
        on_fmt = "Channel activity: {:.4f}, {} until next jamu"
        off_fmt = "Autojamu is off"

        if channel not in self._events[irc.network]:
            s = off_fmt
        else:
            actmon = self._activity_monitor(irc, channel)
            period = self.registryValue('autoJamuPeriod', channel)
            until = period - (monotonic() - self._last_jamu[irc.network][channel])

            if until < 0:
                time_fmt = "-%H:%M:%S"
                until = -until
            else:
                time_fmt = "%H:%M:%S"

            clock = strftime(time_fmt, gmtime(until))
            s = on_fmt.format(actmon.activity(), clock)

        return s

    def _autojamu(self, irc, msg, state):
        channel = msg.args[0].lower()
        if not irc.isChannel(channel):
            return

        if state == "on" and self._events[irc.network].get(channel, None) is None:
            if channel not in self._last_jamu[irc.network]:
                self._last_jamu[irc.network][channel] = monotonic()

            autojamu = lambda: self.Proxy(irc.irc, msg, ["autojamu2"])
            event_name = "autoJamu{}{}".format(irc.network, channel)
            self._events[irc.network][channel] = schedule.addPeriodicEvent(autojamu, 30, event_name)
            self.setRegistryValue("autoJamuEnabled", True, channel)
        elif state == "off":
            if channel in self._events[irc.network]:
                if self._events[irc.network][channel] is not None:
                    schedule.removeEvent(self._events[irc.network][channel])
                    del self._events[irc.network][channel]

            self.setRegistryValue("autoJamuEnabled", False, channel)

        return self._stats(irc, channel)

    @wrap([optional("somethingWithoutSpaces")])
    def autojamu(self, irc, msg, args, state):
        """ [on|off]

        Manage and retrieve Autojamu state for the current channel"""
        s = self._autojamu(irc, msg, state)
        if s:
            irc.reply(s)

    @wrap([optional("somethingWithoutSpaces")])
    def deepjamu(self, irc, msg, args, to_lang):
        """ [lang] """

        if to_lang not in deeplangs.langs:
            to_lang = 'it'

        hiras = self.jamumgr._generate_hiras()
        hiras = self.jamumgr._pre_filter(hiras)
        _, _, (tr, *trs) = deepl.translate("ja", to_lang, q=hiras)
        irc.reply(tr)

    @wrap([optional("somethingWithoutSpaces")])
    def jamu(self, irc, msg, args, to_lang):
        """ [lang] """

        if to_lang not in tr_langs.langs:
            to_lang = 'it'

        self.jamumgr.irc = irc
        text = self.updater.request_jamu(to_lang)

        irc.reply(text)
        #irc.sendMsg(ircmsgs.privmsg(channel, text))

    @wrap([("checkcapability", "owner"), "somethingWithoutSpaces", "text"])
    def jamupush(self, irc, msg, args, lang, jamu):
        """ <lang> <jamu> """

        self.updater.jamus[lang].append(jamu)
        self.updater._ready.set()
        irc.reply(len(self.updater.jamus[lang]))

    @wrap(["somethingWithoutSpaces"])
    def jamucachelen(self, irc, msg, args, lang):
        """ <lang> """
        if lang not in tr_langs.langs:
            irc.error("'%s' is an unrecognized language." % lang)
            return

        try:
            length = len(self.updater.jamus[lang])
        except KeyError:
            length = 0

        irc.reply("%s %d" % (lang, length), prefixNick=True)

    def doJoin(self, irc, msg):
        channel = msg.args[0].lower()
        if msg.nick != irc.nick:
            return

        if self.registryValue("autoJamuEnabled", channel) is False:
            return

        s = self._autojamu(irc, msg, "on")
        if s:
            irc.reply(s)

    def doPart(self, irc, msg):
        channel = msg.args[0].lower()
        if msg.nick != irc.nick:
            return

        if self.registryValue("autoJamuEnabled", channel) is False:
            return

        self._autojamu(irc, msg, "off")
  
    def reload(self):
        for network in self._events.values():
            for event in network.values():
                schedule.removeEvent(event)
 
    def exit(self):
        self.reload()

        self.updater.exit()
        try:
            self.updater.join()
        finally:
            super().exit()

Class = Random


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
