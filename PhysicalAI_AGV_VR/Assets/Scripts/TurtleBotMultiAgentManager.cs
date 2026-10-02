using System;
using UnityEngine;

namespace PhysicalAI.VR
{
    [Serializable]
    public class RobotPoseData
    {
        public string name;
        public float x;
        public float y;
        public float z;
        public float yaw;
        public float linear_vel;
        public float angular_vel;
        public float battery;
        // T-012: 실기 연동 상태·LiDAR 섹터 거리 (m, 없음 = -1). sim은 source="sim", front_min=-1
        public string source;
        public bool online;
        public float front_min = -1f;
        public float rear_min = -1f;
        // T-025: 로봇별 주행 모드·정지 상태 (구버전 서버: null/false)
        public string mode;
        public string auto_state;
        public bool alert;
        public string stop_reason;
    }

    [Serializable]
    public class SafetyData
    {
        public bool interlock;
        public string status;
        // 선택 필드: "tb1" | "tb2" | "all". 미전송(빈 값) 시 tb1 대상으로 간주 (하위 호환)
        public string target;
        // T-015: 정지 원인·LiDAR 추천 탈출 방향 (deg, +좌) / 여유 (m, -1 = 없음)
        public string reason;
        public float escape_heading;
        public float escape_clearance = -1f;
    }

    /// <summary>T-019: 경로 추천·예상 궤적. 좌표는 Unity 월드 평탄 배열 [x0, z0, x1, z1, …]</summary>
    [Serializable]
    public class PathData
    {
        public string robot;   // T-025: 경로 대상 로봇
        public float[] recommended;
        public string recommended_level;
        public float[] predicted;
        public string predicted_level;
        public float[] alternatives;
        public int alt_points;
        // T-024 선회 추천 (FORWARD / PIVOT / NONE)
        public string recommended_mode;
        public float pivot_deg;
        public float[] pivot_points;
        public string pivot_level;
    }

    [Serializable]
    public class TelemetryPacket
    {
        public string type;
        public RobotPoseData tb1;
        public RobotPoseData tb2;
        public SafetyData safety;
        // T-007: 서버가 인정한 현재 텔레옵 권한 로봇 ("tb1" | "tb2"). SELECT_ROBOT ACK
        public string controlled_robot;
        public string camera_robot;   // T-025
        // T-016: tb1 주행 모드 ("MANUAL" | "AUTO") / AUTO 세부 상태
        public string mode;
        public string auto_state;
        // T-019: tb1 경로 + LiDAR 점 (Unity 월드 평탄 배열)
        public PathData path;
        public float[] scan;
    }

    /// <summary>
    /// ROS 2 Humble 다중 TurtleBot3(tb1: 주행 AGV, tb2: 순찰 AGV) 오도메트리 동기화 및 안전 인터록 상태 관리자
    /// </summary>
    public class TurtleBotMultiAgentManager : MonoBehaviour
    {
        [Header("네트워크 매니저")]
        public WebSocketManager wsManager;

        [Header("다중 로봇 트랜스폼")]
        public Transform tb1Transform; // 주행 AGV (사용자 제어)
        public Transform tb2Transform; // 순찰/장애물 AGV (자율 순찰)

        [Header("보간 설정")]
        [Tooltip("위치 추종 시간 (s). 20Hz 텔레메트리 간격·수신 몰림을 속도 연속으로 메움")]
        public float positionSmoothTime = 0.12f;
        [Tooltip("방향 추종 시간 (s)")]
        public float rotationSmoothTime = 0.10f;
        [Tooltip("이 거리 이상 차이 나면 보간 없이 즉시 이동 (RESET_POSE 등, m)")]
        public float snapDistance = 1.5f;

        [Header("실시간 안전 상태 (모니터링)")]
        public bool isInterlocked = false;
        public string safetyStatus = "NORMAL";

        // 내부 목표 위치 및 회전
        private Vector3 _targetPosTB1;
        private Quaternion _targetRotTB1;
        private Vector3 _targetPosTB2;
        private Quaternion _targetRotTB2;

