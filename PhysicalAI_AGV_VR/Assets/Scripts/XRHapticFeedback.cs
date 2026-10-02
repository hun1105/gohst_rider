using UnityEngine;
using UnityEngine.XR;
using UnityEngine.XR.OpenXR.Input;

namespace PhysicalAI.VR
{
    /// <summary>
    /// T-021: Quest 컨트롤러 진동으로 위험을 손에 전달 (화면을 보지 않아도 인지).
    /// 우선순위: 정지(인터록·AUTO STUCK) > 전방 근접 > 예상 경로 YELLOW > 데드맨 안내.
    /// - 정지 진입: 강한 진동 1회 + 지속 중 주기 진동
    /// - 전진 중 전방 장애물: 가까울수록 진동 간격 짧게·세게 (LiDAR front_min, 0.8m → 가드 0.35m)
    /// - 전진 중 예상 경로 YELLOW(좁음): 약한 짧은 진동
    /// - 그립 없이 스틱 조작: 두 번 톡톡 (데드맨 안내)
    /// - T-024 선회 추천: 돌아야 할 쪽 손만 진동 (좌 선회 = 왼손). 정지 중 반복 진동도 그 손으로
    /// OpenXR SendHapticImpulse 사용, 진동 미지원 장치는 무시.
    /// </summary>
    public class XRHapticFeedback : MonoBehaviour
    {
        [Header("연결")]
        public TurtleBotMultiAgentManager agentManager;
        public AGVControllerInput controllerInput;

        [Header("정지 (인터록·STUCK)")]
        public float stopOnsetAmplitude = 0.9f;
        public float stopOnsetDuration = 0.35f;
        public float stopRepeatAmplitude = 0.45f;
        public float stopRepeatDuration = 0.08f;
        public float stopRepeatInterval = 0.5f;

        [Header("전방 근접 (전진 중)")]
        [Tooltip("이 거리부터 진동 시작 (m)")]
        public float proximityStart = 0.8f;
        [Tooltip("릴레이 LiDAR 전방 가드와 같은 값 (m) — 여기서 최대")]
        public float proximityGuard = 0.35f;
        public float proximityMinAmplitude = 0.15f;
        public float proximityMaxAmplitude = 0.6f;
        public float proximitySlowInterval = 0.6f;
        public float proximityFastInterval = 0.12f;
        public float proximityPulseDuration = 0.05f;
        [Tooltip("이 값 이상 전진 명령일 때만 근접 진동 (정지 상태 벽 옆 진동 방지)")]
        public float forwardCommandThreshold = 0.05f;

        [Header("예상 경로 YELLOW")]
        public float cautionAmplitude = 0.25f;
        public float cautionDuration = 0.05f;
        public float cautionInterval = 0.7f;

        [Header("데드맨 안내")]
        public float deadmanTickAmplitude = 0.3f;
        public float deadmanTickDuration = 0.03f;
        public float deadmanTickGap = 0.09f;
        public float deadmanHintInterval = 1.0f;

        [Header("선회 추천 방향 (T-024)")]
        public float pivotCueAmplitude = 0.6f;
        public float pivotCueDuration = 0.12f;
        [Tooltip("선회 추천 시작 후 첫 방향 진동까지 지연 (정지 진동과 구분, s)")]
        public float pivotCueDelay = 0.45f;
        [Tooltip("정지 상태가 아닐 때 방향 진동 반복 간격 (s)")]
        public float pivotCueInterval = 1.0f;

        [Header("그립 체결 확인·시험")]
        public float gripConfirmAmplitude = 0.35f;
        public float gripConfirmDuration = 0.04f;
        [Tooltip("PC에서 누르면 양손 시험 진동 (헤드셋 연결 확인용)")]
        public KeyCode testPulseKey = KeyCode.H;

        private bool _wasStopped;
        private bool _wasGripHeld;
        private bool _wasPivot;
        private float _pivotCueTime = -1f;
        private float _nextPulseTime;
        private float _nextDeadmanHint;
        private float _secondTickTime = -1f;

