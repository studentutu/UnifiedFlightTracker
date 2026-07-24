"""Sortable, filterable table of live flights.

Uses QAbstractTableModel so we can update the underlying data in place
without dropping row selection between polls.
"""
from __future__ import annotations

from typing import Any, Optional

from PyQt6.QtCore import (
    QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt, pyqtSignal
)
from PyQt6.QtGui import QBrush, QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QTableView, QVBoxLayout, QWidget
)


COLUMNS = (
    ("callsign", "Callsign", 90),
    ("type",     "Type",     70),
    ("altitude", "Alt ft",   70),
    ("speed",    "GS kt",    60),
    ("heading",  "Hdg°",     55),
    ("distance_from_obs", "Dist NM", 70),
    ("azimuth",  "Az°",      55),
    ("elevation","El°",      55),
    ("source",   "Source",   150),
    ("hex_id",   "Hex",      90),
)


class FlightModel(QAbstractTableModel):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._rows: list[dict[str, Any]] = []

    # -- Qt required ----------------------------------------------------
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return COLUMNS[section][1]
        return section + 1

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        key, _, _ = COLUMNS[index.column()]
        val = row.get(key)

        if role == Qt.ItemDataRole.DisplayRole:
            if val is None:
                return "—"
            if key in ("altitude", "speed"):
                try:
                    return f"{int(round(float(val))):,}"
                except (TypeError, ValueError):
                    return str(val)
            if key in ("distance_from_obs", "azimuth", "elevation"):
                try:
                    return f"{float(val):.1f}"
                except (TypeError, ValueError):
                    return str(val)
            if key == "heading":
                try:
                    return f"{int(round(float(val))):03d}"
                except (TypeError, ValueError):
                    return str(val)
            return str(val)

        if role == Qt.ItemDataRole.EditRole:
            # Used by the proxy for numeric sorting.
            if isinstance(val, (int, float)):
                return val
            try:
                return float(val)
            except (TypeError, ValueError):
                return val

        if role == Qt.ItemDataRole.ForegroundRole and key == "elevation":
            try:
                el = float(val)
            except (TypeError, ValueError):
                return None
            if el < 0:
                return QBrush(QColor("#f28b82"))     # below horizon = red-ish
            if el > 30:
                return QBrush(QColor("#8bc4ff"))     # high overhead = pale blue

        if role == Qt.ItemDataRole.ForegroundRole and key == "distance_from_obs":
            try:
                d = float(val)
            except (TypeError, ValueError):
                return None
            if d < 5:
                return QBrush(QColor("#a5d6a7"))    # close = green
            if d > 100:
                return QBrush(QColor("#9e9e9e"))    # far = grey

        if role == Qt.ItemDataRole.FontRole and key in (
            "altitude", "speed", "heading", "distance_from_obs", "azimuth", "elevation"
        ):
            font = QFont("monospace")
            return font

        if role == Qt.ItemDataRole.TextAlignmentRole and key in (
            "altitude", "speed", "heading", "distance_from_obs", "azimuth", "elevation"
        ):
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None

    # -- app-facing -----------------------------------------------------
    def set_rows(self, flights: list[dict[str, Any]]) -> None:
        """Replace rows preserving order by hex_id so selection is stable."""
        flights = sorted(flights, key=lambda f: str(f.get("hex_id") or ""))
        if len(flights) == len(self._rows):
            # In-place update — signal each changed cell so views don't reset.
            self._rows = flights
            top = self.index(0, 0)
            bot = self.index(len(flights) - 1, len(COLUMNS) - 1)
            self.dataChanged.emit(top, bot)
        else:
            self.beginResetModel()
            self._rows = flights
            self.endResetModel()

    def hex_id_at(self, row: int) -> Optional[str]:
        if 0 <= row < len(self._rows):
            return str(self._rows[row].get("hex_id") or "")
        return None

    def row_for_hex(self, hex_id: str) -> int:
        for i, r in enumerate(self._rows):
            if str(r.get("hex_id") or "") == hex_id:
                return i
        return -1


class FlightTable(QWidget):
    selectionChanged = pyqtSignal(str)   # emits hex_id (or "" on clear)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.model = FlightModel(self)
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy.setFilterKeyColumn(-1)   # search across all columns
        self.proxy.setSortRole(Qt.ItemDataRole.EditRole)

        self.view = QTableView(self)
        self.view.setModel(self.proxy)
        self.view.setSortingEnabled(True)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.view.setAlternatingRowColors(True)
        self.view.verticalHeader().setDefaultSectionSize(22)
        self.view.verticalHeader().setVisible(False)
        header = self.view.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        for i, (_, _, w) in enumerate(COLUMNS):
            self.view.setColumnWidth(i, w)

        # Search box.
        self._search = QLineEdit(self)
        self._search.setPlaceholderText("filter (callsign, type, hex, source…)")
        self._search.textChanged.connect(self.proxy.setFilterFixedString)

        self._count_label = QLabel("0 aircraft", self)
        self._count_label.setStyleSheet("color:#9aa7b5;")

        top = QHBoxLayout()
        top.addWidget(self._search, 1)
        top.addWidget(self._count_label, 0)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)
        lay.addLayout(top)
        lay.addWidget(self.view)

        self.view.selectionModel().currentRowChanged.connect(self._emit_selection)

    def set_flights(self, flights: list[dict[str, Any]]) -> None:
        self.model.set_rows(flights)
        self._count_label.setText(f"{len(flights)} aircraft")

    def _emit_selection(self, current, _prev) -> None:
        if not current.isValid():
            self.selectionChanged.emit("")
            return
        src_row = self.proxy.mapToSource(current).row()
        hid = self.model.hex_id_at(src_row) or ""
        self.selectionChanged.emit(hid)

    def select_hex(self, hex_id: str) -> None:
        src_row = self.model.row_for_hex(hex_id)
        if src_row < 0:
            return
        idx = self.proxy.mapFromSource(self.model.index(src_row, 0))
        self.view.selectionModel().setCurrentIndex(
            idx,
            self.view.selectionModel().SelectionFlag.SelectCurrent
            | self.view.selectionModel().SelectionFlag.Rows,
        )
