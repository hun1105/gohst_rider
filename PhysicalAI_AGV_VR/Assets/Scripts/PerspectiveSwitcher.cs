using System;
using System.Collections;
using UnityEngine;
using UnityEngine.XR;

namespace PhysicalAI.VR
{
    public enum ViewPerspective
    {
        MacroGodView,   // 거시적 디지털 트윈 조감도 (신 모드)
        MicroFPVCockpit // 1인칭 AGV 빙의 운전 모드 (FPV 콕핏)
    }

    /// <summary>
    /// 빙의 가능한 로봇 1대의 시점 정보 (T-007)
    /// </summary>
    [Serializable]
    public class RobotCockpit
    {
        [Tooltip("tb1 또는 tb2")]
        public string robotId = "tb1";
        [Tooltip("로봇 루트 Transform (마우스 피킹 판정 + 차체 이동 대상)")]
        public Transform robotRoot;
        [Tooltip("1인칭 윈드실드 시점 앵커")]
        public Transform cockpitAnchor;
        [Tooltip("FPV 영상 스크린. 카메라 스트림 없는 로봇은 비움")]
        public GameObject fpvScreen;
    }

    /// <summary>
    /// 거시적 조감도(God View)와 미시적 FPV 빙의 운전(Micro FPV) 간의 시점 전환 제어.
    /// T-007: 선택된 로봇(tb1/tb2)의 콕핏으로 동적 부모 바인딩.
    /// </summary>
    public class PerspectiveSwitcher : MonoBehaviour
    {
        // PROTOCOL.md: TELEPORT.mode 값
        public const string ModeFPV = "FPV";
        public const string ModeGodView = "GOD_VIEW";

        [Header("시점 전환 위치 트랜스폼")]
        public Transform vrCameraRig;         // OVRCameraRig 또는 Main Camera 부모
        public Transform godViewAnchor;       // 상공 조감도 위치

        [Header("빙의 가능 로봇 (T-007)")]
        public RobotCockpit[] robotCockpits = new RobotCockpit[0];
        [Tooltip("시작 시 선택 로봇")]
        public string defaultRobotId = "tb1";

        [Header("UI 및 HUD")]
        public GameObject macroOverviewHUD;   // 거시 관제 HUD

        [Header("통신 매니저")]
        public WebSocketManager wsManager;
        [Tooltip("T-025: telemetry.camera_robot → 영상 스크린을 그 로봇 콕핏으로 이동")]
        public TurtleBotMultiAgentManager agentManager;
        private string _screenRobot;

        [Header("전환 파라미터")]
        public float transitionDuration = 0.5f;
        [Tooltip("XR(헤드셋) 활성 시 카메라 비행 없이 즉시 전환 (VR 멀미·대기 시간 제거)")]
        public bool instantCutInXR = true;

        [Header("God-View 투영 (게임 맵식 탑다운)")]
        [Tooltip("God-View에서 직교 투영. XR 헤드셋 활성 시엔 원근 유지 (HMD는 직교 불가)")]
        public bool godViewOrthographic = true;
        [Tooltip("직교 투영 세로 반폭 (m). 클수록 넓게 보임")]
        public float godViewOrthoSize = 4f;   // 두 로봇 스폰(z 0~5) 포함, 로봇 마커 판독 가능 크기
        [Tooltip("콕핏(원근) 시야각")]
        public float cockpitFieldOfView = 60f;
        [Tooltip("콕핏 시점에서 바닥 경로 띠·LiDAR 점 숨김 (경로는 카메라 영상 위에 그려짐)")]
        public bool hidePathOverlayInCockpit = true;

        public ViewPerspective CurrentView { get; private set; } = ViewPerspective.MacroGodView;
        public bool IsTransitioning => _isTransitioning;
        public string SelectedRobotId => _selected != null ? _selected.robotId : defaultRobotId;
        /// <summary>현재 선택 로봇의 콕핏 앵커 (FPV 진입 시 카메라 리그 부모)</summary>
        public Transform SelectedRobotAnchor => _selected != null ? _selected.cockpitAnchor : null;

        private RobotCockpit _selected;
        private bool _isTransitioning = false;
        private Camera _camera;

