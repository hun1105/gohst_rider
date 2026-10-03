using UnityEngine;
using UnityEngine.XR;

namespace PhysicalAI.VR
{
    /// <summary>
    /// PC 모니터 ↔ Quest HMD 화면 분리.
    /// - XR 활성: HMD = 기존 XR 카메라(God-View/콕핏 전환), PC 모니터 = 전용 탑다운 관제 맵 카메라(직교).
    ///   마우스 피킹은 맵 카메라 기준 → 관제사가 PC 맵에서 로봇 클릭 → 착용자 HMD가 해당 콕핏으로 빙의.
    /// - XR 비활성: 맵 카메라 끔, 기존 단일 카메라 동작 그대로.
    /// HMD 연결·해제(Link 재접속)를 매 프레임 감지해 자동 전환.
    /// </summary>
    public class DualDisplayController : MonoBehaviour
    {
        [Header("카메라")]
        [Tooltip("HMD로 출력되는 기존 메인 카메라 (PerspectiveSwitcher 리그)")]
        public Camera xrCamera;
        [Tooltip("PC 모니터 전용 탑다운 맵 카메라 (Target Eye = None)")]
        public Camera desktopMapCamera;
        [Tooltip("맵 카메라 위치·방향 기준 (수직 탑다운 앵커)")]
        public Transform mapAnchor;

        [Header("마우스 피킹")]
        public RobotSelectionRaycaster picker;

        [Header("맵 표시")]
        [Tooltip("직교 투영 세로 반폭 (m)")]
        public float mapOrthoSize = 4f;
        [Tooltip("XR 카메라보다 나중에 그려 모니터를 덮도록 depth 가산")]
        public float mapDepthOffset = 10f;

        public bool IsDualDisplayActive { get; private set; }

        [Header("PC 관제 맵 줌·이동 (God-View 직교 카메라)")]
        [Tooltip("휠 한 칸당 확대·축소 비율")]
        public float zoomStep = 0.12f;
        public float minOrthoSize = 0.3f;
        public float maxOrthoSize = 6f;
        [Tooltip("이 버튼 드래그로 맵 이동 (1 = 우클릭)")]
        public int panMouseButton = 1;
        [Tooltip("휠 클릭: 줌·이동 초기화")]
        public int resetMouseButton = 2;
        public GodViewSidebarHUD sidebar;

        private float _defaultMapOrtho, _defaultGodOrtho;
        private Vector3 _panOffset;
        private Vector3 _lastMouse;

        [Header("PC ↔ VR 전환 상태 배너")]
        [Tooltip("PC 화면 상단에 헤드셋 연결·착용 상태 표시 (관제사가 착용자 준비 여부 확인)")]
        public bool showVrStatusBanner = true;
        public PerspectiveSwitcher perspectiveSwitcher;

        private bool? _lastXrActive;
        private GUIStyle _bannerStyle;

        private void Awake()
        {
            // 관제사가 다른 창을 누르거나 Link 화면이 포커스를 가져가도 Play가 멈추지 않게
            // (멈추면 헤드셋에 '로딩' 표시 + 릴레이 워치독 정지)
            Application.runInBackground = true;
        }

        /// <summary>헤드셋 착용 여부. 런타임이 근접 센서 값을 주지 않으면 null.</summary>
        private static bool? HeadsetWorn()
        {
            InputDevice head = InputDevices.GetDeviceAtXRNode(XRNode.Head);
            if (head.isValid && head.TryGetFeatureValue(CommonUsages.userPresence, out bool worn)) return worn;
            return null;
        }

        private void OnGUI()
        {
            if (!showVrStatusBanner) return;
            if (_bannerStyle == null)
                _bannerStyle = new GUIStyle(GUI.skin.box) { alignment = TextAnchor.MiddleCenter, fontSize = 15, fontStyle = FontStyle.Bold };

            string text;
            Color color;
            bool? worn = HeadsetWorn();
            bool cockpit = perspectiveSwitcher != null && perspectiveSwitcher.CurrentView == ViewPerspective.MicroFPVCockpit;
            string robot = perspectiveSwitcher != null ? perspectiveSwitcher.SelectedRobotId : "tb1";
            if (!XRSettings.isDeviceActive)
            {
                text = "VR OFF - Quest Link not active (PC only)";
                color = new Color(0.25f, 0.28f, 0.32f, 0.9f);
            }
            else if (worn == false)
            {
                text = cockpit ? $"VR READY - PUT ON HEADSET  >  {robot.ToUpper()} COCKPIT" : "VR READY - headset not worn";
                color = cockpit ? new Color(0.85f, 0.55f, 0.05f, 0.95f) : new Color(0.25f, 0.28f, 0.32f, 0.9f);
            }
            else
            {
                text = cockpit ? $"VR LIVE - operator in {robot.ToUpper()} cockpit" : "VR LIVE - god view (click a robot to hand over)";
                color = cockpit ? new Color(0.1f, 0.55f, 0.25f, 0.95f) : new Color(0.12f, 0.35f, 0.55f, 0.9f);
            }

            float w = 460f, h = 30f;
            Rect r = new Rect((Screen.width - w) * 0.5f, 8f, w, h);
            Color prev = GUI.backgroundColor;
            GUI.backgroundColor = color;
            GUI.Box(r, text, _bannerStyle);
            GUI.backgroundColor = prev;
        }