        private bool _hasReceivedTB1 = false;
        private bool _hasReceivedTB2 = false;

        // ===== HUD / 경고 시각화용 공개 읽기 전용 상태 =====
        public RobotPoseData TB1Data { get; private set; }
        public RobotPoseData TB2Data { get; private set; }
        public float LastTelemetryTime { get; private set; } = -1f;
        public bool IsConnected => wsManager != null && wsManager.IsConnected;
        public string InterlockTarget { get; private set; } = "tb1";
        public string InterlockReason { get; private set; } = string.Empty;
        public float EscapeHeadingDeg { get; private set; }
        public float EscapeClearance { get; private set; } = -1f;
        /// <summary>서버 기준 텔레옵 권한 로봇. 텔레메트리 수신 전에는 빈 문자열.</summary>
        public string ControlledRobot { get; private set; } = string.Empty;
        public string DriveMode { get; private set; } = "MANUAL";
        public string AutoState { get; private set; } = "OFF";
        public PathData LatestPath { get; private set; }
        public float[] LatestScan { get; private set; } = Array.Empty<float>();
        public event Action OnTelemetryUpdated;

        /// <summary>로봇 ID("tb1"/"tb2")별 비상정지 여부</summary>
        public bool IsRobotInterlocked(string robotId)
        {
            if (!isInterlocked) return false;
            return InterlockTarget == "all" || InterlockTarget == robotId;
        }

        public RobotPoseData GetRobotData(string robotId) => robotId == "tb2" ? TB2Data : TB1Data;

        /// <summary>카메라가 달린 로봇 (영상 스크린 부착 대상). 구버전 서버는 tb1.</summary>
        public string CameraRobot { get; private set; } = "tb1";

        /// <summary>T-025: 로봇별 정지·알림 (인터록 또는 AUTO STUCK). 구버전 서버는 기존 규칙으로 판정.</summary>
        public bool RobotAlert(string robotId)
        {
            RobotPoseData d = GetRobotData(robotId);
            if (d != null && !string.IsNullOrEmpty(d.mode)) return d.alert;
            return IsRobotInterlocked(robotId) || (robotId == "tb1" && AutoState == "STUCK");
        }

        public string RobotMode(string robotId)
        {
            RobotPoseData d = GetRobotData(robotId);
            if (d != null && !string.IsNullOrEmpty(d.mode)) return d.mode;
            return robotId == "tb1" ? DriveMode : "MANUAL";
        }

        public string RobotAutoState(string robotId)
        {
            RobotPoseData d = GetRobotData(robotId);
            if (d != null && !string.IsNullOrEmpty(d.auto_state)) return d.auto_state;
            return robotId == "tb1" ? AutoState : "OFF";
        }

        public string RobotStopReason(string robotId)
        {
            RobotPoseData d = GetRobotData(robotId);
            if (d != null && !string.IsNullOrEmpty(d.mode)) return d.stop_reason ?? string.Empty;
            return IsRobotInterlocked(robotId) ? InterlockReason : string.Empty;
        }

        private void Start()
        {
            if (tb1Transform != null)
            {
                _targetPosTB1 = tb1Transform.position;
                _targetRotTB1 = tb1Transform.rotation;
            }
            if (tb2Transform != null)
            {
                _targetPosTB2 = tb2Transform.position;
                _targetRotTB2 = tb2Transform.rotation;
            }
            // AddComponent 직후 OnEnable 시점엔 wsManager 미할당일 수 있음 → Start에서 재확인
            Subscribe();
        }

        private void OnEnable()
        {
            Subscribe();
        }

        private void Subscribe()
        {
            if (wsManager == null) return;
            wsManager.OnTextReceived -= OnTelemetryReceived;  // 중복 구독 방지
            wsManager.OnTextReceived += OnTelemetryReceived;
        }

        private void OnDisable()
        {
            if (wsManager != null)
            {
                wsManager.OnTextReceived -= OnTelemetryReceived;
            }
        }

