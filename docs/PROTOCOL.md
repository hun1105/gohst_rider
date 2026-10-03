# PROTOCOL — Python 릴레이 ↔ Unity 메시지 규격 (단일 진실 원천)

> 필드 변경 순서: 이 문서 수정 → Python → Unity. 수정 권한: Claude.
> T-002에서 실제 코드 기준으로 채움: `python tools/gemini_worker.py -g "ai_relay_server/*.py" -g "PhysicalAI_AGV_VR/Assets/Scripts/*.cs" -t "WS 송수신 메시지 타입과 필드, 단위, 주기 전부 추출"`

## 연결
- WS: `ws://<host>:9090`
- 영상: 640x480 VGA JPEG, 30fps (바이너리 WebSocket 전송, 버퍼 512KB)
- 텔레메트리: JSON, 20Hz (dt=0.05s)

## Server → Unity: telemetry
메시지 타입: `{"type": "telemetry", "tb1": {...}, "tb2": {...}, "safety": {...}, "controlled_robot": "tb1"}`

### 최상위 필드
| 필드 | 타입 | 설명 |
|---|---|---|
| controlled_robot | string | 현재 텔레옵 권한 보유 로봇 (`tb1` / `tb2`). `SELECT_ROBOT` 수신 확인(ACK) 용도 (T-007) |
| camera_robot | string | 카메라가 달린 로봇 (`tb1`/`tb2`, CLI `--camera-robot`). 영상 위 경로·정지 배너·YOLO 판단 대상. Unity는 이 로봇 콕핏에 영상 화면 부착 (T-025) |
| mode | string | `tb1` 주행 모드: `MANUAL` / `AUTO` (T-016, 하위 호환. 로봇별 값은 로봇 객체 `mode`) |
| auto_state | string | AUTO 세부 상태: `OFF` / `CRUISE`(직진 배회) / `AVOID`(회피 조향) / `RETURN`(구역 복귀) / `STUCK`(정지·조작자 개입 대기) (T-016) |
| path | object | 경로 추천·예상 궤적 (아래 "경로 객체"). 대상 = 조종 중인 실기 로봇(LiDAR 수신), 아니면 `camera_robot` (T-019, T-025) |
| scan | float[] | `path.robot` LiDAR 점, Unity 월드 좌표 평탄 배열 `[x0, z0, x1, z1, …]` (m, 최대 180점). 없음 = `[]` (T-019) |

### 경로 객체 (`path`, T-019)
좌표는 모두 Unity 월드 `[x0, z0, x1, z1, …]` 평탄 배열 (JsonUtility 호환), 0.05m 간격, 길이 최대 1.2m.

| 필드 | 타입 | 설명 |
|---|---|---|
| robot | string | 이 경로·`scan`의 대상 로봇 (`tb1`/`tb2`) (T-025) |
| recommended | float[] | 추천 궤적 (곡률 샘플링 중 점수 최대). 모든 후보가 충돌이면 `[]` |
| recommended_level | string | `GREEN`(여유 충분) / `YELLOW`(좁음: 0.5~1.2m 안 충돌 또는 여유 < 0.08m) / `RED`(0.5m 안 충돌) / `NONE` |
| predicted | float[] | 현재 지령 속도를 유지할 때 예상 궤적 (선속도 ≈ 0이면 `[]`, 후진이면 뒤쪽) |
| predicted_level | string | 예상 궤적 신뢰도 (`recommended_level`과 같은 기준) |
| alternatives | float[] | 대안 궤적 최대 2개를 이어 붙인 배열 |
| alt_points | int | 대안 궤적 1개당 점 개수 (`alternatives` 분할용) |
| recommended_mode | string | `FORWARD`(전진 추천 있음) / `PIVOT`(전진 후보 전부 충돌 → 제자리 선회 후 직진) / `NONE`(추천 없음) (T-024) |
| pivot_deg | float | `PIVOT`일 때 제자리 선회 각도 (도, +좌 / −우, 5° 단위). 그 외 0 |
| pivot_points | float[] | `PIVOT`일 때 선회 후 직진 궤적 (로봇 위치 → 선회 방향 최대 1.2m). 그 외 `[]` |
| pivot_level | string | 선회 후 직진 궤적 신뢰도 (`recommended_level`과 같은 기준). 그 외 `NONE` |

- `PIVOT` 조건: 전진 곡률 후보가 전부 `RED` + LiDAR 탈출 방향(`safety.escape_heading`과 같은 계산) 존재 + 로봇 둘레 0.16m 안 장애물 없음(제자리 회전 공간).
- 표시는 방향만 (수치 미표시). 추천일 뿐 자동 실행 없음.

