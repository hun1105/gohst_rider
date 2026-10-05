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

        [Header("크기·위치 (제목줄 드래그로 이동, 위치·크기는 PlayerPrefs에 저장)")]
        [Tooltip("기준 스케일 배율. -/= 키로 실행 중 조절")]
        [Range(0.4f, 1.5f)] public float hudScale = 0.75f;
        public float hudScaleStep = 0.05f;
        public KeyCode scaleDownKey = KeyCode.Minus;
        public KeyCode scaleUpKey = KeyCode.Equals;
        [Tooltip("위치·크기 초기화 (우측 상단)")]
        public KeyCode resetLayoutKey = KeyCode.Home;
        private const float MinHudScale = 0.4f, MaxHudScale = 1.5f;
        private const float TitleBarH = 34f;
        private const float FooterH = 20f;
        private const string PrefX = "PhysicalAI.HUD.x", PrefY = "PhysicalAI.HUD.y", PrefScale = "PhysicalAI.HUD.scale";

        [Header("표시")]
        [Tooltip("시작 시 표시 여부 (F1로 켜고 끔). 촬영·시연 화면을 깔끔하게 두려고 기본은 숨김")]
        public bool visible = false;
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

        // 패널 좌상단 (가상 좌표). NaN = 우측 상단 기본 위치
        private Vector2 _pos = new Vector2(float.NaN, float.NaN);
        private bool _dragging;

        private void Start()
        {
            hudScale = PlayerPrefs.GetFloat(PrefScale, hudScale);
            if (PlayerPrefs.HasKey(PrefX)) _pos = new Vector2(PlayerPrefs.GetFloat(PrefX), PlayerPrefs.GetFloat(PrefY));
        }

        private void Update()
        {
            if (Input.GetKeyDown(toggleKey)) visible = !visible;
            if (Input.GetKeyDown(scaleDownKey)) SetScale(hudScale - hudScaleStep);
            if (Input.GetKeyDown(scaleUpKey)) SetScale(hudScale + hudScaleStep);
            if (Input.GetKeyDown(resetLayoutKey))
            {
                _pos = new Vector2(float.NaN, float.NaN);
                PlayerPrefs.DeleteKey(PrefX);
                PlayerPrefs.DeleteKey(PrefY);
                SetScale(0.75f);
            }
        }

        private void SetScale(float s)
        {
            hudScale = Mathf.Clamp(s, MinHudScale, MaxHudScale);
            PlayerPrefs.SetFloat(PrefScale, hudScale);
        }

        /// <summary>제목줄 드래그로 이동. 패널이 화면 밖으로 나가지 않게 매 프레임 제한.</summary>
        private void HandleDragAndClamp(float virtW, float virtH, float panelH)
        {
            if (float.IsNaN(_pos.x)) _pos = new Vector2(virtW - panelWidth - margin, margin);
            Event e = Event.current;
            Rect title = new Rect(_pos.x, _pos.y, panelWidth, TitleBarH);
            if (e.type == EventType.MouseDown && e.button == 0 && title.Contains(e.mousePosition)) { _dragging = true; e.Use(); }
            else if (e.type == EventType.MouseDrag && _dragging) { _pos += e.delta; e.Use(); }
            else if (e.type == EventType.MouseUp && _dragging)
            {
                _dragging = false;
                PlayerPrefs.SetFloat(PrefX, _pos.x);
                PlayerPrefs.SetFloat(PrefY, _pos.y);
                e.Use();
            }
            _pos.x = Mathf.Clamp(_pos.x, 0f, Mathf.Max(0f, virtW - panelWidth));
            _pos.y = Mathf.Clamp(_pos.y, 0f, Mathf.Max(0f, virtH - panelH - FooterH));   // 아래 안내 문구까지 화면 안
        }

        /// <summary>마우스가 HUD 위에 있는지 (휠 줌·로봇 클릭과 겹침 방지, 화면 좌표 y 하단 기준).</summary>
        public bool ContainsScreenPoint(Vector2 mouse)
        {
            if (!visible || float.IsNaN(_pos.x)) return false;
            float scale = Screen.height / referenceResolution.y * hudScale;
            Vector2 gui = new Vector2(mouse.x, Screen.height - mouse.y) / scale;
            return new Rect(_pos.x, _pos.y, panelWidth, PanelHeight).Contains(gui);
        }

        private const float CardH = 140f;
        private static float PanelHeight => 96f + LineH + CardH * 2f + 16f;

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

            // 해상도 독립 스케일 (높이 기준) × 사용자 배율
            float scale = Screen.height / referenceResolution.y * hudScale;
            Matrix4x4 prev = GUI.matrix;
            GUI.matrix = Matrix4x4.TRS(Vector3.zero, Quaternion.identity, new Vector3(scale, scale, 1f));
            float virtW = Screen.width / scale;
            float virtH = Screen.height / scale;

            float cardH = CardH;
            float panelH = PanelHeight;
            HandleDragAndClamp(virtW, virtH, panelH);
            float x = _pos.x;
            float y = _pos.y;

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
            // T-025: 로봇별 정지·알림 중 하나라도 있으면 적색. 원인은 조종 중인 로봇 → 다른 로봇 순
            string ctrlId = agentManager != null && !string.IsNullOrEmpty(agentManager.ControlledRobot) ? agentManager.ControlledRobot : "tb1";
            string otherId = ctrlId == "tb1" ? "tb2" : "tb1";
            bool alert = agentManager != null && (agentManager.RobotAlert("tb1") || agentManager.RobotAlert("tb2"));
            string sc = alert ? "#FF4040" : "#40FF80";
            string reason = string.Empty;
            if (agentManager != null)
            {
                string id = agentManager.RobotAlert(ctrlId) ? ctrlId : otherId;
                string r = agentManager.RobotStopReason(id);
                if (!string.IsNullOrEmpty(r)) reason = $"{id.ToUpperInvariant()} {r}";
            }
            string safetyTxt = alert && !string.IsNullOrEmpty(reason) ? $"STOP · {reason}" : status;
            GUI.Label(new Rect(cx, cy, cw, LineH), $"SAFETY  <color={sc}><b>{safetyTxt}</b></color>", _label);
            cy += LineH;
            // 정지 중 추천 탈출 방향은 CONTROL 줄의 안내 문구 자리에 표시 (패널 높이 고정)
            string hint = "<color=#999999>(click robot → FPV)</color>";
            // 화면 문구는 방향만 (수치 미표시). T-024 선회 추천이면 '제자리 선회 후 직진'
            PathData p = agentManager != null ? agentManager.LatestPath : null;
            if (p != null && p.recommended_mode == "PIVOT")
            {
                hint = $"<color=#40FF80><b>TURN {(p.pivot_deg > 0f ? "LEFT" : "RIGHT")} IN PLACE → GO</b></color>";
            }
            else if (alert && agentManager.EscapeClearance > 0f)
            {
                float h = agentManager.EscapeHeadingDeg;
                string dir = Mathf.Abs(h) < 3f ? "STRAIGHT" : (h > 0f ? "TURN LEFT" : "TURN RIGHT");
                hint = $"<color=#40FF80><b>ESCAPE {dir}</b></color>";
            }

            // T-007: 서버 확인(ACK) 기준 조종 대상
            string ctrl = agentManager != null ? agentManager.ControlledRobot : string.Empty;
            string ctrlTxt = string.IsNullOrEmpty(ctrl)
                ? "<color=#999999>N/A</color>"
                : $"<color=#{ColorUtility.ToHtmlStringRGB(ctrl == "tb2" ? tb2Color : tb1Color)}><b>{ctrl.ToUpperInvariant()}</b></color>";
            // T-016: AUTO 모드 표시 (STUCK은 적색 — 조작자 개입 대기)
            string modeTxt = string.Empty;
            if (agentManager != null && agentManager.RobotMode(ctrlId) == "AUTO")
            {
                string st = agentManager.RobotAutoState(ctrlId);
                string mc = st == "STUCK" ? "#FF4040" : "#FFC830";
                modeTxt = $"<color={mc}><b>AUTO·{st}</b></color>  ";
            }
            GUI.Label(new Rect(cx, cy, cw, LineH), $"CONTROL  {ctrlTxt}  {modeTxt}{hint}", _label);
            cy += LineH + 12f;

            DrawRobotCard(new Rect(cx, cy, cw, cardH - 8f), "tb1", "TB1  ·  AGV", tb1Color, blinkOn);
            cy += cardH;
            DrawRobotCard(new Rect(cx, cy, cw, cardH - 8f), "tb2", "TB2  ·  AGV", tb2Color, blinkOn);

            GUI.Label(new Rect(x, y + panelH + 2f, panelWidth - 6f, 18f), $"drag title · [-][=] size · [{resetLayoutKey}] reset · [{toggleKey}] hide",
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
            bool estop = agentManager != null && agentManager.RobotAlert(id);

            // 카드 배경: E-STOP 시 빨간 점멸
            Color bg = estop
                ? (blinkOn ? new Color(0.75f, 0.05f, 0.05f, 0.85f) : new Color(0.3f, 0.02f, 0.02f, 0.85f))
                : new Color(1f, 1f, 1f, 0.06f);
            Fill(r, bg);
            Fill(new Rect(r.x, r.y, 4f, r.height), estop ? Color.red : idColor);

            float px = r.x + 12f, pw = r.width - 20f, py = r.y + 6f;

            GUI.Label(new Rect(px, py, pw, LineH), $"<b><color=#{ColorUtility.ToHtmlStringRGB(idColor)}>{title}</color></b>", _label);

            // 상태 배지
            // T-025: 배지 = 정지 / AUTO / MANUAL
            bool auto = agentManager != null && agentManager.RobotMode(id) == "AUTO";
            string badgeText = d == null ? "NO DATA" : (estop ? "STOP" : (auto ? "AUTO" : "MANUAL"));
            Color badgeCol = d == null ? new Color(0.4f, 0.4f, 0.4f)
                : (estop ? Color.red : (auto ? new Color(0.85f, 0.6f, 0.05f) : new Color(0.1f, 0.6f, 0.25f)));
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
            // 상태 줄: 정지 원인(적색) 또는 AUTO 세부 상태
            string why = agentManager != null ? agentManager.RobotStopReason(id) : string.Empty;
            string stateTxt = estop && !string.IsNullOrEmpty(why)
                ? $"<color=#FF6060>{why}</color>"
                : (auto ? $"<color=#FFC830>AUTO·{agentManager.RobotAutoState(id)}</color>" : $"YAW {d.yaw:F0}°");
            GUI.Label(new Rect(px, py, pw, LineH), $"STATE {stateTxt}", _label); py += LineH;
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
