import re
import sys
import time

def splitHostmask(hostmask):
    """hostmask => (nick, user, host)
    Returns the nick, user, host of a user hostmask."""
    assert isUserHostmask(hostmask)
    nick, rest = hostmask.rsplit('!', 1)
    user, host = rest.rsplit('@', 1)
    return (sys.intern(nick), sys.intern(user), sys.intern(host))

userHostmaskRe = re.compile(r'^\S+!\S+@\S+$')
def isUserHostmask(s):
    """Returns whether or not the string s is a valid User hostmask."""
    return userHostmaskRe.match(s) is not None

class MalformedIrcMsg(ValueError):
    pass

class IrcMsg(object):
    """Class to represent an IRC message.

    As usual, ignore attributes that begin with an underscore.  They simply
    don't exist.  Instances of this class are *not* to be modified, since they
    are hashable.  Public attributes of this class are .prefix, .command,
    .args, .nick, .user, and .host.

    The constructor for this class is pretty intricate.  It's designed to take
    any of three major (sets of) arguments.

    Called with no keyword arguments, it takes a single string that is a raw
    IRC message (such as one taken straight from the network).

    Called with keyword arguments, it *requires* a command parameter.  Args is
    optional, but with most commands will be necessary.  Prefix is obviously
    optional, since clients aren't allowed (well, technically, they are, but
    only in a completely useless way) to send prefixes to the server.

    Since this class isn't to be modified, the constructor also accepts a 'msg'
    keyword argument representing a message from which to take all the
    attributes not provided otherwise as keyword arguments.  So, for instance,
    if a programmer wanted to take a PRIVMSG they'd gotten and simply redirect
    it to a different source, they could do this:

    IrcMsg(prefix='', args=(newSource, otherMsg.args[1]), msg=otherMsg)
    """
    # It's too useful to be able to tag IrcMsg objects with extra, unforeseen
    # data.  Goodbye, __slots__.
    # On second thought, let's use methods for tagging.
    __slots__ = ('args', 'command', 'host', 'nick', 'prefix', 'user',
                 '_hash', '_str', '_repr', '_len', 'tags', 'reply_env',
                 'server_tags', 'time', 'channel')
    def __init__(self, s='', command='', args=(), prefix='', msg=None,
            reply_env=None):
        assert not (msg and s), 'IrcMsg.__init__ cannot accept both s and msg'
        if not s and not command and not msg:
            raise MalformedIrcMsg('IRC messages require a command.')
        self._str = None
        self._repr = None
        self._hash = None
        self._len = None
        self.reply_env = reply_env
        self.tags = {}
        if s:
            originalString = s
            try:
                if not s.endswith('\n'):
                    s += '\n'
                self._str = s
                if s[0] == '@':
                    (server_tags, s) = s.split(' ', 1)
                    self.server_tags = parse_server_tags(server_tags[1:])
                else:
                    self.server_tags = {}
                if s[0] == ':':
                    self.prefix, s = s[1:].split(None, 1)
                else:
                    self.prefix = ''
                if ' :' in s: # Note the space: IPV6 addresses are bad w/o it.
                    s, last = s.split(' :', 1)
                    
                    self.args = s.split()
                    self.args.append(last.rstrip('\r\n'))
                else:
                    self.args = s.split()
                self.command = self.args.pop(0)
                if 'time' in self.server_tags:
                    s = self.server_tags['time']
                    date = datetime.datetime.strptime(s, '%Y-%m-%dT%H:%M:%S.%fZ')
                    date = minisix.make_datetime_utc(date)
                    self.time = minisix.datetime__timestamp(date)
                else:
                    self.time = time.time()
            except (IndexError, ValueError):
                raise MalformedIrcMsg(repr(originalString))
        else:
            if msg is not None:
                if prefix:
                    self.prefix = prefix
                else:
                    self.prefix = msg.prefix
                if command:
                    self.command = command
                else:
                    self.command = msg.command
                if args:
                    self.args = args
                else:
                    self.args = msg.args
                if reply_env:
                    self.reply_env = reply_env
                elif msg.reply_env:
                    self.reply_env = msg.reply_env.copy()
                else:
                    self.reply_env = None
                self.tags = msg.tags.copy()
                self.server_tags = msg.server_tags
                self.time = msg.time
            else:
                self.prefix = prefix
                self.command = command
                assert all(ircutils.isValidArgument, args), args
                self.args = args
                self.time = None
                self.server_tags = {}
        self.args = tuple(self.args)
        if isUserHostmask(self.prefix):
            (self.nick,self.user,self.host)=splitHostmask(self.prefix)
        else:
            (self.nick, self.user, self.host) = (self.prefix,)*3

    def __str__(self):
        if self._str is not None:
            return self._str
        if self.prefix:
            if len(self.args) > 1:
                self._str = ':%s %s %s :%s\r\n' % \
                            (self.prefix, self.command,
                             ' '.join(self.args[:-1]), self.args[-1])
            else:
                if self.args:
                    self._str = ':%s %s :%s\r\n' % \
                                (self.prefix, self.command, self.args[0])
                else:
                    self._str = ':%s %s\r\n' % (self.prefix, self.command)
        else:
            if len(self.args) > 1:
                self._str = '%s %s :%s\r\n' % \
                            (self.command,
                             ' '.join(self.args[:-1]), self.args[-1])
            else:
                if self.args:
                    self._str = '%s :%s\r\n' % (self.command, self.args[0])
                else:
                    self._str = '%s\r\n' % self.command
        return self._str

    def __len__(self):
        return len(str(self))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and \
               hash(self) == hash(other) and \
               self.command == other.command and \
               self.prefix == other.prefix and \
               self.args == other.args
    __req__ = __eq__ # I don't know exactly what this does, but it can't hurt.

    def __ne__(self, other):
        return not (self == other)
    __rne__ = __ne__ # Likewise as above.

    def __hash__(self):
        if self._hash is not None:
            return self._hash
        self._hash = hash(self.command) ^ \
                     hash(self.prefix) ^ \
                     hash(repr(self.args))
        return self._hash

    def __repr__(self):
        if self._repr is not None:
            return self._repr
        #self._repr = format('IrcMsg(prefix=%q, command=%q, args=%r)',
        #                    self.prefix, self.command, self.args)
        self._repr = "IrMsg(TODO)"
        return self._repr

    def __reduce__(self):
        return (self.__class__, (str(self),))

    def tag(self, tag, value=True):
        """Affect a key:value pair to this message."""
        self.tags[tag] = value

    def tagged(self, tag):
        """Get the value affected to a tag."""
        return self.tags.get(tag) # Returns None if it's not there.

    def __getattr__(self, attr):
        if attr.startswith('__'): # Since PEP 487, Python calls __set_name__
            raise AttributeError("'%s' object has no attribute '%s'" %
                    (self.__class__.__name__, attr))
        if attr in self.tags:
            warnings.warn("msg.<tagname> is deprecated. Use "
                    "msg.tagged('<tagname>') or msg.tags['<tagname>']"
                    "instead.", DeprecationWarning)
            return self.tags[attr]
        else:
            # TODO: make this raise AttributeError
            return None

