# T-012 실기체 브리지 — 실행·E2E 점검·Level 3 마무리 계획

> 기준: 2026-10-01. 코드: `ai_relay_server/rosbridge_link.py`, `ros2_multi_turtlebot_relay.py`. 규격: `docs/PROTOCOL.md` (T-012 항목).
> 오프라인 검증: `python ai_relay_server/test_real_bridge.py` → `T-012 REAL BRIDGE TEST OK` (18항목).

---

## 1. 구조

```
[Unity 6 / Quest]  ──WS 9090──▶  [릴레이 (노트북, Windows Python 가능)]
                                   │  안전 게이트: 권한 → 장애물 정지·알림 → AUTO → 워치독 → 거리 인터록
                                   │              → 속도 상한 → LiDAR 전·후방 가드 → offline 정지
                                   ├─ rosbridge WS ─▶ TB2 (Humble)  /odom /scan ▲  /cmd_vel ▼
                                   └─ rosbridge WS ─▶ TB1 (Noetic)  /odom /scan ▲  /cmd_vel ▼
```
- **rosbridge 방식 채택 이유**: TB1이 ROS 1 Noetic → `ros1_bridge`는 ROS 1·2 동시 설치 필요(22.04에서 난도 높음). rosbridge는 양쪽 동일 JSON 프로토콜. 릴레이에 `rclpy`·DDS 설정·WSL 네트워크 불필요.
- URL을 준 로봇만 `real`, 나머지는 `sim` → TB2만 먼저 실기 연동 가능.

---

## 2. 실행

### 2.1 로봇 측 (최초 1회 설치)
| 로봇 | 설치 | 실행 (bringup과 별도 SSH 창) |
|---|---|---|
| TB2 Humble | `sudo apt install ros-humble-rosbridge-server` | `source /opt/ros/humble/setup.bash && ros2 launch rosbridge_server rosbridge_websocket_launch.xml` |
| TB1 Noetic | `sudo apt install ros-noetic-rosbridge-server` | `source /opt/ros/noetic/setup.bash && roslaunch rosbridge_server rosbridge_websocket.launch` |

- 둘 다 기본 포트 9090 (로봇 IP라 노트북 릴레이 9090과 충돌 없음).
- **TB1 주의**: TB3 기본 설정은 `ROS_MASTER_URI`가 원격 PC를 가리킴 → 단독 구동 시 `export ROS_MASTER_URI=http://localhost:11311`, `export ROS_HOSTNAME=172.30.1.23` 후 bringup.

### 2.2 토픽 네임스페이스 확인 (필수)
인계서의 `__ns:=/tb2` 인자는 `ros2 launch`에서 무시될 수 있음.
```bash
ros2 topic list | grep -E "odom|scan|cmd_vel"     # TB2
rostopic list | grep -E "odom|scan|cmd_vel"       # TB1
```
| 결과 | 릴레이 인자 |
|---|---|
| `/odom`, `/cmd_vel` | 생략 (기본 `""`) |
| `/tb2/odom`, `/tb2/cmd_vel` | `--tb2-ns tb2` |

### 2.3 로봇 배치 (odom 원점 = bringup 시작 위치)
| 로봇 | Unity 스폰 (`SPAWN_POSES`) | 현장 배치 |
|---|---|---|
| tb1 | (0, 0), +z 방향 | 기준점, 정면 = 통로 방향 |
| tb2 | (1.8, 5.0), 180° | tb1 정면 5.0m·우측 1.8m, tb1을 마주봄 |

- 공간이 좁으면 `ros2_multi_turtlebot_relay.py`의 `SPAWN_POSES` 수정 (Unity 씬 배치도 함께 고려).
- bringup 재시작 = odom 0 리셋 → 로봇을 스폰 위치에 다시 놓고 재시작.

### 2.4 릴레이 (노트북)
```powershell
# TB2만 실기 (지금 바로 가능)
python ai_relay_server/ros2_multi_turtlebot_relay.py --no-ai --tb2-url ws://172.30.1.28:9090

# 2대 실기
python ai_relay_server/ros2_multi_turtlebot_relay.py --tb1-url ws://172.30.1.23:9090 --tb2-url ws://172.30.1.28:9090

# [대안] 검증된 2호기 하드웨어를 소프트웨어 tb1 역할로 (YOLO·LiDAR 인터록, 탈출 경로 표시, AUTO는 tb1 전용)
python ai_relay_server/ros2_multi_turtlebot_relay.py --tb1-url ws://172.30.1.28:9090 --tb1-ros 2
```
| 옵션 | 기본 | 의미 |
|---|---|---|
| `--tbN-url` | 없음(sim) | rosbridge 주소 |
| `--tbN-ros` | tb1=1, tb2=2 | 메시지 타입 형식 |
| `--tbN-ns` | `""` | 토픽 접두 |
| `--real-max-linear` | 0.15 | 실기 선속도 상한 m/s |
| `--real-patrol` | off | 실기 tb2 개루프 순찰 허용 |
| `--allow-no-scan` | off | scan 없이 전·후진 허용 (비권장) |
| `--camera-url` | 없음 | 전방 카메라 MJPEG (없으면 가상 프레임) |