### 로봇 상태 객체 (`tb1`, `tb2`)
| 필드 | 타입 | 단위 | 설명 |
|---|---|---|---|
| name | string | - | `tb1` (주행 텔레옵) / `tb2` (자율 순찰) |
| x | float | m | 3D 위치 X축 |
| y | float | m | 3D 높이 Y축 (기본 0.0) |
| z | float | m | 3D 위치 Z축 |
| yaw | float | deg | 로봇 회전각 (도, 0~360) |
| linear_vel | float | m/s | 선속도 (최대 0.22 m/s) |
| angular_vel | float | rad/s | 각속도 (최대 2.84 rad/s) |
| battery | float | % | 배터리 잔량 (기본 100.0) |
| source | string | - | `sim` (모의 물리) / `real` (실기체 rosbridge 연동) (T-012) |
| online | bool | - | `real`: 오도메트리 수신 0.5s 이내 여부. `sim`: 항상 `true` (T-012) |
| front_min | float | m | LiDAR 전방 ±30° 최소 거리. 데이터 없음 = `-1.0` (T-012) |
| rear_min | float | m | LiDAR 후방 ±30° 최소 거리. 데이터 없음 = `-1.0` (T-012) |
| mode | string | - | 이 로봇 주행 모드 `MANUAL` / `AUTO` (T-025) |
| auto_state | string | - | 이 로봇 AUTO 세부 상태 (`OFF`/`CRUISE`/`AVOID`/`RETURN`/`STUCK`) (T-025) |
| alert | bool | - | 이 로봇 정지·알림 상태 (인터록 또는 AUTO STUCK) (T-025) |
| stop_reason | string | - | 정지 원인 문구 (예: `COLLISION RISK: TB1 AGV (0.80m)`, `AUTO STUCK: …`). 정상 `""` (T-025) |

- `real` 좌표 변환: ROS odom(x 전방, y 좌측, yaw 반시계) → Unity(`z` = 전방, `x` = 우측, `yaw` 시계방향 도). 로봇별 스폰 포즈(시뮬레이션 초기 위치)를 원점 오프셋으로 적용.
- 스폰 포즈 (T-029, 실측 통로 0.445 × 2.317 m 1:1): `tb1` (x 0, z −0.75, 0°), `tb2` (x 0, z +0.75, 180°) — 통로 중앙선 1.50m 대향. Unity `SceneSetupAutomation` 스폰과 동일.
- `linear_vel`/`angular_vel`은 안전 게이트 통과 후 **지령값** (측정값 아님).

### 안전 상태 객체 (`safety`)
| 필드 | 타입 | 설명 |
|---|---|---|
| interlock | bool | 비상정지/인터록 활성화 여부 |
| status | string | `NORMAL` 또는 `EMERGENCY_STOP` |
| target | string | 비상정지 대상 (`tb1`, `tb2`, `all`) |
| escape | string | tb1 장애물 대응 상태: `IDLE` / `STOP` (정지·조작자 개입 대기). 자동 후진·회전 없음 (T-015, 구 T-005 3-Step 대체) |
| reason | string | 인터록 원인 문구 (예: `LIDAR OBSTACLE (0.32m)`, `COLLISION RISK: TB2 AGV (0.92m)`). 정상 시 `""` (T-015) |
| escape_heading | float | 추천 탈출 방향 (deg, 로봇 기준, +좌/-우, -180~180). LiDAR 기반. 없음 = `0` + `escape_clearance=-1` (T-015) |
| escape_clearance | float | 추천 방향 직진 여유 거리 (m, 최대 1.5). 추천 없음·데이터 없음 = `-1.0` (T-015) |
| watchdog | bool | tb1 cmd_vel 워치독 발동 여부 (0.5s 무입력 → 정지, T-006) |

### 안전 동작 규칙 (tb1)
- 워치독: `TWIST`/`DRIVE` 수신 간격 > 0.5s → 선·각속도 0.
- 장애물 정지·알림 (T-015): 인터록 상승 → 즉시 선·각속도 0, `escape=STOP`, `reason` 설정, 영상에 경고 배너 + 추천 탈출 경로 표시.
  - `STOP` 동안 전진 차단, **후진·회전은 조작자 수동 허용** (실기 후방 LiDAR 가드는 유지). 자동 후진·회전 없음.
  - 인터록 해제 → `IDLE`.
- 추천 탈출 경로: 360° LiDAR에서 로봇 폭 회랑(반폭 0.12m)이 가장 길게 비는 방향, 회전량 적을수록 우선. 여유 0.5m 미만 방향 제외.

