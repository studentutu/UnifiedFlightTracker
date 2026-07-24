"""Entrypoint for the PyQt6 flight-tracker dashboard.

Layout (16:9 ergonomic default):

  +-----------------------------------------------------------+
  |  KPI bar: LED · status · [count][closest][highest][lat.]  |
  +-----------------------------+-----------------------------+
  |                             |                             |
  |   Polar sky view (left)     |   Flight table (right)      |
  |   ~55% width                |   ~45% width, filterable    |
  |                             |                             |
  +-----------------------------+-----------------------------+
  |  Altitude strip chart (spans full width, ~140 px tall)    |
  +-----------------------------------------------------------+

The panels are docked so the user can rearrange or float them.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QIcon, QPalette, QColor
from PyQt6.QtWidgets import (
    QApplication, QDockWidget, QMainWindow, QMessageBox, QSplitter, QWidget,
    QVBoxLayout
)

from tracker_client import ObserverConfig, TrackerClient
from widgets.flight_table import FlightTable
from widgets.kpi_bar import KpiBar
from widgets.polar_sky import PolarSkyView
from widgets.strip_chart import AltitudeStripChart


def apply_dark_palette(app: QApplication) -> None:
    """A muted, low-contrast dark palette suitable for long-duration monitoring."""
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor("#0b1420"))
    pal.setColor(QPalette.ColorRole.WindowText, QColor("#e0e8f0"))
    pal.setColor(QPalette.ColorRole.Base, QColor("#0f1a26"))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#14212f"))
    pal.setColor(QPalette.ColorRole.Text, QColor("#e0e8f0"))
    pal.setColor(QPalette.ColorRole.Button, QColor("#182535"))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor("#e0e8f0"))
    pal.setColor(QPalette.ColorRole.Highlight, QColor("#2f6ea0"))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor("#1a2635"))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor("#e0e8f0"))
    app.setPalette(pal)
    app.setStyleSheet(
        """
        QMainWindow, QDockWidget { background:#0b1420; }
        QDockWidget::title {
            background:#132030; padding:4px 8px; color:#c7d2df;
            border-bottom:1px solid #23324a;
        }
        QHeaderView::section {
            background:#14212f; color:#c7d2df;
            padding:4px 6px; border:0; border-right:1px solid #23324a;
        }
        QTableView {
            background:#0f1a26; alternate-background-color:#132030;
            selection-background-color:#2f6ea0; gridline-color:#1c2a3b;
        }
        QLineEdit {
            background:#0f1a26; color:#e0e8f0;
            border:1px solid #23324a; border-radius:4px; padding:4px 6px;
        }
        QToolBar { background:#0b1420; border:0; }
        QStatusBar { background:#0b1420; color:#9fb0c2; }
        """
    )


class MainWindow(QMainWindow):
    def __init__(self, base_url: str, observer: ObserverConfig, interval_s: float):
        super().__init__()
        self.setWindowTitle("Unified Flight Tracker — Dashboard")
        self.resize(1400, 850)

        # --- widgets ---------------------------------------------------
        self.kpi = KpiBar(self)
        self.sky = PolarSkyView(self)
        self.table = FlightTable(self)
        self.strip = AltitudeStripChart(self)

        # Central: KPI on top, then splitter with sky | table.
        split = QSplitter(Qt.Orientation.Horizontal, self)
        split.addWidget(self.sky)
        split.addWidget(self.table)
        split.setStretchFactor(0, 55)
        split.setStretchFactor(1, 45)
        split.setChildrenCollapsible(False)

        central = QWidget(self)
        cl = QVBoxLayout(central)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(4)
        cl.addWidget(self.kpi)
        cl.addWidget(split, 1)
        self.setCentralWidget(central)

        # Strip chart lives in a bottom dock so users can hide/float it.
        dock = QDockWidget("Altitude history (5 min)", self)
        dock.setWidget(self.strip)
        dock.setAllowedAreas(
            Qt.DockWidgetArea.BottomDockWidgetArea | Qt.DockWidgetArea.TopDockWidgetArea
        )
        dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        self._strip_dock = dock

        # Menu.
        self._build_menu()

        self.statusBar().showMessage(
            f"observer ({observer.lat:.4f}, {observer.lon:.4f})  r={observer.radius_nm} NM"
            f"  · polling {base_url}/api/flights every {interval_s:g} s"
        )

        # --- wiring ---------------------------------------------------
        self.sky.aircraftPicked.connect(self.on_sky_pick)
        self.table.selectionChanged.connect(self.on_table_pick)

        self.client = TrackerClient(base_url, observer, interval_s, parent=self)
        self.client.flightsReceived.connect(self.on_flights)
        self.client.error.connect(self.on_error)
        self.client.start()

    def _build_menu(self) -> None:
        m = self.menuBar().addMenu("&View")
        act = self._strip_dock_toggle = QAction("Show altitude history", self, checkable=True)
        act.setChecked(True)
        act.toggled.connect(lambda on: self._strip_dock.setVisible(on))
        m.addAction(act)
        m.addSeparator()
        quit_act = QAction("&Quit", self)
        quit_act.setShortcut("Ctrl+Q")
        quit_act.triggered.connect(self.close)
        m.addAction(quit_act)

    # --- slots ---------------------------------------------------------
    def on_flights(self, flights, messages, elapsed_s):
        self.kpi.set_ok(elapsed_s * 1000.0, messages)
        self.kpi.set_flights(flights)
        self.sky.set_flights(flights)
        self.table.set_flights(flights)
        self.strip.update_from_snapshot(flights)

    def on_error(self, msg):
        self.kpi.set_error(msg)

    def on_sky_pick(self, hex_id: str) -> None:
        self.table.select_hex(hex_id)
        self.strip.set_selected(hex_id, self._label_for(hex_id))

    def on_table_pick(self, hex_id: str) -> None:
        self.sky.select(hex_id or None)
        self.strip.set_selected(hex_id or None, self._label_for(hex_id))

    def _label_for(self, hex_id: str) -> str:
        row = self.table.model.row_for_hex(hex_id)
        if row < 0:
            return hex_id
        d = self.table.model._rows[row]   # noqa: SLF001 — internal helper
        return f"{d.get('callsign', hex_id)} · {d.get('type', '?')} · hex {d.get('hex_id')}"

    def closeEvent(self, event) -> None:
        try:
            self.client.stop()
        finally:
            super().closeEvent(event)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Unified Flight Tracker dashboard (PyQt6)")
    p.add_argument("--url", default=os.environ.get("TRACKER_URL", "http://localhost:5001"),
                   help="base URL of the tracker backend (default: %(default)s)")
    p.add_argument("--lat", type=float, default=float(os.environ.get("TRACKER_LAT", "39.5478")))
    p.add_argument("--lon", type=float, default=float(os.environ.get("TRACKER_LON", "-76.1347")))
    p.add_argument("--radius", type=float, default=float(os.environ.get("TRACKER_RADIUS", "150")),
                   help="search radius in nautical miles (default: %(default)s)")
    p.add_argument("--interval", type=float, default=float(os.environ.get("TRACKER_INTERVAL", "5")),
                   help="poll interval in seconds (default: %(default)s)")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    app = QApplication(sys.argv)
    app.setApplicationName("Unified Flight Tracker")
    apply_dark_palette(app)

    observer = ObserverConfig(lat=args.lat, lon=args.lon, radius_nm=args.radius)
    win = MainWindow(args.url, observer, args.interval)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
