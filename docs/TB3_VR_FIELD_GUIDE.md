# TB3_VR_FIELD_GUIDE — TurtleBot3 실기 × MetaQuest 2 현장 연동 가이드

> 기준: 2026-10-01 코드. 진단 스크립트: `tools/check_tb3_connection.sh`.
> 관련: `docs/TB3_TRANSFER_GUIDE.md`, `docs/PROTOCOL.md`.

---

## 0. 먼저 읽을 것 — 현재 코드 기준 연동 공백

| # | 공백 | 근거 | 영향 |
|---|---|---|---|
| G1 | 릴레이가 항상 모의 모드 | `ros2_multi_turtlebot_relay.py:511` `--mock` = `store_true` + `default=True` → 끌 수 없음 | Unity 화면의 로봇 위치·영상은 시뮬레이션 |
| G2 | 릴레이에 ROS 2 코드 없음 | `rclpy` import 0건. `/cmd_vel` 발행·`/odom` 구독 없음 | VR 조작 → 실물 로봇 **안 움직임** |
| G3 | 로봇 노드가 빈 껍데기 | `turtlebot3_humble_robot_node.py` `cmd_vel_callback` = `pass`, 릴레이 접속 코드 없음 | 로봇 측 브리지 없음 |
| G4 | 카메라 주소 하드코딩 | `ros2_multi_turtlebot_relay.py:303` `http://192.168.0.101:8080/stream` (로봇 IP 아님) + 모의 모드라 미사용 | 실물 파이캠 영상 미표출 → YOLO도 가상 프레임 대상 |
| G5 | XR 공급자 플러그인 없음 | `Packages/manifest.json`에 `com.unity.xr.management`만 존재. OpenXR/Oculus XR 없음, `Assets/XR` 없음 | Quest Link로 Play해도 **헤드셋에 씬 안 뜸** |
| G6 | 썸스틱 코드 비활성 | `AGVControllerInput.cs:106` `#if UNITY_ANDROID \|\| OCULUS_SDK` + `OVRInput`(Meta SDK 미설치) | Link(Windows) 모드에선 WASD만 동작. Android 전환 시 컴파일 에러 |
| G7 | PC/헤드셋 화면 분리 미구현 | XR 카메라 분리(`targetEye`) 코드 없음 | God-View(PC) + FPV(Quest) 동시 표출 불가 |
| G8 | 두 시스템 토픽 체계 불일치 | `tb3_dynamic_detector` = `/scan`·`/odom`·`/cmd_vel`(네임스페이스 없음), 릴레이 문서 = `/tb1/...` | 통합 시 리매핑 필요 |
| G9 | 문서 버튼 매핑 불일치 | 통합문서 "우측 트리거 = STOP" vs 코드 `Button.One/Three`(A/X) | 촬영 시 조작 혼동 |

### 촬영 전략 (택1)
| 안 | 내용 | 정직성 | 준비 시간 |
|---|---|---|---|
| **A. 분리 시연** (오늘 가능) | ① 실물 TB3 = `tb3_dynamic_detector` 자율탐색(LiDAR SLAM·Frontier) ② Unity = 모의 릴레이 + PC 화면 WASD 조작 | 나레이션에 "디지털 트윈 시뮬레이션"·"실기 자율탐색" 구분 필수 | 0 |
| **B. 실연동** | G1~G7 해결 후 VR → 실물 주행 | 콘티 그대로 | 브리지(G1·G2·G4) + OpenXR(G5·G6) + 화면 분리(G7) 구현·현장 검증 필요 |

- 참고: `AGENTS.md`는 "LiDAR 없음"이지만 실물·`tb3_dynamic_detector`는 LDS LiDAR 사용 → 보고서 표현 통일 필요.

---

## 1. 사전 설정

### 1.1 라즈베리파이 Wi-Fi 고정 IP
**권장: 공유기 DHCP 예약** (MAC → `192.168.0.30`). SD카드 설정 실수로 접속 불능될 위험 없음.

대안: netplan (Pi 콘솔에서, 모니터·키보드 연결 상태로 진행)
```bash
# cloud-init이 netplan 덮어쓰는 것 방지
echo 'network: {config: disabled}' | sudo tee /etc/cloud/cloud.cfg.d/99-disable-network-config.cfg
sudo tee /etc/netplan/50-cloud-init.yaml >/dev/null <<'EOF'
network:
  version: 2
  wifis:
    wlan0:
      dhcp4: false
      addresses: [192.168.0.30/24]
      routes: [{to: default, via: 192.168.0.1}]
      nameservers: {addresses: [8.8.8.8]}
      access-points:
        "<SSID>": {password: "<PASSWORD>"}
EOF
sudo chmod 600 /etc/netplan/50-cloud-init.yaml
sudo netplan try    # 120초 내 Enter 안 누르면 자동 롤백
```
- 시연장 공유기 서브넷이 `192.168.0.x`가 아니면 주소·게이트웨이 변경.
- 5GHz 대역 권장 (2.4GHz는 DDS 패킷 유실 多).

