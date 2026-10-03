using System;
using UnityEngine;
using UnityEngine.XR;

namespace PhysicalAI.VR
{
    /// <summary>
    /// Meta Quest 2 컨트롤러(OpenXR, UnityEngine.XR.InputDevices) 및 키보드(WASD) 입력을 처리하여
    /// 1) 유니티 3D 가상 AGV 차체를 실시간 물리 이동/회전
    /// 2) AI 중계 서버로 차동 제어 속도(PWM) 명령 송신
    /// </summary>
    public class AGVControllerInput : MonoBehaviour
    {
        [Header("네트워크 매니저")]
        public WebSocketManager wsManager;

        [Header("시점 전환기")]
        public PerspectiveSwitcher perspectiveSwitcher;

        [Header("조종 권한 (T-007)")]
        [Tooltip("SELECT_ROBOT ACK 확인용 (telemetry.controlled_robot)")]
        public TurtleBotMultiAgentManager agentManager;
        [SerializeField, Tooltip("현재 조종 대상 로봇 ID: tb1 | tb2")]
        private string currentControlledRobot = "tb1";
        [Tooltip("서버 ACK 불일치 시 SELECT_ROBOT 재전송 간격 (초)")]
        public float selectResendInterval = 1.0f;

        public string CurrentControlledRobot => currentControlledRobot;

        [Header("가상 차체 3D 이동 대상")]
        [Tooltip("화면에서 직접 주행할 가상 AGV Transform (조종 대상 전환 시 자동 교체)")]
        public Transform targetAGVTransform;
        [Tooltip("릴레이 없이 단독 테스트할 때만 켬. 켜면 텔레메트리 보간과 충돌해 차체가 앞뒤로 튕김")]
        public bool localPreviewMove = false;
        public float moveSpeed = 3.5f;     // 로컬 미리보기 이동 속도 (m/s)
        public float turnSpeed = 90.0f;    // 로컬 미리보기 회전 속도 (도/s)

        [Header("제어 파라미터")]
        [Range(100, 255)]
        public int maxSpeed = 220;
        public float deadZone = 0.15f;

        [Header("Meta Quest 2 컨트롤러 (OpenXR)")]
        [Tooltip("조향 썸스틱(좌우): 좌측 컨트롤러")]
        public XRNode steerStickHand = XRNode.LeftHand;
        [Tooltip("전진·후진 썸스틱(상하): 우측 컨트롤러")]
        public XRNode driveStickHand = XRNode.RightHand;
        [Tooltip("우 스틱으로 주행 중일 때 좌 스틱 선회 배율 (곡선 주행 급회전 방지, 1 = 감쇠 없음)")]
        [Range(0.2f, 1f)]
        public float turnScaleWhileMoving = 0.6f;
        // A/X = 비상정지(STOP, 양손), B(우) = 시점 전환, Y(좌) = AUTO 재개 (T-016)
        // 그립(양손 중 하나) = 데드맨 (T-021). 좌 스틱 = 선회, 우 스틱 = 직진·후진, 동시 = 곡선
        [Tooltip("그립 버튼을 쥐고 있을 때만 컨트롤러 주행 허용 (키보드는 해당 없음)")]
        public bool requireGripToDrive = true;

        /// <summary>그립 쥐는 중 (햅틱·HUD 표시용)</summary>
        public bool DeadmanHeld { get; private set; }
        /// <summary>이번 프레임 컨트롤러 주행 입력이 그립 미착용으로 막힘</summary>
        public bool DriveBlockedByDeadman { get; private set; }
        /// <summary>마지막 송신 선속도 비율 (-1~1, +전진)</summary>
        public float LastForwardCommand { get; private set; }

        private bool _prevPrimaryButton;
        private bool _prevViewButton;
        private bool _prevAutoButton;

        [Header("자율 배회 AUTO (T-016)")]
        [Tooltip("AUTO 시작/재개 키. 퀘스트는 좌측 Y 버튼")]
        public KeyCode autoResumeKey = KeyCode.R;

        [Header("위치 원점 재설정 (T-019)")]
        [Tooltip("로봇을 현장 원점 마커에 놓고 누르면 Unity 포즈를 스폰 포즈로 맞춤 (RESET_POSE)")]
        public KeyCode poseResetKey = KeyCode.P;
        public float sendInterval = 0.05f; // 20Hz 전송

        private float _lastSendTime;
        private float _lastSelectSendTime = float.NegativeInfinity;
        private int _prevLeft = 0;
        private int _prevRight = 0;

