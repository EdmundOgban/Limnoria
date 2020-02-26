import requests

API_URL = "https://api.litebit.eu/markets"

abbr_2_name = {}

def scrape(coins=['btc', 'bch', 'ltc', 'xrp', 'zec', 'eth'], *, sort=False):
    try:
        req = requests.get(API_URL)
    except Exception:
        print("Error while getting {}".format(API_URL))
    else:
        data = req.json()

        if data["success"] is not True:
            print("Request failed.")
            return

        L = []

        for coin, desc in data["result"].items():
            abbr_2_name[coin] = desc["name"]
            if coin not in coins:
                continue

            avail = desc["available"] > 0
            buy = desc["buy"]
            sell = desc["sell"]

            L.append((coin, avail, buy, sell))

        if sort:
            return sorted(L, key=lambda x: coins.index(x[0]))
        else:
            return L