        private void Awake()
        {
            _camera = vrCameraRig != null ? vrCameraRig.GetComponentInChildren<Camera>() : Camera.main;
            _selected = FindCockpit(defaultRobotId);
            if (_selected == null && robotCockpits.Length > 0) _selected = robotCockpits[0];
        }

        private void Start()
        {
            ApplyInstantPerspective(ViewPerspective.MacroGodView);
        }

        private bool? _lastXrActive;

        private void LateUpdate()
        {
            // OpenXR는 Play 직후 몇 프레임 뒤에 활성화됨. Start 때 적용한 직교 투영이 남으면
            // URP XR이 HMD로 그리지 않아 헤드셋 화면이 비어 보임 → XR 상태가 바뀌면 투영 재적용
            SyncCameraScreen();
            bool xrActive = XRSettings.isDeviceActive;
            if (_lastXrActive == xrActive) return;
            _lastXrActive = xrActive;
            if (!_isTransitioning) ApplyProjection(CurrentView);
        }

        private void OnDisable()
        {
            // 코루틴 중단 시 전환 잠금 해제
            _isTransitioning = false;
        }

        // ===================== 조회 =====================

        public RobotCockpit FindCockpit(string robotId)
        {
            foreach (RobotCockpit c in robotCockpits)
            {
                if (c != null && c.robotId == robotId) return c;
            }
            return null;
        }

        /// <summary>레이캐스트 히트 Transform이 속한 로봇 탐색 (자식 콜라이더 포함)</summary>
        public RobotCockpit FindCockpitByTransform(Transform hit)
        {
            if (hit == null) return null;
            foreach (RobotCockpit c in robotCockpits)
            {
                if (c != null && c.robotRoot != null && hit.IsChildOf(c.robotRoot)) return c;
            }
            return null;
        }

        // ===================== 전환 API =====================

        /// <summary>지정 로봇 콕핏으로 빙의. God-View 또는 다른 로봇 FPV에서 호출 가능.</summary>
        public bool EnterCockpit(string robotId)
        {
            if (_isTransitioning) return false;

            RobotCockpit target = FindCockpit(robotId);
            if (target == null || target.cockpitAnchor == null)
            {
                Debug.LogWarning($"[PerspectiveSwitcher] '{robotId}' 콕핏 앵커 없음. 빙의 취소.");
                return false;
            }
            if (CurrentView == ViewPerspective.MicroFPVCockpit && target == _selected) return false;

            _selected = target;
            StartCoroutine(SmoothTransition(ViewPerspective.MicroFPVCockpit));
            return true;
        }

        /// <summary>조감도 복귀 (퀘스트 B 버튼 / Tab / ESC)</summary>
        public bool ReturnToGodView()
        {
            if (_isTransitioning || CurrentView == ViewPerspective.MacroGodView) return false;
            StartCoroutine(SmoothTransition(ViewPerspective.MacroGodView));
            return true;
        }

        public void TogglePerspective()
        {
            if (CurrentView == ViewPerspective.MacroGodView) EnterCockpit(SelectedRobotId);
            else ReturnToGodView();
        }

        public void SwitchTo(ViewPerspective target)
        {
            if (target == ViewPerspective.MicroFPVCockpit) EnterCockpit(SelectedRobotId);
            else ReturnToGodView();
        }

        // ===================== 내부 =====================

        private Transform AnchorFor(ViewPerspective view) =>
            view == ViewPerspective.MacroGodView ? godViewAnchor : SelectedRobotAnchor;

