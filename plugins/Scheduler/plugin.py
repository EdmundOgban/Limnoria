###
# Copyright (c) 2003-2004, Jeremiah Fincher
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

import time
import re
import os
import shutil
import tempfile
from datetime import datetime

import supybot.conf as conf
import supybot.utils as utils
from supybot.commands import *
import supybot.schedule as schedule
import supybot.callbacks as callbacks
from supybot.i18n import PluginInternationalization, internationalizeDocstring
_ = PluginInternationalization('Scheduler')
import supybot.world as world

import supybot.utils.minisix as minisix
pickle = minisix.pickle

datadir = conf.supybot.directories.data()
filename = conf.supybot.directories.data.dirize('Scheduler.pickle')

class Scheduler(callbacks.Plugin):
    """This plugin allows you to schedule commands to execute at a later time."""
    def __init__(self, irc):
        self.__parent = super(Scheduler, self)
        self.__parent.__init__(irc)
        self.events = {}
        self._restoreEvents(irc)
        world.flushers.append(self._flush)

    def _restoreEvents(self, irc):
        try:
            pkl = open(filename, 'rb')
            try:
                eventdict = pickle.load(pkl)
            except Exception as e:
                self.log.debug('Unable to load pickled data: %s', e)
                return
            finally:
                pkl.close()
        except IOError as e:
            self.log.debug('Unable to open pickle file: %s', e)
            return
        for name, event in eventdict.items():
            ircobj = callbacks.ReplyIrcProxy(irc, event['msg'])
            try:
                if event['type'] in ('single', 'alert'): # non-repeating event
                    n = None
                    if schedule.schedule.counter > int(name):
                        # counter not reset, we're probably reloading the plugin
                        # though we'll never know for sure, because other
                        # plugins can schedule stuff, too.
                        n = int(name)
                    self._add(ircobj, event['msg'],
                              event['time'], event['command'],
                              event['issued_by'], n,
                              event['type'])
                elif event['type'] == 'repeat': # repeating event
                    self._repeat(ircobj, event['msg'], name,
                                 event['time'], event['command'],
                                 event['issued_by'], False)
            except AssertionError as e:
                if str(e) == 'An event with the same name has already been scheduled.':
                    # we must be reloading the plugin, event is still scheduled
                    self.log.info('Event %s already exists, adding to dict.', name)
                    self.events[name] = event
                else:
                    raise

    def _flush(self):
        try:
            pklfd, tempfn = tempfile.mkstemp(suffix='scheduler', dir=datadir)
            pkl = os.fdopen(pklfd, 'wb')
            try:
                pickle.dump(self.events, pkl)
            except Exception as e:
                self.log.warning('Unable to store pickled data: %s', e)
            pkl.close()
            shutil.move(tempfn, filename)
        except (IOError, shutil.Error) as e:
            self.log.warning('File error: %s', e)

    def die(self):
        # Should I do this?
        #self._wipe_alerts()
        self._flush()
        world.flushers.remove(self._flush)
        self.__parent.die()

    def _beforeAdd(self, nick):
        howmany = sum(1 for id, ev in self.events.items() if ev["issued_by"] == nick)
        return howmany < 10

    def _makeCommandFunction(self, irc, msg, command, remove=True):
        """Makes a function suitable for scheduling from command."""
        tokens = callbacks.tokenize(command,
            channel=msg.channel, network=irc.network)
        def f():
            if remove:
                del self.events[str(f.eventId)]
            self.Proxy(irc.irc, msg, tokens)
        return f

    def _add(self, irc, msg, t, command, issued_by, name=None, type="single"):
        f = self._makeCommandFunction(irc, msg, command)
        id = schedule.addEvent(f, t, name)
        f.eventId = id
        self.events[str(id)] = {'command':command,
                                'msg':msg,
                                'time':t,
                                'issued_by':issued_by,
                                'type':type}
        return id

    @internationalizeDocstring
    def add(self, irc, msg, args, seconds, command):
        """<seconds> <command>

        Schedules the command string <command> to run <seconds> seconds in the
        future.  For example, 'scheduler add [seconds 30m] "echo [cpu]"' will
        schedule the command "cpu" to be sent to the channel the schedule add
        command was given in (with no prefixed nick, a consequence of using
        echo).  Do pay attention to the quotes in that example.
        """
        if not self._beforeAdd(msg.nick):
            irc.error("you've got too many scheduled events.", prefixNick=True)
            return

        t = time.time() + seconds
        id = self._add(irc, msg, t, command, msg.nick)
        irc.replySuccess(format(_('Event #%i added.'), id))
    add = wrap(add, ['positiveInt', 'text'])

    @internationalizeDocstring
    def remove(self, irc, msg, args, id):
        """<id>

        Removes the event scheduled with id <id> from the schedule.
        """
        if id in self.events:
            ev = self.events[id]
            if ev["issued_by"] != msg.nick:
                irc.error("event id '{}' does not belong to you.".format(id))
                return

            del self.events[id]
            try:
                id = int(id)
            except ValueError:
                pass
            try:
                schedule.removeEvent(id)
                irc.replySuccess()
            except KeyError:
                irc.error(_('Invalid event id.'))
        else:
            irc.error(_('Invalid event id.'))
    remove = wrap(remove, ['lowered'])

    def _repeat(self, irc, msg, name, seconds, command, issued_by, now=True):
        f = self._makeCommandFunction(irc, msg, command, remove=False)
        id = schedule.addPeriodicEvent(f, seconds, name, now)
        assert id == name
        self.events[name] = {'command':command,
                             'msg':msg,
                             'time':seconds,
                             'issued_by':issued_by,
                             'type':'repeat'}

    @internationalizeDocstring
    def repeat(self, irc, msg, args, name, seconds, command):
        """<name> <seconds> <command>

        Schedules the command <command> to run every <seconds> seconds,
        starting now (i.e., the command runs now, and every <seconds> seconds
        thereafter).  <name> is a name by which the command can be
        unscheduled.
        """
        if not self._beforeAdd(msg.nick):
            irc.error("you've got too many events scheduled.")
            return

        name = name.lower()
        if name in self.events:
            irc.error(_('There is already an event with that name, please '
                      'choose another name.'), Raise=True)
        self._repeat(irc, msg, name, seconds, command)
        # We don't reply because the command runs immediately.
        # But should we?  What if the command doesn't have visible output?
        # irc.replySuccess()
    repeat = wrap(repeat, ['nonInt', 'positiveInt', 'text'])

    def _format_list(self, L):
        L.sort()
        for (i, (name, command)) in enumerate(L):
            time_at = datetime.fromtimestamp(command["time"]-time.time()-3600).strftime("%H:%M:%S")
            L[i] = format('%s: %q -%s', name, command['command'], time_at)

        return L

    @internationalizeDocstring
    @wrap
    def listall(self, irc, msg, args):
        """takes no arguments

        Lists the currently scheduled events.
        """

        L = list(self.events.items())
        if L:
            irc.reply(format('%L', self._format_list(L)))
        else:
            irc.reply(_('There are currently no scheduled commands.'))

    @wrap
    def list(self, irc, msg, args):
        """takes no arguments

        Lists only currently scheduled events for yourself.
        """

        L = list((k, v) for k, v in self.events.items() if v['issued_by'] == msg.nick)
        if L:
            irc.reply(format('%L', self._format_list(L)))
        else:
            irc.reply(_('There are currently no scheduled commands.'))

    @wrap
    def listinternal(self, irc, msg, args):
        """takes no arguments

        Lists all scheduled events, including internal ones.
        """

        internal = schedule.schedule
        out = []
        for sched in internal.schedule:
            time_at = datetime.fromtimestamp(sched[0]).isoformat()
            out.append("{} at {}".format(sched[1], time_at))

        irc.reply(', '.join(out))

    @wrap(['somethingWithoutSpaces', optional('text')])
    def countdown(self, irc, msg, args, units, text):
        """ <howlong> [text]
        Count down to <howlong>. Optionally replies with [text]."""
        m = re.match(r'^(?:([.\d]+)h)?(?:([.\d]+)m)?(?:([.\d]+)s?)?$',
                     units)
        if not m:
            irc.error("invalid input: '{}'".format(units))
            return

        if not self._beforeAdd(msg.nick):
            irc.error("you've got too many events scheduled.")
            return

        if units[-1] not in "hms":
            units += "s"

        attrs = []
        for val in m.groups():
            try:            
                attrs.append(float(val))
            except ValueError:
                irc.error("invalid input: '{}'".format(val))
                return
            except TypeError:
                attrs.append(0)

        timeuntil = attrs.pop() + attrs.pop() * 60 + attrs.pop() * 3600
        if timeuntil > 43200: # 12 Hours
            irc.error("cannot count up to {} (12 hours max).".format(units))
            return

        t = time.time() + timeuntil
        s = text if text else "your {} timer has expired.".format(units)
        id = self._add(irc, msg, t, "echo {}: {}".format(msg.nick, s), msg.nick, type="alert")

    def _wipe_alerts(self):
        cnt = 0
        evs = list(self.events)
        for sid in evs:
            desc = self.events[sid]
            if desc["type"] != "alert":
                continue

            try:
                schedule.removeEvent(int(sid))
                del self.events[sid]
            except KeyError:
                pass
            else:
                cnt += 1

        return cnt

    @wrap(['owner'])
    def wipetimers(self, irc, msg, args):
        """
        Clear all scheduled alerts. """
        cnt = self._wipe_alerts()
        irc.reply("Wiped {} scheduled alert{}.".format(cnt, '' if cnt == 1 else 's'))

Class = Scheduler

# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
