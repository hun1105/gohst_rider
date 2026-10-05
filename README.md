# Ghost_Rider — MetaQuest VR 기반 피지컬 AI AGV 원격 개입 & 협착 방지 디지털 트윈

> **멈추고, 알리며, 사람이 빼낸다.**
> 제4회 경남 AI·SW 경진대회 2026 · 대학부 · 분야 32 (3-2. MetaQuest2 VR 기반 피지컬 AI Agent)

2D LiDAR로 위험을 판단해 AGV가 스스로 멈추고, 정지 원인과 탈출 경로를 카메라 영상·관제 맵에 표시한 뒤,
관제사가 Meta Quest 2로 그 로봇의 콕핏에 들어가 원격으로 빼내는 피지컬 AI 에이전트입니다.
실물 TurtleBot3 2대(ROS 1 + ROS 2), Python 릴레이, Unity 관제 맵·VR 콕핏까지 End-to-End로 동작합니다.

---

## 핵심 기능

| # | 기능 | 내용 |
|---|---|---|
| 1 | 정지 우선 안전 게이트 | 전방 0.35m · AGV 간 0.3m 안이면 전진 지령 차단 (후진·회전만 허용, 자동 후진 없음). 속도 상한 0.15 m/s |
| 2 | LiDAR 탈출 경로 추천 | 360° 스캔을 72방향(5°)으로 평가해 로봇 폭 회랑이 가장 길고 덜 도는 방향 선택 + 곡률 25개 궤적 평가 → 영상 바닥·관제 맵에 표시 |
| 3 | VR 원격 개입 | 관제 맵에서 로봇 클릭 → 그 로봇만 MANUAL, Quest 콕핏으로 전환. 그립 데드맨 + 스틱 조종, 장애물 방향 진동 |
| 4 | 2대 동시 운용 | 로봇별 AUTO, 만나면 둘 다 정지 → 사람이 한 대를 비킴 → `R`로 재개 (사람 승인 없이 자동 재개 없음) |
| 5 | 통신 두절 대응 | 지령·odom 0.5초, LiDAR 1.0초 끊기면 자동 정지 |

## Agent Workflow

```
업무(R: AUTO 시작) → 감지(LiDAR·odom 20 Hz) → 정지(0.35m / 0.3m, 원인 기록)
      → 경로(72방향 탈출 방향 + 궤적) → VR 개입(클릭 → 콕핏 → 원격 탈출) → 재개(R)
```

| 구성 | 내용 |
|---|---|
| AI | LiDAR 기하 추론 (VFH · Follow-the-Gap · DWA 계열). 학습 모델·LLM 미사용 |
| Tool | ROS `/cmd_vel` · `/odom` · `/scan` (rosbridge), Unity 6 + OpenXR, Meta Quest 2 |
| Data | 실시간 LiDAR 360°, 휠 오도메트리, 640×480 카메라 영상 |
| Memory | 로봇별 모드·정지 원인·위치 원점, 운행 이력 로그 (이벤트 + 1 Hz JSONL) |

## 시스템 구조

```
 TurtleBot3 tb1 (ROS 1 Noetic) ─┐  rosbridge
 TurtleBot3 tb2 (ROS 2 Humble) ─┼──────────────►  ai_relay_server (Python asyncio, :9090)
 Pi Camera (ustreamer MJPEG)  ──┘                  ├ 안전 게이트 · 워치독 · AUTO 상태기계
                                                   ├ 탈출 경로 계산 · 영상 오버레이
                                                   └ 텔레메트리 JSON 20 Hz + JPEG 영상
                                                              │ WebSocket
                                                              ▼
                                   Unity 6 디지털 트윈 (PC 관제 맵 + Quest 2 VR 콕핏)
```

메시지 규격: [`docs/PROTOCOL.md`](docs/PROTOCOL.md)

## 저장소 구조

| 경로 | 내용 |
|---|---|
| `ai_relay_server/` | 릴레이 서버, 안전 게이트, 탈출 경로(`escape_planner.py`, `path_planner.py`), 자동 시험 |
| `PhysicalAI_AGV_VR/` | Unity 6 프로젝트 (관제 맵, VR 콕핏, 씬 자동 생성 `Assets/Editor/`) |
| `launch/` | 로봇 기동·릴레이 실행 배치 파일 ([`launch/README.md`](launch/README.md)) |
| `hardware_firmware/` | TurtleBot3 측 설정·노드 |
| `tools/` | 보정, 촬영·영상 편집, TTS, 제출 문서 빌드 스크립트 |
| `docs/` | 보고서·기술설명서·발표 원본, 프로토콜, 시험 기록(`docs/evidence/`) |

