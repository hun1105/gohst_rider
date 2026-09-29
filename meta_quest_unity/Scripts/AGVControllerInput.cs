using System;
using UnityEngine;

namespace PhysicalAI.VR
{
    /// <summary>
    /// Meta Quest 2 컨트롤러 조이스틱/버튼 입력을 차량 차동 제어 속도로 매핑
    /// Meta XR SDK(OVRInput) 및 유니티 에디터(WASD 키보드) 둘 다 완벽 지원
    /// </summary>
    public class AGVControllerInput : MonoBehaviour
    {
        [Header("네트워크 매니저")]
        public WebSocketManager wsManager;

        [Header("시점 전환기")]
        public PerspectiveSwitcher perspectiveSwitcher;

        [Header("제어 파라미터")]
        [Range(100, 255)]
        public int maxSpeed = 220;
        public float deadZone = 0.15f;
        public float sendInterval = 0.05f; // 20Hz 전송

        private float _lastSendTime;
        private int _prevLeft = 0;
        private int _prevRight = 0;

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

            // 주기적 또는 입력 변경 시 전송
            if (Time.time - _lastSendTime >= sendInterval)
            {
                ProcessAndSendCommand(inputDir);
                _lastSendTime = Time.time;
            }
        }

        private Vector2 GetInputVector()
        {
            Vector2 stick = Vector2.zero;

            // 1. 키보드 입력 (에디터 테스트용)
            float h = Input.GetAxisRaw("Horizontal");
            float v = Input.GetAxisRaw("Vertical");
            stick = new Vector2(h, v);

            // 2. Meta Quest 2 우측/좌측 컨트롤러 조이스틱 (OVRInput 리플렉션/조건부)
            #if UNITY_ANDROID || OCULUS_SDK
            // Meta XR Core SDK 사용 시
            Vector2 oculusStick = OVRInput.Get(OVRInput.Axis2D.PrimaryThumbstick);
            if (oculusStick.magnitude > deadZone) stick = oculusStick;
            #endif

            if (stick.magnitude < deadZone)
            {
                return Vector2.zero;
            }

            return stick;
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
            // 전진/후진 (Y), 회전 (X) -> 좌/우 휠 속도 변환
            float forward = dir.y;
            float turn = dir.x;

            float left = forward + turn;
            float right = forward - turn;

            // 정규화 및 PWM 범위(-255 ~ 255) 변환
            int leftSpeed = Mathf.RoundToInt(Mathf.Clamp(left, -1f, 1f) * maxSpeed);
            int rightSpeed = Mathf.RoundToInt(Mathf.Clamp(right, -1f, 1f) * maxSpeed);

            // 상태 변화가 없으면 중복 전송 방지 (대역폭 절약)
            if (leftSpeed == 0 && rightSpeed == 0 && _prevLeft == 0 && _prevRight == 0)
            {
                return;
            }

            _prevLeft = leftSpeed;
            _prevRight = rightSpeed;

            string jsonCmd = $"{{\"cmd\":\"DRIVE\",\"left\":{leftSpeed},\"right\":{rightSpeed}}}";
            _ = wsManager.SendTextAsync(jsonCmd);
        }

        private void SendEmergencyStop()
        {
            _prevLeft = 0;
            _prevRight = 0;
            string jsonCmd = "{\"cmd\":\"STOP\"}";
            _ = wsManager.SendTextAsync(jsonCmd);
            Debug.LogWarning("[AGV] EMERGENCY STOP TRIGGERED!");
        }
    }
}
