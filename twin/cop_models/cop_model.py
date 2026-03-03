"""
COP model for the QSH digital twin.

Provides heat pump COP (Coefficient of Performance) as a function of
outdoor temperature and flow temperature, using bilinear interpolation
over a manufacturer/measured data grid.

YAML format (canonical — from twin profile schema):
    cop_map:
      - { outdoor: -5, flow: 55, cop: 2.0 }
      - { outdoor: -5, flow: 45, cop: 2.5 }
      - { outdoor:  0, flow: 35, cop: 3.6 }
      ...

Falls back to nearest-neighbour extrapolation outside the grid.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class CopMap:
    """Bilinear interpolation COP lookup from a grid of data points.

    Each data point is (outdoor_temp, flow_temp) -> COP.
    The grid need not be regular — the implementation finds the four
    nearest bracketing points and interpolates bilinearly.

    Outside the data range, nearest-neighbour extrapolation is used.
    """

    def __init__(self, points: List[Dict]):
        """
        Args:
            points: List of dicts with keys 'outdoor', 'flow', 'cop'.

        Raises:
            ValueError: If fewer than 1 point is provided or points are invalid.
        """
        if not points:
            raise ValueError("CopMap: need at least 1 data point")

        self._outdoor_vals: List[float] = sorted(set(p["outdoor"] for p in points))
        self._flow_vals: List[float] = sorted(set(p["flow"] for p in points))

        # Build lookup: (outdoor, flow) -> cop
        self._grid: Dict[Tuple[float, float], float] = {}
        for p in points:
            key = (p["outdoor"], p["flow"])
            self._grid[key] = p["cop"]

        logger.info(
            "CopMap: %d points, outdoor=[%.0f..%.0f], flow=[%.0f..%.0f]",
            len(points),
            self._outdoor_vals[0],
            self._outdoor_vals[-1],
            self._flow_vals[0],
            self._flow_vals[-1],
        )

    def get_cop(self, outdoor_temp: float, flow_temp: float) -> float:
        """Return interpolated COP for given conditions.

        Uses bilinear interpolation within the grid, nearest-neighbour
        extrapolation outside.
        """
        # Clamp to grid bounds for extrapolation
        o_clamped = max(self._outdoor_vals[0], min(self._outdoor_vals[-1], outdoor_temp))
        f_clamped = max(self._flow_vals[0], min(self._flow_vals[-1], flow_temp))

        # Find bracketing outdoor values
        o_lo, o_hi = self._bracket(self._outdoor_vals, o_clamped)
        f_lo, f_hi = self._bracket(self._flow_vals, f_clamped)

        # Get COP at four corners (with fallback for sparse grids)
        c00 = self._lookup(o_lo, f_lo)
        c01 = self._lookup(o_lo, f_hi)
        c10 = self._lookup(o_hi, f_lo)
        c11 = self._lookup(o_hi, f_hi)

        # Bilinear interpolation
        o_span = o_hi - o_lo
        f_span = f_hi - f_lo

        if o_span == 0 and f_span == 0:
            return c00

        if o_span == 0:
            # Interpolate along flow only
            t = (f_clamped - f_lo) / f_span
            return c00 + t * (c01 - c00)

        if f_span == 0:
            # Interpolate along outdoor only
            s = (o_clamped - o_lo) / o_span
            return c00 + s * (c10 - c00)

        s = (o_clamped - o_lo) / o_span
        t = (f_clamped - f_lo) / f_span
        return c00 * (1 - s) * (1 - t) + c10 * s * (1 - t) + c01 * (1 - s) * t + c11 * s * t

    def _lookup(self, outdoor: float, flow: float) -> float:
        """Look up COP at exact grid point, with nearest-neighbour fallback."""
        key = (outdoor, flow)
        if key in self._grid:
            return self._grid[key]

        # Find nearest point in grid
        best_key = min(
            self._grid.keys(),
            key=lambda k: (k[0] - outdoor) ** 2 + (k[1] - flow) ** 2,
        )
        return self._grid[best_key]

    @staticmethod
    def _bracket(vals: List[float], x: float) -> Tuple[float, float]:
        """Find the two values in sorted list that bracket x."""
        if len(vals) == 1:
            return vals[0], vals[0]

        for i in range(len(vals) - 1):
            if vals[i] <= x <= vals[i + 1]:
                return vals[i], vals[i + 1]

        # Shouldn't reach here if x is clamped, but handle gracefully
        if x <= vals[0]:
            return vals[0], vals[0]
        return vals[-1], vals[-1]


def create_cop_model(twin_cfg: dict):
    """Factory: create COP model from twin config.

    Returns a callable (outdoor_temp, flow_temp) -> cop.
    If no cop_map in config, returns None (caller uses default).
    """
    cop_map_data = twin_cfg.get("heat_pump", {}).get("cop_map")
    if not cop_map_data:
        return None

    cop_map = CopMap(cop_map_data)
    return cop_map.get_cop
