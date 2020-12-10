##
# Copyright (c) 2002-2004, Jeremiah Fincher
# Copyright (c) 2010, 2013, James McCoy
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

from __future__ import division
from collections import defaultdict
from functools import partial

import html
import queue
import threading
import uuid

import telegram
from telegram.ext import CommandHandler, MessageHandler, InlineQueryHandler
from telegram.ext import Updater, Filters

from . import credentials
from .. import conf, drivers, ircmsgs, ircutils

import logging
log = logging.getLogger("supybot")


# class TelegramIrcServer:
    # def __init__(self):
        # self.groups = defaultdict(dict)

    # def userAdd(self, user, group):
        # pass

    # def userDel(self, user, group):
        # pass

    # def groupAdd(self, group):
        # pass

    # def groupDel(self, group):
        # pass

    # def names(self, group):
        # pass

    # def setTopic(self, group):
        # pass

    # def feedMsg(self, msg: ircmsgs.IrcMsg):
        # pass

telegram_users = dict()

def mircToHtml(s):
    ccodes = {
        "\x02": [False, "<b>", "</b>"],
        "\x1d": [False, "<i>", "</i>"],
        "\x1f": [False, "<u>", "</u>"]
    }
    out = []
    opened = []
    for c in s:
        tags = ccodes.get(c)
        if tags is not None:
            _, open, close = tags
            tags[0] = not tags[0]
            if tags[0] is True:
                out.append(open)
                opened.append(close)
            else:
                out.append(close)
                opened.remove(close)
        else:
            out.append(c)

    opened.reverse()
    return ircutils.stripFormatting("".join(out + opened))


