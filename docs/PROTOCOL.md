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

