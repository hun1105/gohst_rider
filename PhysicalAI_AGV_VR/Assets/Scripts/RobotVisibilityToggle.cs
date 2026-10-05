using UnityEngine;

namespace PhysicalAI.VR
{
    /// <summary>
    /// 촬영·시연용: 관제 맵에서 로봇 한 대를 화면에서만 숨긴다 (F2 = tb1, F3 = tb2).
    /// 렌더링만 끄므로 릴레이 텔레메트리·안전 판단·조종에는 영향 없음.
    /// </summary>
    public class RobotVisibilityToggle : MonoBehaviour
    {
        public TurtleBotMultiAgentManager agentManager;
        public KeyCode toggleTb1Key = KeyCode.F2;
        public KeyCode toggleTb2Key = KeyCode.F3;

        // 숨김 상태는 Play를 다시 켜도 유지 (PlayerPrefs). 첫 실행 기본값: tb1 숨김 (촬영 구성)
        private const string PrefTb1 = "PhysicalAI.Visibility.tb1Hidden", PrefTb2 = "PhysicalAI.Visibility.tb2Hidden";
        private bool _tb1Hidden, _tb2Hidden;

        private void Start()
        {
            _tb1Hidden = PlayerPrefs.GetInt(PrefTb1, 1) == 1;
            _tb2Hidden = PlayerPrefs.GetInt(PrefTb2, 0) == 1;
        }

        private void Update()
        {
            if (agentManager == null) return;
            if (Input.GetKeyDown(toggleTb1Key)) { _tb1Hidden = !_tb1Hidden; PlayerPrefs.SetInt(PrefTb1, _tb1Hidden ? 1 : 0); }
            if (Input.GetKeyDown(toggleTb2Key)) { _tb2Hidden = !_tb2Hidden; PlayerPrefs.SetInt(PrefTb2, _tb2Hidden ? 1 : 0); }
        }

        // 다른 스크립트(경고 원판 등)가 렌더러를 켜도 숨김이 유지되도록 매 프레임 forceRenderingOff 적용
        private void LateUpdate()
        {
            if (agentManager == null) return;
            Apply(agentManager.tb1Transform, _tb1Hidden);
            Apply(agentManager.tb2Transform, _tb2Hidden);
        }

        private static void Apply(Transform robot, bool hidden)
        {
            if (robot == null) return;
            foreach (Renderer r in robot.GetComponentsInChildren<Renderer>(true))
                r.forceRenderingOff = hidden;
        }
    }
}
