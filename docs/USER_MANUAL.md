# 사용 설명서 (User Manual)

Torque Calibration System v1.0.0 — Simulation Mode

> 모든 측정값은 가상 토크측정기가 생성한 **시뮬레이션 데이터**입니다. 화면 오른쪽 위 `SIMULATION MODE` 표시와 성적서의 `DEMO CERTIFICATE — SIMULATED DATA ONLY` 문구는 제거할 수 없습니다.

## 1. 화면 구성

| 영역 | 내용 |
|---|---|
| 상단 헤더 | 프로그램명, 부제, 현재 상태 표시등(READY / RUNNING / PAUSED / WAITING / STOPPED / COMPLETED), 시계, `SIMULATION MODE` |
| 왼쪽 패널 | 장비 정보(Equipment Information) 편집, 환경조건, 교정 설정 요약 + 설정 / 이력 / 결과 검토 버튼, 이벤트 로그 |
| 디지털 표시기 | CURRENT TORQUE(현재 토크, 목표 도달 시 녹색) / TARGET TORQUE(목표 토크) |
| 토크 게이지 | 0 ~ 최대용량 원형 게이지, 주황색 눈금 = 목표값 |
| 진행 상태 | PRELOADING / MEASUREMENT IN PROGRESS / MEASUREMENT CAPTURED 배너, Series·Point·Preload 진행, 측정·시퀀스 진행 막대 |
| 실시간 그래프 | X: Time (s), Y: Torque (N·m). 파랑 = 증가 곡선, 주황 = 해제 곡선, 점선 = 목표, 녹색 별 = 확정 지점. **View** 목록에서 `FULL TIMELINE` 또는 이전 측정(#01, #02 …)을 선택해 다시 볼 수 있음 |
| 결과 테이블 | Target / Series 1~3 / Average / Error(%) / U(k=2) / 판정. 측정 중인 칸은 파란색 강조 |
| 하단 제어 바 | 시퀀스 제어 버튼, 속도 선택, Presentation Mode, 성적서 버튼 |

창 크기에 맞춰 자동으로 배치가 바뀌며, 패널 경계선을 끌어 크기를 조절할 수 있습니다. **F11** = 전체 화면, **Esc** = 전체 화면 해제.

## 2. 교정 절차

1. **장비 정보 확인** — 왼쪽 패널에서 제조사·모델·일련번호·용량·범위·방향·고객·온습도를 확인/수정합니다. 최초 실행 시 기본값이 입력되어 있습니다.
2. **교정 설정 확인(선택)** — `설정 Settings`에서 교정점, 시리즈 수, 사전부하, 허용오차, 판정 규칙, 불확도 입력값, 시뮬레이션 파라미터를 바꿀 수 있습니다.
3. **START CALIBRATION** — 사전부하 3회(100 N·m)가 자동 수행되고 `PRELOADING COMPLETED` 후 Series 1이 시작됩니다.
4. 각 교정점에서 토크가 0 → 목표값까지 연속 증가 → 유지 → `MEASUREMENT CAPTURED` → 0으로 해제됩니다. 확정값은 테이블에 즉시 기록되고 DB에 저장됩니다.
5. Series 3까지 완료되면 평균·오차·불확도·판정이 자동 계산되고 `CALIBRATION COMPLETED` 메시지가 표시됩니다.
6. **결과 검토 Review** — 평균, 지시오차, 상대오차, 보정값, 반복성, 불확도 성분(uA, uref, ures, uadd), uc, U, 두 가지 판정 결과와 적용 가정을 확인합니다.
7. **GENERATE CERTIFICATE** — 성적서 번호(DEMO-연도-일련번호)가 부여되고 PDF가 생성되어 미리보기가 열립니다.
8. **EXPORT PDF / EXPORT EXCEL** — 원하는 위치에 저장합니다. 두 파일은 같은 측정 데이터로 만들어집니다.

## 3. 버튼

| 버튼 | 동작 | 활성 조건 |
|---|---|---|
| START CALIBRATION | 새 교정 기록 생성 후 전체 시퀀스 시작 | 대기 / 정지 / 완료 상태 |
| PAUSE | 현재 지점에서 일시 정지 | 진행 중 |
| RESUME | 정지된 지점부터 계속 | 일시 정지 / 복구 직후 |
| STOP | 시퀀스 종료 (기록은 STOPPED로 보관, 성적서 발행 불가) | 진행 중 |
| RESET | 화면 데이터 초기화 (저장된 이력은 유지) | 진행 중이 아닐 때 |
| NEXT MEASUREMENT | 수동 모드에서 다음 토크 인가 시작 | MANUAL + 대기(WAITING) |
| MODE: AUTO / MANUAL | 자동 연속 측정 ↔ 한 점씩 수동 진행 | 항상 (진행 중 전환 가능) |
| Speed | Normal / Fast / Presentation — 타이밍만 변경, 결과에 영향 없음 | 항상 |
| PRESENTATION MODE | 발표용 화면 + 자동 성적서 생성 | 항상 |
| GENERATE CERTIFICATE | 성적서 생성 + 미리보기 | 15/15 측정 완료 후 |
| EXPORT PDF / EXCEL | 성적서 파일 저장 | 측정 완료 후 |
| OPEN CERTIFICATE | 생성된 성적서 미리보기 | 성적서 생성 후 |
| OPEN OUTPUT FOLDER | 성적서 폴더 열기 | 항상 |

## 4. 설정 항목

**교정 설정** — 교정점(쉼표 구분), 시리즈 수(2~5), 사전부하 횟수(0~5)·토크(0 = 최대용량), 허용오차(기본 ±4 %, 교육용 가정값), 판정 규칙(단순 / 불확도 고려 w = U), 수행자·검토자 이름.

**불확도** — 기준기 이름, 기준기 확장불확도(% of reading)와 k, 분해능, 추가 표준불확도(%), 포함인자 k.

**시뮬레이션** — Random Error Range(±% of target), Systematic bias(실행마다 한 번 결정되는 계통오차 최대값), Noise Level(σ, N·m), Sampling Interval(기본 50 ms), Torque Ramp Speed(N·m/s), Measurement Hold Time(s), 인가 간 대기시간, Simulation Speed 배율, Random seed(비우면 매 실행 값이 달라짐, 숫자를 넣으면 재현 가능).

## 5. Presentation Mode (발표용)

1. 하단의 **PRESENTATION MODE**를 켭니다 → 왼쪽 패널이 숨겨지고 진행 상태 글자가 커지며 속도가 `Presentation`, 모드가 AUTO로 설정됩니다.
2. **F11**로 전체 화면 전환 후 **START CALIBRATION**.
3. 사전부하 3회 → Series 1~3 → 자동 계산 → PDF·Excel 성적서 자동 저장까지 약 75초에 진행됩니다(상태 표시줄에 예상 시간 표시).
4. 완료 시 `CALIBRATION COMPLETED / 15 / 15 Measurements Completed / Certificate Ready` 오버레이가 표시됩니다(클릭하면 닫힘).
5. **OPEN CERTIFICATE**로 성적서를 바로 보여줄 수 있습니다.

발표 팁: 발표 전에 한 번 실행해 결과 화면을 확인하고, `RESET` 후 시연하세요. seed를 고정하면 리허설과 같은 값이 나옵니다.

## 6. 이력 조회 · 성적서 재발행

`이력 History`에서 모든 교정 기록(ID, 성적서 번호, 상태, 모델, 측정 수, 결과)을 볼 수 있습니다.
- **결과 불러오기** — 측정값과 계산 결과를 화면에 표시(VIEWING RECORD 상태). 이 상태에서도 GENERATE / EXPORT / 결과 검토 가능.
- **PDF / Excel 재생성** — 저장된 동일 데이터로 성적서를 다시 만듭니다(성적서 번호 유지).
- **삭제** — 진행 중이 아닌 기록을 삭제.

## 7. 비정상 종료와 복구

측정값은 확정 즉시 저장됩니다. 측정 도중 프로그램이 종료되면 다음 실행 시 *"이전 교정이 완료되지 않은 채 종료되었습니다"* 창이 나타납니다.
- **예** → 장비정보·설정·확정된 값을 불러오고 `RECOVERED — press RESUME` 상태가 됩니다. RESUME을 누르면 마지막으로 확정된 다음 지점부터 이어서 진행합니다.
- **아니오** → 기록은 ABORTED 상태로 이력에 남습니다.

(실제 교정 업무에서는 중단 후 재개 시 사전부하를 다시 하는 것이 일반적이지만, 본 시뮬레이션은 복구 기능 시연을 위해 중단 지점부터 재개합니다.)

## 8. 문제 해결

| 증상 | 조치 |
|---|---|
| macOS "확인되지 않은 개발자" / "손상됨" | README §8 "코드 서명 및 보안 경고" 참고 (Control+클릭 → 열기, 또는 `xattr -dr com.apple.quarantine`) |
| Windows SmartScreen 경고 | "추가 정보 → 실행" |
| 성적서 저장 실패 | 같은 이름의 파일이 Excel/PDF 뷰어에서 열려 있지 않은지 확인 |
| 성적서 미리보기가 비어 있음 | "외부 뷰어로 열기" 버튼 사용 |
| 예기치 않은 오류 | `TorqueCalibration/data/error.log` 내용 확인 |
