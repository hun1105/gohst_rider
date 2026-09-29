# [Claude 협업용 인수인계 마스터 컨텍스트] Physical AI AGV Digital Twin System

> 본 문서는 다른 LLM(Claude 등)과의 원활한 협업을 위해 프로젝트의 전체 아키텍처, 디렉토리 구조, 현재까지 구현된 코드 및 파일 위치, 잔여 작업 목록을 집약한 프롬프트 컨텍스트입니다.

---

## 1. 프로젝트 핵심 정보 (Executive Summary)
- **대회명**: 2026 제4회 경남 AI·SW 경진대회
- **목표 수준**: 상용 서비스가 아닌 시연 가능한 **Level 3 MVP** (E2E 워크플로우 안정 동작, 5대 Test Case 기록)
- **과제 정의**: MetaQuest 2 VR 기반 피지컬 AI 원격 텔레오퍼레이션 & 2대 AGV 협착/충돌 방지 시스템
- **하드웨어 기체**: **TurtleBot3 Burger 2대**
  - **TB1 (`/tb1`)**: 사용자 VR 텔레옵 주행 AGV (Cyan 포인트)
  - **TB2 (`/tb2`)**: 창고 내 자율 순찰 및 동적 장애물 AGV (Orange 포인트)
- **센서 구성**: 전방 파이캠 + 휠 엔코더 + IMU (**LiDAR 제외**)
- **개발 환경**:
  - 로봇/통신: ROS 2 Humble, Python 3.12 (C:\Users\hun\ai_env), PyTorch CPU, Ultralytics YOLOv8, WebSockets
  - 디지털 트윈: Unity 6.0 LTS (6000.0.84f1), Universal Render Pipeline (URP), C# .NET

---

## 2. 프로젝트 디렉토리 및 파일 위치 명세 (Absolute Paths)

**프로젝트 루트**:  
`c:\Users\hun\OneDrive - 국립한국해양대학교\바탕 화면\대회_프로젝트_통합자료\5_경남2026_피지컬AI_메타퀘스트VR_AGV`

```
5_경남2026_피지컬AI_메타퀘스트VR_AGV/
├── ai_relay_server/                           # Python AI 백엔드 & ROS 2 중계 서버
│   ├── ros2_multi_turtlebot_relay.py          # [핵심] WS 포트 9090, YOLOv8 인터록, TB1/TB2 텔레메트리 송출
│   ├── turtlebot3_humble_robot_node.py        # [로봇용] 라즈베리파이 현장 구동용 ROS 2 Humble 브리지 노드
│   ├── test_relay_client.py                   # 통신 검증 스크립트 (이미지 수신 & 텔레메트리 20Hz 확인 완료)
│   ├── relay_agent.py                         # (구버전 단일 릴레이 레거시)
│   └── yolov8n.pt                             # YOLOv8 nano 가중치 파일 (6.5MB)
│
├── PhysicalAI_AGV_VR/                         # Unity 6.0 LTS 디지털 트윈 프로젝트
│   ├── Packages/manifest.json                 # com.unity.ugui: 2.0.0 등록 완료
│   └── Assets/
│       ├── Scripts/
│       │   ├── WebSocketManager.cs            # .NET 표준 비동기 ClientWebSocket 매니저 (바이너리/텍스트 큐)
│       │   ├── TurtleBotMultiAgentManager.cs  # [핵심] TB1, TB2 수신 오도메트리 파싱 및 Vector3.Lerp 스무딩
│       │   ├── TurtleBot3ModelBuilder.cs      # [핵심] 3단 원형 플레이트, DYNAMIXEL 바퀴, OpenCR 절차적 정밀 3D 모델링
│       │   ├── AGVControllerInput.cs          # WASD/조이스틱 입력을 ROS 2 Twist 규격(/tb1/cmd_vel)으로 송신
│       │   ├── FPVStreamReceiver.cs           # 수신 JPEG 바이트를 3D 윈드실드 화면에 실시간 텍스처 디코딩
│       │   └── PerspectiveSwitcher.cs         # Tab 입력 시 거시 조감도(God-View) <-> 1인칭 FPV 콕핏 시점 전환
│       │
│       └── Editor/
│           └── SceneSetupAutomation.cs        # [핵심] 창고 랙, 파렛트, 작업자, TB1, TB2 씬 자동 생성기
│
├── TURTLEBOT3_BURGER_ARCHITECTURE.md          # ROS 2 Humble 2대 터틀봇 마스터 아키텍처 문서
├── MULTI_TURTLEBOT3_ROS2_USER_GUIDE.md        # 실물 로봇 브링업 및 운용 매뉴얼
└── CLAUDE_COLLABORATION_CONTEXT.md            # 본 파일 (협업용 인수인계 컨텍스트)
```

---

## 3. 통신 프로토콜 및 데이터 규격