### 실기체 안전 규칙 (`source: real`, T-012)
- 지령 속도 상한: 선속도 ±0.15 m/s (실내 시연 기본값, CLI `--real-max-linear`).
- LiDAR 가드: `front_min` < 0.35m → 전진 차단, `rear_min` < 0.20m → 후진 차단.
- LiDAR 유효 측정: `max(range_min, 0.12m)` ~ `range_max`. ROS 1 LD08(LDS-02) 드라이버의 `range_min=0.0`·무효값 `0.0`은 제외 (T-026).
- `tb1` 실기: `front_min` < 0.35m도 인터록 원인 → `safety.interlock`·장애물 정지 알림.
- `online=false` → 해당 로봇 지령 0. 릴레이 종료·rosbridge 재접속 시 0 속도 송신.
- 실기 `tb2` 개루프 순찰은 기본 비활성 (CLI `--real-patrol`로 허용). 실기 자율 주행은 AUTO 사용.

### 자율 배회 AUTO 규칙 (T-016 → T-025 로봇별)
- 대상: 실기(`source=real`, `online`, LiDAR 수신) `tb1`·`tb2` 각각. 조건 미충족 시 해당 로봇 `AUTO` 요청 무시. 로봇마다 상태·배회 중심 따로.
- 조종 권한(`controlled_robot`)과 무관하게 AUTO 로봇은 계속 배회. 권한 없는 MANUAL 실기 로봇은 정지 유지.
- 배회 구역: 첫 AUTO 진입 시 오도메트리 위치 중심 반경 0.6m (T-029 실측 통로). 이탈 시 `RETURN`(중심 방향 조향), 반경 70% 안으로 들어오면 `CRUISE`. 클라이언트 연결 해제 시 중심 초기화.
- `CRUISE`: 0.10 m/s 직진. 전방 0.6m 이내 장애물 → `AVOID`: LiDAR 추천 탈출 방향으로 조향 (오차 20° 이내 0.05 m/s 전진, 초과 시 제자리 회전, 최대 0.8 rad/s).
- `STUCK` 전환: 인터록(전방 0.35m, **로봇 간 1.0m 만남**, 카메라 로봇 YOLO) / 추천 경로 없음(막다른 길) / `AVOID` 6초 지속. 즉시 정지, `safety.reason`에 원인, 영상 배너·추천 경로 표시. **자동 재개 없음.**
- 조작자 개입: 그 로봇 대상 0이 아닌 `TWIST`/`DRIVE`, `STOP`, **`TELEPORT` FPV(콕핏 진입)** → 그 로봇만 즉시 `MANUAL`. `AUTO` 재요청(Unity `R` / 퀘스트 Y) → `CRUISE` 재개 (막혀 있으면 곧바로 `STUCK`).
- AUTO 중 워치독 미적용 (조작자 무입력이 정상). 클라이언트 연결 해제 → 모든 AUTO 해제·정지. `SELECT_ROBOT`은 AUTO를 해제하지 않음.
- 로봇 간 만남(거리 < 1.0m): 두 로봇 모두 정지, AUTO 로봇은 `STUCK`, 양쪽 `alert`. 두 로봇 모두 전진 차단, 후진·회전으로 비켜주기만 허용. 거리 확보 후에도 자동 재개 없음 (`AUTO` 재요청). 실기 속도 상한·LiDAR 가드·offline 정지는 그대로 적용.

### 조종 권한 규칙 (T-007)
- 텔레옵 권한은 항상 1대 (`controlled_robot`). 기본 `tb1`.
- `TWIST.robot` ≠ `controlled_robot` → 무시 (전환 직후 잔여 명령 차단). `DRIVE`는 `tb1` 대상으로 간주.
- 워치독(0.5s)은 `controlled_robot`에 적용.
- `tb2` 선택 시: 자율 순찰 정지, 수동 조작. 로봇 간 거리 < 1.0m이면 두 로봇 전진 차단. YOLO 인터록은 `camera_robot` 대상.
- 권한 이양 시: 이전 로봇이 MANUAL이면 즉시 정지 (AUTO면 계속 배회). 새 로봇이 MANUAL이면 정지 상태에서 시작.
- 클라이언트 연결 해제 → 양쪽 정지, 권한 `tb1` 복귀, `tb2` 자율 순찰 재개.

---

## Unity → Server: 제어 명령

### 1. 주행 제어 (`TWIST`)
- 주기: 20Hz (dt=0.05s)
- 형식: `{"cmd":"TWIST","robot":"tb1","linear":0.22,"angular":0.0,"left":220,"right":220}`

| 필드 | 타입 | 단위 | 설명 |
|---|---|---|---|
| cmd | string | - | `"TWIST"` |
| robot | string | - | 대상 로봇 ID (`"tb1"` / `"tb2"`), `controlled_robot`과 일치해야 적용 |
| linear | float | m/s | 선속도 (-0.22 ~ +0.22) |
| angular | float | rad/s | 각속도 (-2.84 ~ +2.84) |
| left | int | PWM | 좌측 휠 속도 (-220 ~ +220) |
| right | int | PWM | 우측 휠 속도 (-220 ~ +220) |

