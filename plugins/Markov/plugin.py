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
try:
    from supybot.i18n import PluginInternationalization
    _ = PluginInternationalization('Markov')
except ImportError:
    # Placeholder that allows to run the plugin on a bot
    # without the i18n module
    _ = lambda x: x

import time
import queue
import kyotocabinet
import random
import threading
import traceback
import os
import functools

import collections

#import mstr_utils


KEY_LENGTH = 2

class KyotoCabinetDB(object):
    def __init__(self, filename):
        self.dbs = ircutils.IrcDict()
        self._cache = {}
        self.filename = filename

    def close(self):
        for db in self.dbs.values():
            db.close()

    def clear_cache(self, channel):
        if channel in self._cache:
            del self._cache[channel]

    def _getDb(self, channel):
        if channel not in self.dbs:
            filename = plugins.makeChannelFilename(self.filename, channel)
            db = kyotocabinet.DB()
            db.open(filename+".kct#dfunit=4", kyotocabinet.DB.OWRITER | kyotocabinet.DB.OCREATE)
            self.dbs[channel] = db

        return self.dbs[channel]

    def _combine(self, key):
        return ' '.join(key)

    def addKey(self, channel, key, follower):
        db = self._getDb(channel)
        combined = self._combine(key)
        last = key[-1]

        if db.check(combined) == -1: # not present
            db.set(combined, follower)
        else:
            db.append(combined, " " + follower)
        
        #if follower == "\n":
        #    if db.check("\n") == -1: # not present
        #        db.set("\n", last)
        #    else:
        #        db.append("\n", " " + last)

        db.synchronize(True)

    def getNextKey(self, channel, key):
        db = self._getDb(channel)

        if channel not in self._cache:
            self._cache[channel] = {}

        comb_key = self._combine(key)
        if comb_key not in self._cache[channel]:
            res = db.get_str(comb_key)
            if res is None:
                raise KeyError("No followers for {} (empty database?)".format(channel))
            self._cache[channel][comb_key] = res.split(' ')

        followers = self._cache[channel][comb_key]
        #follower = mstr_utils.split_and_choose(followers, ' ')
        #follower = utils.iter.choice(followers.split(' '))
        follower = utils.iter.choice(followers)
        key.pop(0)
        key.append(follower)
        return (key, follower == '\n')

    def firsts(self, channel):
        db = self._getDb(channel)
        firsts_key = " ".join(["\n"]*KEY_LENGTH)

        if db.check(firsts_key) != -1:
            return len(set(db.get_str(firsts_key).split()))
        else:
            return 0

    def lasts(self, channel):
        db = self._getDb(channel)
        if db.check("\n") != -1:
            return len(set(db.get_str('\n').split()))
        else:
            return 0

    def keys(self, channel):
        keys_cnt = self._getDb(channel).count()
        return keys_cnt-1 if keys_cnt else 0

    def follows(self, channel):
        class Visitor(kyotocabinet.Visitor):            
            def __init__(self):
                super(Visitor, self).__init__()
                self.follows = 0
            def visit_full(self, k, v):
                if k != "\n":
                    self.follows += v.count(b' ')+1

        db = self._getDb(channel)
        visitor = Visitor()
        return visitor.follows if db.iterate(visitor) else 0
    
    def dbSize(self, channel):
        filename = plugins.makeChannelFilename(self.filename, channel)

        return os.stat(f"{filename}.kct").st_size


MarkovDB = plugins.DB('Markov', {'anydbm': KyotoCabinetDB})
mdb = MarkovDB()
#MarkovDB = KyotoCabinetDB

class MarkovWorkQueue(threading.Thread):
    def __init__(self, *args, **kwargs):
        name = 'Thread #%s (MarkovWorkQueue)' % world.threadsSpawned
        world.threadsSpawned += 1
        threading.Thread.__init__(self, name=name)
        #self.db = MarkovDB(*args, **kwargs)
        self.db = mdb
        self.q = queue.Queue()
        self.killed = False
        self.setDaemon(True)
        self.start()

    def die(self):
        self.killed = True
        self.q.put(None)

    def enqueue(self, f):
        self.q.put(f)

    def run(self):
        while not self.killed:
            f = self.q.get()
            if f is not None:
                try:
                    time.sleep(f.delay)
                except AttributeError:
                    pass
                try:
                    f(self.db)
                except Exception:
                    log.error(traceback.format_exc())
                    raise
        self.db.close()

