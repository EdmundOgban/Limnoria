import kyotocabinet

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
