#-*- coding: utf8 -*-

import urllib.parse as urlparse
import requests
import re
import json

from bs4 import BeautifulSoup as BS


DEFAULT_LANG = "en"

base_url = "https://www.accuweather.com"
#search_path = "{lang}/search-locations?query={query}"
autocomplete_path = "web-api/autocomplete?query={query}&language={lang_tag}"
forecast_path = "{{lang}}/{{id}}/{{location}}/{{key}}/{forecast_type}/{{key}}"

locale = {
    "citynotfound": {
        "it": "città non trovata.",
        "en": "city not found." 
    },

    "unavailable": {
        "it": "non disponibile per questa città.",
        "en": "not available for this city."
    },
}

lang_tags = {
    "it": "it",
    "en": "en-us"
}


def _get_path(path, attrs={}, *, refer_to_self=False):
    hdrs = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:72.0) Gecko/20100101 Firefox/72.0"}

    for k, v in attrs.items():
        attrs[k] = urlparse.quote(v)

    path = path.format(**attrs)
    url = urlparse.urljoin(base_url, path)

    if refer_to_self:
        hdrs["Referer"] = url 

    return requests.get(url, headers=hdrs)


def _search(location, request_path, lang=DEFAULT_LANG):
    results = []

    attrs = {
        "lang": lang,
        "lang_tag": lang_tags.get(lang, lang_tags[DEFAULT_LANG]),
        "query": location
    }
    req = _get_path(autocomplete_path, attrs, refer_to_self=True) 
    locations = req.json()

    """
    multiple_mtch = re.search("var searchLocationResults = ([^;]+)", req.text)
    location_mtch = re.search("var currentLocation = ([^;]+)", req.text)

    if multiple_mtch:
        locations = json.loads(multiple_mtch.group(1))

        if not locations:
            return []

    if location_mtch:
        locations.append(json.loads(location_mtch.group(1)))
    """

    for loc in locations:
        path_data = {
            "lang": lang,
            "location": loc["localizedName"].replace(" ", "-"),
            "id": loc["country"]["id"],
            "key": loc["key"]
        }
        request_path = request_path.format(**path_data)

        results.append({
            "location": path_data["location"],
            "country": loc["country"]["localizedName"],
            "path": request_path.lower()
        })

    return results


def _get_forecast(location, forecast_type, *, lang=DEFAULT_LANG, entry_index=0):
    path = forecast_path.format(forecast_type=forecast_type)
    search_results = _search(location, path, lang)

    if not search_results:
        return

    entry = search_results[entry_index]

    return entry, _get_path(entry["path"])


def forecast(location, *, lang=DEFAULT_LANG, entry_index=0):
    ret = _get_forecast(location, "weather-forecast",
        lang=lang, entry_index=entry_index)

    if ret is None:
        locale_strings = locale["citynotfound"]

        return location, locale_strings.get(lang, locale_strings[DEFAULT_LANG])
    else:
        entry, request = ret

    forecasts = []
    soup = BS(request.text, "html.parser")

    for elem in soup.findAll("div", class_="day-panel"):
        temp_div = elem.find("div", class_="temp")
        temp = temp_div.find("span", class_="high").text.strip()
        unit = temp_div.find("span", class_="low").text.strip()
        condition = elem.find("div", class_="cond").text.strip()
        when = elem.find("p", class_="module-header").text.strip()
        datetime = elem.find("p", class_="module-header sub date").text.strip()
        
        forecasts.append("{} {}: {} {}, {}".format(
            when, datetime, temp, unit, condition))

    pre = "{location}, {country}".format(**entry)
    msg = " | ".join(forecasts)

    return pre, msg


def minutecast(location, *, lang=DEFAULT_LANG, entry_index=0):
    ret = _get_forecast(location, "minute-weather-forecast",
        lang=lang, entry_index=entry_index)

    if ret is None:
        locale_strings = locale["citynotfound"]

        return location, locale_strings.get(lang, locale_strings[DEFAULT_LANG])
    else:
        entry, request = ret

    pre = "{location}, {country}".format(**entry)
    locale_strings = locale["unavailable"]
    msg = locale_strings.get(lang, locale_strings[DEFAULT_LANG])
    minutecast_mtch = re.search("window.minuteCastMinutes = ([^;]+)", request.text)
    summary = None

    soup = BS(request.text, "html.parser")
    mcast_dial = soup.find("div", class_="minutecast-dial")
    if mcast_dial is not None:
        p_title = mcast_dial.find("p", class_="title")
        if p_title:
            summary = p_title.text.strip()

    if minutecast_mtch:
        minutes_forecast = json.loads(minutecast_mtch.group(1))

        if not minutes_forecast:
            return pre, msg

        last_time = minutes_forecast[0]["time"]
        last_phrase = minutes_forecast[0]["phrase"]
        interval_forecast = []

        for minutecast in minutes_forecast:
            phrase = minutecast["phrase"]
            time = minutecast["time"]
            minute = minutecast["minute"]

            if last_time is None:
                last_time = time

            interval_str = ("{} -> {}".format(last_time, time), last_phrase)

            if phrase != last_phrase:
                interval_forecast.append(interval_str)
                last_phrase = phrase
                last_time = None

            if minute == 119:
                if last_time is None:
                    interval_forecast.append((time, phrase))
                else:
                    interval_forecast.append(interval_str)
        
        if len(interval_forecast) == 1 and summary is not None:
            msg = "{}.".format(summary)
        else:
            minutecast_intervals = ["{}: {}".format(time, phrase)
                for time, phrase in interval_forecast]
            msg = "{}. ".format(summary) if summary is not None else ""
            msg += ', '.join(minutecast_intervals)

    return pre, msg

