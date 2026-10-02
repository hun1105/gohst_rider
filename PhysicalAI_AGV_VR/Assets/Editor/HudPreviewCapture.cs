using System.IO;
using PhysicalAI.VR;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace PhysicalAI.EditorTools
{
    /// <summary>
    /// 탑다운 God-View 인터록 시각화(차체 적색·위험 원판) 시각 검증용 캡처 도구.
    /// 배치: Unity -batchmode -projectPath ... -executeMethod PhysicalAI.EditorTools.HudPreviewCapture.Run
    /// 결과: 프로젝트 상위 .agent_cache/hud_preview_*.png (점멸 위상 2종) 저장 후 에디터 종료.
    /// 씬 파일은 저장하지 않음 (플레이 모드 종료 시 원복).
    /// </summary>
    [InitializeOnLoad]
    public static class HudPreviewCapture
    {
        private const string SessionKey = "PhysicalAI.HudPreviewCapture";
        private const string TestRobotName = "TurtleBot3_TB1_Main";
        private const string ScenePath = "Assets/cube_move.unity";
        private const int WarmupFrames = 30;
        private const int CaptureCount = 4;
        private const int FramesBetweenCaptures = 7;   // 점멸 0.3s 주기의 서로 다른 위상
        private const int Width = 1280;
        private const int Height = 720;

        private static int _frame;
        private static int _captured;

        static HudPreviewCapture()
        {
            if (SessionState.GetBool(SessionKey, false)) EditorApplication.update += Tick;
        }

        public static void Run()
        {
            // 배치 모드는 빈 Untitled 씬으로 시작 → 메인 카메라 있는 씬을 연 뒤 생성.
            // 로드 시 예약된 자동 생성(delayCall)은 취소 (강제 경고 플래그 덮어쓰기 방지)
            EditorApplication.delayCall -= SceneSetupAutomation.AutoSetupScene;
            EditorSceneManager.OpenScene(ScenePath);
            SceneSetupAutomation.AutoSetupScene();
            GameObject robot = GameObject.Find(TestRobotName);
            var viz = robot != null ? robot.GetComponent<RobotWarningVisualizer>() : null;
            if (viz == null)
            {
                Debug.LogError("[HudPreview] RobotWarningVisualizer 없음");
                EditorApplication.Exit(1);
                return;
            }
            viz.forceWarningForTest = true;   // 플레이 모드 사본에만 반영, 씬 미저장
            var ribbons = Object.FindAnyObjectByType<PathRibbonVisualizer>();
            if (ribbons != null) ribbons.forceTestPattern = true;   // T-019 경로 띠·LiDAR 점 합성 표시
            SessionState.SetBool(SessionKey, true);
            EditorApplication.isPlaying = true;
        }

        private static void Tick()
        {
            if (!EditorApplication.isPlaying) return;
            _frame++;
            if (_frame < WarmupFrames || (_frame - WarmupFrames) % FramesBetweenCaptures != 0) return;

            Capture(_captured++);
            if (_captured >= CaptureCount)
            {
                SessionState.EraseBool(SessionKey);
                EditorApplication.update -= Tick;
                EditorApplication.Exit(0);
            }
        }

        private static void Capture(int index)
        {
            Camera cam = Camera.main;
            if (cam == null) { Debug.LogError("[HudPreview] Camera.main 없음"); return; }
            var rt = new RenderTexture(Width, Height, 24);
            RenderTexture prevTarget = cam.targetTexture, prevActive = RenderTexture.active;
            cam.targetTexture = rt;
            cam.Render();
            RenderTexture.active = rt;
            var tex = new Texture2D(Width, Height, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0, 0, Width, Height), 0, 0);
            tex.Apply();
            cam.targetTexture = prevTarget;
            RenderTexture.active = prevActive;

            string dir = Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", ".agent_cache"));
            Directory.CreateDirectory(dir);
            string path = Path.Combine(dir, $"hud_preview_{index}.png");
            File.WriteAllBytes(path, tex.EncodeToPNG());
            Object.DestroyImmediate(tex);
            rt.Release();
            Debug.Log($"[HudPreview] saved {path} (ortho={cam.orthographic}, size={cam.orthographicSize})");
        }
    }
}
