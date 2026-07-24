"""Background HTTP polling for /api/flights.

Runs a QThread that emits `flightsReceived(list, list)` on each poll
so the GUI thread can update without blocking.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import requests
from PyQt6.QtCore import QObject, QThread, pyqtSignal


@dataclass(frozen=True)
class ObserverConfig:
    lat: float
    lon: float
    radius_nm: float


class PollWorker(QObject):
    flightsReceived = pyqtSignal(list, list, float)   # flights, messages, elapsed_s
    error = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, base_url: str, observer: ObserverConfig, interval_s: float):
        super().__init__()
        self._base_url = base_url.rstrip('/')
        self._observer = observer
        self._interval_s = interval_s
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        while not self._stop:
            t0 = time.perf_counter()
            try:
                r = requests.get(
                    f"{self._base_url}/api/flights",
                    params={
                        "lat": self._observer.lat,
                        "lon": self._observer.lon,
                        "radius": self._observer.radius_nm,
                    },
                    timeout=8,
                )
                r.raise_for_status()
                body = r.json()
                elapsed = time.perf_counter() - t0
                self.flightsReceived.emit(
                    body.get("flights", []),
                    body.get("messages", []),
                    elapsed,
                )
            except requests.exceptions.RequestException as exc:
                self.error.emit(str(exc))
            except (ValueError, KeyError) as exc:
                self.error.emit(f"bad response: {exc}")

            # Interruptible sleep so stop() takes effect promptly.
            slept = 0.0
            while slept < self._interval_s and not self._stop:
                time.sleep(0.1)
                slept += 0.1
        self.finished.emit()


class TrackerClient(QObject):
    """Owns the polling QThread and re-exports its signals."""

    flightsReceived = pyqtSignal(list, list, float)
    error = pyqtSignal(str)

    def __init__(
        self,
        base_url: str,
        observer: ObserverConfig,
        interval_s: float = 5.0,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._thread = QThread(self)
        self._worker = PollWorker(base_url, observer, interval_s)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.flightsReceived.connect(self.flightsReceived)
        self._worker.error.connect(self.error)
        self._worker.finished.connect(self._thread.quit)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._worker.stop()
        self._thread.quit()
        self._thread.wait(2000)
