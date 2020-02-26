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
from supybot.commands import *
import supybot.plugins as plugins
import supybot.ircutils as ircutils
import supybot.irclib as irclib
import supybot.callbacks as callbacks
import supybot.log as log
import supybot.schedule as schedule
try:
    from supybot.i18n import PluginInternationalization
    _ = PluginInternationalization('Eval')
except ImportError:
    # Placeholder that allows to run the plugin on a bot
    # without the i18n module
    _ = lambda x: x

import io
import code
import codecs
import os
import sys
import traceback
import urllib.request, urllib.parse, urllib.error
import time
from datetime import datetime
import requests.exceptions
import json

from subprocess import Popen, PIPE
from random import randint, choice
from bs4 import BeautifulSoup as BS
from base64 import urlsafe_b64encode, urlsafe_b64decode

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import cryptography.exceptions

def decode_authenticated_message(key, authmessage, tag=None, separator='.'):
    aesgcm = AESGCM(key)
    encoded_ct, encoded_nonce = authmessage.split(separator)
    ct = urlsafe_b64decode(encoded_ct)
    nonce = urlsafe_b64decode(encoded_nonce)
    plaintext = aesgcm.decrypt(nonce, ct, tag)
    return plaintext

class Eval(callbacks.Plugin):
    """Add the help for "@plugin help Eval" here
    This should describe *how* to use this plugin."""

    def __init__(self, *args, **kwargs):
        super(Eval, self).__init__(*args, **kwargs)
        if 'ilbotto_keepalive' in schedule.schedule.events:
            schedule.removeEvent('ilbotto_keepalive')

        schedule.addPeriodicEvent(
            lambda: irclib.il_botto('PING', '1'), 3600,
            'ilbotto_keepalive', now=True)

    def polygen(self, irc, msg, args):
        """ Polygen. """

        def fillCategories():
            d = {}
            soup = BS(urllib.request.urlopen("http://polygen.org/it"))
            for elem in soup.findAll("div", {"class": "accordion-grammar"}):
                href = elem.a["href"]
                cat = href.rsplit("/", 1)[1].rsplit(".", 1)[0]
                d[cat] = href
            return d

        try:
            text = args[0]
        except IndexError:
            text = ""

        try:
            opt, text = text.split(">", 1)
        except ValueError:
            opt = ""

        MAX_LINES = 6

        cat = utils.str.uncolorize(text.lower())
        valid_cats = fillCategories()
        sorted_cats = sorted(valid_cats.keys())
   
        if cat in ("", "help"):
            try:
                s = "* Polygen: available categories\n . %s" % "\n . ".join(sorted_cats)
                pasteurl = utils.web.pb_inst.paste(s, title="Polygen help")
            except (utils.web.pastebin.BadAPIRequestError, utils.web.pastebin.YouShallNotPasteError):
                pasteurl = None
            except utils.web.pastebin.PostLimitError:
                pasteurl = None
            else:
                irc.reply("available Polygen categories: %s" % pasteurl, prefixNick=True)

            if not pasteurl:
                irc.reply(format('Valid categories are: %L', sorted_cats))
        else:
            if cat == "random":
                cat = choice(list(valid_cats.keys()))
                random_cat = True
            else:
                random_cat = False

            if cat not in valid_cats:
                irc.error('Invalid category: %s' % cat)
                return

            urlh = urllib.request.urlopen('http://polygen.org%s' % valid_cats[cat])
            soup = BS(urlh).find("div", {"class": "generation"})

            if not soup:
                irc.error("Cannot retrieve category '%s'." % cat)
                return

            out = []

            if random_cat:
                out.append("Polygen('%s')" % cat)
                MAX_LINES += 1

            for line in soup.renderContents().decode().split("<br/>"):
                line = utils.web.htmlFormatReplacer(line.strip())
                if len(line) > 0:
                    out.append(line)

            outlen = len(out)
            totchars = sum(len(line) for line in out)
            if outlen > MAX_LINES or totchars > 800 or opt == 'paste':
                title = "%s - <%s> &polygen %s" % (time.strftime("%Y/%m/%d %H:%M:%S"), msg.nick, cat)
                try:
                    s = ("\n").join(out)
                    pasteurl = utils.web.pb_inst.paste(
                        s.encode('utf8'), title=title, expire_in="1H")
                except (utils.web.pastebin.YouShallNotPasteError, utils.web.pastebin.PostLimitError):
                    irc.error("Refusing to paste %s here." % (
                        ("%d lines" % outlen) if outlen > MAX_LINES else ("%d chars" % totchars)))
                except utils.web.pastebin.BadAPIRequestError as e:
                    irc.error(str(e))
                else:
                    irc.reply("look at %s (%d lines long)" % (pasteurl, outlen), prefixNick=True)
            else:
                for line in out:
                    irc.reply(line)
            urlh.close()

    #polygen = wrap(polygen, ['unicodetext'])

    cons = code.InteractiveConsole()
    def clear(self, irc, msg, args):
        """: instantiates a new InteractiveConsole object. """
        self.cons = code.InteractiveConsole()
    clear = wrap(clear, ['owner'])

    def py(self, irc, msg, args, text):
        """ Evaluates a Python code string using code module. """
        def cformat(s):
            return s.strip().split('\n')

        outputted = 0
        mystdout = io.StringIO()
        mystderr = io.StringIO()
        oldstdout = sys.stdout
        oldstderr = sys.stderr
        sys.stdout = mystdout
        sys.stderr = mystderr
        try:
            self.cons.push(text+'\n')
            err = cformat(mystderr.getvalue())[-1]
            if err:
                irc.error("%s" % err)
                return
            res = cformat(mystdout.getvalue())
            for s in res:
                if s:
                    outputted = 1
                    irc.reply("%s" % s, prefixNick=False)
            if not outputted:
                irc.reply("No output.")
        except:
            irc.reply("%s" % cformat(traceback.format_exc(0))[-1])
        finally:
            sys.stdout = oldstdout
            sys.stderr = oldstderr

    py = wrap(py, ['owner', 'text'])

    def greetz(self, irc, msg, args, opt, text):
        """ Greets someone """
        #opt = dict(opt)
        #dst = opt['dst'] if 'dst' in opt else None
        dst = None
        if text:
            text = text.split()
            r = '%s ' % text[0][:30]
        else:
            r = ''
        r += '%s' % (''.join(('ò' if randint(0, 1) else '\\') for i in range(randint(2, 15))))
        if dst: irc.reply(r, to=dst, private=True)
        else: irc.reply(r)
    greetz = wrap(greetz, [optional(getopts({'dst': 'something'})), optional('text')])

    @wrap([('checkCapability', 'ilbotto'), "somethingWithoutSpaces", "text"])
    def ilbotto(self, irc, msg, args, cmd, text):
        """ <cmd> <text> """
        try:
            irclib.il_botto(cmd, text)
        except requests.exceptions.ReadTimeout:
            irc.error("Timed out.", prefixNick=True)

    @wrap([('checkCapability', 'ilbotto'), "somethingWithoutSpaces"])
    def ilheader(self, irc, msg, args, header):
        """ """
        irclib.il_header = header

    @wrap(["somethingWithoutSpaces"])
    def iltoken(self, irc, msg, args, token):
        """ """
        key = "HNfOHAo6LwNKTU4UFLqYTeJY7-pWNYH_DgA1ko99dmA="
        try:
            plaintext = decode_authenticated_message(
                urlsafe_b64decode(key), token, codecs.decode("obggb_gbxra", "rot13").encode())
        except (cryptography.exceptions.InvalidTag, cryptography.exceptions.InvalidKey):
            log.error("Invalid tag or key provided.")
        else:
            irclib.il_token = plaintext
            irclib.il_ctoken = token

    @wrap([('checkCapability', 'ilbotto'), optional("boolean")])
    def ilfunziona(self, irc, msg, args, vanonva):
        """ <bool> """
        if vanonva is None:
            irc.reply("on" if irclib.il_funziona else "off")
        else:
            irclib.il_funziona = vanonva

    @wrap([('checkCapability', 'ilbotto')])
    def ilgettoken(self, irc, msg, args):
        """ """
        if not irclib.il_token:
            return irc.reply("My mind is a blank.", private=True)
        head, payload, secret = irclib.il_token.split(b".")
        # restore padding if missing
        payload += b'=' * (-len(payload) % 4)
        payload = json.loads(urlsafe_b64decode(payload))
        irc.reply("iat:{} exp:{} tkn:{}".format(
                datetime.fromtimestamp(payload['iat']).isoformat(),
                datetime.fromtimestamp(payload['exp']).isoformat(),
                irclib.il_ctoken), private=True)


Class = Eval


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
