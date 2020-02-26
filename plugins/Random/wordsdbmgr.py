import os

import supybot.conf as conf


class WordsDBManager:
    def __init__(self, fname="parole_uniche.txt"):
        fname = conf.supybot.directories.data.dirize(fname)
        self.fname = fname
        self.populate_words_db()

    def populate_words_db(self):
        self.words = set()

        with open(self.fname) as f:
            words_cnt = f.readline().strip()
            for line in f:
                if "/" in line:
                    text, comment = line.split("/", 1)
                else:
                    text = line
        
                if text:
                    self.words.add(text.strip().lower())

    def __contains__(self, word):
        return word.lower() in self.words

    def calculate_score(self, period):
        period_words = period.split()
        italians = 0
        total = 1

        for word in period_words:
            word = word.lower()
            word = word.rstrip(".:,;!?'\"")
            word_len = len(word)
            if word in self.words:
               italians += word_len
            total += word_len

        return italians / total

