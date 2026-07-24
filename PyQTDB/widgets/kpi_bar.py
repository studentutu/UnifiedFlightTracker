"""Top KPI strip: connection status, counts, closest/highest aircraft."""
from __future__ import annotations

from typing import Any, Optional

from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget


class _StatusLED(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(14, 14)
        self._state = "unknown"    # "ok" | "warn" | "err" | "unknown"
        self._pulse = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(60)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def set_state(self, state: str) -> None:
        self._state = state
        self._pulse = 1.0

    def _tick(self) -> None:
        if self._pulse > 0:
            self._pulse = max(0.0, self._pulse - 0.05)
            self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = {
            "ok":   QColor("#5cd865"),
            "warn": QColor("#f5b642"),
            "err":  QColor("#e57373"),
            "unknown": QColor("#7c8792"),
        }[self._state]
        # halo
        if self._pulse > 0:
            halo = QColor(color)
            halo.setAlphaF(0.35 * self._pulse)
            p.setBrush(halo)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(self.rect().center(), 7 + int(4 * self._pulse),
                          7 + int(4 * self._pulse))
        p.setBrush(color)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(self.rect().center(), 5, 5)


class KpiTile(QFrame):
    def __init__(self, title: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(
            "QFrame { background:#152030; border:1px solid #23324a; border-radius:6px; }"
        )
        title_lbl = QLabel(title.upper(), self)
        title_lbl.setStyleSheet("color:#7c8ea3; font-size:9pt; letter-spacing:1px;")
        self._value_lbl = QLabel("—", self)
        f = QFont()
        f.setPointSize(16)
        f.setBold(True)
        self._value_lbl.setFont(f)
        self._value_lbl.setStyleSheet("color:#e8f0f8;")
        self._sub_lbl = QLabel("", self)
        self._sub_lbl.setStyleSheet("color:#9fb0c2; font-size:8pt;")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 8)
        lay.setSpacing(0)
        lay.addWidget(title_lbl)
        lay.addWidget(self._value_lbl)
        lay.addWidget(self._sub_lbl)

    def set_value(self, value: str, sub: str = "") -> None:
        self._value_lbl.setText(value)
        self._sub_lbl.setText(sub)


class KpiBar(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._led = _StatusLED(self)
        self._status_text = QLabel("waiting for backend…", self)
        self._status_text.setStyleSheet("color:#c7d2df;")

        self._tile_count   = KpiTile("Aircraft in range")
        self._tile_closest = KpiTile("Closest")
        self._tile_highest = KpiTile("Highest")
        self._tile_latency = KpiTile("Backend latency")

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(6)
        top.addWidget(self._led)
        top.addWidget(self._status_text, 1)

        tiles = QHBoxLayout()
        tiles.setContentsMargins(0, 0, 0, 0)
        tiles.setSpacing(8)
        for tile in (self._tile_count, self._tile_closest,
                     self._tile_highest, self._tile_latency):
            tiles.addWidget(tile)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 4)
        lay.setSpacing(6)
        lay.addLayout(top)
        lay.addLayout(tiles)

    # ------------------------------------------------------------------ API
    def set_ok(self, elapsed_ms: float, messages: list[str]) -> None:
        if messages:
            self._led.set_state("warn")
            self._status_text.setText("connected — " + "; ".join(messages))
        else:
            self._led.set_state("ok")
            self._status_text.setText(f"connected — updated in {elapsed_ms:.0f} ms")
        self._tile_latency.set_value(f"{elapsed_ms:.0f} ms", "round-trip to backend")

    def set_error(self, msg: str) -> None:
        self._led.set_state("err")
        self._status_text.setText(f"backend error — {msg}")

    def set_flights(self, flights: list[dict[str, Any]]) -> None:
        self._tile_count.set_value(str(len(flights)), "current poll")
        if not flights:
            self._tile_closest.set_value("—")
            self._tile_highest.set_value("—")
            return
        closest = min(flights, key=lambda f: _num(f.get("distance_from_obs"), 1e9))
        highest = max(flights, key=lambda f: _num(f.get("altitude"), -1))
        self._tile_closest.set_value(
            f"{_num(closest.get('distance_from_obs'), 0):.1f} nm",
            f"{closest.get('callsign', '?')}"
            f" · el {_num(closest.get('elevation'), 0):.0f}°"
        )
        self._tile_highest.set_value(
            f"{int(_num(highest.get('altitude'), 0)):,} ft",
            f"{highest.get('callsign', '?')}"
            f" · {int(_num(highest.get('speed'), 0)):,} kt"
        )


def _num(x: Any, default: float) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default
