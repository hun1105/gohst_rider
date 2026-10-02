# TurtleBot3 자율탐색 패키지 이전 및 배포 가이드

본 문서는 `tb3_dynamic_detector` (TurtleBot3 동적 장애물 필터링 + Frontier 탐색 + Nav2 Dijkstra 경로 계획) 패키지를 다른 노트북이나 다른 TurtleBot 기기로 이전할 때 필요한 모든 설정과 전달 값을 정리한 가이드입니다.

---

## 1. 다른 노트북으로 전달할 필수 항목 요약

| 구분 | 전달 대상 | 실제 값 / 예시 | 목적 |
| :--- | :--- | :--- | :--- |
| **코드 파일** | 알고리즘 압축본 | `tb3_frontier_nav_algorithm.zip` | 전체 ROS2 패키지 소스 |
| **로봇 IP** | TurtleBot3 Wi-Fi IP | 예: `192.168.0.30` | SSH 및 DDS 통신 접속 |
| **DDS 환경변수**| Discovery Server 주소 | `export ROS_DISCOVERY_SERVER=<터틀봇_IP>:11811` | 호스트-로봇 간 노드 매칭 |
| **로봇 기종** | TurtleBot3 모델명 | `export TURTLEBOT3_MODEL=burger` (또는 `waffle`) | 로봇 크기, URDF, Footprint |
| **호스트 경로** | 새 노트북 윈도우 계정명 | `/mnt/c/Users/<새_사용자명>/...` | 지도 저장 절대 경로 수정 |

---

## 2. 새 노트북 환경 설정 및 빌드 절차

### 1단계: 필수 ROS2 Humble 패키지 설치
```bash
sudo apt update
sudo apt install -y \
  ros-humble-navigation2 \
  ros-humble-nav2-bringup \
  ros-humble-cartographer \
  ros-humble-cartographer-ros \
  ros-humble-turtlebot3 \
  ros-humble-turtlebot3-msgs \
  ros-humble-explore-lite
```

### 2단계: 워크스페이스 생성 및 압축 해제
```bash
mkdir -p ~/tb3_dynamic_ws/src
cd ~/tb3_dynamic_ws/src

# Windows에 있는 zip 파일을 WSL2로 복사하여 압축 해제
cp /mnt/c/Users/<사용자명>/Desktop/tb3_frontier_nav_algorithm.zip .
unzip tb3_frontier_nav_algorithm.zip
rm tb3_frontier_nav_algorithm.zip
```

### 3단계: 빌드 및 환경 설정
```bash
cd ~/tb3_dynamic_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash
```

### 4단계: `~/.bashrc` 자동 등록
```bash
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
echo "source ~/tb3_dynamic_ws/install/setup.bash" >> ~/.bashrc
echo "export TURTLEBOT3_MODEL=burger" >> ~/.bashrc
echo "export ROS_DISCOVERY_SERVER=192.168.0.30:11811" >> ~/.bashrc
```

---

## 3. 기기/노트북 변경 시 코드 수정 체크리스트

1. **지도 저장 절대경로 수정**:
   - 수정 파일: `src/tb3_dynamic_detector/launch/slam_dynamic_frontier_super_manager.launch.py`
   - 수정 위치: `map_path` 기본값 (`/mnt/c/Users/<새_계정명>/...`)
   - 수정 파일: `src/tb3_dynamic_detector/tb3_dynamic_detector/map_snapshot_saver.py`
   - 수정 위치: `DEFAULT_MAP_PATH` 변수

2. **로봇 모델 변경 시 (Burger -> Waffle)**:
   - 터미널: `export TURTLEBOT3_MODEL=waffle`
   - 수정 파일: `src/tb3_dynamic_detector/config/burger_clearance.yaml`
     - `robot_radius`: `0.105` -> `0.22` (또는 `footprint` 값 수정)

3. **TurtleBot Wi-Fi IP 변경 시**:
   - `~/.bashrc` 내 `ROS_DISCOVERY_SERVER` IP 주소 변경
   - SSH 연결 테스트: `ssh <계정>@<새_터틀봇_IP>`

---

## 4. 타 LLM 공유용 요약 프롬프트

```markdown
[TurtleBot3 동적 장애물 필터링 및 프론티어 자율주행 파이프라인 분석 요청]

본 프로젝트는 TurtleBot3와 FastDDS Discovery Server를 기반으로 구축된 무인 자율주행 탐색 시스템입니다.

1. 주요 아키텍처:
- 센서 보정: sensor_freshness_filter (무선 통신 지연/역전 패킷 필터링)
- 동적 장애물 감지: dynamic_map_filter (LiDAR 기반 이동 물체 마스킹 및 /map_static 생성)
- 프론티어 변환: dynamic_frontier_adapter (explore_lite용 삼치화 지도 변환)
- 미지영역 탐색: explore_lite (Frontier 기반 탐색 목표점 추출)
- 전역 경로 계획: Nav2 Planner Server (Dijkstra / NavFn 알고리즘 적용)
- 통합 관리: slam_dynamic_frontier_super_manager.launch.py (FastDDS Super Client 기반 라이프사이클 복구 연동)

2. 질의 내용:
- 위 파이프라인의 데이터 플로우 검증 및 병목 구간 최적화 방안 제시
- 무인수상정(USV)/국방 무인체계 전용 통신 및 자율 탐색 기술로의 확장 방안 제언
```