        private IEnumerator SmoothTransition(ViewPerspective target)
        {
            _isTransitioning = true;
            Transform targetAnchor = AnchorFor(target);
            // 콕핏 진입: 출발 즉시 원근 전환 (직교 상태로 보간하면 왜곡)
            if (target == ViewPerspective.MicroFPVCockpit) ApplyProjection(target);

            bool instant = instantCutInXR && XRSettings.isDeviceActive;
            if (vrCameraRig != null && targetAnchor != null && !instant)
            {
                // 이전 로봇에서 분리 → 월드 좌표 기준 보간 (이동 중인 로봇 추종)
                vrCameraRig.SetParent(null, true);
                Vector3 startPos = vrCameraRig.position;
                Quaternion startRot = vrCameraRig.rotation;
                float elapsed = 0f;

                while (elapsed < transitionDuration)
                {
                    elapsed += Time.deltaTime;
                    float t = Mathf.SmoothStep(0f, 1f, elapsed / transitionDuration);
                    vrCameraRig.position = Vector3.Lerp(startPos, targetAnchor.position, t);
                    vrCameraRig.rotation = Quaternion.Slerp(startRot, targetAnchor.rotation, t);
                    yield return null;
                }

                BindRig(target, targetAnchor);
            }
            else if (vrCameraRig != null && targetAnchor != null)
            {
                BindRig(target, targetAnchor);   // XR: 같은 프레임 즉시 전환
            }

            CurrentView = target;
            UpdateDisplayElements();
            NotifyServer();

            _isTransitioning = false;
        }

        private void ApplyInstantPerspective(ViewPerspective target)
        {
            Transform targetAnchor = AnchorFor(target);
            if (vrCameraRig != null && targetAnchor != null)
            {
                BindRig(target, targetAnchor);
            }
            CurrentView = target;
            UpdateDisplayElements();
        }

        private void BindRig(ViewPerspective view, Transform anchor)
        {
            vrCameraRig.position = anchor.position;
            vrCameraRig.rotation = anchor.rotation;
            // FPV: 선택 로봇 콕핏에 부모 바인딩 → 차체 추종. God-View: 월드 고정
            vrCameraRig.SetParent(view == ViewPerspective.MicroFPVCockpit ? anchor : null, true);
            ApplyProjection(view);
        }

        private void ApplyProjection(ViewPerspective view)
        {
            if (_camera == null) return;
            bool ortho = view == ViewPerspective.MacroGodView && godViewOrthographic && !XRSettings.isDeviceActive && !XRSettings.enabled;
            _camera.orthographic = ortho;
            if (ortho) _camera.orthographicSize = godViewOrthoSize;
            else _camera.fieldOfView = cockpitFieldOfView;

            int overlayBit = 1 << PathRibbonVisualizer.OverlayLayer;
            bool hideOverlay = hidePathOverlayInCockpit && view == ViewPerspective.MicroFPVCockpit;
            _camera.cullingMask = hideOverlay ? _camera.cullingMask & ~overlayBit : _camera.cullingMask | overlayBit;
        }

        /// <summary>T-025: 영상 스크린(윈드실드)을 카메라가 달린 로봇의 콕핏으로 재부착.</summary>
        private void SyncCameraScreen()
        {
            if (agentManager == null) return;
            string target = agentManager.CameraRobot;
            if (target == _screenRobot) return;
            RobotCockpit to = FindCockpit(target);
            RobotCockpit from = null;
            foreach (RobotCockpit c in robotCockpits)
                if (c != null && c.fpvScreen != null) { from = c; break; }
            _screenRobot = target;
            if (to == null || from == null || to == from || to.cockpitAnchor == null) return;
            GameObject screen = from.fpvScreen;
            Vector3 lp = screen.transform.localPosition;
            Quaternion lr = screen.transform.localRotation;
            screen.transform.SetParent(to.cockpitAnchor, false);
            screen.transform.localPosition = lp;
            screen.transform.localRotation = lr;
            from.fpvScreen = null;
            to.fpvScreen = screen;
            UpdateDisplayElements();
            Debug.Log($"[PerspectiveSwitcher] camera screen → {target} cockpit");
        }

        private void UpdateDisplayElements()
        {
            bool isMicro = (CurrentView == ViewPerspective.MicroFPVCockpit);
            foreach (RobotCockpit c in robotCockpits)
            {
                if (c != null && c.fpvScreen != null) c.fpvScreen.SetActive(isMicro && c == _selected);
            }
            if (macroOverviewHUD != null) macroOverviewHUD.SetActive(!isMicro);
        }

        private void NotifyServer()
        {
            if (wsManager == null) return;
            string mode = (CurrentView == ViewPerspective.MicroFPVCockpit) ? ModeFPV : ModeGodView;
            _ = wsManager.SendTextAsync($"{{\"cmd\":\"TELEPORT\",\"mode\":\"{mode}\",\"robot\":\"{SelectedRobotId}\"}}");
        }
    }
}
