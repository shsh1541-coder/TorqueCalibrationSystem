#!/bin/bash
# Double-click launcher for macOS.
# First run: creates a private Python environment (.venv) and installs the
# libraries (takes a few minutes). Later runs: starts the program immediately.
cd "$(dirname "$0")" || exit 1

pause_exit() {
  echo
  read -r -p "엔터(Return) 키를 누르면 이 창을 닫습니다..." _
  exit "$1"
}

echo "=============================================="
echo "  Torque Calibration System - 실행 준비 중"
echo "=============================================="

PY=""
for c in python3.13 python3.12 python3.11 \
         /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 \
         /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 \
         /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 \
         /opt/homebrew/bin/python3 /usr/local/bin/python3; do
  if command -v "$c" >/dev/null 2>&1 && \
     "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    PY="$c"
    break
  fi
done

if [ -z "$PY" ]; then
  echo
  echo "[!] Python 3.11 이상이 설치되어 있지 않습니다."
  echo "    지금 열리는 python.org 페이지에서 macOS용 Python을 설치한 뒤"
  echo "    이 파일을 다시 더블클릭하세요."
  open "https://www.python.org/downloads/macos/"
  pause_exit 1
fi
echo "Python: $("$PY" --version)"

if [ ! -x .venv/bin/python ] || ! .venv/bin/python -c "import PySide6, pyqtgraph, reportlab, openpyxl" 2>/dev/null; then
  echo
  echo "처음 실행: 필요한 프로그램을 설치합니다 (3~10분, 인터넷 필요)."
  echo "이 창을 닫지 말고 기다려 주세요..."
  echo
  "$PY" -m venv .venv || { echo "[!] 가상환경 생성 실패"; pause_exit 1; }
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r requirements.txt || {
    echo
    echo "[!] 설치 중 오류가 발생했습니다. 위의 빨간/영문 메시지를 복사해 알려주세요."
    pause_exit 1
  }
  echo
  echo "설치 완료!"
fi

echo
echo "프로그램을 시작합니다. (프로그램을 사용하는 동안 이 창은 닫지 마세요)"
.venv/bin/python main.py
STATUS=$?
if [ $STATUS -ne 0 ]; then
  echo
  echo "[!] 프로그램이 오류로 종료되었습니다 (코드 $STATUS). 위 메시지를 알려주세요."
  pause_exit $STATUS
fi
