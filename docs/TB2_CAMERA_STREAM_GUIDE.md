# TB2 파이카메라 8080 스트리밍 — 진단·구성·상시 구동

> 대상: TB2 (172.30.1.28, Ubuntu 22.04 / Humble, Pi 4). 스크립트: `tools/tb2/tb2_services.sh`.
> 릴레이 측: `--camera-url http://172.30.1.28:8080/stream` (끊김 시 3초 주기 자동 재접속).

---

## 1. 원인 진단

| 관측 | 의미 |
|---|---|
| `vcgencmd get_camera` → `supported=1 detected=0, libcamera interfaces=1` | **커널(libcamera 스택)은 센서를 인식**. 레거시 스택은 미사용 → 케이블·센서는 정상일 가능성 높음 |
| `camera_auto_detect=1` + `start_x=1` 동시 설정 | 두 카메라 스택이 섞인 상태. `auto_detect=1`이 센서를 `unicam`(libcamera용)에 넘김 |
| `cam --list` segfault | Ubuntu Jammy 기본 libcamera 패키지 문제 → libcamera 경로 사용 불가 |
| `modprobe bcm2835-v4l2` 후 `/dev/video0` 생성, ustreamer 크래시 | `/dev/video0`가 **원시 Bayer 센서 노드**(unicam)이거나, 센서를 못 잡은 레거시 노드 → YUYV/MJPEG 출력 불가 |
| 8080 `ERR_CONNECTION_REFUSED`, 릴레이 `-138` | 스트리머 프로세스 없음 (네트워크 문제 아님) |

**결론**: 레거시 카메라 스택 하나로 통일 → `bcm2835-v4l2`가 YUYV·**하드웨어 MJPEG**를 제공 → ustreamer로 송출.
- 단, **카메라 v3(imx708)는 레거시 미지원** → USB 웹캠(UVC, MJPEG 지원)으로 대체가 가장 빠름.

---

## 2. 픽셀 포맷·해상도 확인 명령

```bash
sudo apt install -y v4l-utils
v4l2-ctl --list-devices                         # 장치 이름: 'unicam' / 'mmal service' / 'UVC'
v4l2-ctl -d /dev/video0 --info                  # 드라이버 이름
v4l2-ctl -d /dev/video0 --list-formats-ext      # 포맷 + 해상도 + fps
sudo dmesg | grep -iE "imx219|ov5647|imx708|imx477|unicam|mmal"   # 센서 모델

# 실제 캡처 시험 (MJPEG 640x480, 60프레임)
v4l2-ctl -d /dev/video0 --set-fmt-video=width=640,height=480,pixelformat=MJPG
v4l2-ctl -d /dev/video0 --stream-mmap --stream-count=60 --stream-to=/tmp/test.mjpg && ls -l /tmp/test.mjpg
```
| `--list-formats-ext` 결과 | 판정 | ustreamer 설정 |
|---|---|---|
| `MJPG`, `YUYV`, `H264` (mmal service) | 레거시 정상 | `--format=MJPEG --encoder=HW` (CPU 거의 0) |
| `YUYV`만 | 사용 가능 | `--format=YUYV --encoder=CPU` (Pi 4 CPU 사용, 15fps 권장) |
| `RG10`, `pRAA`, `BA81` 등 Bayer (unicam) | **사용 불가** | §3 레거시 전환 |

`tools/tb2/tb2_services.sh diag`가 위 명령을 한 번에 실행하고 해석을 출력.

---

## 3. 레거시 카메라 스택 전환 (v1·v2·HQ 카메라)

```bash
bash tb2_services.sh camera-legacy     # config.txt 백업 → 아래 변경 → 재부팅 안내
sudo reboot
vcgencmd get_camera                    # 기대: supported=1 detected=1
bash tb2_services.sh diag              # 기대: 'mmal service', MJPG 포맷
```
스크립트가 하는 변경:
| 항목 | 값 |
|---|---|
| `camera_auto_detect` | `0` (센서 자동 오버레이 끔) |
| `dtoverlay=imx219/ov5647/imx477` | 주석 처리 |
| `start_x` / `gpu_mem` | `1` / `128` (없을 때만 추가) |
| `/etc/modules-load.d/bcm2835-v4l2.conf` | 부팅 시 `bcm2835-v4l2` 자동 로드 |

- 카메라 v3(imx708) 감지 시 중단.
- `/boot/firmware/start4x.elf` 없으면 레거시 스택 기동 불가 → `sudo apt install --reinstall linux-firmware-raspi` 후 재시도.
- 복구: 출력된 백업 파일을 `config.txt`로 복사 후 재부팅.

---

## 4. 스트리머 선택

