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
    }

    [Serializable]
    public class SafetyData
    {
        public bool interlock;
        public string status;
        // 선택 필드: "tb1" | "tb2" | "all". 미전송(빈 값) 시 tb1 대상으로 간주 (하위 호환)
        public string target;
    }

    [Serializable]
    public class TelemetryPacket
    {
        public string type;
        public RobotPoseData tb1;
        public RobotPoseData tb2;
        public SafetyData safety;
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
        public float positionLerpSpeed = 15.0f;
        public float rotationSlerpSpeed = 15.0f;

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
        public event Action OnTelemetryUpdated;

        /// <summary>로봇 ID("tb1"/"tb2")별 비상정지 여부</summary>
        public bool IsRobotInterlocked(string robotId)
        {
            if (!isInterlocked) return false;
            return InterlockTarget == "all" || InterlockTarget == robotId;
        }

        public RobotPoseData GetRobotData(string robotId) => robotId == "tb2" ? TB2Data : TB1Data;

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
        }

        private void OnEnable()
        {
            if (wsManager != null)
            {
                wsManager.OnTextReceived += OnTelemetryReceived;
            }
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
                }

                LastTelemetryTime = Time.unscaledTime;
                OnTelemetryUpdated?.Invoke();
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"[MultiAgentManager] Telemetry parse error: {ex.Message}");
            }
        }

        private void Update()
        {
            // 실시간 부드러운 위치 및 회전 보간 적용
            if (tb1Transform != null && _hasReceivedTB1)
            {
                tb1Transform.position = Vector3.Lerp(tb1Transform.position, _targetPosTB1, Time.deltaTime * positionLerpSpeed);
                tb1Transform.rotation = Quaternion.Slerp(tb1Transform.rotation, _targetRotTB1, Time.deltaTime * rotationSlerpSpeed);
            }

            if (tb2Transform != null && _hasReceivedTB2)
            {
                tb2Transform.position = Vector3.Lerp(tb2Transform.position, _targetPosTB2, Time.deltaTime * positionLerpSpeed);
                tb2Transform.rotation = Quaternion.Slerp(tb2Transform.rotation, _targetRotTB2, Time.deltaTime * rotationSlerpSpeed);
            }
        }
    }
}