        private void Start()
        {
            // 타겟이 미할당되었으면 이름으로 자동 탐색
            if (targetAGVTransform == null)
            {
                GameObject agv = GameObject.Find("Physical_AGV");
                if (agv != null) targetAGVTransform = agv.transform;
            }
        }

        private void Update()
        {
            Vector2 inputDir = GetInputVector();
            bool eStopPressed = GetEmergencyStopInput();

            HandlePerspectiveInput();
            HandleAutoInput();
            HandlePoseResetInput();
            ResyncSelectionIfNeeded();

            if (eStopPressed)
            {
                SendEmergencyStop();
                return;
            }

            // 1. (단독 테스트 전용) 가상 차체 로컬 이동. 평소에는 릴레이 텔레메트리가 유일한 위치 원천
            if (localPreviewMove && targetAGVTransform != null && inputDir.sqrMagnitude > 0.001f)
            {
                float moveDelta = inputDir.y * moveSpeed * Time.deltaTime;
                float turnDelta = inputDir.x * turnSpeed * Time.deltaTime;

                targetAGVTransform.Translate(Vector3.forward * moveDelta, Space.Self);
                targetAGVTransform.Rotate(Vector3.up * turnDelta, Space.Self);
            }

            // 2. 네트워크 중계 서버로 속도 명령 주기적 전송
            if (Time.time - _lastSendTime >= sendInterval)
            {
                ProcessAndSendCommand(inputDir);
                _lastSendTime = Time.time;
            }
        }

        private Vector2 GetInputVector()
        {
            Vector2 stick = Vector2.zero;

            // 1. 키보드 입력 (WASD / 방향키). Input.GetAxisRaw("Horizontal")은 쓰지 않음:
            //    레거시 축이 조이스틱 축까지 읽어 Quest 컨트롤러(Link) 축 하나가 -1에 고정되면 계속 좌회전함
            float h = 0f, v = 0f;
            if (Input.GetKey(KeyCode.W) || Input.GetKey(KeyCode.UpArrow)) v = 1f;
            else if (Input.GetKey(KeyCode.S) || Input.GetKey(KeyCode.DownArrow)) v = -1f;

            if (Input.GetKey(KeyCode.D) || Input.GetKey(KeyCode.RightArrow)) h = 1f;
            else if (Input.GetKey(KeyCode.A) || Input.GetKey(KeyCode.LeftArrow)) h = -1f;

            stick = new Vector2(h, v);
            DriveBlockedByDeadman = false;
            DeadmanHeld = XRGripHeld();

            if (stick != Vector2.zero)
            {
                // 1. 키보드(PC 관제사): 데드맨 대상 아님. 대각선(크기 1.41)만 정규화
                if (stick.magnitude < deadZone) return Vector2.zero;
                return stick.magnitude > 1f ? stick.normalized : stick;
            }

            // 2. Meta Quest 2 컨트롤러
            //    좌측 스틱 좌우 = 좌·우 선회 (단독이면 제자리)
            //    우측 스틱 상하 = 직진·후진
            ControllerFor(steerStickHand).TryGetFeatureValue(CommonUsages.primary2DAxis, out Vector2 steerStick);
            ControllerFor(driveStickHand).TryGetFeatureValue(CommonUsages.primary2DAxis, out Vector2 driveStick);
            float turn = Mathf.Abs(steerStick.x) >= deadZone ? Mathf.Clamp(steerStick.x, -1f, 1f) : 0f;
            float forward = Mathf.Abs(driveStick.y) >= deadZone ? Mathf.Clamp(driveStick.y, -1f, 1f) : 0f;
            if (turn == 0f && forward == 0f) return Vector2.zero;
            // 두 스틱 동시 입력 = 곡선 주행 (좌 = 각속도, 우 = 선속도 독립 합성).
            // 단독: 좌만 → 제자리 선회, 우만 → 직진·후진. 주행 중 선회는 감쇠해 급회전 방지
            if (forward != 0f) turn *= turnScaleWhileMoving;

            // 데드맨: 그립을 쥐고 있을 때만 주행. 손을 떼면 0 명령 → 즉시 정지 (산업용 원격조종 안전장치)
            if (requireGripToDrive && !DeadmanHeld)
            {
                DriveBlockedByDeadman = true;
                return Vector2.zero;
            }

            return new Vector2(turn, forward);
        }

