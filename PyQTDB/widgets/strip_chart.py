"""Scrolling strip chart of altitude vs. time for a chosen aircraft.

Also plots a light-grey background trace of the currently-tracked fleet's
altitude envelope (min/max), which gives useful context even if no
aircraft is selected.
"""
from __future__ import annotations

import time
from collections import deque
from typing import Any, Deque, Optional

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import QWidget


HISTORY_S = 300.0   # 5-minute window
MAX_SAMPLES = 600


class AltitudeStripChart(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(140)
        self.setAutoFillBackground(True)
        # per-aircraft samples: hex_id -> deque[(t_epoch, alt_ft)]
        self._series: dict[str, Deque[tuple[float, float]]] = {}
        self._envelope: Deque[tuple[float, float, float]] = deque(maxlen=MAX_SAMPLES)
        self._selected: Optional[str] = None
        self._label = "no aircraft selected"

        # A repaint timer so the sliding window scrolls smoothly between polls.
        self._anim = QTimer(self)
        self._anim.setInterval(200)
        self._anim.timeout.connect(self.update)
        self._anim.start()

    # ------------------------------------------------------------------ API
    def update_from_snapshot(self, flights: list[dict[str, Any]]) -> None:
        now = time.time()
        alts: list[float] = []
        seen_ids: set[str] = set()
        for f in flights:
            hid = str(f.get("hex_id") or "")
            if not hid:
                continue
            seen_ids.add(hid)
            try:
                alt = float(f.get("altitude") or 0.0)
            except (TypeError, ValueError):
                continue
            alts.append(alt)
            q = self._series.setdefault(hid, deque(maxlen=MAX_SAMPLES))
            q.append((now, alt))

        if alts:
            self._envelope.append((now, min(alts), max(alts)))

        # Trim old samples out of the window and drop series with none left.
        cutoff = now - HISTORY_S
        for hid in list(self._series.keys()):
            q = self._series[hid]
            while q and q[0][0] < cutoff:
                q.popleft()
            if not q:
                del self._series[hid]
        while self._envelope and self._envelope[0][0] < cutoff:
            self._envelope.popleft()

    def set_selected(self, hex_id: Optional[str], label: str = "") -> None:
        self._selected = hex_id or None
        self._label = label or (hex_id or "no aircraft selected")

    # ------------------------------------------------------------------ paint
    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()

        # Panel background.
        p.fillRect(self.rect(), QColor("#0d1620"))

        # Plot area.
        margin_l, margin_r, margin_t, margin_b = 46, 12, 20, 22
        plot = QRectF(margin_l, margin_t, w - margin_l - margin_r, h - margin_t - margin_b)

        # Determine y-axis scale from either the selected series or the envelope.
        now = time.time()
        y_min, y_max = self._y_range()

        # Axes.
        p.setPen(QPen(QColor(255, 255, 255, 60)))
        p.drawRect(plot)

        # y grid + labels.
        font = QFont()
        font.setPointSize(8)
        p.setFont(font)
        p.setPen(QColor(150, 165, 180))
        for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
            y = plot.bottom() - frac * plot.height()
            val = y_min + frac * (y_max - y_min)
            p.setPen(QPen(QColor(255, 255, 255, 20)))
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            p.setPen(QColor(150, 165, 180))
            p.drawText(QRectF(0, y - 8, margin_l - 4, 16),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       f"{int(val):>5d}")
        # x-axis time markers (right edge = now).
        for secs_back in (0, 60, 120, 180, 240, 300):
            frac = 1.0 - secs_back / HISTORY_S
            x = plot.left() + frac * plot.width()
            p.setPen(QPen(QColor(255, 255, 255, 20)))
            p.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))
            p.setPen(QColor(150, 165, 180))
            label = "now" if secs_back == 0 else f"-{secs_back}s"
            p.drawText(QRectF(x - 22, plot.bottom() + 2, 44, 14),
                       Qt.AlignmentFlag.AlignCenter, label)

        def to_pt(t: float, y: float) -> QPointF:
            x = plot.left() + plot.width() * (1.0 - (now - t) / HISTORY_S)
            yy = plot.bottom() - (y - y_min) / max(1.0, y_max - y_min) * plot.height()
            return QPointF(x, yy)

        # Envelope (light band).
        if len(self._envelope) >= 2:
            top_poly = QPolygonF([to_pt(t, hi) for t, _, hi in self._envelope])
            bot_poly = QPolygonF([to_pt(t, lo) for t, lo, _ in reversed(self._envelope)])
            band = QPolygonF(list(top_poly) + list(bot_poly))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(90, 130, 170, 45))
            p.drawPolygon(band)
            p.setPen(QPen(QColor(90, 130, 170, 110), 1.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPolyline(QPolygonF([to_pt(t, hi) for t, _, hi in self._envelope]))
            p.drawPolyline(QPolygonF([to_pt(t, lo) for t, lo, _ in self._envelope]))

        # Selected aircraft trace.
        if self._selected and self._selected in self._series:
            q = self._series[self._selected]
            if len(q) >= 2:
                trace_pen = QPen(QColor("#00e5ff"), 2.0)
                p.setPen(trace_pen)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPolyline(QPolygonF([to_pt(t, a) for t, a in q]))
                # Highlight the most-recent sample.
                t_last, a_last = q[-1]
                pt = to_pt(t_last, a_last)
                p.setBrush(QColor("#00e5ff"))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(pt, 3.5, 3.5)

        # Title.
        title_font = QFont()
        title_font.setBold(True)
        p.setFont(title_font)
        p.setPen(QColor(220, 230, 240))
        p.drawText(QRectF(margin_l, 0, plot.width(), margin_t),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   f"Altitude (ft) — {self._label}")

    # ------------------------------------------------------------------ helpers
    def _y_range(self) -> tuple[float, float]:
        vals: list[float] = []
        if self._selected and self._selected in self._series:
            vals.extend(a for _, a in self._series[self._selected])
        vals.extend(hi for _, _, hi in self._envelope)
        vals.extend(lo for _, lo, _ in self._envelope)
        if not vals:
            return 0.0, 45000.0
        lo, hi = min(vals), max(vals)
        if hi - lo < 2000:
            mid = (hi + lo) / 2
            lo, hi = mid - 1000, mid + 1000
        # Round out to nice numbers.
        lo = max(0.0, (lo // 5000) * 5000.0)
        hi = ((hi // 5000) + 1) * 5000.0
        return lo, hi
