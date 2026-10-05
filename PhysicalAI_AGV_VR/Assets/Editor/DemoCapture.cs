using UnityEditor;
using UnityEngine;

namespace PhysicalAI.EditorTools
{
    /// <summary>
    /// 시연 영상 자동 촬영용: 에디터가 열리고 씬 자동 생성이 끝난 뒤 Game 창을 최대화하고 Play에 들어간다.
    /// 실행: Unity -projectPath ... -executeMethod PhysicalAI.EditorTools.DemoCapture.Play
    /// (tools/demo_capture.py 가 호출. 평소 에디터 사용에는 영향 없음)
    /// </summary>
    public static class DemoCapture
    {
        // SceneSetupAutomation(delayCall)이 씬을 만든 뒤 Play 진입까지 기다리는 시간
        private const double PlayDelaySeconds = 5.0;
        private static double _startAt;

        public static void Play()
        {
            _startAt = EditorApplication.timeSinceStartup + PlayDelaySeconds;
            EditorApplication.update += WaitThenPlay;
        }

        private static void WaitThenPlay()
        {
            if (EditorApplication.timeSinceStartup < _startAt) return;
            EditorApplication.update -= WaitThenPlay;

            // 명령줄 실행(-executeMethod)에서는 InitializeOnLoad의 자동 생성이 돌지 않을 수 있어 직접 호출
            SceneSetupAutomation.AutoSetupScene();

            var gameViewType = System.Type.GetType("UnityEditor.GameView,UnityEditor");
            if (gameViewType != null)
            {
                EditorWindow gameView = EditorWindow.GetWindow(gameViewType);
                gameView.maximized = true;
                gameView.Focus();
            }
            Debug.Log("[DemoCapture] Enter Play mode");
            EditorApplication.isPlaying = true;
        }
    }
}
