using UnityEngine;

namespace PhysicalAI.VR
{
    /// <summary>
    /// T-019: 로봇이 "보는 것"과 "갈 곳"을 디지털 트윈 바닥에 표시 (Waymo 탑승자 화면·NVIDIA PathNet 색 방식 참고).
    /// - 추천 궤적: 로봇 폭 띠, 신뢰도 색 (GREEN 여유 / YELLOW 좁음 / RED 막힘)
    /// - 예상 궤적: 현재 지령 유지 시 경로 (수동 운전 가이드선, 가는 띠)
    /// - 대안 궤적: 흐린 띠 최대 2개
    /// - LiDAR 점: 실제 주변 장애물 → 트윈 배치와 실물 정합 여부를 눈으로 확인
    /// - T-024 선회 추천: 로봇 둘레 선회 호(현재 방향 → 목표 방향) + 선회 후 직진 띠 (수치 미표시)
    /// 탑다운 관제 맵과 콕핏 1인칭 모두에서 보이도록 바닥에 눕힌 띠로 그림.
    /// </summary>
    public class PathRibbonVisualizer : MonoBehaviour
    {
        [Header("연결")]
        public TurtleBotMultiAgentManager agentManager;

        [Header("띠")]
        [Tooltip("추천 궤적 폭 (m) — 로봇 폭 회랑 0.24m")]
        public float recommendedWidth = 0.24f;
        public float predictedWidth = 0.06f;
        public float alternativeWidth = 0.10f;
        [Tooltip("띠 높이 (m). 로봇 트윈 기준면(y 0.1)·위험 원판(y≈0.103) 위로 → 원판에 가려지지 않게")]
        public float ribbonHeight = 0.11f;

        [Header("신뢰도 색")]
        public Color greenColor = new Color(0.12f, 0.80f, 0.40f);
        public Color yellowColor = new Color(0.98f, 0.76f, 0.15f);
        public Color redColor = new Color(0.90f, 0.12f, 0.20f);
        public Color predictedColor = new Color(0.92f, 0.95f, 1.0f);
        [Range(0f, 1f)] public float alternativeDim = 0.45f;

        [Header("선회 추천 (T-024)")]
        [Tooltip("로봇 둘레 선회 호 반경 (m)")]
        public float pivotArcRadius = 0.25f;
        public float pivotArcWidth = 0.05f;
        private const int PivotArcSegments = 24;

        [Header("표시 조건")]
        [Tooltip("관제 맵(God-View) 경로 띠는 인터록(정지·알림) 중인 로봇만 표시. 콕핏은 영상 위 경로로 항상 표시")]
        public bool pathOnlyOnInterlock = true;

        [Header("LiDAR 점")]
        [Tooltip("관제 맵에 LiDAR 점 표시 (배치·정합 점검용, 기본 끔)")]
        public bool showScan = false;
        public KeyCode toggleScanKey = KeyCode.F4;
        public float scanPointSize = 0.05f;
        public float scanHeight = 0.12f;
        public Color scanColor = new Color(0.55f, 0.85f, 1.0f);

        [Header("디버그 (배치 렌더 검증)")]
        public bool forceTestPattern;

        /// <summary>경로 띠·LiDAR 점 전용 레이어. 콕핏 시점 카메라 컬링에서 제외 (영상 위 경로와 중복 방지)</summary>
        public const int OverlayLayer = 31;

        private const int MaxPathPoints = 64;
        private const int MaxScanPoints = 400;
        private const float ParticleLifetime = 1e4f;

        private LineRenderer _recommended, _predicted, _alt1, _alt2, _pivot, _pivotArc;
        private readonly float[] _arcFlat = new float[PivotArcSegments * 2];
        private ParticleSystem _scanSystem;
        private ParticleSystem.Particle[] _particles;
        private readonly Vector3[] _buffer = new Vector3[MaxPathPoints];
        private Material _material;

        private void Start()
        {
            Shader shader = Shader.Find("Universal Render Pipeline/Particles/Unlit") ?? Shader.Find("Sprites/Default");
            _material = new Material(shader) { name = "PathRibbon_Runtime" };
            if (_material.HasProperty("_Cull")) _material.SetFloat("_Cull", 0f);   // 양면 (위·아래 어디서 봐도)
            _alt1 = CreateLine("Path_Alternative_1");
            _alt2 = CreateLine("Path_Alternative_2");
            _recommended = CreateLine("Path_Recommended");
            _predicted = CreateLine("Path_Predicted");
            _pivot = CreateLine("Path_Pivot_Straight");
            _pivotArc = CreateLine("Path_Pivot_Arc");
            _scanSystem = CreateScanSystem();
            _particles = new ParticleSystem.Particle[MaxScanPoints];

            Subscribe();
            if (forceTestPattern) ApplyTestPattern();
        }

