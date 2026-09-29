using UnityEngine;

namespace PhysicalAI.VR
{
    /// <summary>
    /// God-View 우측 상단 반투명 관제 사이드바 (순수 OnGUI, uGUI 의존성 없음).
    /// TB1/TB2 위치·속도·배터리·비상정지 상태 + WS 링크/텔레메트리 지연 표시.
    /// 1920x1080 기준 해상도 자동 스케일. F1 키로 표시 토글.
    /// ※ OnGUI는 PC 모니터/미러 화면 전용. Quest 헤드셋 내부 표시는 WorldSpace 패널 필요.
    /// </summary>
    public class GodViewSidebarHUD : MonoBehaviour
    {
        [Header("데이터 소스")]
        public TurtleBotMultiAgentManager agentManager;

        [Header("레이아웃 (1920x1080 기준 px)")]
        public float panelWidth = 360f;
        public float margin = 20f;
        public Vector2 referenceResolution = new Vector2(1920, 1080);

        [Header("표시")]
        public bool visible = true;
        public KeyCode toggleKey = KeyCode.F1;
        [Range(0f, 1f)] public float panelAlpha = 0.72f;
        [Tooltip("이 시간(초) 이상 텔레메트리 미수신 시 STALE 경고")]
        public float staleTimeout = 1.0f;
        public float blinkPeriod = 0.3f;

        [Header("로봇 식별 색상")]
        public Color tb1Color = Color.cyan;
        public Color tb2Color = new Color(1f, 0.5f, 0f);

        // 내부 리소스
        private Texture2D _texWhite;
        private GUIStyle _title, _label, _small, _badge;
        private bool _stylesReady;

        private const float LineH = 22f;

        private void Awake()
        {
            _texWhite = new Texture2D(1, 1, TextureFormat.RGBA32, false);
            _texWhite.SetPixel(0, 0, Color.white);
            _texWhite.Apply();
            _texWhite.hideFlags = HideFlags.HideAndDontSave;

            if (agentManager == null) agentManager = FindAnyObjectByType<TurtleBotMultiAgentManager>();
        }

        private void OnDestroy()
        {
            if (_texWhite != null) Destroy(_texWhite);
        }

        private void Update()
        {
            if (Input.GetKeyDown(toggleKey)) visible = !visible;
        }

        private void BuildStyles()
        {
            _title = new GUIStyle(GUI.skin.label) { fontSize = 18, fontStyle = FontStyle.Bold, richText = true };
            _title.normal.textColor = Color.white;
            _label = new GUIStyle(GUI.skin.label) { fontSize = 14, richText = true };
            _label.normal.textColor = new Color(0.92f, 0.92f, 0.92f);
            _small = new GUIStyle(_label) { fontSize = 12 };
            _small.normal.textColor = new Color(0.7f, 0.7f, 0.7f);
            _badge = new GUIStyle(_label) { fontSize = 13, fontStyle = FontStyle.Bold, alignment = TextAnchor.MiddleCenter };
            _badge.normal.textColor = Color.white;
            _stylesReady = true;
        }

        private void OnGUI()
        {
            if (!visible) return;
            if (!_stylesReady) BuildStyles();

            // 해상도 독립 스케일 (높이 기준)
            float scale = Screen.height / referenceResolution.y;
            Matrix4x4 prev = GUI.matrix;
            GUI.matrix = Matrix4x4.TRS(Vector3.zero, Quaternion.identity, new Vector3(scale, scale, 1f));
            float virtW = Screen.width / scale;

            float x = virtW - panelWidth - margin;
            float y = margin;
            float cardH = 140f;
            float panelH = 96f + cardH * 2f + 16f;

            bool blinkOn = Mathf.FloorToInt(Time.unscaledTime / Mathf.Max(0.02f, blinkPeriod * 0.5f)) % 2 == 0;

            // 패널 배경
            Fill(new Rect(x, y, panelWidth, panelH), new Color(0.05f, 0.07f, 0.1f, panelAlpha));
            Fill(new Rect(x, y, panelWidth, 3f), new Color(0.2f, 0.8f, 1f, 0.9f));

            float cx = x + 14f;
            float cw = panelWidth - 28f;
            float cy = y + 10f;

            GUI.Label(new Rect(cx, cy, cw, 26f), "GOD-VIEW  CONTROL", _title);
            cy += 28f;

            // 링크 상태
            DrawLinkStatus(new Rect(cx, cy, cw, LineH));
            cy += LineH;

            // 전역 안전 상태
            string status = agentManager != null ? agentManager.safetyStatus : "N/A";
            bool anyEstop = agentManager != null && agentManager.isInterlocked;
            string sc = anyEstop ? "#FF4040" : "#40FF80";
            GUI.Label(new Rect(cx, cy, cw, LineH), $"SAFETY  <color={sc}><b>{status}</b></color>", _label);
            cy += LineH + 12f;

            DrawRobotCard(new Rect(cx, cy, cw, cardH - 8f), "tb1", "TB1  ·  TELEOP AGV", tb1Color, blinkOn);
            cy += cardH;
            DrawRobotCard(new Rect(cx, cy, cw, cardH - 8f), "tb2", "TB2  ·  PATROL AGV", tb2Color, blinkOn);

            GUI.Label(new Rect(x, y + panelH + 2f, panelWidth - 6f, 18f), $"[{toggleKey}] toggle HUD",
                      new GUIStyle(_small) { alignment = TextAnchor.UpperRight });

            GUI.matrix = prev;
        }

