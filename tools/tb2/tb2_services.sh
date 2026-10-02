#!/usr/bin/env bash
# tb2_services.sh — TB2(Ubuntu 22.04 / Humble) bringup·rosbridge·카메라 백그라운드 서비스 관리
#
# 사용 (TB2에서, 일반 계정으로 실행 — 필요 시 내부에서 sudo):
#   bash tb2_services.sh diag            # 카메라 스택 진단 (수정 없음)
#   bash tb2_services.sh camera-legacy   # config.txt를 레거시 카메라 스택으로 전환 (백업 후, 재부팅 필요)
#   bash tb2_services.sh install         # systemd 서비스 3종 생성 (자동 시작은 안 함)
#   bash tb2_services.sh start|stop|restart|status [bringup|rosbridge|camera]
#   bash tb2_services.sh logs <bringup|rosbridge|camera>
#   bash tb2_services.sh check           # 9090·8080 포트, 스냅샷, 토픽 점검
#   bash tb2_services.sh enable|disable  # 부팅 시 자동 시작 on/off (시연 중에만 권장)
#   bash tb2_services.sh uninstall
set -u

# ==================== 현장 설정 ====================
TB3_MODEL="burger"
LDS_MODEL="LDS-02"               # 실측 LiDAR 모델 (인계서는 LDS-01 — 기체 스티커 확인)
ROS_DOMAIN="0"
WS_SETUP="$HOME/turtlebot3_ws/install/setup.bash"
CAM_DEV="/dev/video0"
CAM_PORT="8080"
CAM_RES="640x480"                # PROTOCOL 영상 규격
CAM_FPS="15"                     # 릴레이 YOLO 처리 속도에 맞춤 (30이면 지연 누적)
CAM_FORMAT="YUYV"                # TB2 실측(2026-10-02): 레거시 드라이버가 YUYV 제공, 15fps 확인
CAM_ENCODER="CPU"                # YUYV → CPU JPEG 인코딩 (MJPEG 소스일 때만 HW)
CAM_QUALITY="70"
# ===================================================

SERVICES=(bringup rosbridge camera)
RUN_USER="$(id -un)"
UNIT_DIR="/etc/systemd/system"
BOOT_CFG="/boot/firmware/config.txt"

