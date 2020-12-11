import json
import urllib.parse as urlparse
import time
import logging
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from random import random, uniform
from urllib.error import HTTPError
from uuid import uuid4

import requests


log = logging.getLogger("supybot")

DEEPL_HOMEPAGE = "https://www.deepl.com"
DEEPL_REFERER = DEEPL_HOMEPAGE + "/translator"
DEEPL_STATIC = "https://static.deepl.com"
DEEPL_API = "https://www2.deepl.com/jsonrpc"
DEEPL_STATS = "https://s.deepl.com/web/statistics"
#DEEPL_API = "https://www.httpbin.org/post"
DEFAULT_PREFERRED_LANGS = set(["IT", "EN"])
DELAY_TIME = 0
FAKE_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:83.0) Gecko/20100101 Firefox/83.0"


def js_Datenow():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def deepl_timestamp(q):
    n = q.count("i") + 1
    r = js_Datenow()
    return r + (n - (r % n))
    

class RequestBuilder:

    def __init__(self):
        self.preferred_langs = DEFAULT_PREFERRED_LANGS.copy()
        self.trid = None

    def build_relgroups(self):
        req = self._build_jsonrpc("getExperiments")
        req.update({
            "params": {
                "experimentsRequest": {
                    "tenantId": 1,
                    "clientExperiments": []
                 }
            },
        })

        return req

    def build_clientstate(self):
        req = self._build_jsonrpc("getClientState")
        req.update({
            "v": "20180814" # This should be investigated further
        })

        return req

    def build_translate(self, from_lang, to_lang, q, detected=False):
        req = self._build_jsonrpc("LMT_handle_jobs")

        from_lang = from_lang.lower()
        to_lang = to_lang.upper()
        req.update({
           "params": {
              "jobs": [{
                "kind": "default",
                "raw_en_sentence": q,
                "raw_en_context_before": [],
                "raw_en_context_after": [],
                "preferred_num_beams": 4,
              }],
              "lang": {
                 "user_preferred_langs": list(self.preferred_langs),
                 "target_lang": to_lang
              },
              "priority": -1,
              "commonJobParams": {
              },
              "timestamp": deepl_timestamp(q)
           }
        })
        
        if from_lang == "auto":
            req["params"]["commonJobParams"]["formality"] = None
        else:
            from_lang = from_lang.upper()

        lang = req["params"]["lang"]
        if detected:
            lang["source_lang_computed"] = from_lang
        else:
            lang["source_lang_user_selected"] = from_lang

        return req

    def build_splitsentences(self, from_lang, q):
        req = self._build_jsonrpc("LMT_split_into_sentences")

        from_lang = from_lang if from_lang == "auto" else from_lang.upper()
        req.update({
           "params": {
              "texts": [q],
              "lang": {
                 "lang_user_selected": from_lang,
                 "user_preferred_langs": [], # list(self.preferred_langs),
              },
           }
        })

        return req

    def update_dt(self):
        self.dt_lasttr = datetime.now()

    def reset(self, dt=None):
        self.trid = None
        self.sessid = None
        self.dt_lasttr = dt or (datetime.now() - timedelta(seconds=DELAY_TIME))
        self.preferred_langs.clear()
        self.preferred_langs |= DEFAULT_PREFERRED_LANGS
        self.client_experiments = []

    def build_statistics(self, *, eventid, from_lang=None, to_lang=None,
        sourcelang_detected=False, chars_before=None, chars_translated=None):

        if eventid in (50, 51, 53, 57, 58, 59, 60):
            if from_lang is None or to_lang is None or sourcelang_detected is None:
                raise ValueError("from_lang, to_lang and sourcelang_detected must"
                    " be explicited when eventid is {}".format(eventid))

        if self.sessid is None:
            self.sessid = str(uuid4())

        req = {
           "eventId": eventid,
           "sessionId": self.sessid,
           "url": DEEPL_REFERER,
           "pageId": 110,
           "proUser": False,
           "interfaceLanguage": "it",
           "userAgent": FAKE_UA,
           "screenInfo": {
              "widthCssPixel": 1920,
              "heightCssPixel": 1200,
              "viewportWidthCssPixel": 1714,
              "viewportHeightCssPixel": 481,
              "devicePixelRatio": 1
           },
           "clientExperiments": self.client_experiments
        }

        if eventid == 1:
           req.update({"pageviewData": {
              "referrer":""
           }})
        elif eventid == 50: # ctrl+v
            if chars_translated is None:
                raise ValueError("chars_translated must be explicited when eventid is 50")

            req.update({"translatorFullTranslationData": {
                "languageData": {
                    "sourceLang": from_lang,
                    "isSourceLangDetected": sourcelang_detected,
                    "targetLang": to_lang
                },
                "trigger": 1,
                "formalityMode": 3,
                "customizationMode": 2,
                "numberOfCustomizations": 1,
                "numberOfCustomizationEntriesForLangPair": 0,
                "textSessionId": str(js_Datenow() % 86_400_000),
                "numberOfCharacters": chars_translated,
                "dictionaryTriggered": False
            }})
        elif eventid == 51: # don't know. some periodic informations?
            if not all([chars_translated, chars_before]):
                raise ValueError("chars_translated and chars_before must be"
                    " explicited when eventid is 51")

            req.update({"translatorPartialTranslationData": {
                "languageData":{
                    "sourceLang": from_lang,
                    "isSourceLangDetected": sourcelang_detected,
                    "targetLang": to_lang
                },
                "formalityMode": 3,
                "customizationMode": 2,
                "numberOfCustomizations": 1,
                "numberOfCustomizationEntriesForLangPair": 0,
                "textSessionId": str(js_Datenow() % 86_400_000),
                "numberOfCharactersBefore": chars_before,
                "numberOfCharactersAfter": chars_translated,
                "dictionaryTriggered": False
            }})
        elif eventid in (53, 57, 58, 59, 60): # 53 is shift+home
            req.update({"translatorLanguageData":{
                "sourceLang": from_lang,
                "isSourceLangDetected": sourcelang_detected,
                "targetLang": to_lang
            }})

        return req

    def stringify(self, req):
        s = json.dumps(req)
        if (self.trid + 3) % 13 == 0 or (self.trid + 5) % 29 == 0:
            s = s.replace('method":', 'method" :')

        return s

    def _build_jsonrpc(self, method):
        #print(f"_build_jsonrpc self.trid: {self.trid}")
        if self.trid is None:
            self.trid = int(1e4 * round(1e4 * random()))

        self.trid += 1
        req = {
            "jsonrpc": "2.0",
            "method": method,
            "id": self.trid
        }
        return req


