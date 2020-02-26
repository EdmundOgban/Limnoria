###
# Copyright (c) 2017, Enrico A
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
import supybot.callbacks as callbacks
try:
    from supybot.i18n import PluginInternationalization
    _ = PluginInternationalization('Metar')
except ImportError:
    # Placeholder that allows to run the plugin on a bot
    # without the i18n module
    _ = lambda x: x

import math
import requests
from bs4 import BeautifulSoup as BS
#import xml.etree.ElementTree as ET
import defusedxml.cElementTree as ET

from . import icao_list

class ICAONotFound(Exception):
    pass

class Metar(callbacks.Plugin):
    """Metar"""
    threaded = True

    _URL = "http://www.meteoam.it/metar"
    _headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/603.3.8 (KHTML, like Gecko) Version/10.1.2 Safari/603.3.8"
    }
    def get_metar(self, icao):
        try:
            stream = requests.get(self._URL, headers=self._headers)
        except Exception:
            return "HTTP error"
        soup = BS(stream.text, "html.parser")

        form = soup.find("form")
        form_secret = form.find("input", {"name": "form_build_id"})
        form_secret_value = form_secret["value"]

        data_dict = dict(form_build_id=form_secret_value, icao=icao, form_id="metar_searchform")
        searchres = requests.post(self._URL, data=data_dict, headers=self._headers)
        soup = BS(searchres.text, "html.parser")
        metar_div = soup.find("div", {"class": "alert alert-block alert-success"})
        if not metar_div:
            return "Not found."

        pees = metar_div.find_all("p")
        return pees[0].contents[0].text.replace(" - ", ", "), pees[2].contents[3].split(" ", 2)[-1]

    def get_metar_gov(self, icao):
        URL = "https://www.aviationweather.gov/adds/dataserver_current/httpparam"
        params_dict = {
            "dataSource": "metars",
            "requestType": "retrieve",
            "format": "xml",
            "stationString": icao,
            "hoursBeforeNow": 2
        }

        stream = requests.get(URL, headers=self._headers, params=params_dict)
        root = ET.fromstring(stream.text)
        for child in root:
            if child.tag == "data":
                if int(child.attrib.get("num_results", 0)) > 0:
                    for subchild in child:
                        return subchild[0].text
                else:
                    raise ICAONotFound
            elif child.tag == "errors" and len(child) > 0:
                return child[0].text

    def _construct_reply(self, icao, metar):
        desc = dict(icao=icao, metar=metar)

        if icao in icao_list.airport_desc:
            desc["airport_desc"] = icao_list.airport_desc[icao]
            return "Metar ({airport_desc}): {metar}".format(**desc)
        else:
            return "Metar ({icao}): {metar}".format(**desc)

    @wrap(['text'])
    def metar(self, irc, msg, args, icao):
        """ <icao> """
        icao = icao.upper()

        try:
            if icao not in icao_list.airport_desc:
                for k, v in icao_list.airport_desc.items():
                    if icao.title() in v:
                        icao = k
                        break
            metar = self.get_metar_gov(icao)
        except requests.exceptions.HTTPError:
            irc.error("HTTP Error.")
        except requests.exceptions.ConnectionError:
            irc.error("Connection Error.")
        except requests.exceptions.Timeout:
            irc.error("Request timed out.")
        except ICAONotFound:
            irc.reply(self._construct_reply(icao, "Not found."))
        else:
            irc.reply(self._construct_reply(icao, metar))

    @wrap(['float', 'float'])
    def humidity(self, irc, msg, args, t, td):
        """ <temperature> <dewpoint> """
        rh = round(100*(math.exp((17.625*td)/(243.04+td))/math.exp((17.625*t)/(243.04+t))).real, 1)
        s = "Temperature: {}°C, Dew Point: {}°C, Relative Humidity: {}%".format(t, td, rh)
        irc.reply(s, prefixNick=True)

Class = Metar


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
