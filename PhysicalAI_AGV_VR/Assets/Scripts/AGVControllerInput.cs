using System;
using UnityEngine;

namespace PhysicalAI.VR
{
    /// <summary>
    /// Meta Quest 2 컨트롤러 및 키보드(WASD) 입력을 처리하여
    /// 1) 유니티 3D 가상 AGV 차체를 실시간 물리 이동/회전
    /// 2) AI 중계 서버로 차동 제어 속도(PWM) 명령 송신
    /// </summary>
    public class AGVControllerInput : MonoBehaviour
    {
        [Header("네트워크 매니저")]
        public WebSocketManager wsManager;

        [Header("시점 전환기")]
        public PerspectiveSwitcher perspectiveSwitcher;

        [Header("가상 차체 3D 이동 대상")]
        [Tooltip("화면에서 직접 주행할 가상 AGV Transform")]
        public Transform targetAGVTransform;
        public float moveSpeed = 3.5f;     // 초당 이동 속도 (m/s)
        public float turnSpeed = 90.0f;    // 초당 회전 속도 (도/s)

        [Header("제어 파라미터")]
        [Range(100, 255)]
        public int maxSpeed = 220;
        public float deadZone = 0.15f;
        public float sendInterval = 0.05f; // 20Hz 전송

        private float _lastSendTime;
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
            bool switchPressed = GetPerspectiveSwitchInput();

            if (switchPressed && perspectiveSwitcher != null)
            {
                perspectiveSwitcher.TogglePerspective();
            }

            if (eStopPressed)
            {
                SendEmergencyStop();
                return;
            }

            // 1. 유니티 3D 씬 내 가상 차체 실시간 주행 이동
            if (targetAGVTransform != null && inputDir.sqrMagnitude > 0.001f)
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

            // 1. 키보드 입력 (WASD / 방향키)
            float h = Input.GetAxisRaw("Horizontal");
            float v = Input.GetAxisRaw("Vertical");

            // 직접 키 입력 보강
            if (Input.GetKey(KeyCode.W) || Input.GetKey(KeyCode.UpArrow)) v = 1f;
            else if (Input.GetKey(KeyCode.S) || Input.GetKey(KeyCode.DownArrow)) v = -1f;

            if (Input.GetKey(KeyCode.D) || Input.GetKey(KeyCode.RightArrow)) h = 1f;
            else if (Input.GetKey(KeyCode.A) || Input.GetKey(KeyCode.LeftArrow)) h = -1f;

            stick = new Vector2(h, v);

            // 2. Meta Quest 2 우측/좌측 컨트롤러 조이스틱
            #if UNITY_ANDROID || OCULUS_SDK
            Vector2 oculusStick = OVRInput.Get(OVRInput.Axis2D.PrimaryThumbstick);
            if (oculusStick.magnitude > deadZone) stick = oculusStick;
            #endif

            if (stick.magnitude < deadZone)
            {
                return Vector2.zero;
            }

            return stick.normalized;
        }

        private bool GetEmergencyStopInput()
        {
            if (Input.GetKeyDown(KeyCode.Space)) return true;

            #if UNITY_ANDROID || OCULUS_SDK
            if (OVRInput.GetDown(OVRInput.Button.One) || OVRInput.GetDown(OVRInput.Button.Three)) return true;
            #endif

            return false;
        }

        private bool GetPerspectiveSwitchInput()
        {
            if (Input.GetKeyDown(KeyCode.Tab) || Input.GetKeyDown(KeyCode.T)) return true;

            #if UNITY_ANDROID || OCULUS_SDK
            if (OVRInput.GetDown(OVRInput.Button.Two) || OVRInput.GetDown(OVRInput.Button.Four)) return true;
            #endif

            return false;
        }

        private void ProcessAndSendCommand(Vector2 dir)
        {
            float forward = dir.y;
            float turn = dir.x;

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

                string jsonCmd = $"{{\"cmd\":\"TWIST\",\"robot\":\"tb1\",\"linear\":{linear_x:F3},\"angular\":{angular_z:F3},\"left\":{leftSpeed},\"right\":{rightSpeed}}}";
                _ = wsManager.SendTextAsync(jsonCmd);
            }
        }

        private void SendEmergencyStop()
        {
            _prevLeft = 0;
            _prevRight = 0;
            if (wsManager != null)
            {
                string jsonCmd = "{\"cmd\":\"STOP\",\"robot\":\"tb1\"}";
                _ = wsManager.SendTextAsync(jsonCmd);
            }
            Debug.LogWarning("[AGV] EMERGENCY STOP TRIGGERED!");
        }
    }
}
