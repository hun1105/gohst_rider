#!/usr/bin/env bash
# check_tb3_connection.sh — TurtleBot3 ↔ 호스트(WSL2) 1분 연결 자가진단
# 사용: bash tools/check_tb3_connection.sh [TB3_IP]
# 환경변수로 덮어쓰기: TB3_IP TB3_USER DS_PORT RELAY_HOST RELAY_PORT TOPIC_TIMEOUT_S
# 종료코드: FAIL 개수 (0 = 전부 통과)
set -u

TB3_IP="${1:-${TB3_IP:-192.168.0.30}}"
TB3_USER="${TB3_USER:-ubuntu}"
DS_PORT="${DS_PORT:-11811}"
RELAY_HOST="${RELAY_HOST:-127.0.0.1}"
RELAY_PORT="${RELAY_PORT:-9090}"
TOPIC_TIMEOUT_S="${TOPIC_TIMEOUT_S:-6}"
MAX_CLOCK_SKEW_S="0.10"   # TF·freshness filter 허용 시계 오차
REQUIRED_TOPICS=(/scan /odom /tf)
OPTIONAL_TOPICS=(/map_static)   # tb3_dynamic_detector 기동 시에만 존재

PASS=0; WARN=0; FAIL=0
ok()   { printf '  \033[32m[PASS]\033[0m %s\n' "$*"; PASS=$((PASS+1)); }
warn() { printf '  \033[33m[WARN]\033[0m %s\n' "$*"; WARN=$((WARN+1)); }
bad()  { printf '  \033[31m[FAIL]\033[0m %s\n' "$*"; FAIL=$((FAIL+1)); }
tcp_open() { timeout 2 bash -c "</dev/tcp/$1/$2" 2>/dev/null; }
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=3 -o StrictHostKeyChecking=accept-new)

START=$(date +%s)
echo "== TB3 연결 진단: robot=$TB3_IP  discovery=$TB3_IP:$DS_PORT  relay=$RELAY_HOST:$RELAY_PORT"

echo "[1] 네트워크"
if ping -c 3 -W 1 "$TB3_IP" >/dev/null 2>&1; then
    ok "ping $TB3_IP"
else
    bad "ping $TB3_IP 무응답 (Wi-Fi·IP·같은 공유기 확인)"
fi
SUBNET="${TB3_IP%.*}."
if ip -4 addr 2>/dev/null | grep -q "inet ${SUBNET}"; then
    ok "호스트가 로봇과 같은 서브넷 (${SUBNET}x)"
else
    warn "호스트에 ${SUBNET}x 주소 없음 → WSL2 NAT 모드 의심 (.wslconfig networkingMode=mirrored)"
fi

echo "[2] SSH / Discovery Server"
SSH_OK=0
if tcp_open "$TB3_IP" 22; then
    ok "SSH 포트 22 열림"
    if ssh "${SSH_OPTS[@]}" "$TB3_USER@$TB3_IP" true 2>/dev/null; then
        SSH_OK=1; ok "SSH 키 로그인 ($TB3_USER)"
    else
        warn "SSH 키 로그인 불가 → 원격 점검 생략 (ssh-copy-id $TB3_USER@$TB3_IP)"
    fi
else
    bad "SSH 포트 22 닫힘"
fi
# Fast DDS Discovery Server는 기본 UDP → 외부 TCP 프로브 불가. SSH로 로봇 내부 소켓 확인.
if [ "$SSH_OK" = 1 ]; then
    if ssh "${SSH_OPTS[@]}" "$TB3_USER@$TB3_IP" "ss -uln | grep -q ':$DS_PORT '" 2>/dev/null; then
        ok "Discovery Server UDP $DS_PORT 리슨 중 (로봇)"
    else
        bad "Discovery Server 미기동 (로봇에서: fastdds discovery -i 0 -l 0.0.0.0 -p $DS_PORT)"
    fi
    REMOTE_T=$(ssh "${SSH_OPTS[@]}" "$TB3_USER@$TB3_IP" 'date +%s.%N' 2>/dev/null)
    LOCAL_T=$(date +%s.%N)
    if [ -n "$REMOTE_T" ]; then
        SKEW=$(awk -v a="$LOCAL_T" -v b="$REMOTE_T" -v m="$MAX_CLOCK_SKEW_S" \
            'BEGIN{d=a-b; if(d<0)d=-d; printf "%.3f %d", d, (d>m)}')
        if [ "${SKEW#* }" = 0 ]; then ok "시계 오차 ${SKEW% *}s"
        else bad "시계 오차 ${SKEW% *}s > ${MAX_CLOCK_SKEW_S}s → TF/스캔 폐기 위험 (chrony 동기화)"; fi
    fi