unit() { echo "tb2-$1.service"; }
ros_env() {
    echo "source /opt/ros/humble/setup.bash; [ -f '$WS_SETUP' ] && source '$WS_SETUP'; export TURTLEBOT3_MODEL=$TB3_MODEL LDS_MODEL=$LDS_MODEL ROS_DOMAIN_ID=$ROS_DOMAIN"
}
targets() { if [ $# -gt 0 ] && [ -n "$1" ]; then echo "$(unit "$1")"; else for s in "${SERVICES[@]}"; do unit "$s"; done; fi; }

write_unit() {   # $1=이름 $2=설명 $3=ExecStart $4=추가 [Service] 줄
    sudo tee "$UNIT_DIR/$(unit "$1")" >/dev/null <<EOF
[Unit]
Description=$2
After=network-online.target
Wants=network-online.target

[Service]
User=$RUN_USER
WorkingDirectory=$HOME
ExecStart=$3
$4
Restart=on-failure
RestartSec=3
KillSignal=SIGINT
TimeoutStopSec=15

[Install]
WantedBy=multi-user.target
EOF
}

cmd_install() {
    command -v ustreamer >/dev/null || { echo "ustreamer 없음 → sudo apt install -y ustreamer v4l-utils (또는 문서의 소스 빌드)"; exit 1; }
    dpkg -s ros-humble-rosbridge-server >/dev/null 2>&1 || { echo "rosbridge 없음 → sudo apt install -y ros-humble-rosbridge-server"; exit 1; }
    sudo usermod -aG video,dialout "$RUN_USER"

    write_unit bringup "TB2 TurtleBot3 bringup" \
        "/bin/bash -c \"$(ros_env); exec ros2 launch turtlebot3_bringup robot.launch.py\"" ""
    write_unit rosbridge "TB2 rosbridge WebSocket :9090" \
        "/bin/bash -c \"$(ros_env); exec ros2 launch rosbridge_server rosbridge_websocket_launch.xml\"" ""
    # '+' 접두 = root로 실행 (레거시 V4L2 모듈 로드). 장치 노드 생성 대기 최대 10초.
    write_unit camera "TB2 Pi camera MJPEG :$CAM_PORT" \
        "$(command -v ustreamer) --device=$CAM_DEV --host=0.0.0.0 --port=$CAM_PORT --resolution=$CAM_RES --desired-fps=$CAM_FPS --format=$CAM_FORMAT --encoder=$CAM_ENCODER --quality=$CAM_QUALITY" \
        "ExecStartPre=+-/sbin/modprobe bcm2835-v4l2
ExecStartPre=/bin/sh -c 'for i in \$\$(seq 1 20); do [ -e $CAM_DEV ] && exit 0; sleep 0.5; done; echo \"$CAM_DEV 없음\"; exit 1'"
    sudo systemctl daemon-reload
    echo "설치 완료 (자동 시작 off). 시작: bash $0 start"
    echo "video 그룹 추가가 처음이면 재로그인 또는 재부팅 필요."
}

cmd_diag() {
    echo "== 카메라 스택 설정 ($BOOT_CFG)"
    grep -nE "^\s*(camera_auto_detect|start_x|gpu_mem|dtoverlay=(imx|ov))" "$BOOT_CFG" 2>/dev/null || echo "(관련 항목 없음)"
    echo "== 펌웨어 레거시 스택 파일"
    ls /boot/firmware/start4x.elf /boot/firmware/fixup4x.dat 2>&1
    echo "== vcgencmd"
    vcgencmd get_camera 2>&1
    echo "== 커널 센서 인식 (imx219=v2, ov5647=v1, imx708=v3, imx477=HQ)"
    sudo dmesg | grep -iE "imx219|ov5647|imx708|imx477|unicam|bcm2835-v4l2|mmal" | tail -n 15
    echo "== 로드된 모듈"
    lsmod | grep -E "bcm2835_v4l2|bcm2835_unicam|bcm2835_codec|imx|ov5647" || echo "(없음)"
    echo "== V4L2 장치"
    if command -v v4l2-ctl >/dev/null; then
        v4l2-ctl --list-devices 2>&1
        [ -e "$CAM_DEV" ] && v4l2-ctl -d "$CAM_DEV" --list-formats-ext 2>&1 | head -n 40
    else
        echo "v4l2-ctl 없음 → sudo apt install -y v4l-utils"
    fi
    cat <<'EOF'
== 해석
- 'unicam' 장치 + 포맷 RG10/pRAA/BA81(Bayer) → libcamera 전용 원시 센서. ustreamer 불가 → camera-legacy 전환
- 'mmal service' 장치 + YUYV/MJPG/H264 → 레거시 스택 정상. MJPG 있으면 CAM_FORMAT=MJPEG, CAM_ENCODER=HW
- 'UVC' 웹캠 → 레거시 전환 불필요, MJPG 지원 확인
- dmesg에 imx708(카메라 v3) → 레거시 스택 미지원 → USB 웹캠 대체 권장
EOF
}

cmd_camera_legacy() {
    if sudo dmesg | grep -qi imx708; then
        echo "카메라 v3(imx708) 감지 → 레거시 스택 미지원. 중단 (USB 웹캠 대체 권장)"; exit 1
    fi
    local bak="$BOOT_CFG.bak.$(date +%Y%m%d_%H%M%S)"
    sudo cp "$BOOT_CFG" "$bak" && echo "백업: $bak"
    sudo sed -i -E 's/^\s*camera_auto_detect=.*/camera_auto_detect=0/; s/^\s*(dtoverlay=(imx219|ov5647|imx477).*)$/# \1  # tb2_services: legacy/' "$BOOT_CFG"
    grep -qE "^\s*camera_auto_detect=" "$BOOT_CFG" || echo "camera_auto_detect=0" | sudo tee -a "$BOOT_CFG" >/dev/null
    grep -qE "^\s*start_x=1" "$BOOT_CFG" || echo "start_x=1" | sudo tee -a "$BOOT_CFG" >/dev/null
    grep -qE "^\s*gpu_mem=" "$BOOT_CFG" || echo "gpu_mem=128" | sudo tee -a "$BOOT_CFG" >/dev/null
    echo "bcm2835-v4l2" | sudo tee /etc/modules-load.d/bcm2835-v4l2.conf >/dev/null
    echo "변경 후:"; grep -nE "camera_auto_detect|start_x|gpu_mem" "$BOOT_CFG"
    echo "→ sudo reboot 후 'vcgencmd get_camera'가 detected=1 인지 확인. 복구: sudo cp $bak $BOOT_CFG"
}

cmd_check() {
    local fail=0
    for p in 9090 "$CAM_PORT"; do
        if ss -ltn | grep -q ":$p "; then echo "[PASS] TCP $p 리슨"; else echo "[FAIL] TCP $p 닫힘"; fail=$((fail+1)); fi
    done
    local code
    code=$(curl -s -o /tmp/tb2_snap.jpg -w "%{http_code}" --max-time 3 "http://127.0.0.1:$CAM_PORT/snapshot")
    if [ "$code" = 200 ]; then echo "[PASS] 카메라 스냅샷 $(stat -c %s /tmp/tb2_snap.jpg) bytes"
    else echo "[FAIL] 카메라 스냅샷 HTTP $code"; fail=$((fail+1)); fi
    # shellcheck disable=SC1090
    eval "$(ros_env)"
    local topics; topics=$(timeout 8 ros2 topic list 2>/dev/null)
    for t in /odom /scan /cmd_vel; do
        if echo "$topics" | grep -qx "$t"; then echo "[PASS] 토픽 $t"; else echo "[FAIL] 토픽 $t 없음"; fail=$((fail+1)); fi
    done
    echo "FAIL $fail"; return "$fail"
}

case "${1:-}" in
    diag) cmd_diag ;;
    camera-legacy) cmd_camera_legacy ;;
    install) cmd_install ;;
    start|stop|restart|status) sudo systemctl "$1" $(targets "${2:-}") --no-pager ;;
    logs) journalctl -u "$(unit "${2:?bringup|rosbridge|camera}")" -n 80 -f ;;
    check) cmd_check ;;
    enable|disable) sudo systemctl "$1" $(targets "") ;;
    uninstall)
        sudo systemctl disable --now $(targets "") 2>/dev/null
        for s in "${SERVICES[@]}"; do sudo rm -f "$UNIT_DIR/$(unit "$s")"; done
        sudo systemctl daemon-reload; echo "삭제 완료" ;;
    *) sed -n '2,13p' "$0"; exit 1 ;;
esac