| 후보 | CPU (640x480) | 장점 | 단점 | 판정 |
|---|---|---|---|---|
| **ustreamer** | MJPEG HW 시 매우 낮음 | `/stream`·`/snapshot` 기본 제공, 끊김 복구, 단일 바이너리 | 레거시/UVC 노드 필요 | **채택** |
| mjpg-streamer | 낮음 | 오래 쓰임 | Ubuntu 패키지 없음, 유지보수 중단 | 보류 |
| v4l2_camera + web_video_server | 높음 (raw 이미지 → DDS → JPEG 재인코딩) | ROS 토픽(`/image_raw`) 동시 확보 | Pi 4에서 bringup과 CPU 경합, 지연 | 비권장 |

설치:
```bash
sudo apt install -y ustreamer v4l-utils ros-humble-rosbridge-server
# apt에 ustreamer가 없으면 소스 빌드
sudo apt install -y build-essential libevent-dev libjpeg-dev libbsd-dev git
git clone --depth=1 https://github.com/pikvm/ustreamer && cd ustreamer && make && sudo make install
```

수동 단독 시험:
```bash
ustreamer --device=/dev/video0 --host=0.0.0.0 --port=8080 \
  --resolution=640x480 --desired-fps=15 --format=MJPEG --encoder=HW --quality=70
# PC 브라우저: http://172.30.1.28:8080/stream  (스냅샷: /snapshot)
```
- **15fps 권장 이유**: 릴레이는 프레임마다 YOLO 추론 → 30fps 공급 시 수신 버퍼에 프레임이 쌓여 지연 증가 = 인터록이 옛 영상으로 판단.

---

## 5. 상시 구동 (systemd)

PC에서 TB2로 복사:
```powershell
scp tools/tb2/tb2_services.sh user@172.30.1.28:~/
```
TB2에서:
```bash
bash ~/tb2_services.sh install      # 서비스 3종 생성 (부팅 자동 시작은 off)
bash ~/tb2_services.sh start        # bringup + rosbridge + camera
bash ~/tb2_services.sh check        # 9090·8080·스냅샷·토픽 PASS 확인
bash ~/tb2_services.sh logs camera  # 실시간 로그
bash ~/tb2_services.sh stop         # 시연 종료 시
```
| 서비스 | 내용 | 실패 시 |
|---|---|---|
| `tb2-bringup` | `turtlebot3_bringup robot.launch.py` (`LDS_MODEL=LDS-02`) | 3초 후 재시작 |
| `tb2-rosbridge` | `rosbridge_websocket_launch.xml` (:9090) | 3초 후 재시작 |
| `tb2-camera` | `bcm2835-v4l2` 로드 → `/dev/video0` 대기 → ustreamer (:8080) | 3초 후 재시작 |

- 스크립트 상단 `현장 설정`에서 모델·포맷·fps 변경. YUYV만 지원 시 `CAM_FORMAT=YUYV`, `CAM_ENCODER=CPU`.
- 기존에 수동 실행 중인 bringup·rosbridge가 있으면 먼저 종료 (중복 노드 → 토픽 충돌).
- **부팅 자동 시작(`enable`)은 시연 기간에만**: rosbridge는 인증이 없어 같은 Wi-Fi의 누구나 조종 가능.
- bringup 재시작 = odom 원점 리셋 → 디지털 트윈 위치가 스폰 포즈로 점프. 로봇을 스폰 위치에 다시 놓을 것.
- 인계서 `LDS_MODEL=LDS-01` vs 현장 `LDS-02` 불일치 → 기체 스티커로 확정 후 스크립트 값 맞춤.

---

## 6. 릴레이 연결

```powershell
# 2호기를 소프트웨어 tb1 역할로 (카메라 YOLO 인터록·정지 알림·탈출 경로가 이 로봇에 적용)
python ai_relay_server/ros2_multi_turtlebot_relay.py --tb1-url ws://172.30.1.28:9090 --tb1-ros 2 --camera-url http://172.30.1.28:8080/stream
```
- 정상 로그: `카메라 스트림 연결: http://172.30.1.28:8080/stream`.
- 카메라가 늦게 켜지거나 끊겨도 3초마다 재접속 (이번 수정). 끊긴 동안 가상 프레임.
- 다른 해상도로 들어와도 640x480으로 맞춤 (YOLO 회랑 픽셀 기준 유지).
- **주의**: `--camera-url`은 `tb1` 전방 카메라로 취급 → TB2를 `tb2` 역할로 둔 채 넣으면 TB2 영상으로 가상 `tb1`이 인터록됨. 위처럼 2호기를 `tb1`로 실행.
- **주의**: 실제 카메라 + YOLO 활성 시 사람 인식만으로 실기 인터록 정지가 발동 (자동 후진·회전은 없음) → 첫 시험은 바퀴를 들고 진행.
- YOLO 사용 시 PC에 `pip install ultralytics` 필요.