### 1.2 시계 동기화 (필수)
Pi는 RTC 없음 → 부팅 직후 시계 오차 → TF `extrapolation` 에러, `sensor_freshness_filter`가 스캔 전량 폐기.
```bash
sudo apt install -y chrony
# 인터넷 없는 현장: Pi가 노트북(WSL) 시계를 따르도록
echo "server <노트북_IP> iburst" | sudo tee -a /etc/chrony/chrony.conf
sudo systemctl restart chrony && chronyc tracking
```
- 노트북 측(WSL)에도 chrony 설치 후 `allow 192.168.0.0/24` 추가.
- 진단 스크립트가 0.1s 초과 오차 시 FAIL.

### 1.3 Fast DDS Discovery Server (Pi 상주 서비스)
```bash
sudo tee /etc/systemd/system/fastdds-discovery.service >/dev/null <<'EOF'
[Unit]
Description=Fast DDS Discovery Server
After=network-online.target
Wants=network-online.target

[Service]
User=ubuntu
ExecStart=/bin/bash -c 'source /opt/ros/humble/setup.bash && fastdds discovery -i 0 -l 0.0.0.0 -p 11811'
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload && sudo systemctl enable --now fastdds-discovery
ss -uln | grep 11811     # UDP 리슨 확인
```
- `User=`는 실제 계정(`jshim` 또는 `ubuntu`)으로.
- Discovery Server는 **UDP** → 외부에서 `nc -z`(TCP) 점검은 항상 실패. 정상.

### 1.4 환경변수
| 위치 | `~/.bashrc` 추가 |
|---|---|
| Pi | `export TURTLEBOT3_MODEL=burger` / `export LDS_MODEL=LDS-01` (기체 스티커 확인, LDS-02 가능) / `export ROS_DISCOVERY_SERVER=127.0.0.1:11811` |
| 노트북 WSL | `export TURTLEBOT3_MODEL=burger` / `export ROS_DISCOVERY_SERVER=192.168.0.30:11811` / `export ROS_SUPER_CLIENT=TRUE` (CLI 도구용) / `export TB3_MAP_DIR=~/tb3_maps` |
| 양쪽 | `RMW_IMPLEMENTATION` 미설정 또는 `rmw_fastrtps_cpp` (CycloneDDS는 Discovery Server 불가) |

- 환경변수 변경 후 항상 `ros2 daemon stop` (데몬이 옛 설정 캐시).

### 1.5 WSL2 네트워크 (Windows 11)
기본 NAT 모드 → 로봇이 WSL로 DDS 응답 불가. **mirrored 모드 필수.**
```ini
# %UserProfile%\.wslconfig
[wsl2]
networkingMode=mirrored
```
```powershell
wsl --shutdown
# 관리자 PowerShell: WSL 인바운드 허용 (Hyper-V 방화벽)
Set-NetFirewallHyperVVMSetting -Name '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}' -DefaultInboundAction Allow
```
- 확인: WSL에서 `ip -4 addr`에 `192.168.0.x` 보이면 성공.
- Windows 방화벽이 "공용 네트워크"면 UDP 차단 → 시연장 Wi-Fi를 "개인"으로 변경.

### 1.6 MetaQuest 2 + Quest Link 체크리스트
| 항목 | 확인 |
|---|---|
| PC 앱 | Meta Quest Link 앱 설치·로그인, 헤드셋 페어링 |
| PC 앱 설정 | 일반 → **OpenXR 런타임 = Meta Quest Link** 활성 / 베타 → 개발자 런타임 기능 ON |
| 케이블 | USB 3 C타입, 앱 "장치 설정 → USB 테스트" 2Gbps 이상 |
| AirLink | PC 유선 LAN + 5GHz 공유기, 헤드셋·PC 같은 네트워크 |
| 헤드셋 | 빠른 설정 → Quest Link → 연결 → Link 홈 화면 진입 |
| 배터리 | 헤드셋·컨트롤러 80% 이상 (촬영 30분 기준) |
| Unity (G5 해결 전 필수) | Package Manager → **OpenXR Plugin** 설치 → Project Settings → XR Plug-in Management → Windows 탭 **OpenXR** 체크 → OpenXR → Interaction Profiles에 **Oculus Touch Controller Profile** 추가 |

---

## 2. 실행 순서

