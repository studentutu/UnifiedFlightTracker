#!/usr/bin/env bash
# Linux installer for the PyQt6 flight-tracker dashboard.
# Creates a local .venv and installs PyQt6 + requests.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

# --- 1. system prerequisites ----------------------------------------------
# PyQt6 wheels are self-contained on most distros, but we need python3-venv
# and libgl (used by QtGui) for Qt to render at all under X11/Wayland.
if command -v apt-get >/dev/null 2>&1; then
    echo "[install] installing system prerequisites via apt-get..."
    sudo apt-get update -qq
    sudo apt-get install -y --no-install-recommends \
        python3 python3-venv python3-pip \
        libgl1 libegl1 libxkbcommon0 libdbus-1-3 \
        libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
        libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-sync1 \
        libxcb-xfixes0 libxcb-xkb1 libxkbcommon-x11-0
elif command -v dnf >/dev/null 2>&1; then
    echo "[install] installing system prerequisites via dnf..."
    sudo dnf install -y python3 python3-pip python3-virtualenv \
        mesa-libGL libxkbcommon xcb-util-cursor
else
    echo "[install] no supported package manager detected; make sure Python 3.9+"
    echo "          and libGL/libxkbcommon are present."
fi

# --- 2. python venv --------------------------------------------------------
if [[ ! -d .venv ]]; then
    echo "[install] creating .venv..."
    python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# --- 3. launcher shim ------------------------------------------------------
cat > run-dashboard.sh <<'SH'
#!/usr/bin/env bash
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
source .venv/bin/activate
exec python -m dashboard "$@"
SH
chmod +x run-dashboard.sh

echo
echo "[install] done."
echo "  run:  ./run-dashboard.sh --url http://localhost:5001"
echo "  or:   source .venv/bin/activate && python -m dashboard"
