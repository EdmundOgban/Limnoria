import requests
from bs4 import BeautifulSoup as BS

_URL = "http://www.meteoam.it/metar"
_headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/603.3.8 (KHTML, like Gecko) Version/10.1.2 Safari/603.3.8"
}
def get_metar(icao):
    try:
        stream = requests.get(_URL, headers=_headers)
    except Exception:
        return "HTTP error"
    soup = BS(stream.text, "html.parser")
    
    form = soup.find("form")
    form_secret = form.find("input", {"name": "form_build_id"})
    form_secret_value = form_secret["value"]

    data_dict = dict(form_build_id=form_secret_value, icao=icao, form_id="metar_searchform")
    searchres = requests.post(_URL, data=data_dict, headers=_headers)
    soup = BS(searchres.text, "html.parser")
    metar_div = soup.find("div", {"class": "alert alert-block alert-success"})
    if not metar_div:
        return "Not found."

    metar = metar_div.find_all("p")[2]
    return metar.contents[3].split(" ", 2)[-1]

print(get_metar('LIAA'))