### 3.1 ROS 2 Humble 토픽 매핑
- `/tb1/cmd_vel` (`geometry_msgs/msg/Twist`): VR 텔레오퍼레이션 주행 지령 ($v_x \le 0.22\text{ m/s}, \omega_z \le 2.84\text{ rad/s}$)
- `/tb1/odom` (`nav_msgs/msg/Odometry`): 주행 로봇 실시간 오도메트리
- `/tb1/camera/image_raw` (`sensor_msgs/msg/Image`): 전방 FPV 카메라 영상 (YOLOv8 추론용)
- `/tb2/cmd_vel` (`geometry_msgs/msg/Twist`): 보조 로봇 순찰 주행 지령
- `/tb2/odom` (`nav_msgs/msg/Odometry`): 보조 로봇 가상 공간 실시간 위치 동기화

### 3.2 WebSocket JSON 패킷 규격 (Port: 9090)
- **Unity $\rightarrow$ Relay (주행 명령)**:
  `{"cmd": "TWIST", "robot": "tb1", "linear": 0.15, "angular": 0.0}`
- **Relay $\rightarrow$ Unity (텔레메트리 20Hz)**:
  ```json
  {
    "type": "telemetry",
    "tb1": { "name": "tb1", "x": 0.5, "y": 0.0, "z": 1.2, "yaw": 45.0, "linear_vel": 0.15, "angular_vel": 0.0, "battery": 98.5 },
    "tb2": { "name": "tb2", "x": 1.8, "y": 0.0, "z": 4.0, "yaw": 180.0, "linear_vel": 0.22, "angular_vel": 0.0, "battery": 97.2 },
    "safety": { "interlock": false, "status": "NORMAL" }
  }
  ```
- **Relay $\rightarrow$ Unity (FPV 영상)**:
  바이너리 JPEG 바이트 배열 (640x480, 30fps)

---

## 4. 현재까지 완료된 핵심 구현 내역
1. **Python AI 서버 완성**:
   - `ros2_multi_turtlebot_relay.py`에 모의 시뮬레이션(--mock) 및 YOLOv8 다중 객체(작업자/타AGV/화물) 인터록 내장.
   - `test_relay_client.py` 실행 결과: 18KB JPEG 프레임 수신 및 TB1/TB2 텔레메트리 정상 동작 검증 완료.
2. **Unity 6 C# 엔진 및 씬 완성**:
   - 컴파일 에러 0건 (`unity_build.log` 통과).
   - `SceneSetupAutomation`을 통해 물류창고 바닥, 선반 랙 8개, 박스 적재물, 안전조끼 작업자 모델, TurtleBot3 Burger 2대(TB1 Cyan, TB2 Orange) 자동 배치 완료.
   - 키보드(WASD) 및 MetaQuest 썸스틱으로 3D 차체 이동 및 `Tab` 키로 FPV 콕핏 시점 전환 정상 동작.

---

## 5. 방금 확정된 추가 설계 사항 (User Feedback 반영)
1. **God-View (거시 조감도) 관제 사이드바 UI**:
   - 화면 우측에 실시간 텍스트 상태 카드 출력 (TB1/TB2 배터리, 상태).
   - 비상 정지(인터록) 발생 시 해당 로봇의 색상을 **빨간색(Red) 경고 점멸**로 변경.
2. **전면 카메라 한계 및 휠 슬립 극복 '3단계 안전 탈출 시퀀스'**:
   - 터틀봇3는 전면 카메라만 있고 후방 카메라가 없으며 휠 슬립 오차가 발생할 수 있음.
   - **1단계 (궤적 역추적 안전 후진)**: 직전 2초간 지나온 안전 오도메트리를 거꾸로 0.5m만 역행 (방금 지나온 공간이므로 충돌 위험 제로).
   - **2단계 (제자리 선회 탐색)**: 0반경 제자리 회전으로 전면 카메라 시야를 45도 회전시켜 빈 통로 직접 탐색.
   - **3단계 (경로 확보 및 전진)**: YOLOv8이 빈 통로 확인 시 녹색 HUD 점등 후 전진 허용.

---

## 6. Claude에게 요청할 다음 잔여 과제 (Next Action Items)
1. **Unity UI 고도화**:
   - God-View 관제 사이드바 텍스트 패널 (`GodViewSidebarHUD.cs`)
   - 이상 로봇 외곽선/바디 적색 점멸 로직 (`RobotWarningVisualizer.cs`)
   - FPV 콕핏 3단계 탈출 가이드 화살표 HUD 오버레이
2. **대회 필수 제출물 5종 작성**:
   - [ ] 개발완료보고서 (A4 5페이지 이내)
   - [ ] AI Agent 기술설명서 (1페이지)
   - [ ] 대표 Test Case 5건 실측 기록서
   - [ ] 3분 시연영상 촬영 콘티 시나리오
   - [ ] 발표자료 PPT 10장 구성안