---

## 7. 점검 순서
- [ ] `diag` → 센서 모델·포맷 확인 (§2 표로 판정).
- [ ] 필요 시 `camera-legacy` → 재부팅 → `detected=1`.
- [ ] ustreamer 수동 실행 → PC 브라우저 `/stream` 영상.
- [ ] `install` → `start` → `check` FAIL 0.
- [ ] PC 릴레이 `--camera-url` → Unity 윈드실드에 실영상.
- [ ] 바퀴 든 상태로 카메라 앞에 사람 → `INTERLOCK: person` + `[OBSTACLE] tb1 정지` 로그.
- [ ] 카메라 서비스 `restart` → 릴레이 로그 끊김 → 3초 내 재연결.

---

## 8. 타임아웃(`Stream timeout ... 3094 ms`) 장애 분기

증상 변화 `연결 거부` → `타임아웃` = 무언가 바뀜 (ustreamer는 떴으나 프레임 없음 / 재부팅 후 IP·방화벽 변화).

**PC에서 1회 실행 → 어느 단계에서 끊기는지 확정**
```powershell
python tools/check_camera_stream.py --host 172.30.1.28
```
| 첫 FAIL 단계 | 원인 | 조치 |
|---|---|---|
| [1] TCP 무응답 | 로봇 오프라인, 재부팅 후 IP 변경, `ufw` drop | `ping 172.30.1.28` → 공유기 DHCP 목록 확인 / TB2 `sudo ufw allow 8080/tcp; sudo ufw allow 9090/tcp` |
| [1] TCP 거부 | ustreamer 미기동 | `bash ~/tb2_services.sh status camera`, `logs camera` |
| [2] `online=False` / [3] 503 / [4] 헤더만 | **서버는 정상, 카메라 프레임 없음** (릴레이 타임아웃과 동일 증상) | TB2 `diag` → Bayer면 `camera-legacy`+재부팅 / `MJPG` 없으면 `CAM_FORMAT=YUYV CAM_ENCODER=CPU` / `sudo fuser -v /dev/video0`로 중복 점유 프로세스 종료 |
| [4] fps < 5 | Wi-Fi 대역폭, 어두운 조명(노출 증가), YUYV CPU 인코딩 | 15fps·quality 60, 조명 확보 |
| [5]만 FAIL | OpenCV/FFmpeg 프로브 지연 | 릴레이 `--camera-open-timeout-ms 15000` (기본 8000) |

**TB2에서 함께 확인 (네트워크 배제: 로봇 자신에게 요청)**
```bash
bash ~/tb2_services.sh status camera; journalctl -u tb2-camera -n 40 --no-pager
ss -ltnp | grep -E ':8080|:9090'
curl -s http://127.0.0.1:8080/state; echo
curl -s -o /dev/null -w "snapshot %{http_code} %{size_download}B\n" http://127.0.0.1:8080/snapshot
bash ~/tb2_services.sh diag
sudo ufw status; sudo fuser -v /dev/video0
```
- 로봇 내부 `snapshot 200`인데 PC에서 실패 → 네트워크·방화벽.
- 로봇 내부에서도 `503`/`online:false` → 카메라 스택.

---

## 9. 해결 기록 (2026-10-02)
| 원인 | 근거 | 조치 |
|---|---|---|
| ① 런처 인자 오류: `ustreamer -m 15` (`-m` = `--format`) | `Unknown pixel format: 15` 후 즉시 종료 → 8080 미개방. `&` 백그라운드라 bringup에 가려 안 보임 | `launch/start_tb2_robot.bat`, `start_all.sh` → `-m YUYV -f 15 -q 70 --persistent` |
| ② 카메라 스택 충돌: `camera_auto_detect=1` | `imx219`+`bcm2835_unicam` 로드, `detected=0`. `/dev/video0` `Unable to start capturing`, `/dev/video1`(unicam) YUYV/MJPEG 거부 → `online:false` 빈 화면 | `config.txt` 33행 `camera_auto_detect=0` (백업 `config.txt.bak.20261002_004327`), `bcm2835-v4l2` 부팅 자동 로드 |

검증: `detected=1` → ustreamer `online:true` 15fps → PC `check_camera_stream.py` 5단계 PASS (OpenCV 열기 141ms) → 릴레이 `카메라 스트림 연결`.
남은 문제: 실영상 하단 절반이 로봇 구조물에 가려짐 → YOLO 회랑(하단 영역) 판정 불가. 카메라 마운트 각도·위치 조정 필요.
