from datetime import datetime, timedelta
from math import exp

class ActivityMonitor:
    period = 420.0

    def __init__(self, base_level=0, last_timestamp=None):
        self.activity_level = base_level
        self.last_timestamp = last_timestamp or datetime.utcnow()

    def on_message(self, timestamp=None):
        if not timestamp:
            timestamp = datetime.utcnow()

        self.activity_level = self.activity(timestamp) + 1
        self.last_timestamp = timestamp

    def activity(self, timestamp=None):
        if not timestamp:
            timestamp = datetime.utcnow()

        assert timestamp >= self.last_timestamp

        elapsed_time = (timestamp - self.last_timestamp).total_seconds()
        level = self.activity_level
        decay = exp(-elapsed_time / self.period)
        level *= decay

        return level

    def frequency(self, timestamp=None):
        if not timestamp:
            timestamp = datetime.utcnow()

        return self.activity(timestamp) / self.period