        private void Start()
        {
            if (xrCamera == null) xrCamera = Camera.main;
            if (perspectiveSwitcher == null) perspectiveSwitcher = FindFirstObjectByType<PerspectiveSwitcher>();
            if (desktopMapCamera != null)
            {
                desktopMapCamera.stereoTargetEye = StereoTargetEyeMask.None;  // HMD로 보내지 않음
                desktopMapCamera.orthographic = true;
                desktopMapCamera.orthographicSize = mapOrthoSize;
                desktopMapCamera.enabled = false;
            }
            if (sidebar == null) sidebar = FindFirstObjectByType<GodViewSidebarHUD>();
            _defaultMapOrtho = mapOrthoSize;
            _defaultGodOrtho = perspectiveSwitcher != null ? perspectiveSwitcher.godViewOrthoSize : mapOrthoSize;
            Apply(XRSettings.isDeviceActive);
        }

        /// <summary>PC 화면에 보이는 직교 관제 카메라 (XR: 맵 카메라, PC 단독: God-View 메인 카메라). 콕핏이면 null.</summary>
        private Camera PcMapCamera()
        {
            if (IsDualDisplayActive) return desktopMapCamera;
            bool godView = perspectiveSwitcher != null && perspectiveSwitcher.CurrentView == ViewPerspective.MacroGodView
                           && !perspectiveSwitcher.IsTransitioning;
            return godView && xrCamera != null && xrCamera.orthographic ? xrCamera : null;
        }

        /// <summary>휠 = 확대·축소, 우클릭 드래그 = 이동, 휠 클릭 = 초기화. HUD 위에서는 무시.</summary>
        private void HandleZoomPan(Camera cam)
        {
            Vector3 mouse = Input.mousePosition;
            bool overHud = sidebar != null && sidebar.ContainsScreenPoint(mouse);
            if (Input.GetMouseButtonDown(resetMouseButton) && !overHud)
            {
                _panOffset = Vector3.zero;
                SetOrtho(cam, IsDualDisplayActive ? _defaultMapOrtho : _defaultGodOrtho);
            }
            float scroll = Input.mouseScrollDelta.y;
            if (Mathf.Abs(scroll) > 0.01f && !overHud)
                SetOrtho(cam, cam.orthographicSize * Mathf.Pow(1f - zoomStep, scroll));   // 위로 = 확대
            if (Input.GetMouseButtonDown(panMouseButton)) _lastMouse = mouse;
            if (Input.GetMouseButton(panMouseButton))
            {
                // 수직 탑다운: 화면 오른쪽 = +X, 위쪽 = +Z. 픽셀 → 월드 = 2·orthoSize / 화면 높이
                float worldPerPixel = 2f * cam.orthographicSize / Mathf.Max(1, cam.pixelHeight);
                Vector3 d = mouse - _lastMouse;
                _panOffset -= new Vector3(d.x, 0f, d.y) * worldPerPixel;
                _lastMouse = mouse;
            }
        }

        private void SetOrtho(Camera cam, float size)
        {
            size = Mathf.Clamp(size, minOrthoSize, maxOrthoSize);
            cam.orthographicSize = size;
            // 콕핏 왕복·XR 전환 후에도 유지되도록 원본 값도 갱신
            if (IsDualDisplayActive) mapOrthoSize = size;
            else if (perspectiveSwitcher != null) perspectiveSwitcher.godViewOrthoSize = size;
        }

        private void LateUpdate()
        {
            bool xrActive = XRSettings.isDeviceActive;
            if (_lastXrActive != xrActive) Apply(xrActive);

            Camera cam = PcMapCamera();
            if (cam != null) HandleZoomPan(cam);

            if (mapAnchor == null) return;
            if (IsDualDisplayActive)
            {
                desktopMapCamera.transform.SetPositionAndRotation(mapAnchor.position + _panOffset, mapAnchor.rotation);
            }
            else if (cam != null)
            {
                cam.transform.position = mapAnchor.position + _panOffset;   // PC 단독 God-View (HMD 없음)
            }
        }

        private void Apply(bool xrActive)
        {
            _lastXrActive = xrActive;
            IsDualDisplayActive = xrActive && desktopMapCamera != null;

            if (desktopMapCamera != null)
            {
                desktopMapCamera.enabled = IsDualDisplayActive;
                if (xrCamera != null) desktopMapCamera.depth = xrCamera.depth + mapDepthOffset;
            }
            if (picker != null)
            {
                picker.pickCamera = IsDualDisplayActive ? desktopMapCamera : xrCamera;
                picker.allowPickInCockpit = IsDualDisplayActive;
            }
            if (xrActive)
            {
                // XR 미러를 Game 뷰에 복사하지 않음 → 모니터는 맵 카메라 전용
                XRSettings.gameViewRenderMode = IsDualDisplayActive ? GameViewRenderMode.None : GameViewRenderMode.LeftEye;
            }
            Debug.Log($"[DualDisplay] XR={(xrActive ? "ON" : "OFF")} → PC 모니터: {(IsDualDisplayActive ? "탑다운 맵 전용" : "메인 카메라")}");
        }
    }
}
