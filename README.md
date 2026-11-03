# Torque Wrench Automatic Calibration & Certificate Generation System

**토크렌치 자동교정 시뮬레이션 및 교정성적서 자동발행 프로그램** — 대학원 프로젝트 (v1.0.0)

> ⚠️ **SIMULATION MODE ONLY.** 이 프로그램은 실제 토크측정기와 연결되지 않습니다. 모든 측정값은 가상 토크측정기(Virtual Torque Measuring Device)가 생성한 데이터이며, 생성되는 성적서는 *"DEMO CERTIFICATE — SIMULATED DATA ONLY"* 표시가 있는 교육용 문서로 유효한 교정성적서가 아닙니다.

---

## 1. 개요

실제 자동교정 소프트웨어처럼 **50 ms 간격의 연속 토크 신호**를 생성하고, 사전부하(Preloading) 3회 → 3개 측정 시리즈(Measurement Series) × 5개 교정점 = **15개 측정값**을 자동으로 수집한 뒤 평균·지시오차·상대오차·보정값·반복성·측정불확도를 계산하여 **PDF / Excel 교정성적서**를 발행합니다.

| 항목 | 기본값 (GUI에서 수정 가능) |
|---|---|
| 대상 | Torque Wrench / DEMO TOOLS / TW-100 / S/N TW2026-001 |
| 최대용량 · 범위 · 방향 | 100 N·m · 20~100 N·m · Clockwise (CW) |
| 교정점 | 20, 40, 60, 80, 100 N·m |
| 시퀀스 | Preloading 3회(100 N·m) + 3 Series × 5 Points = 18회 토크 인가 |
| 환경조건 | 23.0 °C, 50 %RH |
| 허용오차 | ±4 % (**교육용 가정값** — 모든 토크렌치에 공통인 규격값이 아님) |
| 포함인자 | k = 2 |

## 2. 검증 현황 (정직한 상태 표시)

| 항목 | 상태 | 비고 |
|---|---|---|
| 시뮬레이터 · 교정 시퀀스 · 계산 · 불확도 · DB · 복구 | ✅ 실행·테스트 완료 | Linux / Python 3.13, `pytest` 30개 통과 |
| PDF 성적서 | ✅ 생성·렌더링 확인 | 한글 폰트 임베딩, 2페이지, 상/하단 DEMO 문구 |
| Excel 성적서 | ✅ 생성 + 수식 검증 | LibreOffice로 재계산한 값이 Python 계산값과 일치 |
| GUI 제어 로직 (버튼·상태·성적서 연동·복구) | 🟡 부분 검증 | 실제 Qt 없이 대체 스텁으로 흐름만 실행. **화면 렌더링은 미검증** |
| PySide6 GUI 실제 실행 | ⬜ **미검증** | 개발 환경에서 PySide6 설치 불가. `tests/test_gui_smoke.py`로 직접 확인 필요 |
| macOS `.app` / Windows `.exe` 빌드 | ⬜ **미검증** | 각 OS에서 빌드 스크립트 실행 필요 |
| macOS · Windows 실행 | ⬜ **별도 검증 필요** | 아래 §9 체크리스트 참고 |

## 3. 빠른 실행 (개발 모드)

