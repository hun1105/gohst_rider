using UnityEngine;

namespace PhysicalAI.VR
{
    /// <summary>
    /// WebSocket을 통해 실시간으로 수신되는 카메라 JPEG 스트림을 
    /// 3D 가상 스크린(MeshRenderer/Renderer)에 실시간 텍스처로 디코딩 및 렌더링
    /// uGUI 의존성 없이 순수 UnityEngine 기반 동작 보장
    /// </summary>
    public class FPVStreamReceiver : MonoBehaviour
    {
        [Header("참조 컴포넌트")]
        public WebSocketManager wsManager;

        [Header("렌더링 대상 (3D 콕핏 앞유리/스크린)")]
        [Tooltip("3D 콕핏 앞유리/스크린용 Renderer (Quad, Plane 등)")]
        public Renderer targetScreenRenderer;

        [Header("PC 화면 미리보기 (OnGUI PIP)")]
        [Tooltip("PC Game 뷰 좌하단 카메라 PIP. 기본 꺼짐: 콕핏 앞유리에 영상이 이미 표시됨. 디버그용으로만 켬")]
        public bool showDesktopPreview = false;
        [Tooltip("PC 화면이 God-View(탑다운 관제 맵)일 때 PIP 숨김. 콕핏(1인칭)일 때만 표시")]
        public bool hidePreviewInGodView = true;
        public PerspectiveSwitcher perspectiveSwitcher;
        [Tooltip("XR 화면 분리 활성 시 PC 모니터는 항상 관제 맵 → PIP 숨김")]
        public DualDisplayController dualDisplay;
        public Vector2 previewSize = new Vector2(320f, 240f);
        public float previewMargin = 12f;
        [Tooltip("이 시간(초) 동안 프레임이 없으면 NO SIGNAL 표시")]
        public float signalTimeout = 1.0f;

        private Texture2D _videoTexture;
        private float _lastFrameTime = float.NegativeInfinity;
        private int _frameCount;

        private void Awake()
        {
            // 640x480 기본 해상도 동적 텍스처 생성
            _videoTexture = new Texture2D(640, 480, TextureFormat.RGB24, false);

            if (targetScreenRenderer != null)
            {
                targetScreenRenderer.material.mainTexture = _videoTexture;
            }
        }

        private void OnEnable()
        {
            Subscribe();
        }

        // AddComponent 직후 OnEnable 시점엔 wsManager 미할당일 수 있음 → Start에서 재확인
        private void Start()
        {
            Subscribe();
        }

        private void Subscribe()
        {
            if (wsManager == null) return;
            wsManager.OnImageFrameReceived -= OnFrameReceived;  // 중복 구독 방지
            wsManager.OnImageFrameReceived += OnFrameReceived;
        }

        private void OnDisable()
        {
            if (wsManager != null)
            {
                wsManager.OnImageFrameReceived -= OnFrameReceived;
            }
        }

        private void OnFrameReceived(byte[] jpegBytes)
        {
            if (jpegBytes == null || jpegBytes.Length == 0) return;

            // JPEG 바이트를 실시간 텍스처에 로드
            if (_videoTexture != null)
            {
                if (_videoTexture.LoadImage(jpegBytes))
                {
                    _lastFrameTime = Time.unscaledTime;
                    _frameCount++;
                }
            }
        }

        /// <summary>PC 모니터에 탑다운 관제 맵이 떠 있는지: XR 화면 분리 중이거나 시점이 God-View.</summary>
        private bool PcShowsGodView()
        {
            if (dualDisplay != null && dualDisplay.IsDualDisplayActive) return true;
            return perspectiveSwitcher != null && perspectiveSwitcher.CurrentView == ViewPerspective.MacroGodView;
        }

        private void OnGUI()
        {
            if (!showDesktopPreview || _videoTexture == null) return;
            if (hidePreviewInGodView && PcShowsGodView()) return;
            var rect = new Rect(previewMargin, Screen.height - previewSize.y - previewMargin, previewSize.x, previewSize.y);
            bool live = Time.unscaledTime - _lastFrameTime < signalTimeout;
            if (_frameCount > 0) GUI.DrawTexture(rect, _videoTexture, ScaleMode.ScaleToFit);
            else GUI.Box(rect, GUIContent.none);
            GUI.Label(new Rect(rect.x + 6f, rect.y + 4f, rect.width, 22f),
                live ? $"TB CAM LIVE ({_videoTexture.width}x{_videoTexture.height})" : "TB CAM: NO SIGNAL");
        }

        private void OnDestroy()
        {
            if (_videoTexture != null)
            {
                Destroy(_videoTexture);
            }
        }
    }
}
