# [통합 종합 문서] MetaQuest 2 VR 연동 완벽 가이드 및 전체 프로젝트 진행 현황

> **문서 목적**: MetaQuest 2 VR 헤드셋과의 구체적 연동 절차(노트북 마우스 피킹 $\rightarrow$ VR 콕핏 빙의)와 지금까지 구현된 모든 시스템 구조, 파일 위치, 태스크 완료 상태(T-001 ~ T-007)를 단일 문서로 영구 보존합니다.

---

## 1. MetaQuest 2 VR 연동 완벽 가이드

### 1.1 하이브리드 관제 구조 (노트북 $\leftrightarrow$ 메타퀘스트 2)
본 시스템은 **노트북(관제실)**과 **메타퀘스트 2(현장 운전자)**가 역할을 분담하는 비대칭 디지털 트윈 구조입니다.

```
[노트북 PC 화면]                               [MetaQuest 2 VR 헤드셋]
  - 거시 조감도 (God-View) 상시 표출             - 1인칭 FPV 윈드실드 시야 몰입
  - 우측 관제 사이드바 (TB1/TB2 실시간 카드)      - 3D 콕핏 내부 공간 렌더링
  - 마우스로 특정 로봇(TB1/TB2) 좌클릭!           - 좌측 썸스틱: 주행 조작 (/tb1/cmd_vel)
           │                                              │
           └─────────── [로봇 클릭 시 즉시 빙의 전환] ───────┘
                                   │
                    (복귀: 퀘스트 B 버튼 or 노트북 Tab/ESC)
```

---

### 1.2 VR 구동 방법 2가지

#### [방식 A] Meta Quest Link (유선 / AirLink 무선) — **[강력 권장]**
PC의 고성능 GPU 연산 결과를 헤드셋으로 초저지연 스트리밍하는 방식으로, 별도의 Android 빌드 대기 시간 없이 Unity Play 버튼만으로 즉시 시연 가능합니다.

1. **사전 준비**:
   - PC에 `Oculus App` (공식 Meta Quest Link 소프트웨어) 설치 및 실행.
   - 고속 USB 3.0 C-to-C 케이블 연결 (또는 동일 5GHz Wi-Fi 접속 후 AirLink 활성화).
2. **헤드셋 설정**:
   - MetaQuest 2 착용 $\rightarrow$ 빠른 설정 $\rightarrow$ `Quest Link` (또는 `AirLink`) 클릭 $\rightarrow$ PC 연결.
3. **Unity 6 실행**:
   - `5_경남2026_피지컬AI_메타퀘스트VR_AGV\PhysicalAI_AGV_VR` 프로젝트 열기.
   - 상단 **Play (▶)** 버튼 클릭.
   - 노트북 화면에 God-View 조감도가 뜨고, 마우스로 TB1을 클릭하면 메타퀘스트 2 헤드셋 안에서 1인칭 FPV 콕핏으로 즉각 이동합니다.

#### [방식 B] Standalone APK 무선 단독 빌드
PC 없이 메타퀘스트 2 헤드셋 자체 연산으로 구동하는 방식입니다 (최종 전시/시연용).
1. Unity 상단 메뉴 `File` $\rightarrow$ `Build Profiles`.
2. 플랫폼을 `Android`로 Switch.
3. Texture Compression: `ASTC`, Run Device: `Oculus Quest 2` 선택 후 `Build and Run`.

---

### 1.3 메타퀘스트 2 컨트롤러 조작 맵핑