### 2. 비상 정지 (`STOP`)
- 형식: `{"cmd":"STOP","robot":"tb1"|"tb2"}` (`robot` 생략 시 `tb1`)
- 지정 로봇 즉시 정지.

### 3. 하위 호환 주행 (`DRIVE`)
- 형식: `{"cmd":"DRIVE","left":100,"right":100}`

### 4. 시점 전환 통보 (`TELEPORT`)
- 형식: `{"cmd":"TELEPORT","mode":"FPV"|"GOD_VIEW","robot":"tb1"|"tb2"}`
- 조종 권한은 변경하지 않음 → `SELECT_ROBOT` 사용. `mode=FPV`면 그 로봇 AUTO 해제(MANUAL) (T-025).
- `robot`: FPV면 빙의 대상, GOD_VIEW면 현재 조종 대상.

### 5. 조종 대상 선택 (`SELECT_ROBOT`) — T-007
- 형식: `{"cmd":"SELECT_ROBOT","robot":"tb1"|"tb2"}`
- 텔레옵 권한 이양. 규칙은 "조종 권한 규칙" 참조. 미지원 ID는 무시.
- Unity 송신 순서: `SELECT_ROBOT` → 시점 전환 완료 → `TELEPORT`.
- Unity는 `telemetry.controlled_robot` 불일치 시 `SELECT_ROBOT` 재전송 (재연결 대비).

### 6. 자율 배회 (`AUTO`) — T-016
- 형식: `{"cmd":"AUTO","robot":"tb1"|"tb2","enable":true|false}` (T-025: `tb2` 허용)
- `enable=true`: AUTO 진입/재개, `false`: MANUAL 전환·정지. 규칙은 "자율 배회 AUTO 규칙" 참조.

### 7. 위치 원점 재설정 (`RESET_POSE`) — T-019
- 형식: `{"cmd":"RESET_POSE","robot":"tb1"}` 또는 `{"cmd":"RESET_POSE","robot":"tb1","x":0.0,"z":0.0,"yaw":0.0}`
- 로봇을 현장 원점 마커에 놓고 송신 → 현재 odom을 원점으로 기록, 이후 Unity 포즈 = 기준 포즈 + (현재 odom − 기록 원점).
- 기준 포즈: `x`·`z`(m)·`yaw`(deg, Unity 기준) 주면 그 값, 생략 시 해당 로봇 스폰 포즈.
- 실기(`source=real`) 로봇만 적용. bringup 재시작 없이 맞춤. AUTO 배회 구역 중심은 영향 없음(odom 상대 거리 기준).

---

## 변경 이력
| 날짜 | 변경 | 작성 |
|---|---|---|
| 2026-09-30 | 코드 기반 실제 송수신 필드 확정 (T-002 완료) | claude & antigravity |
| 2026-09-30 | `safety.escape`, `safety.watchdog` 추가 + tb1 안전 동작 규칙 (T-005, T-006) | claude |
| 2026-09-30 | `SELECT_ROBOT` 추가, `TELEPORT.robot` 추가·mode 값 코드와 통일(`FPV`/`GOD_VIEW`), `controlled_robot` 추가, 조종 권한 규칙 (T-007) | claude |
| 2026-10-01 | 로봇 객체 `source`·`online`·`front_min`·`rear_min` 추가, 실기체 안전 규칙 (T-012) | claude |
| 2026-10-02 | 3-Step Escape 자동 후진·회전 삭제 → 정지·알림. `safety.reason`·`escape_heading`·`escape_clearance` 추가 (T-015) | claude |
| 2026-10-02 | `AUTO` 명령, `mode`·`auto_state` 필드, 자율 배회 규칙 추가 (T-016) | claude |
| 2026-10-02 | `path`(추천·예상·대안 궤적 + 신뢰도)·`scan` 필드, `RESET_POSE` 명령 추가 (T-019) | claude |
| 2026-10-02 | `path.recommended_mode`·`pivot_deg`·`pivot_points`·`pivot_level` 추가 — 제자리 선회 후 직진 추천 (T-024) | claude |
| 2026-10-02 | AUTO 로봇별(`tb2` 포함), 로봇 객체 `mode`·`auto_state`·`alert`·`stop_reason`, `camera_robot`, `path.robot`, 콕핏 진입 MANUAL, 로봇 간 만남 둘 다 정지 (T-025) | claude |
| 2026-10-02 | LiDAR 유효 최소 거리 하한 0.12m (ROS 1 LD08 무효값 0.0 오판 방지) (T-026) | claude |
| 2026-10-03 | 스폰 포즈 실측 통로 1:1 (tb1 z −0.75 / tb2 z +0.75 대향) (T-029) | claude |
| 2026-10-03 | AUTO 배회 반경 1.5 → 0.6m (실측 통로) (T-029) | claude |
