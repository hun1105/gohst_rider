using System.Collections;
using UnityEngine;

namespace PhysicalAI.VR
{
    public enum ViewPerspective
    {
        MacroGodView,   // 거시적 디지털 트윈 조감도 (신 모드)
        MicroFPVCockpit // 1인칭 AGV 빙의 운전 모드 (FPV 콕핏)
    }

    /// <summary>
    /// 거시적 조감도(God View)와 미시적 FPV 빙의 운전(Micro FPV) 간의 시점 전환 제어
    /// </summary>
    public class PerspectiveSwitcher : MonoBehaviour
    {
        [Header("시점 전환 위치 트랜스폼")]
        public Transform vrCameraRig;         // OVRCameraRig 또는 Main Camera 부모
        public Transform godViewAnchor;       // 상공 조감도 위치
        public Transform agvCockpitAnchor;    // AGV 차량 내부/상단 위치

        [Header("UI 및 HUD")]
        public GameObject fpvScreenObject;    // FPV 스트림 화면 또는 콕핏 메쉬
        public GameObject macroOverviewHUD;   // 거시 관제 HUD

        [Header("통신 매니저")]
        public WebSocketManager wsManager;

        [Header("전환 파라미터")]
        public float transitionDuration = 0.5f;

        public ViewPerspective CurrentView { get; private set; } = ViewPerspective.MacroGodView;
        private bool _isTransitioning = false;

        private void Start()
        {
            ApplyInstantPerspective(ViewPerspective.MacroGodView);
        }

        public void TogglePerspective()
        {
            if (_isTransitioning) return;

            ViewPerspective target = (CurrentView == ViewPerspective.MacroGodView)
                ? ViewPerspective.MicroFPVCockpit
                : ViewPerspective.MacroGodView;

            StartCoroutine(SmoothTransition(target));
        }

        public void SwitchTo(ViewPerspective target)
        {
            if (_isTransitioning || CurrentView == target) return;
            StartCoroutine(SmoothTransition(target));
        }

        private IEnumerator SmoothTransition(ViewPerspective target)
        {
            _isTransitioning = true;
            Transform targetAnchor = (target == ViewPerspective.MacroGodView) ? godViewAnchor : agvCockpitAnchor;

            if (vrCameraRig != null && targetAnchor != null)
            {
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

                vrCameraRig.position = targetAnchor.position;
                vrCameraRig.rotation = targetAnchor.rotation;
                if (target == ViewPerspective.MicroFPVCockpit)
                {
                    // 차량을 따라가도록 부모 관계 설정
                    vrCameraRig.SetParent(agvCockpitAnchor);
                }
                else
                {
                    vrCameraRig.SetParent(null);
                }
            }

            CurrentView = target;
            UpdateDisplayElements();

            // 백엔드 중계 서버에 상태 통보
            if (wsManager != null)
            {
                string modeStr = (CurrentView == ViewPerspective.MicroFPVCockpit) ? "MICRO_FPV" : "MACRO_GOD";
                _ = wsManager.SendTextAsync($"{{\"cmd\":\"TELEPORT\",\"mode\":\"{modeStr}\"}}");
            }

            _isTransitioning = false;
        }

        private void ApplyInstantPerspective(ViewPerspective target)
        {
            Transform targetAnchor = (target == ViewPerspective.MacroGodView) ? godViewAnchor : agvCockpitAnchor;
            if (vrCameraRig != null && targetAnchor != null)
            {
                vrCameraRig.position = targetAnchor.position;
                vrCameraRig.rotation = targetAnchor.rotation;
                if (target == ViewPerspective.MicroFPVCockpit)
                    vrCameraRig.SetParent(agvCockpitAnchor);
                else
                    vrCameraRig.SetParent(null);
            }
            CurrentView = target;
            UpdateDisplayElements();
        }

        private void UpdateDisplayElements()
        {
            bool isMicro = (CurrentView == ViewPerspective.MicroFPVCockpit);
            if (fpvScreenObject != null) fpvScreenObject.SetActive(isMicro);
            if (macroOverviewHUD != null) macroOverviewHUD.SetActive(!isMicro);
        }
    }
}