| 입력 장치 | 조작 방식 | 기능 및 연동 토픽 |
| :--- | :--- | :--- |
| **노트북 마우스** | 3D 모델 좌클릭 | 원하는 로봇(TB1/TB2) 선택 $\rightarrow$ VR 콕핏 빙의 (`SELECT_ROBOT`) |
| **노트북 키보드** | `Tab` 또는 `ESC` | 1인칭 콕핏 $\leftrightarrow$ 거시 조감도(God-View) 전환 (`TELEPORT`) |
| **Quest 좌측 컨트롤러** | 썸스틱 상하좌우 | 선택된 로봇 실시간 전후진 및 좌우 회전 (`/{robot}/cmd_vel`) |
| **Quest 우측 컨트롤러** | 'B' 버튼 클릭 | FPV 콕핏 탈출 $\rightarrow$ 노트북 거시 조감도(God-View)로 시점 복귀 |
| **Quest 우측 트리거** | 검지 트리거 입력 | 피지컬 AI 수동 비상 정지 (`STOP`) |
| **Quest 우측 컨트롤러** | 썸스틱 좌우 | VR 플레이어 헤드 시야 스냅 회전 (Snap Turn) |

---

## 2. 전체 프로젝트 진행 현황 및 태스크 완료 내역

### 2.1 작업 보드 현황 (`docs/TASKS.md`)
모든 핵심 개발 작업(T-001 ~ T-007)이 **100% 완료(done)**되었으며, 빌드 및 E2E 통신 검증을 모두 통과했습니다.

| ID | 작업 항목 | 담당 | 상태 | 상세 구현 내용 및 검증 결과 |
| :--- | :--- | :--- | :--- | :--- |
| **T-001** | 멀티 에이전트 환경 구축 | human | **done** | Claude-Gemini-Antigravity 협업 툴킷 및 스크립트 구축 |
| **T-002** | PROTOCOL.md 송수신 규격 확정 | claude | **done** | Python $\leftrightarrow$ Unity 간 20Hz 텔레메트리/제어 프로토콜 단일 원천 정립 |
| **T-003** | GodViewSidebarHUD.cs | antigravity | **done** | 우측 상단 반투명 관제 사이드바 카드 실시간 상태 출력 |
| **T-004** | RobotWarningVisualizer.cs | antigravity | **done** | 비상 정지 시 해당 로봇 악센트 링 머티리얼 적색(Red) 경고 점멸 |
| **T-005** | 3-Step Escape 안전 상태머신 | claude | **done** | STOP(1s) $\rightarrow$ BACKUP(-0.1m/s, 1.5s) $\rightarrow$ ROTATE(90°) 자동 회피 |
| **T-006** | cmd_vel 0.5s 무입력 워치독 | claude | **done** | 통신 두절 및 조작 누락 시 0.5초 만에 Fail-safe 자동 모터 제동 |
| **T-007** | 마우스 피킹 및 다중 로봇 VR 빙의 | claude | **done** | 노트북 마우스 클릭 $\rightarrow$ 메타퀘스트 2 콕핏 진입 및 조종권 전환 |

---

## 3. 핵심 소스코드 및 파일 위치 명세 (Absolute Paths)

**프로젝트 루트 경로**:  
`c:\Users\hun\OneDrive - 국립한국해양대학교\바탕 화면\대회_프로젝트_통합자료\5_경남2026_피지컬AI_메타퀘스트VR_AGV`

### 3.1 백엔드 AI 릴레이 서버 (`ai_relay_server/`)
- `ros2_multi_turtlebot_relay.py`:
  - WebSocket 포트 `9090` 가동.
  - YOLOv8 다중 객체(작업자, 타AGV, 파렛트) 검출 및 충돌 회랑 인터록.
  - T-005 3단계 탈출 머신 및 T-006 0.5s 워치독 내장.
  - 640x480 JPEG 영상(30fps) 및 JSON 텔레메트리(20Hz) 브로드캐스트.
- `turtlebot3_humble_robot_node.py`: 실물 라즈베리파이 현장 구동용 ROS 2 Humble 브리지.
- `test_relay_client.py`: 백엔드 통신 검증 클라이언트 (18KB 프레임 수신 및 텔레메트리 확인 완료).

