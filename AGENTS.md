# AGENTS.md — 공통 규칙 (Claude / Gemini / Antigravity 전원 적용)

프로젝트: 2026 경남 AI·SW 경진대회 — MetaQuest VR 피지컬 AI AGV 디지털 트윈

## 1. 구조
| 경로 | 내용 | 스택 |
|---|---|---|
| `ai_relay_server/` | WS 릴레이(9090), YOLOv8 인터록, 텔레메트리 | Python 3.12, ROS 2 Humble |
| `PhysicalAI_AGV_VR/Assets/Scripts/` | 디지털 트윈 런타임 | Unity 6 LTS, URP, C# |
| `PhysicalAI_AGV_VR/Assets/Editor/` | 씬 자동 생성 | Unity Editor C# |
| `docs/PROTOCOL.md` | Python↔Unity 메시지 규격 (단일 진실 원천) | |
| `docs/TASKS.md` | 작업 보드 | |
| `docs/handoff/` | 에이전트 간 인계서 | |

## 2. 로봇 규약
- `tb1`: 텔레옵 주행, Cyan 포인트.
- `tb2`: 순찰/장애물, Orange 포인트.
- LiDAR 없음. 전방 파이캠 + YOLOv8 + 휠 오도메트리 퓨전.
- 영상: 640x480 JPEG 30fps. 텔레메트리: JSON 20Hz.

## 3. 역할 분담
| 에이전트 | 담당 | 금지 |
|---|---|---|
| Claude | 설계, 안전 로직, 통합, 리뷰, PROTOCOL.md 수정 | 로그·PDF·대용량 파일 직접 전수 독해 |
| Gemini (worker) | 대용량 독해 → JSON 요약 | 파일 수정 |
| Antigravity | handoff에 명시된 파일만 구현 | 안전 로직, PROTOCOL.md 수정 |

**안전 로직 = Claude 전용**: 인터록, 3-Step Escape, cmd_vel 워치독, 비상정지 경로.

## 4. 공통 규칙
- 읽기 금지: `Library/ Temp/ obj/ Logs/ Build/ UserSettings/ .git/ __pycache__/`
- Unity: uGUI 신규 의존 금지. OnGUI 또는 기존 Canvas 사용.
- Unity: `.meta` 파일 함께 커밋. 에셋 이동은 Unity 에디터에서만.
- 머티리얼 색 변경: `MaterialPropertyBlock` 사용 (인스턴스 누수 방지).
- 메시지 필드 추가·변경 → `docs/PROTOCOL.md` 먼저 수정 → 코드 수정.
- Python: 타입힌트, `asyncio` 기반 유지. 블로킹 호출 금지.
- 매직넘버 금지. 상수/SerializeField로 노출.
- 커밋 메시지: `[agent] 범위: 내용` 예) `[antigravity] hud: 배터리 바 추가`

## 5. 작업 흐름
1. Claude가 `docs/TASKS.md`에 작업 등록 + `docs/handoff/T-xxx.md` 작성.
2. 담당 에이전트가 자기 브랜치(`agent/<이름>`)에서 구현.
3. 검증: `tools/unity_check.ps1` (Unity) / `python -m py_compile` (Python).
4. Claude가 리뷰 후 `main` 병합.

## 6. 완료 기준 (Definition of Done)
- Unity 배치 컴파일 에러 0.
- handoff의 수락 기준 전부 충족.
- PROTOCOL.md와 코드 필드명 일치.
- TASKS.md 상태 갱신.