class DeepTr:
    def __init__(self):
        self.reqbuild = RequestBuilder()
        self.reset()

    def request_data(self, payload, url=DEEPL_API):
        hdrs = {
            "User-Agent": FAKE_UA,
        }

        if self.cookiejar is None:
            log.info("--> Filling cookie jar")
            resp = requests.get(DEEPL_HOMEPAGE, headers=hdrs)
            self.cookiejar = resp.cookies
            resp = requests.get(DEEPL_STATIC, headers=hdrs, cookies=self.cookiejar)
            self.cookiejar.update(resp.cookies)

        hdrs.update({
            "Origin": DEEPL_HOMEPAGE,
            "Referer": DEEPL_REFERER,
            "Content-Type": "application/json",
        })
        payload = self.reqbuild.stringify(payload)
        log.warning(f"--> POSTing {url} payload:{payload}")
        resp = requests.post(url, headers=hdrs, data=payload, cookies=self.cookiejar)
        self.cookiejar.update(resp.cookies)
        if resp.status_code != 200:
            raise HTTPError(code=resp.status_code, msg=resp.reason, url=DEEPL_API, hdrs=hdrs, fp=None)

        if not resp:
            raise IOError("No data received")

        data = resp.json()
        return data

    def request_result(self, payload, url=DEEPL_API):
        data = self.request_data(payload, url)
        result = data.get("result")
        if result is None:
            raise IOError("No 'result' in JSON data.")

        return result    

    def request_translate(self, from_lang, to_lang, q, retry=0):
        self._tr_delay_if_needed()
        payload = self.reqbuild.build_translate(from_lang, to_lang, q)
        try:
            result = self.request_result(payload)
        except HTTPError as e:
            if e.code == 429 and retry < 2:
                self.reset(dt=datetime.now())
                return self.request_translate(from_lang, to_lang, q, retry=retry+1)
            else:
                raise
        else:
            return result

    # def send_paste_event(self):
        # payload = self.reqbuild.build_statistics(
            # eventid=50,
            # from_lang=self.detected_lang.lower(),
            # to_lang=self.to_lang.lower(),
            # sourcelang_detected=(self.from_lang == "auto"),
            # chars_translated=self.chars_translated
        # )
        # self_chars_before = self.chars_translated
        # self.chars_translated = 0
        # self.request_data(payload, url=DEEPL_STATS)

    # def send_event51(self):
        # payload = self.reqbuild.build_statistics(
            # eventid=51,
            # from_lang=self.detected_lang.lower(),
            # to_lang=self.to_lang.lower(),
            # sourcelang_detected=(self.from_lang == "auto"),
            # chars_before=self.chars_before,
            # chars_translated=self.chars_translated
        # )
        # self_chars_before = self.chars_translated
        # self.chars_translated = 0
        # self.request_data(payload, url=DEEPL_STATS)

    def split_sentences(self, from_lang, s):
        payload = self.reqbuild.build_splitsentences(from_lang, s)
        result = self.request_result(payload)
        return result["lang"], result["splitted_texts"][0], result["lang_is_confident"]

    @lru_cache
    def translate(self, from_lang, to_lang, *, q):
        result = self.request_translate(from_lang, to_lang, q)
        self.chars_translated += len(q)
        self.lang_confident = result["source_lang_is_confident"]
        #if self.from_lang != from_lang:
        #    self.evpaste_count = 0

        beams = result["translations"][0]["beams"]
        detected_lang = result["source_lang"].lower()
        translations = [beam["postprocessed_sentence"] for beam in beams]
        self.from_lang = from_lang
        self.detected_lang = detected_lang
        self.to_lang = to_lang
        #if self.lang_confident is False and from_lang == "auto":
        #    payload = self.reqbuild.build_translate(detected_lang, to_lang, q, detected=True)
        #    self.lang_confident = self.request_result(payload)["source_lang_is_confident"]

        #if self.evpaste_count < 3:
        #    self.send_paste_event()
        #    self.evpaste_count += 1

        self.reqbuild.update_dt()
        self.reqbuild.preferred_langs.update([detected_lang.upper(), to_lang.upper()]) 
        return detected_lang.lower(), to_lang.lower(), translations

    # def _first_time_init(self):
        # hdrs = {
            # "User-Agent": FAKE_UA,
            # "Origin": DEEPL_HOMEPAGE,
            # "Referer": DEEPL_HOMEPAGE + "/translator",
        # }
        # payload = self.reqbuild.build_relgroups()
        # print(f"--> POSTing https://s.deepl.com/web/release-groups payload:{payload}")
        # resp = requests.post("https://s.deepl.com/web/release-groups",
           # headers=hdrs, json=payload)
        # result = resp.json().get("result")
        # if result is None:
           # raise IOError("No 'result' in JSON data.")

        # self.reqbuild.client_experiments.extend(result["clientExperiments"])
        # payload = self.reqbuild.build_clientstate()
        # print(f"--> POSTing https://www.deepl.com/PHP/backend/clientState.php?request_type=jsonrpc&il=IT payload:{payload}")
        # requests.post("https://www.deepl.com/PHP/backend/clientState.php?request_type=jsonrpc&il=IT",
           # headers=hdrs, json=payload)
        # payload = self.reqbuild.build_statistics(eventid=1)
        # print(f"--> POSTing {DEEPL_STATS} payload:{payload}")
        # requests.post(DEEPL_STATS, headers=hdrs, json=payload)
        # self.initialized = True

    # @staticmethod
    # def _fragment(s):
        # end = 0
        # top = len(s)
        # while True:
            # args = (1, 1) if end == 0 else (2, 4)
            # end += round(uniform(*args))
            # yield s[:end]
            # if end >= top:
                # break

    def _tr_delay_if_needed(self):
        lasttr = self.reqbuild.dt_lasttr
        now = datetime.now()
        delayed = None
        if now < lasttr + timedelta(seconds=DELAY_TIME):
            now_secs = now.second + (now.microsecond / 1000000)
            lasttr_secs = lasttr.second + (lasttr.microsecond / 1000000)
            delayed = DELAY_TIME - (now_secs - lasttr_secs)
            time.sleep(delayed)

        return delayed

    def reset(self, dt=None):
        self.cookiejar = None
        self.sessid = None
        self.lang_confident = False       
        self.from_lang = ""
        self.to_lang = ""
        self.evpaste_count = 0
        self.chars_before = 0
        self.chars_translated = 0
        self.reqbuild.reset(dt)

deeptr = DeepTr()
split_sentences = deeptr.split_sentences
translate = deeptr.translate
tr = translate
