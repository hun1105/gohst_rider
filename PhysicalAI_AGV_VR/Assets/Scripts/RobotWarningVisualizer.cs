using UnityEngine;

namespace PhysicalAI.VR
{
    /// <summary>
    /// 로봇 악센트 링 경고 시각화.
    /// 평상시: 원래 식별 색상 유지 (TB1 Cyan / TB2 Orange)
    /// 비상정지(인터록) 시: Red ↔ 원색 0.3초 주기 점멸 + 발광
    /// T-015: 탑다운 God-View 가시성 — 차체 전체 적색 점멸 + 바닥 적색 위험 원판
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

        [Header("T-015 탑다운 가시성")]
        [Tooltip("인터록 시 차체 전체(링 외 렌더러)도 적색 점멸")]
        public bool tintWholeRobot = true;
        [Tooltip("적색 대상에서 제외할 오브젝트 이름 (FPV 영상 스크린, 선택 헤일로)")]
        public string[] tintExcludeNames = { "FPV_Screen_Windshield", "Selection_Halo" };
        [Tooltip("인터록 시 로봇 아래 바닥 적색 원판 표시")]
        public bool showDangerDisc = true;
        [Tooltip("위험 원판 반경 (m) — LiDAR 전방 가드 0.35m 기준")]
        public float dangerDiscRadius = 0.45f;
        public float dangerDiscThickness = 0.004f;
        public float dangerDiscHeight = 0.003f;

        [Header("디버그")]
        public bool forceWarningForTest = false;

        public bool IsWarningActive { get; private set; }

        private const float OffPhaseDim = 0.35f;  // 점멸 OFF 위상 적색 밝기

        private static readonly int BaseColorId = Shader.PropertyToID("_BaseColor"); // URP
        private static readonly int ColorId = Shader.PropertyToID("_Color");         // Built-in 폴백
        private static readonly int EmissionId = Shader.PropertyToID("_EmissionColor");

        private MaterialPropertyBlock _mpb;
        private MaterialPropertyBlock _clearBlock;
        private Renderer[] _bodyRenderers = new Renderer[0];
        private GameObject _dangerDisc;
        private Renderer _dangerDiscRenderer;
        private Material _dangerDiscMaterial;
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
            _clearBlock = new MaterialPropertyBlock();
            CollectBodyRenderers();
            CreateDangerDisc();
        }

        private void CollectBodyRenderers()
        {
            if (!tintWholeRobot) return;
            var list = new System.Collections.Generic.List<Renderer>();
            foreach (Renderer r in GetComponentsInChildren<Renderer>(true))
            {
                if (r == accentRenderer || System.Array.IndexOf(tintExcludeNames, r.gameObject.name) >= 0) continue;
                list.Add(r);
            }
            _bodyRenderers = list.ToArray();
        }

        private void CreateDangerDisc()
        {
            if (!showDangerDisc) return;
            _dangerDisc = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            _dangerDisc.name = "Interlock_Danger_Disc";
            Destroy(_dangerDisc.GetComponent<Collider>());  // 마우스 피킹 방해 금지
            _dangerDisc.transform.SetParent(transform, false);
            _dangerDisc.transform.localPosition = new Vector3(0f, dangerDiscHeight, 0f);
            // Cylinder 높이 2 기준 → Y 스케일 절반
            _dangerDisc.transform.localScale = new Vector3(dangerDiscRadius * 2f, dangerDiscThickness * 0.5f, dangerDiscRadius * 2f);
            _dangerDiscRenderer = _dangerDisc.GetComponent<Renderer>();
            // 링 머티리얼 복제 (런타임 셰이더 스트리핑 회피), 색은 MPB로만 변경
            _dangerDiscMaterial = new Material(accentRenderer.sharedMaterial) { name = "InterlockDangerDisc_Runtime" };
            _dangerDiscRenderer.sharedMaterial = _dangerDiscMaterial;
            _dangerDisc.SetActive(false);
        }

        private void ApplyBody(bool red, Color emission)
        {
            foreach (Renderer r in _bodyRenderers)
            {
                if (r == null) continue;
                if (!red) { r.SetPropertyBlock(_clearBlock); continue; }  // 원래 머티리얼 색 복귀
                r.GetPropertyBlock(_mpb);
                _mpb.SetColor(BaseColorId, warningColor);
                _mpb.SetColor(ColorId, warningColor);
                _mpb.SetColor(EmissionId, emission);
                r.SetPropertyBlock(_mpb);
            }
        }

        private void SetDangerDisc(bool visible, bool bright)
        {
            if (_dangerDisc == null) return;
            if (_dangerDisc.activeSelf != visible) _dangerDisc.SetActive(visible);
            if (!visible) return;
            _dangerDiscRenderer.GetPropertyBlock(_mpb);
            Color c = bright ? warningColor : warningColor * 0.45f;
            _mpb.SetColor(BaseColorId, c);
            _mpb.SetColor(ColorId, c);
            _mpb.SetColor(EmissionId, bright ? warningColor * warningEmissionIntensity : Color.black);
            _dangerDiscRenderer.SetPropertyBlock(_mpb);
        }

        private void Update()
        {
            // T-016 → T-025: 로봇별 정지·알림 (인터록·로봇 간 만남·AUTO STUCK) → 적색 경고
            bool warning = forceWarningForTest || (agentManager != null && agentManager.RobotAlert(robotId));
            IsWarningActive = warning;

            if (!warning)
            {
                if (_lastWarning)
                {
                    ApplyColor(normalColor, Color.black); // 경고 해제 즉시 복귀
                    ApplyBody(false, Color.black);
                    SetDangerDisc(false, false);
                }
                _lastWarning = false;
                return;
            }

            float half = Mathf.Max(0.02f, blinkPeriod * 0.5f);
            bool blinkOn = Mathf.FloorToInt(Time.unscaledTime / half) % 2 == 0;

            // 경고 진입 첫 프레임 또는 위상 전환 시에만 갱신
            if (!_lastWarning || blinkOn != _lastBlinkOn)
            {
                if (blinkOn) ApplyColor(warningColor, warningColor * warningEmissionIntensity);
                else ApplyColor(warningColor * OffPhaseDim, Color.black); // 어두운 적색: 경고 중 식별색(청록/주황) 노출 금지
                // 차체: 점멸 ON = 발광 적색 / OFF = 어두운 적색 (경고 동안 계속 빨간 계열 유지)
                ApplyBody(true, blinkOn ? warningColor * (warningEmissionIntensity * 0.5f) : Color.black);
                SetDangerDisc(true, blinkOn);
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
            if (_clearBlock != null) ApplyBody(false, Color.black);
            SetDangerDisc(false, false);
            _lastWarning = false;
        }

        private void OnDestroy()
        {
            if (_dangerDiscMaterial != null) Destroy(_dangerDiscMaterial);
        }
    }
}