else
    warn "Discovery Server·시계 오차 점검 생략 (SSH 키 필요)"
fi

echo "[3] ROS 2 환경"
if [ -f /opt/ros/humble/setup.bash ]; then
    # shellcheck disable=SC1091
    source /opt/ros/humble/setup.bash
    [ -f "$HOME/tb3_dynamic_ws/install/setup.bash" ] && source "$HOME/tb3_dynamic_ws/install/setup.bash"
    export ROS_DISCOVERY_SERVER="$TB3_IP:$DS_PORT"
    export ROS_SUPER_CLIENT=TRUE   # CLI가 전체 그래프를 보려면 Super Client 필요
    ok "ROS 2 Humble 로드 (ROS_DISCOVERY_SERVER=$ROS_DISCOVERY_SERVER)"
    RMW="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"
    if [ "$RMW" = rmw_fastrtps_cpp ]; then ok "RMW=$RMW"
    else bad "RMW=$RMW → Discovery Server는 Fast DDS 전용 (unset RMW_IMPLEMENTATION)"; fi
    [ "${TURTLEBOT3_MODEL:-}" = burger ] && ok "TURTLEBOT3_MODEL=burger" \
        || warn "TURTLEBOT3_MODEL='${TURTLEBOT3_MODEL:-}' (burger 권장)"
    ros2 daemon stop >/dev/null 2>&1
else
    bad "/opt/ros/humble 없음 → WSL2 Ubuntu 22.04에서 실행"
fi

echo "[4] ROS 2 토픽 수신"
if command -v ros2 >/dev/null 2>&1; then
    TOPICS=$(timeout 10 ros2 topic list 2>/dev/null)
    if [ -z "$TOPICS" ]; then
        bad "토픽 목록 비어 있음 (bringup 미기동 또는 Discovery 불일치)"
    else
        ok "토픽 $(echo "$TOPICS" | wc -l)개 발견"
    fi
    check_topic() {   # $1=토픽 $2=required|optional
        if ! echo "$TOPICS" | grep -qx "$1"; then
            [ "$2" = required ] && bad "$1 없음" || warn "$1 없음 (선택: tb3_dynamic_detector 기동 시 생성)"
            return
        fi
        if timeout "$TOPIC_TIMEOUT_S" ros2 topic echo --once --no-arr "$1" >/dev/null 2>&1; then
            ok "$1 메시지 수신"
        else
            [ "$2" = required ] && bad "$1 목록엔 있으나 ${TOPIC_TIMEOUT_S}s 내 메시지 없음 (QoS·Wi-Fi 유실)" \
                                || warn "$1 메시지 없음"
        fi
    }
    for t in "${REQUIRED_TOPICS[@]}"; do check_topic "$t" required; done
    for t in "${OPTIONAL_TOPICS[@]}"; do check_topic "$t" optional; done
    if timeout "$TOPIC_TIMEOUT_S" ros2 run tf2_ros tf2_echo odom base_footprint 2>/dev/null | grep -q Translation; then
        ok "TF odom → base_footprint"
    else
        bad "TF odom → base_footprint 조회 실패 (bringup·시계 확인)"
    fi
else
    bad "ros2 명령 없음 → 토픽 점검 생략"
fi

echo "[5] AI 릴레이 WebSocket"
if tcp_open "$RELAY_HOST" "$RELAY_PORT"; then
    ok "릴레이 $RELAY_HOST:$RELAY_PORT 열림"
else
    bad "릴레이 $RELAY_HOST:$RELAY_PORT 닫힘 (python ai_relay_server/ros2_multi_turtlebot_relay.py)"
fi

echo "== 결과: PASS $PASS / WARN $WARN / FAIL $FAIL  ($(( $(date +%s) - START ))s)"
exit "$FAIL"