        /// <summary>양손 중 하나라도 그립 버튼을 쥐고 있으면 true (XR 장치 없으면 false).</summary>
        private static bool XRGripHeld()
        {
            bool held = false;
            if (ControllerFor(XRNode.LeftHand).TryGetFeatureValue(CommonUsages.gripButton, out bool l) && l) held = true;
            if (ControllerFor(XRNode.RightHand).TryGetFeatureValue(CommonUsages.gripButton, out bool r) && r) held = true;
            return held;
        }

        private static readonly System.Collections.Generic.List<InputDevice> _devBuf = new System.Collections.Generic.List<InputDevice>();

        /// <summary>
        /// 손별 컨트롤러. XRNode 조회가 무효면 (Link 재접속 직후 등) 특성(Controller+Left/Right)으로 재탐색.
        /// </summary>
        private static InputDevice ControllerFor(XRNode hand)
        {
            InputDevice d = InputDevices.GetDeviceAtXRNode(hand);
            if (d.isValid) return d;
            var side = hand == XRNode.LeftHand ? InputDeviceCharacteristics.Left : InputDeviceCharacteristics.Right;
            InputDevices.GetDevicesWithCharacteristics(InputDeviceCharacteristics.Controller | side, _devBuf);
            return _devBuf.Count > 0 ? _devBuf[0] : d;
        }

        private bool GetEmergencyStopInput()
        {
            bool keyboard = Input.GetKeyDown(KeyCode.Space);
            bool xr = XRButtonDown(CommonUsages.primaryButton, ref _prevPrimaryButton);  // A / X
            return keyboard || xr;
        }

        // ===================== T-007: 조종 대상 전환 =====================

        /// <summary>
        /// 조종 대상 로봇 전환 + 서버에 SELECT_ROBOT 송신.
        /// 서버가 이전 로봇 정지·권한 이양 처리 (PROTOCOL.md 조종 권한 규칙).
        /// </summary>
        public void SetControlledRobot(string robotId, Transform robotTransform)
        {
            if (string.IsNullOrEmpty(robotId)) return;

            if (robotId != currentControlledRobot)
            {
                Debug.Log($"[AGV] Control handover {currentControlledRobot} -> {robotId}");
            }
            currentControlledRobot = robotId;
            if (robotTransform != null) targetAGVTransform = robotTransform;

            // 이전 로봇 기준 차동 상태 초기화 → 새 로봇 첫 명령 누락 방지
            _prevLeft = 0;
            _prevRight = 0;
            SendSelectRobot();
        }

        private void SendSelectRobot()
        {
            _lastSelectSendTime = Time.unscaledTime;
            if (wsManager == null) return;
            _ = wsManager.SendTextAsync($"{{\"cmd\":\"SELECT_ROBOT\",\"robot\":\"{currentControlledRobot}\"}}");
        }

        /// <summary>재연결 등으로 서버 권한이 어긋나면 주기적으로 재요청 (불일치 동안 서버는 TWIST 무시 = 정지)</summary>
        private void ResyncSelectionIfNeeded()
        {
            if (agentManager == null || wsManager == null || !wsManager.IsConnected) return;
            string acked = agentManager.ControlledRobot;
            if (string.IsNullOrEmpty(acked) || acked == currentControlledRobot) return;
            if (Time.unscaledTime - _lastSelectSendTime < selectResendInterval) return;

            Debug.LogWarning($"[AGV] Server control '{acked}' != local '{currentControlledRobot}'. Resending SELECT_ROBOT.");
            SendSelectRobot();
        }

        /// <summary>
        /// God-View: Tab/T/퀘스트 B·Y → 현재 조종 로봇 콕핏 진입.
        /// FPV: Tab/T/ESC/퀘스트 B·Y → God-View 복귀.
        /// </summary>
        private void HandlePerspectiveInput()
        {
            if (perspectiveSwitcher == null) return;

            bool toggle = Input.GetKeyDown(KeyCode.Tab) || Input.GetKeyDown(KeyCode.T);
            bool escape = Input.GetKeyDown(KeyCode.Escape);

            if (XRButtonDown(XRNode.RightHand, CommonUsages.secondaryButton, ref _prevViewButton)) toggle = true;  // B

            if (perspectiveSwitcher.CurrentView == ViewPerspective.MicroFPVCockpit)
            {
                if (toggle || escape) perspectiveSwitcher.ReturnToGodView();
            }
            else if (toggle)
            {
                perspectiveSwitcher.EnterCockpit(currentControlledRobot);
            }
        }