class TelegramReceiver(threading.Thread):
    def __init__(self, inqueue, excqueue, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.inqueue = inqueue
        self.excqueue = excqueue
        self.connected = threading.Event()
        start_handler = CommandHandler('start', self.cmd_start)
        text_handler = MessageHandler(Filters.text, # & (~Filters.command)
            self.incoming_text)
        inline_handler = InlineQueryHandler(self.inline_query)
        self.updater = Updater(token=credentials.TOKEN, use_context=True)
        self.updater.dispatcher.add_handler(start_handler)
        self.updater.dispatcher.add_handler(text_handler)
        self.updater.dispatcher.add_handler(inline_handler)
        self.connected.set()

    @staticmethod
    def cmd_start(update, context):
        context.bot.send_message(chat_id=update.effective_chat.id,
            text="{rattobaleno}")        

    def _fake_privmsg(self, chat, user, text):
        recipient = ("Sleipnir" if chat is None or chat.type == "private"
            else "#{}".format(chat.id))
        nick = user.name.replace(" ", "_")
        ident = user.id
        host = "telegram.irc"
        hostmask = "{}!{}@{}".format(nick, ident, host)
        #realname = "{} {}".format(user.first_name, user.last_name)
        fake_privmsg = ":{} PRIVMSG {} :{}".format(hostmask, recipient, text)

        return fake_privmsg

    def incoming_text(self, update, context):
        chat = update.effective_chat
        user = update.effective_user
        message = update.message
        if message is None:
            return

        telegram_users[user.name.replace(" ", "_")] = str(user.id)
        fake_privmsg = self._fake_privmsg(chat, user, message.text)
        log.warning("Incoming message: '%s'", fake_privmsg)
        msg = drivers.parseMsg(fake_privmsg)
        msg.tag("telegram_sender", user.id)
        self.inqueue.put(msg)

    def inline_query(self, update, context):
        chat = update.effective_chat
        user = update.effective_user
        inline_query = update.inline_query

        telegram_users[user.name.replace(" ", "_")] = str(user.id)
        fake_privmsg = self._fake_privmsg(chat, user, inline_query.query)
        msg = drivers.parseMsg(fake_privmsg)
        inline_id = uuid.uuid4()
        msg.tag("telegram_inline", inline_id)
        msg.tag("telegram_inline_query", inline_query)
        log.info("Telegram: Inline query: '%s'", inline_query.query)
        self.inqueue.put(msg)

    def _run(self):
        self.updater.start_polling()

    def run(self):
        while True:
            try:
                self._run()
            except Exception as e:
                self.excqueue.put(e)
                self.disconnect()
            finally:
                break

    def disconnect(self):
        self.updater.stop()
        self.connected.clear()


class TelegramSender(threading.Thread):
    def __init__(self, outqueue, excqueue, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.outqueue = outqueue
        self.excqueue = excqueue
        self.botnick = None
        self.bot = telegram.Bot(token=credentials.TOKEN)

    def _run(self):
        while True:
            msg = self.outqueue.get()
            if msg is None:
                break

            try:
                recipient, text = msg.args
            except ValueError:
                text = msg.args[0]

            if msg.command == "PRIVMSG" and ircmsgs.isAction(msg):
                text = "/me {}".format(ircmsgs.unAction(msg))

            text = mircToHtml(html.escape(text))
            inline_id = msg.tagged("telegram_inline")
            if inline_id is not None:   
                query = msg.tagged("telegram_inline_query")
                query.answer([
                    telegram.InlineQueryResultArticle(
                        id=inline_id,
                        title=text,
                        input_message_content=telegram.InputTextMessageContent(
                            text, parse_mode=telegram.ParseMode.HTML))],
                    cache_time=10)
            elif msg.command in ("PRIVMSG", "NOTICE"):
                recipient = telegram_users.get(recipient, recipient)
                try:
                    self.bot.send_message(recipient.lstrip("#"),
                        text=text,
                        parse_mode=telegram.ParseMode.HTML)
                except (telegram.error.BadRequest, telegram.error.Unauthorized) as e:
                    sender = msg.tagged("telegram_sender")
                    if sender is not None:
                        self.bot.send_message(sender,
                            text="{}: {}".format(recipient, str(e)))

    def run(self):
        while True:
            try:
                self._run()
            except Exception as e:
                self.excqueue.put(e)
                self.outqueue.put(None)
            finally:
                break

    def disconnect(self):
        self.outqueue.put(None)


class TelegramDriver(drivers.IrcDriver, drivers.ServersMixin):
    def __init__(self, irc):
        assert irc is not None
        self.irc = irc
        drivers.IrcDriver.__init__(self, irc)
        drivers.ServersMixin.__init__(self, irc)
        self.botnick = None
        self.connected = False
        self.inqueue = queue.Queue()
        self.outqueue = queue.Queue()
        self.excqueue = queue.Queue()
        self.telegram_recv = TelegramReceiver(self.inqueue, self.excqueue)
        self.telegram_send = TelegramSender(self.outqueue, self.excqueue)
        self.connect()

    def _fake_serverconn(self):
        if self.botnick is None:
            return

        numerics = [
            ":{server} 004 {nick} {server} TelegramIRC-0.1 i nto :BEFJYbdefghjklov",
            ":{server} 005 {nick} ACCEPT=30 AWAYLEN=200 CASEMAPPING=ascii CHANLIMIT=#:2048",
                " CHANMODES=,,nto CHANNELLEN=255 LINELEN=4096 CHANTYPES=# :",
            ":{server} 005 {nick} HOSTLEN=64 KEYLEN=32 KICKLEN=255 MAXLIST=beg:100"
                " MAXTARGETS=20 MODES=20 NETWORK=TelegramIRC NICKLEN=255 OVERRIDE"
                " PREFIX=(o)@ SAFELIST SECURELIST=60 :",
            ":{server} 005 {nick} STATUSMSG=@%+ TOPICLEN=307 USERLEN=10 USERMODES=,,s,i :",
            ":{server} 376 {nick} :End of message of the day."
        ]

        for numeric in numerics:
            s = numeric.format(server="bridge.telegram.irc", nick=self.botnick)
            msg = drivers.parseMsg(s)
            self.inqueue.put(msg)

    def _sendIfMsgs(self):
        if not self.connected:
            return

        msg = self.irc.takeMsg()
        while msg is not None:
            in_q = []

            # HACK: to correctly complete the connection we have to fake a 
            #  message exchange with a real IRC server
            log.warning("Outgoing message: '{!r}'".format(msg))
            if msg.command == "NICK":
                self.botnick = msg.args[0]
                log.warn("Received NICK %s", self.botnick)
            elif msg.command == "USER":
                log.warn("Faking connection to IRC server")
                self._fake_serverconn()
            elif msg.command == "PING":
                in_q.append("PONG")
            elif msg.command == "JOIN":
                channel = msg.args[0]
                in_q.append(":!@ JOIN {}".format(channel))
                in_q.append(":bridge.telegram.irc 366 {} {} :".format(
                    self.botnick, channel))
            elif msg.command == "PART":
                channel = msg.args[0]
                in_q.append(":!@ PART {}".format(channel))
            else:
                self.outqueue.put(msg)

            for s in in_q:
                msg = drivers.parseMsg(s)
                self.inqueue.put(msg)

            msg = self.irc.takeMsg()

    def run(self):
        self._sendIfMsgs()
        try:
            msg = self.inqueue.get(timeout=conf.supybot.drivers.poll())
        except queue.Empty:
            pass
        else:
            if msg is not None and self.irc is not None:
                self.irc.feedMsg(msg)
                if not self.irc.zombie:
                    self._sendIfMsgs()

        try:
            e = self.excqueue.get_nowait()
        except queue.Empty:
            pass
        else:
            if e:
                raise e

    def die(self):
        self.telegram_recv.disconnect()
        self.telegram_send.disconnect()
        super().die()

    def connect(self):
        if self.connected is False:
            self.telegram_send.start()
            self.telegram_recv.start()
            self.telegram_recv.connected.wait()
            self.connected = True

    def reconnect(self, wait=False):
        pass
        # TODO: restart thread
        #self.telegram.disconnect()

        # TODO: reconnection scheduler
        #if wait:
        #    self.scheduleReconnect()
        #    return


Driver = TelegramDriver

# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