### 3.2 프론트엔드 Unity 6 디지털 트윈 (`PhysicalAI_AGV_VR/Assets/`)
- `Scripts/RobotSelectionRaycaster.cs`: God-View 3D 마우스 피킹, 호버 헤일로 하이라이트, 콕핏 빙의 트리거.
- `Scripts/PerspectiveSwitcher.cs`: 거시 조감도 $\leftrightarrow$ 선택 로봇 콕핏 동적 트랜스폼 바인딩 및 시점 전환.
- `Scripts/GodViewSidebarHUD.cs`: OnGUI 기반 경량 관제 사이드바 (TB1/TB2 배터리, 속도, 인터록, 탈출 상태).
- `Scripts/RobotWarningVisualizer.cs`: `MaterialPropertyBlock` 기반 로봇 링 적색 경고 점멸.
- `Scripts/TurtleBotMultiAgentManager.cs`: JSON 텔레메트리 파싱 및 `Vector3.Lerp`/`Quaternion.Slerp` 부드러운 위치 동기화.
- `Scripts/TurtleBot3ModelBuilder.cs`: 3단 원형 플레이트, DYNAMIXEL 휠, OpenCR 절차적 정밀 3D 모델 빌더.
- `Scripts/AGVControllerInput.cs`: 썸스틱/WASD 입력을 정규화된 ROS 2 Twist(`/tb1/cmd_vel`, `/tb2/cmd_vel`)로 변환.
- `Scripts/FPVStreamReceiver.cs`: 수신 바이너리 JPEG를 3D 윈드실드 머티리얼에 디코딩.
- `Scripts/WebSocketManager.cs`: .NET 표준 비동기 ClientWebSocket 매니저.
- `Editor/SceneSetupAutomation.cs`: 창고 바닥, 랙 8개, 박스 적재물, 안전조끼 작업자, TB1, TB2 자동 씬 생성.

### 3.3 프로젝트 규약 및 거버넌스 문서 (`docs/`)
- `docs/PROTOCOL.md`: 단일 진실 원천 통신 메시지 규격서.
- `docs/TASKS.md`: 작업 보드 및 진행 상태.
- `AGENTS.md`: Claude - Gemini - Antigravity 공통 협업 지침.
- `CLAUDE_COLLABORATION_CONTEXT.md`: Claude 핸드오버 마스터 프롬프트.
- `METAQUEST_VR_INTEGRATION_AND_FULL_STATUS.md`: **본 종합 문서**.

---

## 4. 빌드 및 검증 통과 증거

1. **Unity 6 LTS 컴파일 검증**:
   - 실행: `powershell -ExecutionPolicy Bypass -File tools/unity_check.ps1`
   - 결과: **`UNITY_CHECK OK (warnings: 0)`** (컴파일 에러 0건, 경고 0건).
2. **Python 릴레이 서버 문법 검증**:
   - 실행: `python -m py_compile ai_relay_server/ros2_multi_turtlebot_relay.py`
   - 결과: 에러 없이 정상 통과.
3. **E2E 통신 실측 검증**:
   - 실행: `python ai_relay_server/test_relay_client.py`
   - 결과: **`VERIFICATION SUCCESSFUL: Both FPV video (18KB) and Multi-TurtleBot telemetry (20Hz) functioning!`**

---

## 5. 경진대회 제출을 위한 잔여 작업 (Next Steps)
- [ ] **1페이지 AI Agent 기술설명서** (A4 1쪽, Goal-Planning-Reasoning-Tool-Memory 6요소 명세)
- [ ] **5페이지 개발완료보고서** (A4 5쪽, 문제정의, E2E 워크플로우, 실측 Test Case 5건)
- [ ] **3분 시연영상 촬영** (노트북 화면 녹화 + 퀘스트 VR 콕핏 화면 + 실기체 연동)
- [ ] **10장 발표자료 PPT** (심사위원 배점 맞춤형 구성안)