        private void OnEnable() => Subscribe();

        private void Update()
        {
            if (Input.GetKeyDown(toggleScanKey)) showScan = !showScan;   // 다음 텔레메트리에 반영
        }

        private void OnDisable()
        {
            if (agentManager != null) agentManager.OnTelemetryUpdated -= Refresh;
        }

        private void OnDestroy()
        {
            if (_material != null) Destroy(_material);
        }

        private void Subscribe()
        {
            if (agentManager == null || _recommended == null) return;   // Start 전(OnEnable 선행)은 Start에서 재시도
            agentManager.OnTelemetryUpdated -= Refresh;
            agentManager.OnTelemetryUpdated += Refresh;
        }

        private LineRenderer CreateLine(string objectName)
        {
            var go = new GameObject(objectName) { layer = OverlayLayer };
            go.transform.SetParent(transform, false);
            go.transform.rotation = Quaternion.Euler(90f, 0f, 0f);   // TransformZ 정렬 → 바닥에 눕힌 띠
            var lr = go.AddComponent<LineRenderer>();
            lr.useWorldSpace = true;
            lr.alignment = LineAlignment.TransformZ;
            lr.sharedMaterial = _material;
            lr.numCapVertices = 2;
            lr.numCornerVertices = 2;
            lr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            lr.receiveShadows = false;
            lr.positionCount = 0;
            return lr;
        }

        private ParticleSystem CreateScanSystem()
        {
            var go = new GameObject("LiDAR_Scan_Points") { layer = OverlayLayer };
            go.transform.SetParent(transform, false);
            var ps = go.AddComponent<ParticleSystem>();
            ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            var main = ps.main;
            main.loop = false;
            main.playOnAwake = false;
            main.maxParticles = MaxScanPoints;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.startSpeed = 0f;
            main.startLifetime = ParticleLifetime;
            var emission = ps.emission;
            emission.enabled = false;
            var shape = ps.shape;
            shape.enabled = false;
            var renderer = go.GetComponent<ParticleSystemRenderer>();
            renderer.sharedMaterial = _material;
            renderer.renderMode = ParticleSystemRenderMode.Billboard;
            ps.Play();
            return ps;
        }

        private void Refresh()
        {
            if (forceTestPattern || agentManager == null) return;
            PathData path = agentManager.LatestPath;
            if (pathOnlyOnInterlock && path != null)
            {
                string owner = string.IsNullOrEmpty(path.robot) ? "tb1" : path.robot;
                if (!agentManager.RobotAlert(owner)) path = null;   // 정상 주행 중엔 띠 숨김 (아래 SetLine이 null → 0점)
            }
            Color rec = LevelColor(path?.recommended_level);
            SetLine(_recommended, path?.recommended, 0, PointCount(path?.recommended), recommendedWidth, rec);
            SetLine(_predicted, path?.predicted, 0, PointCount(path?.predicted), predictedWidth,
                    Color.Lerp(predictedColor, LevelColor(path?.predicted_level), 0.35f));
            int n = path != null ? path.alt_points : 0;
            int alts = n > 0 ? PointCount(path.alternatives) / n : 0;
            Color dim = Color.Lerp(Color.black, greenColor, alternativeDim);
            SetLine(_alt1, path?.alternatives, 0, alts >= 1 ? n : 0, alternativeWidth, dim);
            SetLine(_alt2, path?.alternatives, n, alts >= 2 ? n : 0, alternativeWidth, dim);
            SetScan(agentManager.LatestScan);
            RefreshPivot(path);
        }

        /// <summary>선회 추천: 현재 방향 → 목표 방향 호 + 선회 후 직진 띠. PIVOT 아니면 숨김.</summary>
        private void RefreshPivot(PathData path)
        {
            Transform owner = path != null && path.robot == "tb2" ? agentManager.tb2Transform : agentManager.tb1Transform;
            bool pivot = path != null && path.recommended_mode == "PIVOT" && owner != null;
            if (!pivot)
            {
                _pivot.positionCount = 0;
                _pivotArc.positionCount = 0;
                return;
            }
            Color c = LevelColor(path.pivot_level);
            SetLine(_pivot, path.pivot_points, 0, PointCount(path.pivot_points), recommendedWidth, c);
            Vector3 center = owner.position;
            float yaw = owner.eulerAngles.y;
            for (int i = 0; i < PivotArcSegments; i++)
            {
                // pivot_deg +좌(반시계) → Unity yaw(시계 방향 도)는 감소
                float a = (yaw - path.pivot_deg * i / (PivotArcSegments - 1)) * Mathf.Deg2Rad;
                _arcFlat[2 * i] = center.x + pivotArcRadius * Mathf.Sin(a);
                _arcFlat[2 * i + 1] = center.z + pivotArcRadius * Mathf.Cos(a);
            }
            SetLine(_pivotArc, _arcFlat, 0, PivotArcSegments, pivotArcWidth, c);
        }