        private void Update()
        {
            if (agentManager == null || controllerInput == null) return;
            float now = Time.unscaledTime;
            string robot = controllerInput.CurrentControlledRobot;
            GripConfirm(now);

            // 데드맨 안내 두 번째 톡
            if (_secondTickTime > 0f && now >= _secondTickTime)
            {
                Pulse(deadmanTickAmplitude, deadmanTickDuration);
                _secondTickTime = -1f;
            }

            // T-024: 선회 추천 방향 손 (경로 추천은 tb1 실기 LiDAR 기준)
            PathData path = agentManager.LatestPath;
            bool pivot = path != null && path.recommended_mode == "PIVOT" && (string.IsNullOrEmpty(path.robot) || path.robot == robot);
            XRNode pivotHand = pivot && path.pivot_deg > 0f ? XRNode.LeftHand : XRNode.RightHand;
            if (pivot && !_wasPivot) _pivotCueTime = now + pivotCueDelay;
            if (!pivot) _pivotCueTime = -1f;
            _wasPivot = pivot;
            if (pivot && _pivotCueTime > 0f && now >= _pivotCueTime)
            {
                SendTo(pivotHand, pivotCueAmplitude, pivotCueDuration);
                _pivotCueTime = -1f;
                _nextPulseTime = now + pivotCueInterval;
            }

            bool stopped = agentManager.RobotAlert(robot);
            if (stopped && !_wasStopped)
            {
                Pulse(stopOnsetAmplitude, stopOnsetDuration);
                _nextPulseTime = now + stopRepeatInterval;
            }
            _wasStopped = stopped;

            if (stopped)
            {
                if (now >= _nextPulseTime)
                {
                    // 선회 추천이 있으면 반복 진동을 돌아야 할 쪽 손으로만 → 손으로 방향 인지
                    if (pivot) SendTo(pivotHand, pivotCueAmplitude, stopRepeatDuration);
                    else Pulse(stopRepeatAmplitude, stopRepeatDuration);
                    _nextPulseTime = now + stopRepeatInterval;
                }
                return;
            }

            if (pivot)
            {
                if (now >= _nextPulseTime) { SendTo(pivotHand, pivotCueAmplitude, pivotCueDuration); _nextPulseTime = now + pivotCueInterval; }
                return;
            }

            bool drivingForward = controllerInput.LastForwardCommand >= forwardCommandThreshold;
            RobotPoseData data = agentManager.GetRobotData(robot);
            float front = data != null ? data.front_min : -1f;
            if (drivingForward && front > 0f && front < proximityStart)
            {
                float t = Mathf.InverseLerp(proximityStart, proximityGuard, front);   // 0 = 멀다, 1 = 가드
                if (now >= _nextPulseTime)
                {
                    Pulse(Mathf.Lerp(proximityMinAmplitude, proximityMaxAmplitude, t), proximityPulseDuration);
                    _nextPulseTime = now + Mathf.Lerp(proximitySlowInterval, proximityFastInterval, t);
                }
                return;
            }

            if (drivingForward && path != null && path.predicted_level == "YELLOW" && now >= _nextPulseTime)
            {
                Pulse(cautionAmplitude, cautionDuration);
                _nextPulseTime = now + cautionInterval;
            }

            if (controllerInput.DriveBlockedByDeadman && now >= _nextDeadmanHint)
            {
                Pulse(deadmanTickAmplitude, deadmanTickDuration);
                _secondTickTime = now + deadmanTickGap;
                _nextDeadmanHint = now + deadmanHintInterval;
            }
        }

        private static void Pulse(float amplitude, float duration)
        {
            SendTo(XRNode.LeftHand, amplitude, duration);
            SendTo(XRNode.RightHand, amplitude, duration);
        }

        private static void SendTo(XRNode node, float amplitude, float duration)
        {
            InputDevice device = InputDevices.GetDeviceAtXRNode(node);
            if (!device.isValid) return;
            // OpenXR 런타임은 레거시 TryGetHapticCapabilities가 supportsImpulse=false를 돌려줘 진동이 막힘
            // → OpenXR 전용 경로로 직접 송신 (frequency 0 = 런타임 기본값)
            OpenXRInput.SendHapticImpulse(device, Mathf.Clamp01(amplitude), 0f, duration);
        }

        /// <summary>그립을 새로 쥔 순간 짧은 진동 1회 (데드맨 체결 확인)</summary>
        private void GripConfirm(float now)
        {
            bool held = controllerInput.DeadmanHeld;
            if (held && !_wasGripHeld) Pulse(gripConfirmAmplitude, gripConfirmDuration);
            _wasGripHeld = held;
            if (Input.GetKeyDown(testPulseKey)) { Pulse(stopOnsetAmplitude, stopOnsetDuration); Debug.Log("[Haptics] test pulse"); }
        }
    }
}
