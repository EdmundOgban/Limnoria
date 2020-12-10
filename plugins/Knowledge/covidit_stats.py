from collections import deque
from datetime import datetime, timedelta
from pathlib import Path

import json
import re


DB_PATH = Path(__file__).parent.joinpath("covidit.json")
covidit_stats = deque(maxlen=2)


class Stat:
    def __init__(self, value=0, delta=1):
        self.value = value
        self.delta = delta

    @classmethod
    def load(cls, obj):
        return cls(*obj)

    def dump(self):
        return self.value, self.delta

    def __iter__(self):
        yield self.value
        yield self.delta

    def __repr__(self):
        return "{}(value={}, delta={})".format(
            self.__class__.__name__,
            self.value,
            self.delta
        )


class DayStat:
    def __init__(self, total, infected, deaths, recovered, tested, date):
        self.total = total
        self.infected = infected
        self.deaths = deaths
        self.recovered = recovered
        self.tested = tested
        self.date = date

    def values(self):
        return self.total, self.infected, self.deaths, self.recovered, self.tested

    @classmethod
    def load(cls, obj):
        idx = len(obj) - 1
        return cls(*obj[:idx], datetime.strptime(obj[idx], "%Y-%m-%dT%H:%M:%S"))

    def dump(self):
        return [tuple(val) for val in self.values()] + [self.date.isoformat()]

    def __iter__(self):
        for item in self.values():
            yield item

    def __repr__(self):
        return ("{}(total={}, infected={}, deaths={}, recovered={}",
            " tested={}, date='{}') ").format(
            self.__class__.__name__,
            self.total,
            self.infected,
            self.deaths,
            self.recovered,
            self.date
        )


#class StatsJSONEncoder(json.JSONEncoder):
#    def default(self, obj):
#        if isinstance(obj, (Stat, DayStat)):
#            return tuple(obj)
#        elif isinstance(obj, deque):
#            return list(obj)
#
#        return super().default(obj)


def load(stats=covidit_stats):
    with open(DB_PATH) as f:
        for stat in json.load(f):
            idx = len(stat) - 1
            L = [Stat.load(val) for val in stat[:idx]]
            L.append(stat[idx])
            stats.append(DayStat.load(L))


def dump(stats=covidit_stats):
    dmp = [stat.dump() for stat in stats]
    with open(DB_PATH, "w") as f:
        json.dump(dmp, f)


covidit_re = re.compile("Italy: "
                        r"Total cases: (\d+).+"
                        r"Infected: (\d+).+"
                        r"Deaths: (\d+).+"
                        r"Recovered: (\d+).+"
                        r"Tested: (\d+).+"
                        r"Date: (.+)$")
def feed(msg, stats=covidit_stats):
    m = covidit_re.match(msg)
    if not m:
        return

    *cur_vals, date = m.groups()
    cur_date = datetime.strptime(date, "%Y-%m-%dT%H:%M:%S")
    if len(stats) == 0 or cur_date > stats[-1].date:
        vals = [Stat(value=int(val)) for val in cur_vals]
        stats.append(DayStat(*vals, cur_date))
        dump(stats)

    if len(stats) == 1:
        return

    cur_stat = stats[-1]
    if cur_date < cur_stat.date:
        return False

    prev_stat = stats[-2]
    out = []        
    for elem, prev_elem in zip(cur_stat, prev_stat):
        elem.delta = elem.value - prev_elem.value
        percent = (elem.delta - prev_elem.delta) / abs(prev_elem.delta) * 100
        out.extend([elem.delta, '+' if percent > 0 else '', percent])

    out.append(cur_stat.total.delta / cur_stat.tested.delta * 100)
    day_delta = cur_stat.date - prev_stat.date
    out.extend([day_delta.days, "" if day_delta.days == 1 else "s"])
    dump(stats)
    return out


if DB_PATH.exists():
    load()
