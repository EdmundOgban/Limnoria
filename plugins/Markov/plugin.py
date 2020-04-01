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
import supybot.ircmsgs as ircmsgs
import supybot.plugins as plugins
import supybot.ircutils as ircutils
import supybot.schedule as schedule
import supybot.callbacks as callbacks
import supybot.log as log
import supybot.utils as utils
try:
    from supybot.i18n import PluginInternationalization
    _ = PluginInternationalization('Markov')
except ImportError:
    # Placeholder that allows to run the plugin on a bot
    # without the i18n module
    _ = lambda x: x

import time
import queue
import random
import threading
import traceback
import os
import functools
import collections
import sqlite3


class DBKeyError(Exception):
    pass

class MarkovSqlite:
    def __init__(self, filename):
        self.dbs = ircutils.IrcDict()
        self.filename = filename

    def _getDb(self, channel):
        if channel not in self.dbs:
            filename = plugins.makeChannelFilename(self.filename, channel)
            db = sqlite3.connect(filename, check_same_thread=False)
            cur = db.cursor()
            cur.execute('''CREATE TABLE IF NOT EXISTS starters (
                starter TEXT PRIMARY KEY
            )''')
            cur.execute('''CREATE TABLE IF NOT EXISTS follows (
                key_a TEXT,
                key_b TEXT,
                follow TEXT,
                PRIMARY KEY (key_a, key_b)
            )''')
            self.dbs[channel] = db

        return self.dbs[channel]

    def add(self, channel, sentence):
        db = self._getDb(channel)
        cur = db.cursor()
        sentence = sentence.split(" ")
        sentence.extend(["\n", "\n"])
        cur.execute("INSERT OR IGNORE INTO starters (starter) VALUES (?)", (sentence[0],))
        for a, b, follow in utils.seq.window(sentence, 3):
            resultset = cur.execute("SELECT follow FROM follows WHERE key_a = ? AND key_b = ?", (a, b))
            follows = resultset.fetchone()
            if follows is None:
                cur.execute("INSERT INTO follows (key_a, key_b, follow) VALUES (?, ?, ?)", (a, b, follow))
            else:
                follows = "{} {}".format(follows[0], follow)
                cur.execute("UPDATE follows SET follow = ? WHERE key_a = ? AND key_b = ?", (follows, a, b))

    def get(self, channel, key_a=None, key_b=None):
        if key_a is None and key_b is not None:
            raise ValueError("key_a must not be None when key_b is given")

        db = self._getDb(channel)
        cur = db.cursor()
        if key_a is None:
            # start random
            resultset = cur.execute("SELECT starter FROM starters ORDER BY RANDOM() LIMIT 1")
            fetch = resultset.fetchone()
            if fetch is None:
                raise DBKeyError("DB for {} is empty.".format(channel))

            key_a = fetch[0]

        if key_b is None:
            # start with one specified word
            resultset = cur.execute("SELECT key_b FROM follows WHERE key_a = ? ORDER BY RANDOM() LIMIT 1", (key_a,))
            fetch = resultset.fetchone()
            if fetch is None:
                raise DBKeyError("Can't start a chain with '{}'.".format(key_a))

            key_b = fetch[0]

        out = [key_a, key_b]
        while key_b != "\n":
            resultset = cur.execute("SELECT follow FROM follows WHERE key_a = ? and key_b = ?", (key_a, key_b))
            fetch = resultset.fetchone()
            # Chain stuck
            if fetch is None:
                raise DBKeyError("No follower for pair ('{}', '{}')".format(key_a, key_b))

            follows = fetch[0]
            key_a = key_b
            key_b = random.choice(follows.split(" "))
            # Chain ended
            if key_b == "\n":
                break

            out.append(key_b)

        if out[-1] == "\n":
            out.pop()

        return out

    def get_filtered(self, channel, key_a=None, key_b=None, *, func=lambda s: s):
        valid_sentence = False
        while not valid_sentence:
            sentence = self.get(channel, key_a, key_b)
            valid_sentence = func(sentence)

        return sentence

    def close(self):
        for db in self.dbs.values():
            db.commit()
            db.close()

    def firsts(self, channel):
        db = self._getDb(channel)
        cur = db.cursor()
        resultset = cur.execute("SELECT COUNT(*) FROM starters")
        fetch = resultset.fetchone()
        return int(fetch[0])

    def keys(self, channel):
        db = self._getDb(channel)
        cur = db.cursor()
        resultset = cur.execute("SELECT COUNT(*) FROM follows")
        fetch = resultset.fetchone()
        return int(fetch[0])

    def follows(self, channel, key_a=None, key_b=None):
        if key_a is None and key_b is not None:
            raise ValueError("key_a must not be None when key_b is given")

        db = self._getDb(channel)
        cur = db.cursor()
        follows = 0
        #query = "SELECT * FROM follows"
        query = "SELECT SUM(LENGTH(follow)-LENGTH(REPLACE(follow, ' ', ''))) FROM follows"
        args = []
        if key_a:
            query += " WHERE key_a = ?"
            args.append(key_a)

        if key_b:
            query += " AND key_b = ?"
            args.append(key_b)

        resultset = cur.execute(query, args)
        fetch = resultset.fetchone()
        if fetch and fetch[0] is not None:
            follows = fetch[0] + 1

        #for res in cur.execute(query, args):
        #    follows += res[-1].count(" ") + 1
        return follows

    def dbSize(self, channel):
        filename = plugins.makeChannelFilename(self.filename, channel)
        return os.stat(filename).st_size