```bash
cd TorqueCalibrationSystem
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

테스트:

```bash
python -m pytest -q tests                                   # 핵심 기능 (Qt 불필요)
QT_QPA_PLATFORM=offscreen python -m pytest -q tests/test_gui_smoke.py -s   # GUI 스모크 (PySide6 필요)
```

GUI 스모크 테스트는 실제 메인 윈도우를 띄워 Presentation Mode 전 과정을 실행하고, 성적서 생성 여부를 확인하며 `output/data/gui_smoke_*.png` 스크린샷을 저장합니다.

예시 성적서 재생성(GUI 불필요): `python tools/generate_examples.py --seed 2026`

## 4. 프로젝트 구조

```
TorqueCalibrationSystem/
├── main.py                    # 진입점 (QApplication, 스타일, 예외 처리)
├── requirements.txt / README.md / build_mac.sh / build_windows.bat
├── src/                       # Qt 독립 핵심 로직 (단위 테스트 대상)
│   ├── config.py              # 장비정보·교정설정·시뮬레이션 설정 데이터 모델 및 기본값
│   ├── data_source.py         # TorqueDataSource / SimulatedTorqueSource / HardwareTorqueSource
│   ├── simulator.py           # CalibrationEngine: 사전부하→시리즈 시퀀스 상태기계
│   ├── calibration.py         # 평균·오차·상대오차·보정값·반복성·판정
│   ├── uncertainty.py         # 불확도 버짓 (uA, uref, ures, uadd → uc, U)
│   ├── database.py            # SQLite 저장, 중복방지, 복구
│   ├── report_data.py         # PDF·Excel 공통 데이터 묶음 (값 일치 보장)
│   ├── certificate_pdf.py     # ReportLab PDF 성적서
│   ├── certificate_excel.py   # OpenPyXL Excel 성적서 (6 시트, 수식)
│   ├── fonts.py / paths.py    # 한글 폰트 등록, OS별 경로
├── gui/
│   ├── main_window.py         # 메인 화면 · 버튼 · 상태 제어 · 성적서/이력/복구
│   ├── dashboard.py           # 장비정보 패널, 디지털 표시기, 진행 패널, 결과 테이블, 로그
│   ├── torque_gauge.py        # QPainter 원형 게이지
│   ├── realtime_graph.py      # PyQtGraph 실시간 그래프 + 이전 측정 다시보기
│   ├── certificate_preview.py # QtPdf 성적서 미리보기
│   ├── dialogs.py             # 설정 / 결과 검토 / 이력 대화상자
│   └── theme.py               # 다크 테마 색상·폰트
├── resources/  icons/ (png·ico·icns) · styles/dark.qss · fonts/ (Noto Sans KR 서브셋, OFL)
├── tests/      test_calculation.py · test_simulation.py · test_certificate.py · test_gui_smoke.py
├── tools/generate_examples.py
├── docs/USER_MANUAL.md        # 프로그램 사용 설명서
└── output/ certificates/ (예시 PDF·Excel) · data/ (SQLite DB)
```

## 5. 설계 요점

- **GUI 무정지(non-blocking) 구조**: 메인 스레드의 50 ms `QTimer`가 `CalibrationEngine.advance(dt)`를 호출합니다. 한 번의 호출이 처리하는 작업은 수 개의 샘플뿐이라 GUI가 멈추지 않고, 별도 스레드가 없으므로 경쟁 조건이 없습니다.
- **시간 독립적 측정값**: 각 토크 인가의 지시값은 인가 시작 시점에 난수 발생기에서 결정되고, 화면 노이즈는 별도 난수 발생기를 씁니다. 따라서 Normal / Fast / Presentation 속도를 바꿔도 같은 seed에서 **결과가 완전히 동일**합니다 (테스트로 검증).
- **신호 단계**: Zero → Torque Increasing → Approaching Target(88 % 이후 감속) → Torque Applied(유지) → Measurement Captured → Torque Released.
- **확정값**: 유지 구간이 끝나는 순간의 측정기 필터 출력값을 확정값으로 사용합니다(분해능 0.01 N·m로 반올림). 사전부하는 피크값만 별도 기록하며 결과 계산에서 제외합니다.
- **확장 구조**: `HardwareTorqueSource`는 인터페이스만 있으며 `connect()`가 `False`를 반환하므로 실제 장비 모드로는 실행되지 않습니다. 실제 장비를 붙이려면 이 클래스에 시리얼/USB 통신과 `read_sample()`을 구현하면 됩니다.
- **데이터 안전**: 측정값은 확정 즉시 SQLite(WAL)에 커밋됩니다. `(calibration_id, series, point_index)` UNIQUE 제약으로 중복 저장이 불가능합니다. 비정상 종료 후 재실행하면 복구 여부를 묻고, 마지막 확정 지점 다음부터 이어서 진행합니다.

## 6. 계산식

| 항목 | 식 |
|---|---|
| 평균 Mean | (M1 + M2 + M3) / 3 |
| 지시오차 Indication Error | Mean − Reference Torque  [N·m] |
| 상대오차 Relative Error | Error / Reference × 100  [%] |
| 보정값 Correction | Reference − Mean  [N·m] |
| 반복성 s | STDEV.S(M1, M2, M3) |
| A형 표준불확도 uA | s / √3 (일반식 s/√n) |
| 기준기 uref | (U_ref % / k_ref) × Reference / 100 — 기본 U_ref = 0.2 %, k = 2 |
| 분해능 ures | r / (2√3), r = 0.01 N·m (직사각형 분포) |
| 추가 성분 uadd | 0.05 % × Reference (환경·재현성 여유, 가정값) |
| 합성 uc | √(uA² + uref² + ures² + uadd²) |
| 확장 U | k × uc, k = 2 |

**판정 규칙**
- 단순 판정(Simple): |상대오차| ≤ 허용오차 → PASS
- 불확도 고려 판정(Guard band w = U, ILAC-G8:2019 개념 참고): |오차| + U ≤ 허용한계 → PASS, |오차| − U > 허용한계 → FAIL, 그 외 INCONCLUSIVE

> 불확도 단순화 가정: n = 3에서 uA의 자유도는 2이므로 엄밀한 GUM 평가(Welch–Satterthwaite 유효자유도)에서는 k가 2보다 커집니다. 본 프로젝트는 교육 목적상 k = 2로 고정했으며, 이 가정은 GUI(결과 검토), PDF, Excel에 모두 명시됩니다. 성적서는 ISO 6789-2를 *교육용 참고*로만 표기하며 그 전체 요구사항 충족을 주장하지 않습니다.

## 7. 데이터 저장 위치

| 실행 방식 | 위치 |
|---|---|
| 개발 모드 (`python main.py`) | `TorqueCalibrationSystem/output/` |
| 배포 앱 (.app / .exe) | `~/Documents/TorqueCalibration/` (Windows: `문서\TorqueCalibration\`) |
| 강제 지정 | 환경변수 `TORQUECAL_HOME` |

`data/torque_calibration.db` (SQLite), `certificates/*.pdf, *.xlsx`, `data/error.log`(예외 발생 시).

## 8. 독립 실행 파일 빌드

빌드하는 컴퓨터에만 Python 3.11+이 필요합니다. 최종 사용자는 Python 설치가 필요 없습니다. PyInstaller는 크로스 컴파일을 지원하지 않으므로 **macOS 앱은 macOS에서, Windows EXE는 Windows에서** 빌드합니다.

### macOS

```bash
chmod +x build_mac.sh
./build_mac.sh              # → dist/TorqueCalibration.app, TorqueCalibration_Mac.zip
```

`--windowed` 옵션으로 터미널 창 없이 GUI만 실행되는 `.app` 번들이 만들어집니다.

**Apple Silicon vs Intel**
- 빌드 결과물의 아키텍처는 **빌드에 사용한 Python의 아키텍처**를 따릅니다.
- Apple Silicon(M1~M5)의 arm64 Python으로 빌드 → arm64 앱 (Intel Mac에서는 실행 불가).
- Intel Mac(또는 x86_64 Python)으로 빌드 → x86_64 앱. **Apple Silicon에서도 Rosetta 2로 실행**됩니다(첫 실행 시 Rosetta 설치 안내가 나올 수 있음).
- 두 아키텍처를 모두 배포하려면 각각 빌드한 뒤 `TorqueCalibration_Mac_arm64.zip`, `TorqueCalibration_Mac_x86_64.zip`처럼 이름을 나눠 배포하는 방법이 가장 안전합니다. PyInstaller의 `--target-arch universal2`는 Python과 모든 확장 모듈(NumPy 등)이 universal2 바이너리여야 해서 일반 pip 환경에서는 실패하는 경우가 많습니다.
- 현재 Mac 확인: `uname -m` (arm64 / x86_64), Python 확인: `python3 -c "import platform; print(platform.machine())"`.

### Windows 10 / 11

```bat
build_windows.bat          → dist\TorqueCalibration.exe, TorqueCalibration_Windows.zip
```

`--onefile --windowed`로 CMD 창 없이 실행되는 단일 EXE가 만들어집니다. 단일 파일 EXE는 실행 시 임시 폴더에 압축을 풀기 때문에 첫 실행이 몇 초 걸릴 수 있습니다.

### 코드 서명 및 보안 경고

본 프로젝트의 실행 파일은 Apple Developer ID나 Windows 코드 서명 인증서로 서명되지 않았습니다(macOS는 ad-hoc 서명만 적용). 따라서 다른 컴퓨터에서 처음 실행할 때 경고가 표시됩니다.

**macOS (Gatekeeper)** — "확인되지 않은 개발자" 또는 "손상되었기 때문에 열 수 없습니다"
1. Finder에서 `TorqueCalibration.app`을 **Control+클릭 → 열기 → 열기**.
2. 또는 시스템 설정 → 개인정보 보호 및 보안 → 하단의 **"그래도 열기"**.
3. 인터넷에서 받은 zip이라 "손상됨"이 뜨면 터미널에서 격리 속성 제거:
   `xattr -dr com.apple.quarantine /path/to/TorqueCalibration.app`
4. 정식 배포 시에는 Developer ID 서명(`codesign --options runtime`)과 `notarytool` 공증이 필요합니다.

**Windows (SmartScreen)** — "Windows의 PC 보호"
1. **추가 정보 → 실행** 클릭.
2. 백신이 PyInstaller 단일 EXE를 오탐하는 경우가 있습니다. 이때는 예외 등록하거나 `--onefile` 대신 폴더형(onedir) 빌드를 사용하세요.
3. 정식 배포 시에는 코드 서명 인증서와 `signtool sign`이 필요합니다.

## 9. 크로스 플랫폼 검증 체크리스트 (직접 확인 필요)

- [ ] `python -m pytest -q tests` 전체 통과 (GUI 스모크 포함)
- [ ] `python main.py` → 1920×1080 및 MacBook 해상도에서 화면 배치, 창 크기 변경 시 자동 조정
- [ ] START → 사전부하 3회 → Series 1~3 → CALIBRATION COMPLETED, 결과 테이블 15칸
- [ ] PAUSE/RESUME/STOP/RESET, AUTO/MANUAL + NEXT MEASUREMENT 동작
- [ ] Presentation Mode: 약 75초 내 완료 + 성적서 자동 생성
- [ ] GENERATE CERTIFICATE → 미리보기, EXPORT PDF / EXCEL 저장 및 열기
- [ ] 측정 도중 강제 종료 → 재실행 시 복구 → RESUME으로 이어서 완료
- [ ] `.app` / `.exe` 더블클릭 실행, 터미널/CMD 창 미표시, Python 미설치 PC에서 실행

## 10. 라이선스 및 표기

- 번들 폰트: Noto Sans CJK KR의 서브셋을 TrueType으로 변환(SIL Open Font License 1.1) — `resources/fonts/FONT_LICENSE.txt`.
- 실제 교정기관의 로고, 인정마크, 공식 인증표시는 사용하지 않습니다. 기준기 이름 "Simulated Reference Torque Transducer (DEMO-REF-01)"는 가상의 명칭입니다.