        private void DrawLinkStatus(Rect r)
        {
            string txt;
            if (agentManager == null)
            {
                txt = "<color=#FF4040>LINK  NO MANAGER</color>";
            }
            else if (!agentManager.IsConnected)
            {
                txt = "<color=#FF4040>LINK  DISCONNECTED</color>";
            }
            else if (agentManager.LastTelemetryTime < 0f)
            {
                txt = "<color=#FFC040>LINK  WAITING DATA</color>";
            }
            else
            {
                float age = Time.unscaledTime - agentManager.LastTelemetryTime;
                txt = age > staleTimeout
                    ? $"<color=#FFC040>LINK  STALE  ({age:F1}s)</color>"
                    : $"<color=#40FF80>LINK  ONLINE</color>  <color=#999999>({age * 1000f:F0} ms)</color>";
            }
            GUI.Label(r, txt, _label);
        }

        private void DrawRobotCard(Rect r, string id, string title, Color idColor, bool blinkOn)
        {
            RobotPoseData d = agentManager != null ? agentManager.GetRobotData(id) : null;
            bool estop = agentManager != null && agentManager.IsRobotInterlocked(id);

            // 카드 배경: E-STOP 시 빨간 점멸
            Color bg = estop
                ? (blinkOn ? new Color(0.75f, 0.05f, 0.05f, 0.85f) : new Color(0.3f, 0.02f, 0.02f, 0.85f))
                : new Color(1f, 1f, 1f, 0.06f);
            Fill(r, bg);
            Fill(new Rect(r.x, r.y, 4f, r.height), estop ? Color.red : idColor);

            float px = r.x + 12f, pw = r.width - 20f, py = r.y + 6f;

            GUI.Label(new Rect(px, py, pw, LineH), $"<b><color=#{ColorUtility.ToHtmlStringRGB(idColor)}>{title}</color></b>", _label);

            // 상태 배지
            string badgeText = d == null ? "NO DATA" : (estop ? "E-STOP" : "NORMAL");
            Color badgeCol = d == null ? new Color(0.4f, 0.4f, 0.4f) : (estop ? Color.red : new Color(0.1f, 0.6f, 0.25f));
            Rect badge = new Rect(r.xMax - 88f, py + 1f, 80f, 20f);
            Fill(badge, badgeCol);
            GUI.Label(badge, badgeText, _badge);
            py += LineH + 4f;

            if (d == null)
            {
                GUI.Label(new Rect(px, py, pw, LineH), "Waiting for telemetry...", _small);
                return;
            }

            GUI.Label(new Rect(px, py, pw, LineH), $"POS   x {d.x,6:F2}  z {d.z,6:F2} m", _label); py += LineH;
            GUI.Label(new Rect(px, py, pw, LineH), $"YAW   {d.yaw,6:F1}°", _label); py += LineH;
            GUI.Label(new Rect(px, py, pw, LineH), $"VEL   v {d.linear_vel,5:F2} m/s   ω {d.angular_vel,5:F2} rad/s", _label); py += LineH + 4f;

            // 배터리 바
            float bat = Mathf.Clamp(d.battery, 0f, 100f);
            Color batCol = bat > 50f ? new Color(0.25f, 0.85f, 0.35f) : bat > 20f ? new Color(1f, 0.75f, 0.1f) : Color.red;
            GUI.Label(new Rect(px, py, 50f, LineH), "BAT", _label);
            Rect barBg = new Rect(px + 46f, py + 5f, pw - 110f, 12f);
            Fill(barBg, new Color(0f, 0f, 0f, 0.5f));
            Fill(new Rect(barBg.x, barBg.y, barBg.width * bat / 100f, barBg.height), batCol);
            GUI.Label(new Rect(barBg.xMax + 8f, py, 60f, LineH), $"{bat:F0}%", _label);
        }

        private void Fill(Rect r, Color c)
        {
            Color prev = GUI.color;
            GUI.color = c;
            GUI.DrawTexture(r, _texWhite);
            GUI.color = prev;
        }
    }
}