        private void OnTelemetryReceived(string json)
        {
            if (string.IsNullOrEmpty(json) || !json.Contains("\"type\":\"telemetry\"") && !json.Contains("\"type\": \"telemetry\""))
            {
                return;
            }

            try
            {
                TelemetryPacket packet = JsonUtility.FromJson<TelemetryPacket>(json);
                if (packet == null) return;

                // 1. tb1 (주행 로봇) 동기화
                if (packet.tb1 != null)
                {
                    _targetPosTB1 = new Vector3(packet.tb1.x, 0.1f, packet.tb1.z);
                    _targetRotTB1 = Quaternion.Euler(0f, packet.tb1.yaw, 0f);
                    _hasReceivedTB1 = true;
                    TB1Data = packet.tb1;
                }

                // 2. tb2 (순찰/장애물 로봇) 동기화
                if (packet.tb2 != null)
                {
                    _targetPosTB2 = new Vector3(packet.tb2.x, 0.1f, packet.tb2.z);
                    _targetRotTB2 = Quaternion.Euler(0f, packet.tb2.yaw, 0f);
                    _hasReceivedTB2 = true;
                    TB2Data = packet.tb2;
                }

                // 3. 피지컬 AI 안전 인터록 상태 갱신
                if (packet.safety != null)
                {
                    isInterlocked = packet.safety.interlock;
                    safetyStatus = packet.safety.status;
                    InterlockTarget = string.IsNullOrEmpty(packet.safety.target) ? "tb1" : packet.safety.target;
                    InterlockReason = packet.safety.reason ?? string.Empty;
                    EscapeHeadingDeg = packet.safety.escape_heading;
                    EscapeClearance = packet.safety.escape_clearance;
                }

                // T-019: 경로·LiDAR 점 (구버전 서버: null → 비움)
                LatestPath = packet.path;
                LatestScan = packet.scan ?? Array.Empty<float>();

                // T-016: 주행 모드 (구버전 서버: 필드 없음 → 기존 값 유지)
                if (!string.IsNullOrEmpty(packet.mode)) DriveMode = packet.mode;
                if (!string.IsNullOrEmpty(packet.auto_state)) AutoState = packet.auto_state;
                if (!string.IsNullOrEmpty(packet.camera_robot)) CameraRobot = packet.camera_robot;

                // 4. 조종 권한 ACK (구버전 서버: 필드 없음 → 빈 문자열 유지)
                if (!string.IsNullOrEmpty(packet.controlled_robot))
                {
                    ControlledRobot = packet.controlled_robot;
                }

                LastTelemetryTime = Time.unscaledTime;
                OnTelemetryUpdated?.Invoke();
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"[MultiAgentManager] Telemetry parse error: {ex.Message}");
            }
        }

        // SmoothDamp 속도 상태 (로봇별)
        private Vector3 _velTB1, _velTB2;
        private float _yawVelTB1, _yawVelTB2;

        private void Update()
        {
            // 임계 감쇠 추종: 지수 Lerp는 50ms마다 급정지·급출발(계단)을 만들어 앞뒤로 튕겨 보임
            if (tb1Transform != null && _hasReceivedTB1)
                Follow(tb1Transform, _targetPosTB1, _targetRotTB1, ref _velTB1, ref _yawVelTB1);
            if (tb2Transform != null && _hasReceivedTB2)
                Follow(tb2Transform, _targetPosTB2, _targetRotTB2, ref _velTB2, ref _yawVelTB2);
        }

        private void Follow(Transform t, Vector3 targetPos, Quaternion targetRot, ref Vector3 vel, ref float yawVel)
        {
            if ((t.position - targetPos).sqrMagnitude > snapDistance * snapDistance)
            {
                t.SetPositionAndRotation(targetPos, targetRot);
                vel = Vector3.zero;
                yawVel = 0f;
                return;
            }
            Vector3 pos = Vector3.SmoothDamp(t.position, targetPos, ref vel, positionSmoothTime);
            float yaw = Mathf.SmoothDampAngle(t.eulerAngles.y, targetRot.eulerAngles.y, ref yawVel, rotationSmoothTime);
            t.SetPositionAndRotation(pos, Quaternion.Euler(0f, yaw, 0f));
        }
    }
}