        private static int PointCount(float[] flat) => flat == null ? 0 : flat.Length / 2;

        private Color LevelColor(string level)
        {
            switch (level)
            {
                case "GREEN": return greenColor;
                case "YELLOW": return yellowColor;
                case "RED": return redColor;
                default: return greenColor;
            }
        }

        private void SetLine(LineRenderer lr, float[] flat, int startPoint, int count, float width, Color color)
        {
            if (lr == null) return;
            count = Mathf.Min(count, MaxPathPoints);
            if (flat == null || count < 2 || (startPoint + count) * 2 > flat.Length)
            {
                lr.positionCount = 0;
                return;
            }
            for (int i = 0; i < count; i++)
            {
                int k = (startPoint + i) * 2;
                _buffer[i] = new Vector3(flat[k], ribbonHeight, flat[k + 1]);
            }
            lr.positionCount = count;
            lr.SetPositions(_buffer);
            lr.startWidth = lr.endWidth = width;
            lr.startColor = color;
            lr.endColor = new Color(color.r, color.g, color.b, 0.35f);   // 끝으로 갈수록 옅게 (투명 지원 셰이더일 때)
        }

        private void SetScan(float[] flat)
        {
            if (_scanSystem == null) return;
            int count = showScan && flat != null ? Mathf.Min(flat.Length / 2, MaxScanPoints) : 0;
            for (int i = 0; i < count; i++)
            {
                _particles[i].position = new Vector3(flat[2 * i], scanHeight, flat[2 * i + 1]);
                _particles[i].startSize = scanPointSize;
                _particles[i].startColor = scanColor;
                _particles[i].remainingLifetime = ParticleLifetime;
                _particles[i].startLifetime = ParticleLifetime;
            }
            _scanSystem.SetParticles(_particles, count);
        }

        /// <summary>배치 렌더 검증용: tb1 주변에 추천(녹)·예상·대안 띠와 벽·상자 형태의 LiDAR 점을 합성.</summary>
        private void ApplyTestPattern()
        {
            Vector3 p = agentManager != null && agentManager.tb1Transform != null ? agentManager.tb1Transform.position : Vector3.zero;
            float yaw = agentManager != null && agentManager.tb1Transform != null ? agentManager.tb1Transform.eulerAngles.y : 0f;
            SetLine(_recommended, Arc(p, yaw, -1.2f), 0, 24, recommendedWidth, greenColor);
            SetLine(_predicted, Arc(p, yaw, 0f), 0, 12, predictedWidth, Color.Lerp(predictedColor, yellowColor, 0.35f));
            Color dim = Color.Lerp(Color.black, greenColor, alternativeDim);
            SetLine(_alt1, Arc(p, yaw, 1.0f), 0, 24, alternativeWidth, dim);
            SetLine(_alt2, Arc(p, yaw, -2.4f), 0, 18, alternativeWidth, dim);
            var scan = new float[2 * 120];
            for (int i = 0; i < 120; i++)
            {
                // 전방 0.7m 상자(폭 0.4m) + 좌측 0.6m 벽
                Vector2 local = i < 40 ? new Vector2(-0.2f + i * 0.01f, 0.7f) : new Vector2(-0.6f, -0.6f + (i - 40) * 0.03f);
                Vector3 w = p + Quaternion.Euler(0f, yaw, 0f) * new Vector3(local.x, 0f, local.y);
                scan[2 * i] = w.x;
                scan[2 * i + 1] = w.z;
            }
            SetScan(scan);
        }

        private static float[] Arc(Vector3 origin, float yawDeg, float curvature)
        {
            var flat = new float[MaxPathPoints * 2];
            for (int i = 0; i < MaxPathPoints; i++)
            {
                float s = (i + 1) * 0.05f;
                // 로봇 좌표: x 전방, y 좌측 / 양의 곡률 = 좌회전
                float fx = Mathf.Abs(curvature) < 1e-4f ? s : Mathf.Sin(curvature * s) / curvature;
                float fy = Mathf.Abs(curvature) < 1e-4f ? 0f : (1f - Mathf.Cos(curvature * s)) / curvature;
                Vector3 w = origin + Quaternion.Euler(0f, yawDeg, 0f) * new Vector3(-fy, 0f, fx);
                flat[2 * i] = w.x;
                flat[2 * i + 1] = w.z;
            }
            return flat;
        }
    }
}
