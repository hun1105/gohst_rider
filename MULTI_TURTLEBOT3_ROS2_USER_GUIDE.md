# [운용 매뉴얼] ROS 2 Humble 다중 TurtleBot3 Burger + MetaQuest VR 디지털 트윈 연동 가이드

## 1. 시스템 구조 개요
본 시스템은 **ROS 2 Humble** 기반의 TurtleBot3 Burger 2대(`tb1`: 주행 로봇, `tb2`: 순찰/장애물 로봇)와 **MetaQuest 2 VR 디지털 트윈(Unity 6)**을 실시간 연동하는 피지컬 AI 솔루션입니다.

```
+-----------------------------------------------------------------------------------+
|                            ROS 2 Humble Ecosystem                                 |
|                                                                                   |
|  [TurtleBot3 #1: tb1]                           [TurtleBot3 #2: tb2]             |
|   - /tb1/cmd_vel (주행 수신)                     - /tb2/cmd_vel (순찰 자율 주행)   |
|   - /tb1/odom (위치 송신)                        - /tb2/odom (위치 송신)          |
|   - /tb1/camera/image_raw (FPV 전방 영상)                                         |
+----------------------------------------+------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
|                 AI Relay Server (ros2_multi_turtlebot_relay.py)                   |
|                                                                                   |
|  1. ROS 2 네임스페이스 라우팅 (/tb1, /tb2)                                        |
|  2. YOLOv8 객체 탐지 (작업자, tb2, 파렛트/화물)                                   |
|  3. 피지컬 AI 협착 방지 인터록 (충돌 회랑 진입 시 tb1 강제 비상 정지)             |
|  4. Unity 6 전용 고주파 Telemetry JSON 브로드캐스트 (20Hz)                        |
|  5. 1인칭 FPV JPEG 초저지연 스트리밍 (30fps)                                      |
+----------------------------------------+------------------------------------------+
                                         │ WebSocket (Port 9090)
                                         ▼
+-----------------------------------------------------------------------------------+
|                     Unity 6 Digital Twin (MetaQuest 2 VR)                         |
|                                                                                   |
|  - 3D 절차적 TurtleBot3 Burger 2대 모델 렌더링 (TB1: Cyan, TB2: Orange)           |
|  - Real2Sim 위치 동기화 (Vector3.Lerp, Quaternion.Slerp)                          |
|  - Sim2Real 텔레오퍼레이션 (VR 썸스틱 -> /tb1/cmd_vel)                            |
|  - FPV 1인칭 콕핏 시야 & 거시적 조감도(God-View) 원클릭 전환 (Tab / 컨트롤러 버튼)|
|  - 피지컬 AI 비상 정지 HUD 알람                                                   |
+-----------------------------------------------------------------------------------+
```

---

## 2. ROS 2 Humble 토픽 명세

| 로봇 네임스페이스 | 토픽명 | 메시지 타입 | 용도 |
| :--- | :--- | :--- | :--- |
| `tb1` (주행 로봇) | `/tb1/cmd_vel` | `geometry_msgs/msg/Twist` | VR 텔레오퍼레이션 주행 지령 ($v_x, \omega_z$) |
| `tb1` (주행 로봇) | `/tb1/odom` | `nav_msgs/msg/Odometry` | 실물 로봇 휠 엔코더+IMU 기반 위치 |
| `tb1` (주행 로봇) | `/tb1/camera/image_raw` | `sensor_msgs/msg/Image` | 전방 파이캠 영상 (YOLOv8 추론용) |
| `tb2` (순찰 로봇) | `/tb2/cmd_vel` | `geometry_msgs/msg/Twist` | 물류창고 자율 순찰 궤적 명령 |
| `tb2` (순찰 로봇) | `/tb2/odom` | `nav_msgs/msg/Odometry` | 실시간 위치 트윈 동기화 |

---

## 3. 실행 방법 (Step-by-Step)

### 단계 1: Python AI 릴레이 서버 실행
실물 하드웨어 유무와 관계없이 시뮬레이션 모드로 즉시 동작 가능합니다:
```bash
# 가상 시뮬레이션 및 AI 인터록 서버 기동
C:\Users\hun\ai_env\Scripts\python.exe 5_경남2026_피지컬AI_메타퀘스트VR_AGV\ai_relay_server\ros2_multi_turtlebot_relay.py --mock
```

### 단계 2: Unity 6 에디터 또는 VR 실행
1. Unity 6 프로젝트(`PhysicalAI_AGV_VR`)를 엽니다.
2. 상단 메뉴 `[PhysicalAI] -> [Setup Dual TurtleBot3 Warehouse Scene]`을 클릭하면 TB1, TB2, 선반 랙, 작업자가 자동 생성됩니다.
3. Unity **Play (▶)** 버튼을 클릭합니다.
4. 조작법:
   - **주행**: `W/A/S/D` 키보드 또는 MetaQuest 좌측 썸스틱
   - **시점 전환**: `Tab` 키 또는 MetaQuest 버튼 (거시적 조감도 $\leftrightarrow$ 1인칭 FPV 콕핏)
   - **비상 정지**: `Space` 키 또는 MetaQuest 트리거

### 단계 3: 실물 TurtleBot3 라즈베리파이 연결 시
각 TurtleBot3 라즈베리파이 터미널에서 다음 명령을 실행합니다:
```bash
# 로봇 1 (tb1)
ros2 run turtlebot3_bringup robot.launch.py __ns:=/tb1

# 로봇 2 (tb2)
ros2 run turtlebot3_bringup robot.launch.py __ns:=/tb2
```
