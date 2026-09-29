using UnityEngine;

namespace PhysicalAI.VR
{
    /// <summary>
    /// 로봇 악센트 링 경고 시각화.
    /// 평상시: 원래 식별 색상 유지 (TB1 Cyan / TB2 Orange)
    /// 비상정지(인터록) 시: Red ↔ 원색 0.3초 주기 점멸 + 발광
    /// 로봇 루트 GameObject에 부착. MaterialPropertyBlock 사용 → 머티리얼 인스턴스 누수 없음.
    /// </summary>
    [DisallowMultipleComponent]
    public class RobotWarningVisualizer : MonoBehaviour
    {
        [Header("연결")]
        public TurtleBotMultiAgentManager agentManager;
        [Tooltip("tb1 또는 tb2")]
        public string robotId = "tb1";

        [Header("대상 렌더러 (비우면 'Accent_Status_Ring' 자동 탐색)")]
        public Renderer accentRenderer;
        public string accentObjectName = "Accent_Status_Ring";

        [Header("색상")]
        public Color normalColor = Color.cyan;
        public Color warningColor = Color.red;
        [Tooltip("경고 시 발광 세기 (URP Lit Emission)")]
        public float warningEmissionIntensity = 3.0f;

        [Header("점멸")]
        [Tooltip("한 주기(ON+OFF) 길이, 초")]
        public float blinkPeriod = 0.3f;

        [Header("디버그")]
        public bool forceWarningForTest = false;

        public bool IsWarningActive { get; private set; }

        private static readonly int BaseColorId = Shader.PropertyToID("_BaseColor"); // URP
        private static readonly int ColorId = Shader.PropertyToID("_Color");         // Built-in 폴백
        private static readonly int EmissionId = Shader.PropertyToID("_EmissionColor");

        private MaterialPropertyBlock _mpb;
        private bool _lastBlinkOn;
        private bool _lastWarning;

        private void Awake()
        {
            _mpb = new MaterialPropertyBlock();

            if (accentRenderer == null)
            {
                foreach (Transform t in GetComponentsInChildren<Transform>(true))
                {
                    if (t.name == accentObjectName)
                    {
                        accentRenderer = t.GetComponent<Renderer>();
                        break;
                    }
                }
            }

            if (accentRenderer == null)
            {
                Debug.LogWarning($"[RobotWarningVisualizer:{robotId}] '{accentObjectName}' 렌더러 없음. 비활성화.");
                enabled = false;
                return;
            }

            // 원래 색상 자동 취득 (인스펙터 기본값보다 실제 머티리얼 우선)
            Material m = accentRenderer.sharedMaterial;
            if (m != null)
            {
                if (m.HasProperty(BaseColorId)) normalColor = m.GetColor(BaseColorId);
                else if (m.HasProperty(ColorId)) normalColor = m.GetColor(ColorId);

                // 발광 키워드 활성화 (MPB로 _EmissionColor 제어 가능하도록)
                if (m.HasProperty(EmissionId))
                {
                    m.EnableKeyword("_EMISSION");
                    m.globalIlluminationFlags = MaterialGlobalIlluminationFlags.RealtimeEmissive;
                }
            }

            ApplyColor(normalColor, Color.black);
        }

        private void Update()
        {
            bool warning = forceWarningForTest ||
                           (agentManager != null && agentManager.IsRobotInterlocked(robotId));
            IsWarningActive = warning;

            if (!warning)
            {
                if (_lastWarning) ApplyColor(normalColor, Color.black); // 경고 해제 즉시 복귀
                _lastWarning = false;
                return;
            }

            float half = Mathf.Max(0.02f, blinkPeriod * 0.5f);
            bool blinkOn = Mathf.FloorToInt(Time.unscaledTime / half) % 2 == 0;

            // 경고 진입 첫 프레임 또는 위상 전환 시에만 갱신
            if (!_lastWarning || blinkOn != _lastBlinkOn)
            {
                if (blinkOn) ApplyColor(warningColor, warningColor * warningEmissionIntensity);
                else ApplyColor(normalColor * 0.25f, Color.black); // 어둡게 → 대비 극대화
                _lastBlinkOn = blinkOn;
            }
            _lastWarning = true;
        }

        private void ApplyColor(Color baseColor, Color emission)
        {
            if (accentRenderer == null) return;
            accentRenderer.GetPropertyBlock(_mpb);
            _mpb.SetColor(BaseColorId, baseColor);
            _mpb.SetColor(ColorId, baseColor);
            _mpb.SetColor(EmissionId, emission);
            accentRenderer.SetPropertyBlock(_mpb);
        }

        private void OnDisable()
        {
            if (accentRenderer != null) ApplyColor(normalColor, Color.black);
            _lastWarning = false;
        }
    }
}
