# PROTOCOL — Python 릴레이 ↔ Unity 메시지 규격 (단일 진실 원천)

> 필드 변경 순서: 이 문서 수정 → Python → Unity. 수정 권한: Claude.
> T-002에서 실제 코드 기준으로 채움: `python tools/gemini_worker.py -g "ai_relay_server/*.py" -g "PhysicalAI_AGV_VR/Assets/Scripts/*.cs" -t "WS 송수신 메시지 타입과 필드, 단위, 주기 전부 추출"`

## 연결
- WS: `ws://<host>:9090`
- 영상: 640x480 JPEG, 30fps, 전송 형식: <binary/base64 확인 필요>
- 텔레메트리: JSON, 20Hz

## Server → Unity: telemetry
| 필드 | 타입 | 단위 | 설명 |
|---|---|---|---|
| robot_id | string | - | `tb1` / `tb2` |
| x, y | float | m | 오도메트리 위치 |
| yaw | float | rad | |
| v, w | float | m/s, rad/s | |
| battery | float | % | |
| isInterlocked | bool | - | 비상정지 상태 |
| escape_step | int | - | 0=없음, 1=역추적, 2=선회, 3=전진 (예정) |

## Unity → Server: cmd_vel
| 필드 | 타입 | 단위 |
|---|---|---|
| robot_id | string | - |
| linear_x | float | m/s |
| angular_z | float | rad/s |

## 변경 이력
| 날짜 | 변경 | 작성 |
|---|---|---|
| | 초안 (필드명은 추정, T-002에서 확정) | claude |