### 2.1 실기체 (Pi, SSH 터미널)
| 터미널 | 명령 | 정상 신호 |
|---|---|---|
| P0 | `systemctl status fastdds-discovery` | active (running) |
| P1 | `ros2 launch turtlebot3_bringup robot.launch.py` | LDS 회전, `/scan`·`/odom` 발행 |
| P2 (G4 해결 후) | `ros2 run v4l2_camera v4l2_camera_node --ros-args -p image_size:="[640,480]"` | `/image_raw` 발행 |
| P3 (G4 해결 후) | `ros2 run web_video_server web_video_server` | `http://192.168.0.30:8080/stream?topic=/image_raw` 브라우저 표출 |

- P2·P3 패키지: `sudo apt install ros-humble-v4l2-camera ros-humble-web-video-server`.
- 현재 릴레이는 카메라를 읽지 않음(G1·G4) → 안 A에선 P2·P3 생략.

### 2.2 호스트 노트북
| 터미널 | 위치 | 명령 |
|---|---|---|
| H1 | WSL | `bash tools/check_tb3_connection.sh` → FAIL 0 확인 |
| H2 | WSL | `ros2 launch tb3_dynamic_detector slam_dynamic_frontier_super_manager.launch.py` |
| H3 | WSL | `ros2 run rviz2 rviz2` (지도·Frontier 확인용, 선택) |
| H4 | Windows | `python ai_relay_server/ros2_multi_turtlebot_relay.py` (릴레이는 ROS 미사용 → Windows Python 가능) |

**H2 안전 주의**
- H2는 Nav2가 `/cmd_vel`을 직접 발행 → **로봇이 스스로 움직임.** 반경 2m 비우고 시작.
- 정지: H2 `Ctrl+C` 후 `ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist "{}"`.
- G2 해결 후에도 H2와 VR 텔레옵을 **동시에 켜지 말 것** (`/cmd_vel` 경합 → 예측 불가 주행).

### 2.3 Unity 6
1. H4 릴레이가 `running on ws://0.0.0.0:9090` 로그 출력 확인.
2. Unity Hub → `PhysicalAI_AGV_VR` 열기 → 콘솔 에러 0 확인.
3. Hierarchy → `WebSocketManager` → `serverUri` = `ws://127.0.0.1:9090` (릴레이가 다른 PC면 그 IP).
4. Quest Link 연결 → Link 홈 화면 진입.
5. Play ▶ → God-View + 우측 사이드바(F1 토글) 표출 → 카드 값 20Hz 갱신 확인.

---

## 3. 통신 검증

### 3.1 확인 포인트 (WSL)
| 대상 | 명령 | 기대값 |
|---|---|---|
| `/scan` | `ros2 topic hz /scan` | ≈5 Hz (LDS-01) |
| `/odom` | `ros2 topic hz /odom` | ≈20~30 Hz |
| `/tf` | `ros2 run tf2_ros tf2_echo odom base_footprint` | Translation 연속 출력 |
| TF 트리 | `ros2 run tf2_tools view_frames` | `map → odom → base_footprint → base_link → base_scan` 단일 트리 |
| `/map_static` | `ros2 topic echo --once --no-arr /map_static` | H2 기동 후 OccupancyGrid 1건 |
| WS 9090 | PowerShell `Test-NetConnection 127.0.0.1 -Port 9090` | `TcpTestSucceeded : True` |
| WS 데이터 | `python ai_relay_server/test_relay_client.py` | 영상 프레임 + 텔레메트리 수신 |

### 3.2 실패 예방 체크리스트
**DDS 서비스 드롭**
- [ ] Discovery Server를 systemd로 상주 (§1.3), 재부팅 후 자동 기동.
- [ ] CLI는 `ROS_SUPER_CLIENT=TRUE` 없으면 토픽 일부만 보임 → "토픽 없음" 오판 주의.
- [ ] 환경변수 변경 후 `ros2 daemon stop`.
- [ ] 노드 재시작 반복 시 Discovery Server 재시작 (`sudo systemctl restart fastdds-discovery`).

**패킷 유실**
- [ ] 5GHz, 로봇–공유기 직선거리 확보, 시연장 혼잡 채널 회피.
- [ ] 노트북 절전·Wi-Fi 절전 해제 (전원 옵션 → 고성능).
- [ ] RViz에서 `/scan` 표시 끄기 (대역폭 절감), 지도만 표시.
- [ ] `/scan`은 BEST_EFFORT → 구독 QoS `sensor_data`로 맞춤.

**TF 트리 불일치**
- [ ] 시계 오차 < 0.1s (§1.2).
- [ ] `odom → base_footprint` 발행자 1개만 (bringup). 다른 노드의 중복 TF 금지.
- [ ] `use_sim_time:=false` (실기).
- [ ] 네임스페이스 혼용 금지 (G8): 실기 단독 시 `/scan`, 다중 로봇 시 전 노드 `tb1/` 통일.