정상 로그: `[tb2] rosbridge connected ...` → `[REAL GUARD] tb2 clear`.

---

## 3. 안전 동작 요약 (코드 = PROTOCOL.md)
| 조건 | 동작 |
|---|---|
| odom 0.5s 무수신 | `online=false`, 지령 0 |
| scan 1.0s 무수신 | 전·후진 차단 (회전만 허용) |
| `front_min` < 0.35m | 전진 차단. 실기 tb1이면 인터록 → 정지·알림 (T-015) |
| `rear_min` < 0.20m | 후진 차단 (수동 후진 포함) |
| 지령 > 0.15 m/s | 0.15로 제한, 각속도 1.5 rad/s 제한 |
| Unity 0.5s 무입력 | 워치독 → 0 (기존 T-006) |
| Unity 연결 해제 | 양쪽 0 |
| rosbridge 재접속 / 릴레이 Ctrl+C | 0 송신 |
| Unity 클라이언트 지연 | 제어 루프와 분리됨 → cmd_vel 계속 갱신 (이번에 발견·수정한 결함) |

**남은 위험 (현장 확인 필요)**
- 릴레이 **강제 종료**·Wi-Fi 단절 시 로봇이 마지막 속도를 유지하는지는 펌웨어 의존 → §4 S4-5에서 확인.
- rosbridge는 인증 없음 → 같은 Wi-Fi의 누구나 조종 가능. 시연 후 rosbridge 종료.
- LDS `range_min`(0.12m) 미만 물체는 측정 불가.

---

## 4. E2E 점검 체크리스트

### S0. 오프라인 (노트북만)
- [ ] `python ai_relay_server/test_real_bridge.py` → `T-012 REAL BRIDGE TEST OK`.
- [ ] `python -m py_compile ai_relay_server/*.py`.

### S1. 네트워크·rosbridge
- [ ] 노트북이 `olleh_GiGA_WiFi_1141` 접속, `ping 172.30.1.28` 응답.
- [ ] TB2 bringup + rosbridge 실행, `Test-NetConnection 172.30.1.28 -Port 9090` → True.
- [ ] 네임스페이스 확인 (§2.2).

### S2. 릴레이 ↔ TB2 (**바퀴 들어 올린 상태**)
- [ ] 릴레이 실행 → `[tb2] rosbridge connected`, `[REAL GUARD] tb2 clear`.
- [ ] `python ai_relay_server/test_relay_client.py` → TB2 x/z 출력.
- [ ] 손으로 TB2 회전 → 텔레메트리 `yaw` 변화 (odom 수신).
- [ ] 손을 LiDAR 전방 30cm에 → `front_min` ≈ 0.3.

### S3. Unity (PC 화면)
- [ ] Unity Play → 사이드바 TB2 카드 값 갱신.
- [ ] 바닥에서 TB2를 손으로 밀기 → Unity TB2 모델 동일 방향 이동 (좌표축 확인).
- [ ] TB2 클릭 → FPV → 릴레이 로그 `Teleop handover tb1 -> tb2`.
- [ ] (바퀴 든 상태) `W` → 바퀴 전진 회전, `S` → 후진, `A/D` → 좌우 반대 회전.
- [ ] 키 뗌 → 즉시 정지. `Space` → 정지.

### S4. 실주행·안전 (바닥, 반경 2m 비움, 1명은 로봇 옆 대기)
- [ ] S4-1 `W` 유지 → 0.15 m/s 이하 주행, Unity 모델 동기 이동.
- [ ] S4-2 전방 0.35m에 상자 → 전진 정지, 로그 `front 0.3xm`.
- [ ] S4-3 후방 0.2m에 상자 → `S` 후진 정지.
- [ ] S4-4 Unity 창 닫기 → 로봇 정지.
- [ ] S4-5 저속 주행 중 **작업관리자로 python 강제 종료** → 로봇 정지 여부 기록. 멈추지 않으면 시연 중 속도 상한 0.10으로 낮추고 비상정지 담당자 배치.
- [ ] S4-6 노트북 Wi-Fi 끄기 → 동일 기록.
- [ ] S4-7 (tb1 역할 실기) 전방 0.3m 장애물 유지 → `STOP` 정지 유지(자동 후진·회전 없음) + 탈출 경로 표시, Unity 적색 점멸.

