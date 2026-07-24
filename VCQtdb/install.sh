#!/usr/bin/env bash
# Linux installer for the C++/Qt6 flight-tracker dashboard.
# Installs build prerequisites (Qt6 + CMake + a C++ toolchain), configures
# the project into ./build, and compiles it.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

# --- 1. system prerequisites ----------------------------------------------
if command -v apt-get >/dev/null 2>&1; then
    echo "[install] installing Qt6 + build tools via apt-get..."
    sudo apt-get update -qq
    sudo apt-get install -y --no-install-recommends \
        build-essential cmake ninja-build pkg-config \
        qt6-base-dev qt6-base-dev-tools \
        libqt6network6 libqt6widgets6 libqt6gui6 libqt6core6 \
        libgl1 libglx-mesa0
elif command -v dnf >/dev/null 2>&1; then
    echo "[install] installing Qt6 + build tools via dnf..."
    sudo dnf install -y \
        gcc-c++ cmake ninja-build pkgconf \
        qt6-qtbase-devel qt6-qtbase-gui qt6-qtbase-network
elif command -v pacman >/dev/null 2>&1; then
    echo "[install] installing Qt6 + build tools via pacman..."
    sudo pacman -Sy --noconfirm --needed base-devel cmake ninja qt6-base
else
    echo "[install] no supported package manager detected."
    echo "          Install Qt6 (Base + Widgets + Network), CMake >= 3.19,"
    echo "          Ninja, and a C++17 compiler, then re-run this script."
    exit 1
fi

# --- 2. configure + build --------------------------------------------------
BUILD_DIR="${BUILD_DIR:-build}"
echo "[install] configuring in $BUILD_DIR ..."
cmake -S . -B "$BUILD_DIR" -G Ninja -DCMAKE_BUILD_TYPE=Release
echo "[install] building..."
cmake --build "$BUILD_DIR" --parallel

# --- 3. launcher shim ------------------------------------------------------
cat > run-dashboard.sh <<SH
#!/usr/bin/env bash
HERE="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
exec "\$HERE/$BUILD_DIR/vcqtdb" "\$@"
SH
chmod +x run-dashboard.sh

echo
echo "[install] done."
echo "  binary: $HERE/$BUILD_DIR/vcqtdb"
echo "  run:    ./run-dashboard.sh --url http://localhost:5001"