        /// <summary>
        /// T-016: AUTO 시작/재개 요청. 서버가 실기 tb1·LiDAR 조건 확인 후 수락.
        /// AUTO 해제는 별도 키 없음: 주행 입력(WASD/썸스틱) 또는 STOP → 서버가 즉시 MANUAL 전환.
        /// </summary>
        private void HandleAutoInput()
        {
            bool pressed = Input.GetKeyDown(autoResumeKey)
                           | XRButtonDown(XRNode.LeftHand, CommonUsages.secondaryButton, ref _prevAutoButton);  // Y
            if (!pressed || wsManager == null) return;
            _ = wsManager.SendTextAsync($"{{\"cmd\":\"AUTO\",\"robot\":\"{currentControlledRobot}\",\"enable\":true}}");
            Debug.Log($"[AGV] AUTO resume requested ({currentControlledRobot})");
        }

        /// <summary>T-019: 현장 원점 마커 정렬. 서버가 현재 odom을 원점으로 기록 (실기 로봇만).</summary>
        private void HandlePoseResetInput()
        {
            if (!Input.GetKeyDown(poseResetKey) || wsManager == null) return;
            _ = wsManager.SendTextAsync($"{{\"cmd\":\"RESET_POSE\",\"robot\":\"{currentControlledRobot}\"}}");
            Debug.Log($"[AGV] RESET_POSE requested ({currentControlledRobot}) — 로봇이 원점 마커 위에 있어야 함");
        }

        /// <summary>지정 손 컨트롤러 버튼이 새로 눌린 프레임에 true (에지 검출).</summary>
        private static bool XRButtonDown(XRNode hand, InputFeatureUsage<bool> usage, ref bool prevPressed)
        {
            bool pressed = InputDevices.GetDeviceAtXRNode(hand).TryGetFeatureValue(usage, out bool v) && v;
            bool down = pressed && !prevPressed;
            prevPressed = pressed;
            return down;
        }

        /// <summary>양손 컨트롤러 중 하나라도 버튼이 새로 눌린 프레임에 true (에지 검출).</summary>
        private static bool XRButtonDown(InputFeatureUsage<bool> usage, ref bool prevPressed)
        {
            bool pressed = false;
            if (InputDevices.GetDeviceAtXRNode(XRNode.LeftHand).TryGetFeatureValue(usage, out bool left) && left) pressed = true;
            if (InputDevices.GetDeviceAtXRNode(XRNode.RightHand).TryGetFeatureValue(usage, out bool right) && right) pressed = true;
            bool down = pressed && !prevPressed;
            prevPressed = pressed;
            return down;
        }

        private void ProcessAndSendCommand(Vector2 dir)
        {
            float forward = dir.y;
            float turn = dir.x;
            LastForwardCommand = forward;

            float left = forward + turn;
            float right = forward - turn;

            int leftSpeed = Mathf.RoundToInt(Mathf.Clamp(left, -1f, 1f) * maxSpeed);
            int rightSpeed = Mathf.RoundToInt(Mathf.Clamp(right, -1f, 1f) * maxSpeed);

            if (leftSpeed == 0 && rightSpeed == 0 && _prevLeft == 0 && _prevRight == 0)
            {
                return;
            }

            _prevLeft = leftSpeed;
            _prevRight = rightSpeed;

            if (wsManager != null)
            {
                // ROS 2 Humble Twist (m/s, rad/s)
                float linear_x = forward * 0.22f; // TurtleBot3 Burger 최대 선속도 0.22 m/s
                float angular_z = -turn * 2.84f;  // TurtleBot3 Burger 최대 각속도 2.84 rad/s

                string jsonCmd = $"{{\"cmd\":\"TWIST\",\"robot\":\"{currentControlledRobot}\",\"linear\":{linear_x:F3},\"angular\":{angular_z:F3},\"left\":{leftSpeed},\"right\":{rightSpeed}}}";
                _ = wsManager.SendTextAsync(jsonCmd);
            }
        }

        private void SendEmergencyStop()
        {
            _prevLeft = 0;
            _prevRight = 0;
            if (wsManager != null)
            {
                string jsonCmd = $"{{\"cmd\":\"STOP\",\"robot\":\"{currentControlledRobot}\"}}";
                _ = wsManager.SendTextAsync(jsonCmd);
            }
            Debug.LogWarning($"[AGV] EMERGENCY STOP TRIGGERED! ({currentControlledRobot})");
        }
    }
}