---

## 4. 인터랙션 점검 절차

| 단계 | 조작 | 기대 결과 | 현재 상태 |
|---|---|---|---|
| 1 | PC 화면에서 TB1 위로 마우스 이동 | 노란 헤일로 + 라벨 | 동작 |
| 2 | 좌클릭 | FPV 콕핏 전환, 릴레이 로그 `SELECT_ROBOT tb1` → `TELEPORT FPV` | 동작 (PC 화면) |
| 3 | 헤드셋 착용 | 콕핏 내부 시야 | **G5·G7 해결 필요** |
| 4 | 키보드 `W/A/S/D` | 사이드바 TB1 `linear_vel` ±0.22 | 동작 (모의 로봇) |
| 5 | 키 떼기 | 속도 0 (Unity가 0 명령 계속 송신). 워치독은 Unity 종료·통신 두절 시 0.5s 후 발동 | 동작 |
| 6 | `Space` | `STOP` 송신, 즉시 정지 | 동작 |
| 7 | 퀘스트 좌측 썸스틱 | 주행 | **G6 해결 필요** |
| 8 | `Tab`/`T`/`ESC` | God-View 복귀 | 동작 |
| 9 | TB2 클릭 → WASD | TB2 수동, 순찰 정지, TB1 1m 내 전진 차단 | 동작 |

- 4~9 단계의 "동작"은 **모의 로봇 기준.** 실물 주행은 G2 해결 후.

---

## 5. 진단 스크립트 `tools/check_tb3_connection.sh`

```bash
bash tools/check_tb3_connection.sh                 # 기본 192.168.0.30
bash tools/check_tb3_connection.sh 192.168.0.42    # IP 지정
TB3_USER=jshim RELAY_HOST=192.168.0.10 bash tools/check_tb3_connection.sh
```
| 단계 | 점검 | FAIL 시 조치 |
|---|---|---|
| 1 | ping, 같은 서브넷 여부 | Wi-Fi·IP, WSL mirrored |
| 2 | SSH 22, Discovery UDP 11811(SSH로 로봇 내부 확인), 시계 오차 | `ssh-copy-id`, §1.3, §1.2 |
| 3 | ROS 2 Humble, RMW, 모델 | §1.4 |
| 4 | `/scan` `/odom` `/tf` 메시지 + TF 조회, `/map_static`(선택) | bringup, QoS, Wi-Fi |
| 5 | 릴레이 9090 TCP | H4 실행 |

- WSL에서 실행 (Git Bash는 `ping` 문법 달라 오판).
- 소요 ≈ 30~50s. 종료코드 = FAIL 개수.
- SSH 키 미등록 시 2단계 원격 점검은 WARN으로 건너뜀.

---

## 6. `TB3_TRANSFER_GUIDE.md` 개선 제언

| # | 문제 | 제언 |
|---|---|---|
| 1 | §1·§3 "지도 절대경로 수정" 지시가 낡음 | T-009로 `TB3_MAP_DIR` 환경변수화 완료 → 해당 항목을 `export TB3_MAP_DIR=...`로 교체 |
| 2 | zip 기반 이전 → 버전 추적 불가 | `hardware_firmware/tb3_dynamic_detector`를 git 추적 후 `git clone`/`rsync`로 이전 |
| 3 | `explore_lite` apt 패키지 가정 | Humble apt 제공 여부 확인 필요. 미제공 시 `m-explore-ros2` 소스 빌드 절차 추가 |
| 4 | `ROS_SUPER_CLIENT` 누락 | CLI용 `export ROS_SUPER_CLIENT=TRUE` + `ros2 daemon stop` 명시 |
| 5 | Discovery Server 기동 방법 없음 | §1.3 systemd 서비스 절차 추가 |
| 6 | WSL2 NAT 문제 미언급 | mirrored 모드 + Hyper-V 방화벽 절차 추가 |
| 7 | 시계 동기화 미언급 | chrony 절차 추가 (freshness filter 오동작 원인 1순위) |
| 8 | `LDS_MODEL` 미언급 | Humble bringup 필수 변수로 명시 |
| 9 | `RMW_IMPLEMENTATION` 미언급 | Fast DDS 고정 명시 |
| 10 | 의존성 설치 후 `rosdep` 없음 | `rosdep install --from-paths src -y --ignore-src` 추가 |
| 11 | 빌드 후 검증 단계 없음 | `colcon test --packages-select tb3_dynamic_detector` + 진단 스크립트 실행 추가 |
| 12 | 로봇 모델 변경 시 `explore_params.yaml`·Nav2 footprint 누락 가능 | 변경 대상 파일 전체 목록화 |
| 13 | §4 타 LLM 프롬프트가 배포 문서에 혼재 | 별도 파일로 분리 |