### S5. MetaQuest 2 — **현재 차단 (T-013)**
| 항목 | 상태 |
|---|---|
| 헤드셋에 씬 표출 | OpenXR 플러그인 미설치 (`manifest.json`에 `com.unity.xr.management`만) |
| 썸스틱 주행 | `AGVControllerInput.cs:106` `OVRInput` 전용 코드 → Link 모드 비활성 |
| PC=God-View / HMD=FPV 분리 | 미구현 |

T-013 완료 후 추가 점검:
- [ ] Link 연결 → Play → 헤드셋에 콕핏.
- [ ] 좌측 썸스틱 → TB 실주행, 놓으면 정지.
- [ ] A/X 버튼 → STOP, B/Y → God-View 복귀.
- [ ] 헤드셋 벗기(프로세스 일시정지) → 워치독 0.5s 정지.

---

## 5. Level 3 MVP 마무리 계획

> ※ 2026-10-02 갱신: 3-Step Escape는 T-015(정지·알림 + LiDAR 탈출 경로)로 대체. 아래 5.2·5.3 표는 당시 수정 목록 기록이며, 보고서·콘티에는 반영 완료.

### 5.1 우선순위
| 순서 | 작업 | 담당 | 비고 |
|---|---|---|---|
| 1 | S1~S4 현장 점검 (TB2) | human | 결과를 Test Case 증거로 사용 |
| 2 | 촬영 방식 결정: VR 포함(T-013 선행) vs PC 화면 조작 | human | 아래 5.2 |
| 3 | T-013 OpenXR + 입력 전환 | claude + human(에디터 설치) | VR 촬영 시 필수 |
| 4 | 콘티 수정 → 촬영 | human | |
| 5 | 보고서 사실관계 수정 | human (Claude 검수) | 아래 5.3 |
| 6 | `tools/package_submission.ps1` 패키징 | human | |

### 5.2 콘티 수정안 (실제 동작 기준)
| Scene | 현행 콘티 | 수정 |
|---|---|---|
| 1 God-View | TB2 자율 순찰 | 실기 TB2는 순찰 기본 off → `--real-patrol` 사용 또는 "대기 중 실기 로봇" 표현. 사이드바 `source=real` 강조 |
| 2 빙의 | 퀘스트 썸스틱 주행 | T-013 전: PC `WASD`. 실물 PIP에 바퀴 동기 주행 필수 노출 |
| 3 인터록 | YOLO가 작업자 감지, "모터 전원 물리 차단" | 실기 카메라 미연동 → **LiDAR 전방 0.35m 인터록**으로 시연 (상자·사람 다리). YOLO는 디지털 트윈 가상 프레임 시연으로 구분. "전원 차단" → "속도 지령 0 강제" |
| 4 Escape | 궤적 역추적 0.5m, 45°, 녹색 "통로 확보" | 직선 후진 0.15m(-0.10 m/s×1.5s), 90° 회전, 해제 시 `IDLE`. 후방 LiDAR 0.2m 가드 언급 |
| 5 마무리 | "3D 라이다 없이 카메라만으로" | 실기는 2D LDS 사용 → "저가 2D LiDAR + 비전 AI" |

### 5.3 `REPORT_5P.md` 사실관계 수정 목록
| 위치 | 현재 서술 | 코드 사실 |
|---|---|---|
| §2.2 Memory | 직전 2초 궤적 링버퍼 | 없음. 상태머신 5상태 + 시도 횟수만 |
| §3.2 1단계 | 궤적 역추적 0.5m | 직선 후진 약 0.15m |
| §3.2 2단계 | 45도 선회 | 90도 |
| §3.2 3단계 | 녹색 HUD 후 전진 허용 | 인터록 해제 시 `IDLE` 복귀 (녹색 HUD 코드 없음) |
| §3.1 | 실카메라 YOLO 차단 | 실기 카메라 미연동. 실기 인터록은 LiDAR (T-012) |
| TC-01 | 실측 person 0.88 PASS | 실기 증거 없음 → S4-2(LiDAR) 결과로 교체 또는 "시뮬레이션"으로 명시 |
| TC-04 | 궤적 역추적 성공 | S4-7 결과로 교체 |
| §5.1 | 슬립 1cm 미만 억제, 360도 확인 | 측정 근거 없음 → 삭제 또는 향후 과제로 |
| §5.2 | LiDAR 대신 카메라만으로 동일 등급 | 실기는 LiDAR 병용 → 표현 수정 |
| 신규 | — | 실기 브리지 TC 추가: `test_real_bridge.py` 18항목 + S4 현장 결과 |

---

## 6. 보안 메모
- `docs/handoff/20261001_TURTLEBOT_HARDWARE_HANDOVER.md`에 Wi-Fi·SSH 비밀번호 평문 → **커밋 금지** (제출 ZIP은 `docs/handoff/` 제외됨).