class Markov(callbacks.Plugin):
    """ Markov chains! """

    def __init__(self, irc):
        self.q = MarkovWorkQueue()
        self.__parent = super(Markov, self)
        self.__parent.__init__(irc)
        self.lastSpoke = time.time()
        self.am = {}

    def die(self):
        self.q.die()
        self.__parent.die()

    def _tokenize(self, m):
        if ircmsgs.isAction(m):
            return utils.str.try_coding(ircmsgs.unAction(m)).split()
        elif ircmsgs.isCtcp(m):
            return []
        else:
            return utils.str.try_coding(m.args[1]).split()

    #def _tokenize(self, m):
    #    if ircmsgs.isAction(m):
    #        return list(utils.str.try_coding(ircmsgs.unAction(m)))
    #    elif ircmsgs.isCtcp(m):
    #        return []
    #    else:
    #        return list(utils.str.try_coding(m.args[1]))

    def _markov(self, channel, irc, query="", **kwargs):
        q = queue.Queue(maxsize=KEY_LENGTH)
        prepend_list = []
        key = []

        for i in range(KEY_LENGTH):
            q.put("\n")

        if query:
            for word in query.split():
                try:
                    q.put_nowait(word)
                except queue.Full:
                    item = q.get()
                    if item != "\n":
                        prepend_list.append(item)
                    q.put(word)

        for i in range(KEY_LENGTH):
            key.append(q.get())

        def f(orig_key, prepend_list, db):
            chain_length = 0
            chain_tries = 0
            min_chain_length = self.registryValue('minChainLength', channel)
            max_chain_tries = self.registryValue('maxAttempts', channel)
            longest_chain = []
            
            while chain_length < min_chain_length and chain_tries < max_chain_tries:
                response = [token for token in orig_key if token != "\n"]
                key = orig_key[:]

                finished = False
                #log.error("while not finished, key:'{}'".format(key))
                while not finished:
                    try:
                        key, finished = db.getNextKey(channel, key)
                        #log.error("    key:'{}' finished:{}".format(key, finished))
                    except KeyError as e:
                        #log.error("    except KeyError")
                        firsts_key = ["\n"]*KEY_LENGTH
                        if key == firsts_key:
                            db.clear_cache(channel)
                            irc.error(e.args[0])
                            return
                        else:
                            orig_key = firsts_key[:]
                            prepend_list = []
                            finished = True
                    else:
                        follower = key[-1]
                        if follower != "\n":
                            response.append(follower)
                else:
                    #chain_length = len("".join(prepend_list + response))
                    chain_length = len(prepend_list + response)
                    if chain_length > len(longest_chain):
                        longest_chain = response
                    #log.error("  finished, chain_length:{} chain_tries:{}\n".format(chain_length, chain_tries))
                    if chain_length < min_chain_length:
                        chain_tries += 1
                        if chain_tries < max_chain_tries:
                            continue
                        else:
                            response = longest_chain

                    db.clear_cache(channel)
                    self.lastSpoke = time.time()
                    irc.reply(" ".join(prepend_list + response),
                        prefixNick=kwargs['prefixNick'] if 'prefixNick' in kwargs else False)

        f = functools.partial(f, key, prepend_list)
        try:
            f.delay = kwargs['replyDelay']
        except KeyError:
            f.delay = 0

        return f

    @wrap(['channeldb', optional('text')])
    def markov(self, irc, msg, args, channel, words):
        """[<channel>] [words]

        Returns a randomly generated Markov Chain sentence from the
        data kept on <channel> (which is only necessary if not sent in the
        channel itself). If a sequence of words is specified, that will be used
        as a start and as a guide through the chain.
        """
        f = self._markov(channel, irc, words or "", prefixNick=False)
        f(mdb)
        #self.q.enqueue(f)

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
        f = self._markov("#python", irc, words, prefixNick=False)
        self.q.enqueue(f)

    @wrap([optional('text')])
    def urkov(self, irc, msg, args, words):
        """[words] """

        words = self._parametrize("Urban Dictionary", words)
        f = self._markov("#python", irc, words, prefixNick=False)
        self.q.enqueue(f)

    @wrap(['channeldb'])
    def firsts(self, irc, msg, args, channel):
        """[<channel>]

        Returns the number of Markov's first links in the database for
        <channel>.
        """
        def firsts(db):
            s = 'There are %s firsts in my Markov database for %s.'
            irc.reply(s % (db.firsts(channel), channel))
        self.q.enqueue(firsts)

    @wrap(['channeldb'])
    def lasts(self, irc, msg, args, channel):
        """[<channel>]

        Returns the number of Markov's last links in the database for
        <channel>.
        """
        def lasts(db):
            irc.reply(
                format('There are %i lasts in my Markov database for %s.',
                       db.lasts(channel), channel))
        self.q.enqueue(lasts)

    @wrap(['channeldb'])
    def keys(self, irc, msg, args, channel):
        """[<channel>]

        Returns the number of Markov's chain links in the database for
        <channel>.
        """
        def keys(db):
            irc.reply(
                format('There are %i keys in my Markov database for %s.',
                       db.keys(channel), channel))
        self.q.enqueue(keys)

    @wrap(['channeldb'])
    def follows(self, irc, msg, args, channel):
        """[<channel>]

        Returns the number of Markov's third links in the database for
        <channel>.
        """
        def follows(db):
            irc.reply(
                format('There are %i follows in my Markov database for %s.',
                       db.follows(channel), channel))
        self.q.enqueue(follows)

    @wrap(['channeldb'])
    def stats(self, irc, msg, args, channel):
        """[<channel>]

        Returns all stats (firsts, lasts, keys, follows) for <channel>'s
        Markov database.
        """
        def stats(db):
            irc.reply(
                format('Firsts: %i; Keys: %i; Follows: %i',
                       db.firsts(channel),
                       db.keys(channel), db.follows(channel)))
        self.q.enqueue(stats)

    @wrap(['channeldb'])
    def dbsize(self, irc, msg, args, channel):
        """[<channel>]

        Returns the database file size on disk
        """
        def dbsize(db):
            def convert_size(size):
                power = 2**10 # 1024
                n = 0
                while size > power:
                    size /=  power
                    n += 1
                return "%.1f %sB" % (size, ["", "k", "M", "G", "T"][n])

            irc.reply(
                format('Markov database for %s is %s in size.' % (
                    channel, convert_size(db.dbSize(channel)))))

        self.q.enqueue(dbsize)
    
    def doPrivmsg(self, irc, msg):
        if not irc.isChannel(msg.args[0]):
            return

        channel = plugins.getChannel(msg.args[0])
        now = time.time()
        throttle = self.registryValue('randomSpeaking.throttleTime',
                                      channel)
        prob_from_conf = self.registryValue('randomSpeaking.probability', channel)
        #delay = self.registryValue('randomSpeaking.maxDelay', channel)
        irc = callbacks.SimpleProxy(irc, msg)

        words = ['\n']*KEY_LENGTH
        words.extend(self._tokenize(msg))
        words.append('\n')

        # This shouldn't happen often (CTCP messages being the possible exception)
        if not words or len(words) == KEY_LENGTH+1:
            return

        if self.registryValue('ignoreBotCommands', channel) and \
                callbacks.addressed(irc.nick, msg):
            return

        def auto_markov(prefix_nick=False, delay=0):
            tokens = msg.args[1].split(" ")
            len_tokens = len(tokens)
            if len_tokens > KEY_LENGTH:
                maxidx = random.randint(KEY_LENGTH, len_tokens)
                words = tokens[maxidx-KEY_LENGTH:maxidx]
            elif len_tokens == KEY_LENGTH:
                words = tokens
            else:
                words = [tokens[0]]

            return self._markov(channel, irc, " ".join(words),
                prefixNick=prefix_nick, replyDelay=delay)

        def add_key(db):
            for *key, follower in utils.seq.window(words, KEY_LENGTH+1):
                db.addKey(channel, key, follower)

        
        # register channel activity
        #activity = am.get_activity_level()
        #probability = (15.0-activity)/15.0

        # clamp probability
        #probability = max(min(probability, prob_from_conf), 0)

        #if now > self.lastSpoke + throttle:
        #    self.lastSpoke = time.time()
        #    if random.random() <= probability:
        #        self.q.enqueue(auto_markov(delay=random.randint(3, 5)))

        self.q.enqueue(add_key)

Class = Markov

# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
