###
# Copyright (c) 2011, Edmund_Ogban
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

from supybot.commands import *
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks
import supybot.schedule as schedule
import supybot.world as world

import os.path
import subprocess
import re
import ftplib

PISG_DIR = '/home/enrico/envs/supybot_new/bin/pisg'
PISG_CFGFILE = 'pisg.cfg'
PISG_EXE = 'pisg'
FTP_HOST = 'sooon.altervista.org'
BASE_URL = FTP_HOST
STATS_PATH = '/stats'
STATS_URL = 'http://{}{}/%s.html'.format(BASE_URL, STATS_PATH)
STATS_DELAY = 3600 # in seconds

credentials = dict(userid='SoooN', password='voscor58')

class StatsGeneratorAndUploader(object):
    def __init__(self, event_name, active_stats):
        self.event_name = event_name
        self.active_stats = active_stats

    def __call__(self):
        return self._generate()

    def _upload(self):
        ftp = ftplib.FTP(FTP_HOST, credentials['userid'],
                         credentials['password'])
        for stat in self.active_stats:
            statfname = '%s.html' % stat[1:]
            statfpath = os.path.join(PISG_DIR, statfname)
            try:
                ftp.cwd(STATS_PATH)
            except ftplib.error_perm as e:
                if str(e).startswith('550'):
                    ftp.mkd(STATS_PATH)
                    ftp.cwd(STATS_PATH)
            finally:
                ftp.storbinary('STOR %s' % statfname, open(statfpath, 'rb'))

        ftp.close()

    def _generate(self):
        # Fucking PISG creates statistics in the current directory, so
        # we have to do something to create the files where we want.
        world.flush()
        olddir = os.getcwd()
        os.chdir(PISG_DIR)
        s = os.path.join(PISG_DIR, PISG_EXE)
        retcode = subprocess.call([s])
        os.chdir(olddir)
        self._upload()

class PisgStats(callbacks.Plugin):
    """ """
    threaded = True

    def __init__(self, irc):
        super(PisgStats, self).__init__(irc)
        self.event_name = 'generate_stats'
        self.chan_re = re.compile(r'<channel="([\S]+)">')
        self.active_stats = self._parse_active()
        self.generator = StatsGeneratorAndUploader(self.event_name,
                                                   self.active_stats)
        #self._schedule()

    def _parse_active(self):
        L = []
        for line in open(os.path.join(PISG_DIR, PISG_CFGFILE)):
           r = self.chan_re.search(line)
           if r:
                L.append(r.group(1))
        return L

    def _schedule(self):
        id = schedule.addPeriodicEvent(self.generator, STATS_DELAY, self.event_name)
        if id is None:
            self.log.info('Event %s was already scheduled. '
                          'Removing and rescheduling.' % self.event_name)
            schedule.removeEvent(self.event_name)
            schedule.addPeriodicEvent(self.generator, STATS_DELAY,
                                      self.event_name)

    @wrap(['owner'])
    def genstats(self, irc, msg, args):
        """ generate stats """
        self.generator()
        irc.reply('Statistics generation done.')

    def chanstats(self, irc, msg, args):
        """ show stats link """
        channel = msg.args[0]
        if ircutils.isChannel(channel):
            if channel in self.active_stats:
                irc.reply('Statistics for %s: %s' % (channel, (STATS_URL %
                                                               channel[1:])))

Class = PisgStats


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
