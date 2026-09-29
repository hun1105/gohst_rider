# PROTOCOL — Python 릴레이 ↔ Unity 메시지 규격 (단일 진실 원천)

> 필드 변경 순서: 이 문서 수정 → Python → Unity. 수정 권한: Claude.
> T-002에서 실제 코드 기준으로 채움: `python tools/gemini_worker.py -g "ai_relay_server/*.py" -g "PhysicalAI_AGV_VR/Assets/Scripts/*.cs" -t "WS 송수신 메시지 타입과 필드, 단위, 주기 전부 추출"`

## 연결
- WS: `ws://<host>:9090`
- 영상: 640x480 VGA JPEG, 30fps (바이너리 WebSocket 전송, 버퍼 512KB)
- 텔레메트리: JSON, 20Hz (dt=0.05s)

## Server → Unity: telemetry
메시지 타입: `{"type": "telemetry", "tb1": {...}, "tb2": {...}, "safety": {...}}`

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

### 안전 상태 객체 (`safety`)
| 필드 | 타입 | 설명 |
|---|---|---|
| interlock | bool | 비상정지/인터록 활성화 여부 |
| status | string | `NORMAL` 또는 `EMERGENCY_STOP` |
| target | string | 비상정지 대상 (`tb1`, `tb2`, `all`) |
| escape | string | tb1 3-Step Escape 상태: `IDLE` / `STOP` / `BACKUP` / `ROTATE` / `FAULT` (T-005) |
| watchdog | bool | tb1 cmd_vel 워치독 발동 여부 (0.5s 무입력 → 정지, T-006) |

### 안전 동작 규칙 (tb1)
- 워치독: `TWIST`/`DRIVE` 수신 간격 > 0.5s → 선·각속도 0. Escape 진행 중(`STOP`/`BACKUP`/`ROTATE`)엔 미적용.
- 3-Step Escape: 인터록 상승 시 `STOP`(1.0s 정지) → 인터록 지속 시 `BACKUP`(-0.10 m/s, 1.5s) → `ROTATE`(1.0 rad/s, 90°).
  - `STOP` 중 인터록 해제 → `IDLE` 복귀 (후진 생략).
  - 사이클 후에도 인터록 지속 → 재시도, 최대 3회 후 `FAULT`.
  - `FAULT`: 자동 회피 중단, 수동 조작 허용(전진은 인터록이 차단). 인터록 해제 시 `IDLE`.
  - `STOP`/`BACKUP`/`ROTATE` 중 조작자 `TWIST`/`DRIVE` 무시. `STOP` 명령 또는 클라이언트 연결 해제 → Escape 즉시 중단, 인터록 해제까지 재발동 금지.

---

## Unity → Server: 제어 명령

### 1. 주행 제어 (`TWIST`)
- 주기: 20Hz (dt=0.05s)
- 형식: `{"cmd":"TWIST","robot":"tb1","linear":0.22,"angular":0.0,"left":220,"right":220}`

| 필드 | 타입 | 단위 | 설명 |
|---|---|---|---|
| cmd | string | - | `"TWIST"` |
| robot | string | - | 대상 로봇 ID (`"tb1"`) |
| linear | float | m/s | 선속도 (-0.22 ~ +0.22) |
| angular | float | rad/s | 각속도 (-2.84 ~ +2.84) |
| left | int | PWM | 좌측 휠 속도 (-220 ~ +220) |
| right | int | PWM | 우측 휠 속도 (-220 ~ +220) |

### 2. 비상 정지 (`STOP`)
- 형식: `{"cmd":"STOP","robot":"tb1"}`

### 3. 하위 호환 주행 (`DRIVE`)
- 형식: `{"cmd":"DRIVE","left":100,"right":100}`

### 4. 시점 전환 통보 (`TELEPORT`)
- 형식: `{"cmd":"TELEPORT","mode":"FPV"|"GOD_VIEW"}`

---

## 변경 이력
| 날짜 | 변경 | 작성 |
|---|---|---|
| 2026-09-30 | 코드 기반 실제 송수신 필드 확정 (T-002 완료) | claude & antigravity |
| 2026-09-30 | `safety.escape`, `safety.watchdog` 추가 + tb1 안전 동작 규칙 (T-005, T-006) | claude |

