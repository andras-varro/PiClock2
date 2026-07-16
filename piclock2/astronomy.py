"""
Sunrise/sunset and moon-phase math, ported from n0bel/PiClock's PyQtPiClock.py.

Original (Python 2) implementation: PyQtPiClock.py:37-152.
"""

import datetime
import math


class suntimes:
    def __init__(self, lat, lng):
        self.lat = lat
        self.long = lng

    def sunrise(self, when):
        self.__preptime(when)
        self.__calc()
        return suntimes.__timefromdecimalday(self.sunrise_t)

    def sunset(self, when):
        self.__preptime(when)
        self.__calc()
        return suntimes.__timefromdecimalday(self.sunset_t)

    @staticmethod
    def __timefromdecimalday(day):
        if day < 0.0:
            xdt = datetime.datetime.now()
            return datetime.time(hour=xdt.hour, minute=xdt.minute, second=xdt.second)
        hours = 24.0 * day
        h = int(hours)
        minutes = (hours - h) * 60
        m = int(minutes)
        seconds = (minutes - m) * 60
        s = int(seconds)
        return datetime.time(hour=h, minute=m, second=s)

    def __preptime(self, when):
        self.day = when.toordinal() - (734124 - 40529)
        t = when.time()
        self.time = (t.hour + t.minute / 60.0 + t.second / 3600.0) / 24.0
        self.timezone = 0
        offset = when.utcoffset()
        if offset is not None:
            self.timezone = offset.total_seconds() / 3600.0

    def __calc(self):
        timezone = self.timezone
        longitude = self.long
        latitude = self.lat
        time = self.time
        day = self.day

        Jday = day + 2415018.5 + time - timezone / 24
        Jcent = (Jday - 2451545) / 36525

        Manom = 357.52911 + Jcent * (35999.05029 - 0.0001537 * Jcent)
        Mlong = 280.46646 + Jcent * (36000.76983 + Jcent * 0.0003032) % 360
        Eccent = 0.016708634 - Jcent * (0.000042037 + 0.0001537 * Jcent)
        Mobliq = (23 + (26 + ((21.448 - Jcent * (46.815 + Jcent *
                  (0.00059 - Jcent * 0.001813)))) / 60) / 60)
        obliq = (Mobliq + 0.00256 *
                 math.cos(math.radians(125.04 - 1934.136 * Jcent)))
        vary = (math.tan(math.radians(obliq / 2)) *
                math.tan(math.radians(obliq / 2)))
        Seqcent = (math.sin(math.radians(Manom)) *
                   (1.914602 - Jcent * (0.004817 + 0.000014 * Jcent)) +
                   math.sin(math.radians(2 * Manom))
                   * (0.019993 - 0.000101 * Jcent) +
                   math.sin(math.radians(3 * Manom)) * 0.000289)
        Struelong = Mlong + Seqcent
        Sapplong = (Struelong - 0.00569 - 0.00478 *
                    math.sin(math.radians(125.04 - 1934.136 * Jcent)))
        declination = (math.degrees(math.asin(math.sin(math.radians(obliq)) *
                       math.sin(math.radians(Sapplong)))))

        eqtime = (4 * math.degrees(vary * math.sin(2 * math.radians(Mlong)) -
                  2 * Eccent * math.sin(math.radians(Manom)) + 4 * Eccent *
                  vary * math.sin(math.radians(Manom)) *
                  math.cos(2 * math.radians(Mlong)) - 0.5 * vary * vary *
                  math.sin(4 * math.radians(Mlong)) - 1.25 * Eccent * Eccent *
                  math.sin(2 * math.radians(Manom))))

        hourangle0 = (math.cos(math.radians(90.833)) /
                      (math.cos(math.radians(latitude)) *
                      math.cos(math.radians(declination))) -
                      math.tan(math.radians(latitude)) *
                      math.tan(math.radians(declination)))

        self.solarnoon_t = (720 - 4 * longitude - eqtime + timezone * 60) / 1440
        if hourangle0 > 1.0:
            self.sunrise_t = 0.0
            self.sunset_t = 1.0 - 1.0 / 86400.0
            return
        if hourangle0 < -1.0:
            self.sunrise_t = 0.0
            self.sunset_t = 0.0
            return

        hourangle = math.degrees(math.acos(hourangle0))
        self.sunrise_t = self.solarnoon_t - hourangle * 4 / 1440
        self.sunset_t = self.solarnoon_t + hourangle * 4 / 1440


def moon_phase(dt=None):
    """Returns 0.0..1.0 representing the lunar cycle position."""
    if dt is None:
        dt = datetime.datetime.now()
    diff = dt - datetime.datetime(2001, 1, 1)
    days = float(diff.days) + (float(diff.seconds) / 86400.0)
    lunations = 0.20439731 + days * 0.03386319269
    return lunations % 1.0


_MOON_NAMES = [
    "New Moon",
    "Waxing Crescent",
    "First Quarter",
    "Waxing Gibbous",
    "Full Moon",
    "Waning Gibbous",
    "Third Quarter",
    "Waning Crescent",
]


def moon_phase_name(phase_value):
    """Map a 0..1 moon-phase value to one of 8 named phases."""
    # 8 bins of width 0.125
    idx = int((phase_value + 0.0625) * 8) % 8
    return _MOON_NAMES[idx]
