# [마스터 아키텍처] ROS 2 Humble 다중 TurtleBot3 Burger (2대) + MetaQuest VR 디지털 트윈 시스템

## 1. 프로젝트 개요 (Executive Summary)
- **대회명**: 2026 제4회 경남 AI·SW 경진대회
- **목표**: ROS 2 Humble 기반의 실물 TurtleBot3 Burger 2대(`tb1`: 주행 로봇, `tb2`: 순찰/장애물 로봇)와 MetaQuest 2 VR 디지털 트윈 연동 피지컬 AI 협착 방지 및 군집 물류 관제 시스템 구축
- **핵심 기술 스택**:
  1. **ROS 2 Humble 다중 에이전트 네임스페이스**: `/tb1`, `/tb2` 독립 토픽 파이프라인
  2. **Real2Sim 고정밀 공간 동기화**: `/tb1/odom`, `/tb2/odom` 기반 실시간 디지털 트윈 위치 매핑
  3. **Sim2Real 텔레오퍼레이션**: VR 썸스틱 지령 $\rightarrow$ `/tb1/cmd_vel` 실시간 주행 전달
  4. **비전 피지컬 AI 안전 인터록**: YOLOv8 기반 작업자(Worker) 및 타 AGV(`tb2`), 파렛트/화물 실시간 충돌 감지 및 모터 강제 비상 정지 (Shared Autonomy)
  5. **초저지연 1인칭 FPV 콕핏**: WebRTC/WebSocket JPEG 스트리밍 (30fps)

---

## 2. 하드웨어 및 소프트웨어 사양

### 2.1 하드웨어 사양 (TurtleBot3 Burger 2대)
| 구성 요소 | 부품 사양 | 역할 |
| :--- | :--- | :--- |
| **SBC** | Raspberry Pi 4 (Ubuntu 22.04 LTS + ROS 2 Humble) | ROS 2 노드, 파이캠 스트리밍 |
| **제어 보드** | OpenCR 1.0 (ARM Cortex-M7) | 휠 엔코더 오도메트리 계산, DYNAMIXEL 모터 PID 제어 |
| **구동 모터** | DYNAMIXEL XL430-W250 2EA | 차동 구동(Differential Drive), 최대 선속도 0.22 m/s |
| **비전 센서** | Raspberry Pi Camera Module v2 / USB 웹캠 | 전방 시야 확보 및 YOLOv8 다중 객체 검출 |
| **전원** | Li-Po 11.1V 1800mAh | 메인 전원 공급 |

### 2.2 소프트웨어 스택
- **로봇 OS**: ROS 2 Humble on Ubuntu 22.04 LTS
- **AI 릴레이 서버**: Python 3.12 (PyTorch CPU, Ultralytics YOLOv8, WebSockets)
- **VR & 디지털 트윈**: Unity 6.0 LTS (6000.0.84f1), Universal RP, .NET C#

---

## 3. ROS 2 토픽 및 데이터 인터페이스

```
[TurtleBot3 #1 (tb1)]                       [TurtleBot3 #2 (tb2)]
  ├── /tb1/odom ──────────────────────┐       ├── /tb2/odom ──────────────────────┐
  ├── /tb1/camera/image_raw ──────────┤       └── /tb2/cmd_vel <── (자율 순찰)     │
  └── /tb1/cmd_vel <───────────┐      │                                           │
                               │      │                                           │
                               ▼      ▼                                           ▼
                    [ROS 2 Humble Multi-Relay (ros2_multi_turtlebot_relay.py)]
                               │
               ┌───────────────┴───────────────┐
               ▼                               ▼
       [Physical AI Guard]           [Unity 6 Digital Twin]
       - YOLOv8 다중 객체 탐지        - TB1 (주행 로봇, Cyan) 3D 모델
       - 작업자 / TB2 충돌 회랑 감시   - TB2 (순찰 로봇, Orange) 3D 모델
       - 거리 1.0m 이내 비상 정지    - FPV 1인칭 콕핏 & 거시 조감도
       - /tb1/cmd_vel 강제 차단      - MetaQuest 썸스틱 입력 (/tb1/cmd_vel)
```

### 3.1 토픽 매핑 테이블
| 토픽명 | 메시지 타입 | 주기 | 설명 |
| :--- | :--- | :--- | :--- |
| `/tb1/cmd_vel` | `geometry_msgs/msg/Twist` | 20Hz | VR 컨트롤러로부터 수신한 선속도/각속도 ($v_x, \omega_z$) |
| `/tb1/odom` | `nav_msgs/msg/Odometry` | 30Hz | 주행 로봇 실물 엔코더 오도메트리 |
| `/tb1/camera/image_raw`| `sensor_msgs/msg/Image` | 30Hz | 전방 FPV 카메라 스트림 |
| `/tb2/cmd_vel` | `geometry_msgs/msg/Twist` | 20Hz | 창고 내 보조 로봇 순찰 궤적 명령 |
| `/tb2/odom` | `nav_msgs/msg/Odometry` | 30Hz | 보조 로봇 실시간 위치 동기화 |

---

## 4. Unity 6 - ROS 2 좌표계 매핑
- **수평 위치**: $X_{Unity} = X_{ROS2}, \quad Z_{Unity} = Z_{ROS2}$
- **방위각(Yaw)**: $\text{Rotation}_{Unity} = \text{Quaternion.Euler}(0, \text{Yaw}_{ROS2}, 0)$
- **스무딩**: `Vector3.Lerp` 및 `Quaternion.Slerp` 적용으로 네트워크 지연 시에도 부드러운 트윈 표현.

---

## 5. 실행 및 검증 완료 내역
- [x] Python Multi-TurtleBot ROS 2 릴레이 서버 구축 (`ai_relay_server/ros2_multi_turtlebot_relay.py`)
- [x] Unity 6 다중 에이전트 동기화 스크립트 작성 (`Assets/Scripts/TurtleBotMultiAgentManager.cs`)
- [x] TurtleBot3 Burger 정밀 3D 모델 절차적 생성기 구현 (`Assets/Scripts/TurtleBot3ModelBuilder.cs`)
- [x] 물류창고 환경(랙, 박스, 작업자) 및 TB1/TB2 자동 생성기 검증 (`Assets/Editor/SceneSetupAutomation.cs`)
- [x] FPV 영상 수신 및 텔레메트리 20Hz 송수신 E2E 테스트 통과 (`test_relay_client.py`)
