"""Radar-style polar sky view centered on the observer.

Azimuth 0° is North (top), 90° is East (right).
The radial axis is elevation, with the zenith at the center and horizon
at the outer ring. Aircraft below the horizon are drawn dimmed on an
outer 'below-horizon' band so the operator still sees them.

Aircraft dots are color-coded by altitude (band → color) and
pulse briefly when their track updates, giving the plot a live feel.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any, Optional

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QPainter, QPen, QRadialGradient
)
from PyQt6.QtWidgets import QWidget


# --- altitude → color ramp (feet) -----------------------------------------
# Ergonomic 5-stop ramp: ground=amber, low=green, mid=cyan, high=blue,
# very high=magenta. Keeps color hue stable while the operator scans.
_ALT_BANDS = [
    (0,      QColor("#f5b642")),   # <2 kft — ground/pattern
    (2000,   QColor("#4caf50")),
    (10000,  QColor("#00bcd4")),
    (25000,  QColor("#2196f3")),
    (40000,  QColor("#e040fb")),
]


def _color_for_altitude(alt_ft: float) -> QColor:
    for i in range(len(_ALT_BANDS) - 1, -1, -1):
        if alt_ft >= _ALT_BANDS[i][0]:
            return _ALT_BANDS[i][1]
    return _ALT_BANDS[0][1]


@dataclass
class _Track:
    hex_id: str
    callsign: str
    az: float
    el: float
    alt: float
    dist_nm: float
    last_seen_ms: float


class PolarSkyView(QWidget):
    aircraftPicked = pyqtSignal(str)   # hex_id when a dot is clicked

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(360, 360)
        self.setMouseTracking(True)
        self.setAutoFillBackground(True)
        self._tracks: dict[str, _Track] = {}
        self._hover_hex: Optional[str] = None
        self._selected_hex: Optional[str] = None

        # 30 fps repaint for smooth pulse animations even when data updates
        # arrive only every 5 s. Lightweight — paint cost is O(N) tracks.
        self._anim = QTimer(self)
        self._anim.setInterval(33)
        self._anim.timeout.connect(self.update)
        self._anim.start()

    # ------------------------------------------------------------------ API
    def set_flights(self, flights: list[dict[str, Any]]) -> None:
        now = time.monotonic() * 1000.0
        seen: set[str] = set()
        for f in flights:
            hid = str(f.get("hex_id") or f.get("callsign") or "")
            if not hid:
                continue
            seen.add(hid)
            self._tracks[hid] = _Track(
                hex_id=hid,
                callsign=str(f.get("callsign") or hid),
                az=float(f.get("azimuth") or 0.0),
                el=float(f.get("elevation") or 0.0),
                alt=float(f.get("altitude") or 0.0),
                dist_nm=float(f.get("distance_from_obs") or 0.0),
                last_seen_ms=now,
            )
        # Drop tracks that haven't been reported for >120 s (loosely tracks
        # the backend's own MAX_AIRCRAFT_AGE_SECONDS).
        stale = [h for h, t in self._tracks.items() if (now - t.last_seen_ms) > 120_000]
        for h in stale:
            self._tracks.pop(h, None)

    def selected(self) -> Optional[str]:
        return self._selected_hex

    # ------------------------------------------------------------------ math
    def _sky_geom(self) -> tuple[QPointF, float, float]:
        """Return (center, radius_horizon, radius_outer) in widget coords."""
        w, h = self.width(), self.height()
        side = min(w, h) - 20
        cx, cy = w / 2, h / 2
        r_horizon = side / 2 * 0.85          # inner ring = horizon (el=0)
        r_outer = side / 2                    # outer band = below-horizon aircraft
        return QPointF(cx, cy), r_horizon, r_outer

    def _project(self, az_deg: float, el_deg: float) -> QPointF:
        center, r_horizon, r_outer = self._sky_geom()
        # Elevation 90 → r=0 (zenith), elevation 0 → r=r_horizon,
        # elevation <0 mapped linearly onto the [horizon, outer] band.
        if el_deg >= 0:
            r = r_horizon * (1.0 - min(el_deg, 90.0) / 90.0)
        else:
            r = r_horizon + (r_outer - r_horizon) * min(abs(el_deg) / 30.0, 1.0)
        theta = math.radians(az_deg - 90.0)   # rotate so 0°=up
        return QPointF(center.x() + r * math.cos(theta),
                       center.y() + r * math.sin(theta))

    # ------------------------------------------------------------------ paint
    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Background — subtle dark radial to give depth.
        center, r_horizon, r_outer = self._sky_geom()
        grad = QRadialGradient(center, r_outer)
        grad.setColorAt(0.0, QColor("#0f1a24"))
        grad.setColorAt(1.0, QColor("#050a10"))
        p.fillRect(self.rect(), grad)

        # Below-horizon band.
        p.setBrush(QColor(20, 24, 30, 180))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(center, r_outer, r_outer)

        # Sky disk.
        sky = QColor(18, 30, 44)
        p.setBrush(sky)
        p.drawEllipse(center, r_horizon, r_horizon)

        # Elevation rings at 30°/60° and horizon.
        p.setBrush(Qt.BrushStyle.NoBrush)
        grid_pen = QPen(QColor(255, 255, 255, 45))
        grid_pen.setWidthF(1.0)
        p.setPen(grid_pen)
        for el in (0, 30, 60):
            r = r_horizon * (1.0 - el / 90.0)
            p.drawEllipse(center, r, r)
        # Zenith dot.
        p.setBrush(QColor(255, 255, 255, 90))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(center, 2.0, 2.0)

        # Cardinals + inter-cardinals.
        p.setPen(QPen(QColor(255, 255, 255, 60)))
        for az in range(0, 360, 30):
            p.drawLine(center, self._project(az, 0))
        p.setPen(QPen(QColor(255, 255, 255, 200)))
        font = QFont()
        font.setBold(True)
        p.setFont(font)
        for az, label in ((0, "N"), (90, "E"), (180, "S"), (270, "W")):
            pt = self._project(az, -5)   # just outside horizon
            p.drawText(QRectF(pt.x() - 12, pt.y() - 10, 24, 20),
                       Qt.AlignmentFlag.AlignCenter, label)

        # Aircraft dots.
        now = time.monotonic() * 1000.0
        for hid, t in self._tracks.items():
            pt = self._project(t.az, t.el)
            color = _color_for_altitude(t.alt)
            # Freshness pulse: brighter halo shortly after an update.
            age_ms = now - t.last_seen_ms
            halo = max(0.0, 1.0 - age_ms / 3000.0)   # 3-second decay
            if halo > 0:
                p.setPen(Qt.PenStyle.NoPen)
                halo_color = QColor(color)
                halo_color.setAlphaF(0.30 * halo)
                p.setBrush(halo_color)
                p.drawEllipse(pt, 10.0 + 6.0 * halo, 10.0 + 6.0 * halo)

            # Dim below-horizon tracks — they can't be seen anyway.
            body_color = QColor(color)
            if t.el < 0:
                body_color.setAlphaF(0.55)

            p.setBrush(body_color)
            p.setPen(QPen(QColor(255, 255, 255, 200), 1.2))
            radius = 6.5 if hid == self._selected_hex else 5.0
            p.drawEllipse(pt, radius, radius)

            # Callsign — small, above the dot; skipped for below-horizon
            # unless selected/hovered to reduce clutter.
            if t.el >= 0 or hid in (self._hover_hex, self._selected_hex):
                p.setPen(QColor(255, 255, 255, 220))
                p.drawText(QRectF(pt.x() + 8, pt.y() - 8, 90, 14),
                           Qt.AlignmentFlag.AlignLeft, t.callsign)

        # Legend.
        self._draw_legend(p)

    def _draw_legend(self, p: QPainter) -> None:
        pad = 8
        w = 130
        h = 6 + len(_ALT_BANDS) * 14 + 8
        rect = QRectF(pad, self.height() - h - pad, w, h)
        p.setBrush(QColor(0, 0, 0, 140))
        p.setPen(QPen(QColor(255, 255, 255, 60)))
        p.drawRoundedRect(rect, 5, 5)
        p.setPen(QColor(200, 210, 220))
        font = QFont()
        font.setPointSize(8)
        p.setFont(font)
        y = rect.top() + 12
        for lo, color in _ALT_BANDS:
            p.setBrush(color)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(rect.left() + 12, y - 3), 4, 4)
            p.setPen(QColor(210, 220, 230))
            if lo == 0:
                label = "< 2 kft"
            else:
                label = f"≥ {lo // 1000} kft"
            p.drawText(QRectF(rect.left() + 22, y - 9, w - 24, 14),
                       Qt.AlignmentFlag.AlignLeft, label)
            y += 14

    # ------------------------------------------------------------------ hit
    def _nearest(self, pos: QPointF, threshold: float = 12.0) -> Optional[str]:
        best_hid: Optional[str] = None
        best_d = threshold
        for hid, t in self._tracks.items():
            pt = self._project(t.az, t.el)
            d = math.hypot(pt.x() - pos.x(), pt.y() - pos.y())
            if d < best_d:
                best_d = d
                best_hid = hid
        return best_hid

    def mouseMoveEvent(self, ev) -> None:
        self._hover_hex = self._nearest(ev.position())

    def mousePressEvent(self, ev) -> None:
        hid = self._nearest(ev.position())
        if hid:
            self._selected_hex = hid
            self.aircraftPicked.emit(hid)

    def select(self, hex_id: Optional[str]) -> None:
        self._selected_hex = hex_id
