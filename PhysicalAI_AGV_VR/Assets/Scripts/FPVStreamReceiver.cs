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

        private Texture2D _videoTexture;

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
            if (wsManager != null)
            {
                wsManager.OnImageFrameReceived += OnFrameReceived;
            }
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
                _videoTexture.LoadImage(jpegBytes);
            }
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