## 실행 방법

### 요구 사항
- Python 3.11+ (`pip install -r ai_relay_server/requirements.txt`)
- Unity 6000.0.84f1 (URP, OpenXR), Meta Quest 2 + Quest Link (선택)
- 실물 시연 시: TurtleBot3 Burger 2대, 같은 Wi-Fi 망, 로봇에 rosbridge_server

### 1) 하드웨어 없이 자동 시험
```bash
python ai_relay_server/test_real_bridge.py      # 가짜 rosbridge 2대 + 릴레이 E2E 시험 (78항목)
python ai_relay_server/soak_test.py 300         # 300초 부하 시험 (안전 불변식 위반 횟수 측정)
```

### 2) 실물 2대 시연 (Windows)
1. `launch/start_tb1_robot.bat`, `launch/start_tb2_robot.bat` → 로봇 브링업
2. `launch/run_relay_tb1_tb2.bat` → `tb1 = REAL`, `tb2 = REAL` 확인
3. Unity에서 `PhysicalAI_AGV_VR` 열기 → 메뉴 `PhysicalAI > Setup Dual TurtleBot3 Warehouse Scene` → Play
4. `R`로 두 대 AUTO → 정지 시 로봇 클릭 → 콕핏에서 탈출 → `Esc`로 관제 복귀 → `R` 재개

로봇 IP 등 현장 값은 배치 파일 안에서 수정합니다.

### Unity 조작 키

| 키 | 동작 |
|---|---|
| `R` / `Shift+R` | 전체 AUTO / 선택 로봇만 AUTO |
| 로봇 클릭, `Tab`/`T` | 콕핏(1인칭) 진입 |
| `Esc` | 관제 맵 복귀 |
| `W` `A` `S` `D` | 수동 주행 (콕핏) |
| `Space` | 비상정지 |
| `P` / `Shift+P` | 위치 원점 재설정 |
| 휠 / 우클릭 드래그 / `Q`·`E` / 휠 클릭 | 관제 맵 확대 / 이동 / 회전 / 초기화 |
| `F1` / `F2` `F3` / `F4` | 사이드바 / tb1·tb2 표시 / LiDAR 점 표시 |

Quest 2: 그립을 쥔 동안만 조종(데드맨), 양손 스틱으로 전후진·회전, `Y` = AUTO.

## 검증 결과

| 시험 | 결과 | 기록 |
|---|---|---|
| E2E 자동 시험 (가짜 rosbridge 2대) | 78/78 PASS | `docs/evidence/test_real_bridge_20261002.txt` |
| 같은 시험 10회 반복 | 10/10 무결점 (당시 73항목) | `docs/evidence/stress_10x_20261003.txt` |
| 300초 부하 시험 | 안전 위반 0건, 텔레메트리 19.99 Hz (150 ms 초과 간격 1회, 최대 190.8 ms) | `docs/evidence/soak_test_20261003.txt` |
| 실물 시연 | 2대 만남 정지, 상자 앞 정지, VR 콕핏 원격 탈출 | 시연 영상 |

## 한계 및 발전 계획
- 2D LiDAR 한 평면만 감지 → 깊이카메라 융합으로 높이 사각 보완
- 휠 오도메트리 누적 오차 → 바닥·벽 마커(AprilTag) 보정
- 기존 AGV·건설기계 PLC 연동, 카메라 객체 인식으로 정지 원인 구분, 운행 로그 원격 점검

## 팀
**Ghost_Rider** — 조재호, 한정훈

## 출처 및 라이선스
- 사용한 오픈소스·AI 도구·통계 출처는 출처·AI 활용 신고서에 정리했습니다 (원본 `docs/SOURCE_AI_DISCLOSURE.md`).
- 주요 오픈소스: ROS 1/2, TurtleBot3 (Apache-2.0), rosbridge_suite (BSD-3), OpenCV, websockets, Unity OpenXR Plugin.
- ustreamer(GPL-3.0)는 로봇에서 별도 프로세스로 실행하며 이 저장소에 포함하지 않습니다.
- YOLOv8(AGPL-3.0)은 선택 기능이며 기본 실행(`--no-ai`)에서는 쓰지 않습니다.
