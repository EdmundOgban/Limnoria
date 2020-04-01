import random
import sqlite3
from collections import defaultdict

def _window(L, size):
    """list * size -> window iterable

    Returns a sliding 'window' through the list L of size size."""
    assert not isinstance(L, int), 'Argument order swapped: _window(L, size)'

    if size < 1:
        raise ValueError('size <= 0 disallowed.')

    for i in range(len(L) - (size-1)):
        yield L[i:i+size]

class MarkovDB:
    def __init__(self, filename):
        self.dbs = dict()
        self.filename = filename

    def _getDb(self, channel):
        if channel not in self.dbs:
            filename = plugins.makeChannelFilename(self.filename, channel)
            db = sqlite3.connect(filename)
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

    def add(self, channel, sentence):
        db = self._getDb(channel)
        cur = db.cursor()
        sentence = sentence.split(" ")
        sentence.extend(["\n", "\n"])
        cur.execute("INSERT OR IGNORE INTO starters (starter) VALUES (?)", (sentence[0],))
        for a, b, follow in _window(sentence, 3):
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
                return

            key_a = fetch[0]

        if key_b is None:
            # start with one specified word
            resultset = cur.execute("SELECT key_b FROM follows WHERE key_a = ? ORDER BY RANDOM() LIMIT 1", (key_a,))
            fetch = resultset.fetchone()
            if fetch is None:
                return

            key_b = fetch[0]

        out = [key_a, key_b]
        while key_b != "\n":
            resultset = cur.execute("SELECT follow FROM follows WHERE key_a = ? and key_b = ?", (key_a, key_b))
            fetch = resultset.fetchone()
            # Chain stuck
            if fetch is None:
                raise KeyError("No follower for pair ({}, {})".format(key_a, key_b))

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
        cur.execute("SELECT COUNT(*) FROM starters")
        fetch = resultset.fetchone()
        return int(fetch[0])

    def keys(self, channel):
        db = self._getDb(channel)
        cur = db.cursor()
        cur.execute("SELECT COUNT(*) FROM follows")
        fetch = resultset.fetchone()
        return int(fetch[0])

    def follows(self, channel):
        db = self._getDb(channel)
        cur = db.cursor()
        follows = 0
        for res in cur.execute("SELECT * FROM follows"):
            follows += res[-1].count(" ") + 1

        return follows

    def dbSize(self, channel):
        filename = plugins.makeChannelFilename(self.filename, channel)
        return os.stat("{}.db".format(filename)).st_size
