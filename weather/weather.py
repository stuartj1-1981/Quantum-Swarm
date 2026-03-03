"""
Weather data sources for the QSH digital twin.

Provides outdoor temperature and solar irradiance at any simulation timestamp.

Sources:
  - StaticWeather: Fixed values for testing
  - CsvWeather: Hourly CSV with linear interpolation to 30-second resolution

Interface: get(sim_time) -> (outdoor_temp, solar_irradiance)

CSV format: timestamp_unix,outdoor_temp_c,solar_irradiance_kw_m2
"""

from __future__ import annotations

import csv
import logging
from typing import List, Optional, Protocol, Tuple

logger = logging.getLogger(__name__)


class WeatherSource(Protocol):
    """Interface for weather data providers."""

    def get(self, sim_time: float) -> Tuple[float, float]:
        """Return (outdoor_temp_c, solar_irradiance_kw_m2) at sim_time."""
        ...


class StaticWeather:
    """Fixed weather for testing — constant outdoor temp and solar."""

    def __init__(self, outdoor_temp: float = 5.0, solar: float = 0.0):
        self._outdoor = outdoor_temp
        self._solar = solar

    def get(self, sim_time: float) -> Tuple[float, float]:
        return self._outdoor, self._solar


class CsvWeather:
    """Hourly weather from CSV with linear interpolation.

    CSV columns: timestamp_unix, outdoor_temp_c, solar_irradiance_kw_m2
    Rows must be sorted by timestamp. Interpolation is linear between
    adjacent rows. Outside the data range, nearest-neighbour extrapolation
    is used (first/last row values).
    """

    def __init__(self, filepath: str):
        self._times: List[float] = []
        self._temps: List[float] = []
        self._solars: List[float] = []

        with open(filepath, "r") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if header is None:
                raise ValueError(f"Weather CSV '{filepath}' is empty")

            for row_num, row in enumerate(reader, start=2):
                if len(row) < 3:
                    logger.warning(
                        "Weather CSV row %d: expected 3 columns, got %d — skipping",
                        row_num,
                        len(row),
                    )
                    continue
                try:
                    t = float(row[0])
                    temp = float(row[1])
                    solar = float(row[2])
                except ValueError:
                    logger.warning(
                        "Weather CSV row %d: non-numeric value — skipping",
                        row_num,
                    )
                    continue
                self._times.append(t)
                self._temps.append(temp)
                self._solars.append(solar)

        if not self._times:
            raise ValueError(f"Weather CSV '{filepath}' has no valid data rows")

        logger.info(
            "CsvWeather: loaded %d rows from '%s' (%.0f–%.0f)",
            len(self._times),
            filepath,
            self._times[0],
            self._times[-1],
        )

    def get(self, sim_time: float) -> Tuple[float, float]:
        """Linearly interpolate weather at sim_time."""
        times = self._times

        # Before first row — extrapolate with first value
        if sim_time <= times[0]:
            return self._temps[0], self._solars[0]

        # After last row — extrapolate with last value
        if sim_time >= times[-1]:
            return self._temps[-1], self._solars[-1]

        # Binary search for bracketing interval
        lo, hi = 0, len(times) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if times[mid] <= sim_time:
                lo = mid
            else:
                hi = mid

        # Linear interpolation
        span = times[hi] - times[lo]
        if span == 0:
            return self._temps[lo], self._solars[lo]

        frac = (sim_time - times[lo]) / span
        temp = self._temps[lo] + frac * (self._temps[hi] - self._temps[lo])
        solar = self._solars[lo] + frac * (self._solars[hi] - self._solars[lo])
        return temp, max(0.0, solar)


def create_weather(twin_cfg: dict) -> WeatherSource:
    """Factory: create weather source from twin config.

    Config keys checked:
      twin.weather.csv_path  → CsvWeather
      twin.weather.static    → StaticWeather with given values
      (fallback)             → StaticWeather(5.0, 0.0)
    """
    weather_cfg = twin_cfg.get("weather", {})

    csv_path = weather_cfg.get("csv_path")
    if csv_path:
        return CsvWeather(csv_path)

    static_cfg = weather_cfg.get("static", {})
    if static_cfg:
        return StaticWeather(
            outdoor_temp=static_cfg.get("outdoor_temp", 5.0),
            solar=static_cfg.get("solar_irradiance", 0.0),
        )

    # Fallback: use start conditions or defaults
    start = twin_cfg.get("simulation", {}).get("start_conditions", {})
    return StaticWeather(
        outdoor_temp=start.get("outdoor_temp", 5.0),
        solar=0.0,
    )