MarkovDB = plugins.DB('Markov', {'sqlite3': MarkovSqlite})


class Markov(callbacks.Plugin):
    """ Markov chains! """
    threaded = True

    def __init__(self, irc):
        self.__parent = super(Markov, self)
        self.__parent.__init__(irc)
        self.db = MarkovDB()

    def die(self):
        self.db.close()
        self.__parent.die()

    def _markov(self, channel, query=""):
        tokens = query.split()
        response = tokens[:-2]
        key = tokens[-2:]

        chain_length = 0
        chain_tries = 0
        min_chain_length = self.registryValue('minChainLength', channel)
        max_chain_tries = self.registryValue('maxAttempts', channel)
        res = []
        longest_chain = []
        while chain_length < min_chain_length and chain_tries < max_chain_tries:
            try:
                res = self.db.get(channel, *key)
            except DBKeyError as e:
                return "Error: {}".format(e)
            else:
                chain_length = len(res)
                if chain_length > len(longest_chain):
                    longest_chain = res

            chain_tries += 1

        if chain_length < min_chain_length:
            response.extend(longest_chain)
        else:
            response.extend(res)

        return " ".join(response)

    @wrap(['channeldb', optional('text')])
    def markov(self, irc, msg, args, channel, words):
        """[<channel>] [words]

        Returns a randomly generated Markov Chain sentence from the
        data kept on <channel> (which is only necessary if not sent in the
        channel itself). If a sequence of words is specified, that will be used
        as a start and as a guide through the chain.
        """
        s = self._markov(channel, words or "")
        irc.reply(s)

    def _parametrize(self, prefix, words):
        if words:
            if not words.startswith("<"):
                words = "<%s" % words
            if words.endswith(">"):
                words = "%s:" % words
            elif not words.endswith(":"):
                words = "%s>:" % words
            words = " ".join([prefix, words])
        else:
            words = prefix
        return words

    @wrap([optional('text')])
    def markopedia(self, irc, msg, args, words):
        """[words] """

        words = self._parametrize("Wikipedia", words)
        s = self._markov("#python", words)
        irc.reply(s)

    @wrap([optional('text')])
    def urkov(self, irc, msg, args, words):
        """[words] """

        words = self._parametrize("Urban Dictionary", words)
        s = self._markov("#python", words)
        irc.reply(s)

    @wrap(['channeldb'])
    def firsts(self, irc, msg, args, channel):
        """[<channel>]

        Returns the number of Markov's first links in the database for
        <channel>.
        """
        s = 'There are %s firsts in my Markov database for %s.'
        irc.reply(s % (self.db.firsts(channel), channel))

    @wrap(['channeldb'])
    def keys(self, irc, msg, args, channel):
        """[<channel>]

        Returns the number of Markov's chain links in the database for
        <channel>.
        """
        irc.reply(
            format('There are %i keys in my Markov database for %s.',
                   self.db.keys(channel), channel))

    @wrap(['channeldb', optional('somethingWithoutSpaces'), additional('somethingWithoutSpaces')])
    def follows(self, irc, msg, args, channel, key_a, key_b):
        """[<channel>]

        Returns the number of Markov's third links in the database for
        <channel>.
        """
        fmt = "There are %i follows{}in my Markov database for %s."
        if key_a is not None and key_b is not None:
            fmt = fmt.format(" for pair ('{}', '{}') ".format(key_a, key_b))
        elif key_a is not None:
            fmt = fmt.format(" for starter '{}' ".format(key_a))
        else:
            fmt = fmt.format(" ")

        irc.reply(format(fmt, self.db.follows(channel, key_a, key_b), channel))

    @wrap(['channeldb'])
    def stats(self, irc, msg, args, channel):
        """[<channel>]

        Returns all stats (firsts, lasts, keys, follows) for <channel>'s
        Markov database.
        """
        irc.reply(
            format('Firsts: %i; Keys: %i; Follows: %i',
                   self.db.firsts(channel),
                   self.db.keys(channel), self.db.follows(channel)))

    @wrap(['channeldb'])
    def dbsize(self, irc, msg, args, channel):
        """[<channel>]

        Returns the database file size on disk
        """
        def convert_size(size):
            power = 2**10 # 1024
            n = 0
            while size > power:
                size /=  power
                n += 1
            return "%.1f %sB" % (size, ["", "k", "M", "G", "T"][n])

        irc.reply(
            format('Markov database for %s is %s in size.' % (
                channel, convert_size(self.db.dbSize(channel)))))
    
    def doPrivmsg(self, irc, msg):
        def _normalize(m):
            if ircmsgs.isAction(m):
                return utils.str.try_coding(ircmsgs.unAction(m))
            elif ircmsgs.isCtcp(m):
                return ''
            else:
                return utils.str.try_coding(m.args[1])

        if not irc.isChannel(msg.args[0]):
            return

        channel = plugins.getChannel(msg.args[0])
        text = _normalize(msg)
        # This shouldn't happen often (CTCP messages being the possible exception)
        if not text:
            return

        if not (self.registryValue('ignoreBotCommands', channel) and
                callbacks.addressed(irc.nick, msg)):
            self.db.add(channel, text)

Class = Markov

# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
