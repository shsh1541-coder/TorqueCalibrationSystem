#!/usr/bin/env bash
# Build TorqueCalibration.app and TorqueCalibration_Mac.zip (run on macOS).
#
#   ./build_mac.sh                 # native build for this Mac (arm64 or x86_64)
#   SKIP_TESTS=1 ./build_mac.sh    # skip the test suite
#   PYTHON=/usr/local/bin/python3.12 ./build_mac.sh
#
# The app is built for the architecture of the Python interpreter used:
#   Apple Silicon Python  -> arm64 app  (M1/M2/M3/M4/M5 only)
#   Intel Python          -> x86_64 app (Intel Macs; also runs on Apple Silicon via Rosetta 2)
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
"$PY" -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ required"'
ARCH="$("$PY" -c 'import platform; print(platform.machine())')"
echo "==> Python: $("$PY" --version)  architecture: $ARCH"

if [ ! -d .venv-build ]; then
  "$PY" -m venv .venv-build
fi
# shellcheck disable=SC1091
source .venv-build/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if [ "${SKIP_TESTS:-0}" != "1" ]; then
  echo "==> Running tests"
  QT_QPA_PLATFORM=offscreen python -m pytest -q tests
fi

echo "==> Building app bundle"
rm -rf build dist
pyinstaller --noconfirm --clean --windowed \
  --name TorqueCalibration \
  --icon resources/icons/app.icns \
  --osx-bundle-identifier edu.university.torquecalibration \
  --add-data "resources:resources" \
  --collect-submodules pyqtgraph \
  --exclude-module tkinter --exclude-module matplotlib \
  --exclude-module PyQt5 --exclude-module PyQt6 \
  main.py

# Ad-hoc signature (no Apple Developer ID). Keeps Apple Silicon happy; Gatekeeper will
# still warn on other Macs - see README "보안 경고".
codesign --force --deep --sign - dist/TorqueCalibration.app || echo "codesign skipped"

echo "==> Creating TorqueCalibration_Mac.zip"
rm -f TorqueCalibration_Mac.zip
ditto -c -k --sequesterRsrc --keepParent dist/TorqueCalibration.app TorqueCalibration_Mac.zip
echo "==> Done: dist/TorqueCalibration.app  ->  TorqueCalibration_Mac.zip  ($ARCH)"
