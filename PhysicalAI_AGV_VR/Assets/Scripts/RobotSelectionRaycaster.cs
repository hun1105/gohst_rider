using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace PhysicalAI.VR
{
    /// <summary>
    /// T-007: God-View 마우스 피킹 → 로봇 선택 → FPV 빙의 + 조종 권한 전환.
    /// - 호버: 로봇 발밑 노란 헤일로 + 마우스 옆 라벨 (OnGUI, uGUI 의존 없음)
    /// - 좌클릭: AGVControllerInput.SetControlledRobot → PerspectiveSwitcher.EnterCockpit
    /// 로봇 목록은 PerspectiveSwitcher.robotCockpits 단일 원천 사용.
    /// 헤일로는 별도 오브젝트 → RobotWarningVisualizer의 MaterialPropertyBlock과 충돌 없음.
    /// </summary>
    [DisallowMultipleComponent]
    public class RobotSelectionRaycaster : MonoBehaviour
    {
        private const int MaxRaycastHits = 16;
        private const string HaloObjectName = "Selection_Halo";

        private static readonly int BaseColorId = Shader.PropertyToID("_BaseColor"); // URP
        private static readonly int ColorId = Shader.PropertyToID("_Color");         // Built-in 폴백

        [Header("연결")]
        public PerspectiveSwitcher perspectiveSwitcher;
        public AGVControllerInput controllerInput;
        [Tooltip("비우면 Camera.main 사용")]
        public Camera pickCamera;
        [Tooltip("듀얼 디스플레이(PC 맵 상시 표시) 시 콕핏 시점에서도 PC 맵 클릭으로 로봇 전환 허용")]
        public bool allowPickInCockpit;

        [Header("레이캐스트")]
        public float maxPickDistance = 100f;
        public LayerMask pickMask = ~0;
        [Tooltip("true: 랙 등 가림막 뒤 로봇도 선택 (관제 편의)")]
        public bool pickThroughOccluders = true;

        [Header("호버 하이라이트")]
        public Color highlightColor = new Color(1f, 0.92f, 0.1f);
        [Tooltip("헤일로 지름 (m). 절차 모델 플레이트 지름 0.35m 대비 여유")]
        public float haloDiameter = 0.6f;
        [Tooltip("헤일로 두께 (Cylinder Y 스케일)")]
        public float haloThickness = 0.005f;
        [Tooltip("로봇 루트 기준 헤일로 높이 (m)")]
        public float haloLocalY = 0.01f;

        [Header("호버 라벨")]
        public bool showHoverLabel = true;
        public Vector2 labelOffset = new Vector2(18f, 6f);
        public Vector2 labelSize = new Vector2(260f, 26f);
        public int labelFontSize = 14;

        public string HoveredRobotId => _hovered != null ? _hovered.robotId : null;

        private readonly RaycastHit[] _hits = new RaycastHit[MaxRaycastHits];
        private readonly Dictionary<RobotCockpit, GameObject> _halos = new Dictionary<RobotCockpit, GameObject>();
        private RobotCockpit _hovered;
        private Material _haloMaterial;
        private GUIStyle _labelStyle;

        private void Awake()
        {
            if (perspectiveSwitcher == null) perspectiveSwitcher = FindAnyObjectByType<PerspectiveSwitcher>();
            if (controllerInput == null) controllerInput = FindAnyObjectByType<AGVControllerInput>();

            Shader shader = Shader.Find("Universal Render Pipeline/Unlit") ?? Shader.Find("Unlit/Color");
            if (shader != null)
            {
                _haloMaterial = new Material(shader) { name = "SelectionHalo_Runtime" };
                if (_haloMaterial.HasProperty(BaseColorId)) _haloMaterial.SetColor(BaseColorId, highlightColor);
                if (_haloMaterial.HasProperty(ColorId)) _haloMaterial.SetColor(ColorId, highlightColor);
            }
            else
            {
                Debug.LogWarning("[RobotSelectionRaycaster] Unlit 셰이더 없음. 헤일로 없이 라벨만 표시.");
            }
        }

        private void Update()
        {
            RobotCockpit hit = CanPick() ? PickUnderMouse() : null;
            SetHovered(hit);

            if (hit != null && Input.GetMouseButtonDown(0))
            {
                Select(hit);
            }
        }

        private bool CanPick()
        {
            if (perspectiveSwitcher == null || !Input.mousePresent) return false;
            if (!allowPickInCockpit && perspectiveSwitcher.CurrentView != ViewPerspective.MacroGodView) return false;
            if (perspectiveSwitcher.IsTransitioning) return false;

            Vector3 m = Input.mousePosition;
            return m.x >= 0f && m.y >= 0f && m.x <= Screen.width && m.y <= Screen.height;
        }

        private RobotCockpit PickUnderMouse()
        {
            Camera cam = pickCamera != null ? pickCamera : Camera.main;
            if (cam == null) return null;

            Ray ray = cam.ScreenPointToRay(Input.mousePosition);
            int count = Physics.RaycastNonAlloc(ray, _hits, maxPickDistance, pickMask, QueryTriggerInteraction.Collide);

            // NonAlloc 결과는 정렬 안 됨 → 최근접 선별
            RobotCockpit best = null;
            float bestRobotDist = float.MaxValue;
            float nearestAnyDist = float.MaxValue;
            for (int i = 0; i < count; i++)
            {
                float d = _hits[i].distance;
                if (d < nearestAnyDist) nearestAnyDist = d;

                RobotCockpit c = perspectiveSwitcher.FindCockpitByTransform(_hits[i].transform);
                if (c != null && d < bestRobotDist)
                {
                    best = c;
                    bestRobotDist = d;
                }
            }

            // 가림막 차단 모드: 로봇이 최전면 히트가 아니면 선택 불가
            if (!pickThroughOccluders && best != null && bestRobotDist > nearestAnyDist) return null;
            return best;
        }

        private void Select(RobotCockpit target)
        {
            // 1) 조종 권한 전환 (SELECT_ROBOT 먼저) → 2) 시점 전환 (완료 시 TELEPORT)
            if (controllerInput != null) controllerInput.SetControlledRobot(target.robotId, target.robotRoot);
            perspectiveSwitcher.EnterCockpit(target.robotId);
            SetHovered(null);
        }

        // ===================== 하이라이트 =====================

        private void SetHovered(RobotCockpit target)
        {
            if (target == _hovered) return;
            SetHaloActive(_hovered, false);
            _hovered = target;
            SetHaloActive(_hovered, true);
        }

        private void SetHaloActive(RobotCockpit target, bool active)
        {
            if (target == null || target.robotRoot == null) return;

            if (!_halos.TryGetValue(target, out GameObject halo) || halo == null)
            {
                if (!active || _haloMaterial == null) return;
                halo = CreateHalo(target.robotRoot);
                _halos[target] = halo;
            }
            halo.SetActive(active);
        }

        private GameObject CreateHalo(Transform robotRoot)
        {
            GameObject halo = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            halo.name = HaloObjectName;
            // 피킹 대상 아님. (Destroy는 프레임 끝 처리지만 로봇 자식이라 오선택 없음)
            Destroy(halo.GetComponent<Collider>());

            halo.transform.SetParent(robotRoot, false);
            halo.transform.localPosition = new Vector3(0f, haloLocalY, 0f);
            halo.transform.localRotation = Quaternion.identity;
            halo.transform.localScale = new Vector3(haloDiameter, haloThickness, haloDiameter);

            MeshRenderer mr = halo.GetComponent<MeshRenderer>();
            mr.sharedMaterial = _haloMaterial; // 공유 머티리얼 1개 → 인스턴스 누수 없음
            mr.shadowCastingMode = ShadowCastingMode.Off;
            mr.receiveShadows = false;
            return halo;
        }

        private void OnGUI()
        {
            if (!showHoverLabel || _hovered == null) return;

            if (_labelStyle == null)
            {
                _labelStyle = new GUIStyle(GUI.skin.box) { fontSize = labelFontSize, fontStyle = FontStyle.Bold, alignment = TextAnchor.MiddleLeft };
                _labelStyle.normal.textColor = highlightColor;
            }

            Vector3 m = Input.mousePosition;
            Rect r = new Rect(m.x + labelOffset.x, Screen.height - m.y + labelOffset.y, labelSize.x, labelSize.y);
            GUI.Box(r, $" {_hovered.robotId.ToUpperInvariant()}  |  CLICK: ENTER FPV COCKPIT", _labelStyle);
        }

        private void OnDisable()
        {
            SetHovered(null);
        }

        private void OnDestroy()
        {
            foreach (GameObject halo in _halos.Values)
            {
                if (halo != null) Destroy(halo);
            }
            _halos.Clear();
            if (_haloMaterial != null) Destroy(_haloMaterial);
        }
    }
}
