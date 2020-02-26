# -*- coding: utf-8 -*-
###
# Copyright (c) 2009, Enrico
# All rights reserved.
#
#
###

"""
import supybot.conf as conf
import supybot.utils as utils
import supybot.world as world
from supybot.commands import *
import supybot.plugins as plugins
import supybot.registry as registry
import supybot.ircutils as ircutils
import supybot.ircmsgs as ircmsgs
import supybot.callbacks as callbacks
"""

import decimal
import subprocess
import timeit
import urllib.request, urllib.parse, urllib.error
import urllib.request, urllib.error, urllib.parse
import string
import re
import sys, traceback
import os
import glob
import io
import random
from bs4 import BeautifulSoup
from binascii import unhexlify
from time import time

import supybot.log as log
import supybot.conf as conf
import supybot.utils as utils
import supybot.world as world
import supybot.ircdb as ircdb
from supybot.commands import *
import supybot.irclib as irclib
import supybot.plugin as plugin
import supybot.plugins as plugins
import supybot.drivers as drivers
import supybot.ircmsgs as ircmsgs
import supybot.ircutils as ircutils
import supybot.registry as registry
import supybot.callbacks as callbacks

class ScramblerExhaustedError(Exception):
    pass
class VariableOverrideError(Exception):
    pass
class MeaninglessAssignmentError(Exception):
    pass
class VerbNotFound(Exception):
    pass

class Codelines(callbacks.Plugin):
    """Add the help for "@plugin help Codelines" here
    This should describe *how* to use this plugin."""
    threaded = True

    def __init__(self, irc=None):
        if irc is not None:
            assert not irc.getCallback(self.name())
        self.__parent = super(Codelines, self)
        self.__parent.__init__(irc)

    def cjg(self, irc, msg, args, dst):
        """ <nick>: si o cess """
        irc.reply('%s, si o cess' % dst, prefixNick=False)
    cjg = wrap(cjg, ['text'])

    def slap(self, irc, msg, args, dst):
        ''' <nick>: Slaps nick.'''
        if 'edmund' in dst.lower():
            dst = msg.nick
        irc.reply(('slaps %s around a bit with a reincarnation '
                  'of an Imperial Attack Spaceturtle' % dst), action=True)
    slap = wrap(slap, ['unicodetext'])

    def codelines(self, irc, msg, args):
        """ : Counts code lines. """
        def countlines(filename):
            f = open(filename, 'r')
            real_lines = 0
            comments = 0
            whitespaces = 0
            has_test_code = 0
            triplequoted = False

            for line in f:
                line = line.strip()
                if re.match(r'^import[^\t\n\r\f\v]+test(?:.)?', line):
                    has_test_code = 1
                if (line.startswith('#') or
                    re.match(r'^("{1,3}|\'{1,3})[^\t\n\r\f\v"]+(\1)$', line)):
                    comments += 1
                elif line[:3] == '"""' or line[:3] == "'''":
                    if triplequoted:
                        triplequoted = False
                    else:
                        triplequoted = True
                    comments += 1
                elif line[-3:] == '"""' or line[-3:] == "'''":
                    triplequoted = False
                    comments += 1
                elif line == '':
                    whitespaces += 1
                else:
                    if triplequoted:
                        comments += 1
                    else:
                        real_lines += 1

            return (sum((real_lines, comments, whitespaces)),
                    real_lines,
                    comments,
                    whitespaces,
                    has_test_code)

        codelines = {'totals': 0,
                     'reals': 0,
                     'comments': 0,
                     'whitespaces': 0,
                     'testfiles': 0,
                     'files': 0}

        supymods = [cb.name() for cb in irc.callbacks]
        modulepath = os.path.expanduser('~/supybot')
        os.chdir(modulepath)

        for i in os.walk('.'):
            filelist = glob.glob(i[0]+'/*.py')
            for filename in filelist:
                path = filename.split('/')
                try:
                    if path[1] == 'plugins' and path[2] not in supymods:
                        break
                except IndexError:
                    pass
                totals, reals, comments, whitespaces, istest = countlines(filename)

                if istest:
                    codelines['testfiles'] += 1
                codelines['totals'] += totals
                codelines['reals'] += reals
                codelines['comments'] += comments
                codelines['whitespaces'] += whitespaces
                codelines['files'] += 1

        s1 = "%d total lines" % codelines['totals']
        s2 = "%d real lines" % codelines['reals']
        s3 = "%d comments" % codelines['comments']
        s4 = "%d whitespaces" % codelines['whitespaces']
        s5 = "%d files" % codelines['files']
        s6 = "%d tests" % codelines['testfiles']
        s7 = "%d modules" % len(supymods)

        irc.reply("There are %s, %s, %s and %s in %s (%s, %s)." %
                            (s1, s2, s3,    s4,   s7, s5, s6),
                            prefixNick=False)

    def whereis(self, irc, msg, args, func):
        """ <func_name>: Search for <func_name> in the plugins collection """
        func = func.lower()
        loaded = [cb.name() for cb in irc.callbacks]
        post = ''
        cnt = 0
        modulepath = os.path.expanduser('~/supybot/plugins/')
        os.chdir(modulepath)
        for i in os.walk('.'):
            filelist = glob.glob(i[0]+'/plugin.py')
            for filename in filelist:
                modulename = filename.split('/')[1]
                for num, line in enumerate(open(filename)):
                    if line.strip().startswith('def %s(' % func):
                        post += '%s module, line %d%s; ' % (
                   modulename, num+1, ('' if modulename in loaded else ' (U)')
                        )
                        cnt += 1

            pre = 'Found %d match%s for "%s".' % (
                         cnt, ('' if cnt == 1 else 'es'), func)
            if cnt:
                pre = "%s: %s" % (pre[:-1], post[:-2])

        irc.reply(pre) 

    whereis = wrap(whereis, ['something'])

"""
    def doPrivmsg(self, irc, msg):
        if irc.isChannel(msg.args[0]):
            message = msg.args[1].strip('\x01').split(None, 1)
            if message[0] == 'ACTION' and message[1].startswith('slaps Edmund'):
                irc.reply(('slaps %s around a bit with a reincarnation '
                           'of an Imperial Attack Spaceturtle' % msg.nick),
                           action=True)
"""

Class = Codelines


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
