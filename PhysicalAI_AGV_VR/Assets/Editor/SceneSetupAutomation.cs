using UnityEngine;
using UnityEditor;
using PhysicalAI.VR;

namespace PhysicalAI.EditorTools
{
    [InitializeOnLoad]
    public static class SceneSetupAutomation
    {
        // FPV 콕핏 앵커 (로봇 루트 기준)
        private static readonly Vector3 CockpitLocalPosition = new Vector3(0f, 0.22f, 0.05f);

        // T-007: 마우스 피킹용 BoxCollider (조감도 7.5m 상공에서 클릭하기 쉽도록 차체보다 크게)
        private const float PickColliderWidth = 0.6f;
        private const float PickColliderHeight = 0.4f;

        // T-031: 벽 없는 넓은 바닥 (실물 장애물은 LiDAR 점으로 표시)
        private const float FloorSize = 10f;
        private const float FloorThickness = 0.1f;

        // 스폰: 실측 중심 간격 1.097m 대향 (범퍼 간 S20 FE 세로 6개) (릴레이 SPAWN_POSES와 동일해야 함)
        private static readonly Vector3 TB1SpawnPosition = new Vector3(0f, 0f, -0.5484f);
        private static readonly Vector3 TB2SpawnPosition = new Vector3(0f, 0f, 0.5484f);
        private const float TB2SpawnYaw = 180f;

        // God-View: 통로 중앙 3.5m 상공 수직 탑다운 (화면 위쪽 = +Z). 직교 반높이 1.45m → 2.32m 통로 전체 + 여백
        private static readonly Vector3 GodViewPosition = new Vector3(0f, 3.5f, 0f);
        private static readonly Vector3 GodViewEuler = new Vector3(90f, 0f, 0f);
        private const float GodViewOrthoSize = 1.45f;

        static SceneSetupAutomation()
        {
            // Play 진입 시 도메인 리로드마다 재실행되면 런타임 객체가 통째로 재생성됨.
            // 플레이 중 AddComponent는 즉시 OnEnable → 참조 할당 전에 이벤트 구독 실패
            // (영상 NO SIGNAL·텔레메트리 단절, WebSocket 이중 연결). 에디트 모드에서만 실행.
            if (EditorApplication.isPlayingOrWillChangePlaymode) return;
            EditorApplication.delayCall += AutoSetupScene;
        }

        [MenuItem("PhysicalAI/Setup Dual TurtleBot3 Warehouse Scene")]
        public static void AutoSetupScene()
        {
            if (EditorApplication.isPlayingOrWillChangePlaymode)
            {
                Debug.LogWarning("[PhysicalAI] 플레이 모드에서는 씬 자동 생성을 건너뜀");
                return;
            }

            Debug.Log("[PhysicalAI] Starting Dual TurtleBot3 Burger Scene Generation...");

            // 0. 기존 객체 정리 (구버전 큐브 등)
            GameObject oldAGV = GameObject.Find("Physical_AGV");
            if (oldAGV != null) Object.DestroyImmediate(oldAGV);

            GameObject oldFloor = GameObject.Find("Warehouse_Floor");
            if (oldFloor != null) Object.DestroyImmediate(oldFloor);

            GameObject oldTB1 = GameObject.Find("TurtleBot3_TB1_Main");
            if (oldTB1 != null) Object.DestroyImmediate(oldTB1);

            GameObject oldTB2 = GameObject.Find("TurtleBot3_TB2_Patrol");
            if (oldTB2 != null) Object.DestroyImmediate(oldTB2);

            GameObject oldManager = GameObject.Find("[PhysicalAI_Manager]");
            if (oldManager != null) Object.DestroyImmediate(oldManager);

            GameObject oldGod = GameObject.Find("GodView_Anchor");
            if (oldGod != null) Object.DestroyImmediate(oldGod);

            GameObject oldRacks = GameObject.Find("Warehouse_Environment");
            if (oldRacks != null) Object.DestroyImmediate(oldRacks);

            // 1. 바닥: 벽 없는 넓은 바닥 (두께 0.1m 큐브, 윗면 = y 0)
            GameObject floor = GameObject.CreatePrimitive(PrimitiveType.Cube);
            floor.name = "Warehouse_Floor";
            floor.transform.position = new Vector3(0f, -FloorThickness * 0.5f, 0f);
            floor.transform.localScale = new Vector3(FloorSize, FloorThickness, FloorSize);
            Material floorMat = new Material(Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard"));
            floorMat.color = new Color(0.2f, 0.22f, 0.25f);
            floor.GetComponent<Renderer>().material = floorMat;


            // 3. TurtleBot3 Burger 2대 생성
            // TB1: 주행 AGV (Cyan 포인트)
            GameObject tb1 = TurtleBot3ModelBuilder.CreateTurtleBot3Burger(
                "TurtleBot3_TB1_Main",
                Color.cyan,
                TB1SpawnPosition,
                Quaternion.identity
            );

            // TB2: 보조/순찰 AGV (Orange 포인트)
            GameObject tb2 = TurtleBot3ModelBuilder.CreateTurtleBot3Burger(
                "TurtleBot3_TB2_Patrol",
                new Color(1.0f, 0.5f, 0.0f),
                TB2SpawnPosition,
                Quaternion.Euler(0f, TB2SpawnYaw, 0f)
            );

            // 4. TB1에 FPV 콕핏 앵커 및 전면 윈드실드 HUD 스크린 부착
            GameObject cockpitAnchor = CreateCockpitAnchor(tb1, "TB1_Cockpit_Anchor");

            GameObject screenQuad = GameObject.CreatePrimitive(PrimitiveType.Quad);
            screenQuad.name = "FPV_Screen_Windshield";
            screenQuad.transform.SetParent(cockpitAnchor.transform);
            screenQuad.transform.localPosition = new Vector3(0, 0.1f, 0.65f);
            screenQuad.transform.localRotation = Quaternion.identity;
            screenQuad.transform.localScale = new Vector3(1.1f, 0.65f, 1.0f);

            // 4-1. T-007: TB2 콕핏 앵커 (영상 스트림 없음 → 스크린 미부착, 3D 트윈 시점만)
            GameObject tb2CockpitAnchor = CreateCockpitAnchor(tb2, "TB2_Cockpit_Anchor");

            // 4-2. T-007: 마우스 레이캐스트 판정용 BoxCollider
            AddPickCollider(tb1);
            AddPickCollider(tb2);

            // 5. 상공 조감도 (GodView) 앵커 생성
            GameObject godViewAnchor = new GameObject("GodView_Anchor");
            godViewAnchor.transform.position = GodViewPosition;
            godViewAnchor.transform.rotation = Quaternion.Euler(GodViewEuler);

            // 6. [PhysicalAI_Manager] 생성 및 컴포넌트 결합
            GameObject manager = new GameObject("[PhysicalAI_Manager]");
            WebSocketManager ws = manager.AddComponent<WebSocketManager>();
            AGVControllerInput input = manager.AddComponent<AGVControllerInput>();
            TurtleBotMultiAgentManager multiManager = manager.AddComponent<TurtleBotMultiAgentManager>();
            FPVStreamReceiver fpv = manager.AddComponent<FPVStreamReceiver>();
            PerspectiveSwitcher switcher = manager.AddComponent<PerspectiveSwitcher>();

            // 7. 의존성 와이어링
            input.wsManager = ws;
            input.perspectiveSwitcher = switcher;
            input.agentManager = multiManager;
            input.targetAGVTransform = tb1.transform;

            multiManager.wsManager = ws;
            multiManager.tb1Transform = tb1.transform;
            multiManager.tb2Transform = tb2.transform;

            // 7-1. God-View 관제 사이드바 + 로봇별 경고 점멸 시각화
            GodViewSidebarHUD hud = manager.AddComponent<GodViewSidebarHUD>();
            hud.agentManager = multiManager;

            RobotWarningVisualizer warn1 = tb1.AddComponent<RobotWarningVisualizer>();
            warn1.agentManager = multiManager;
            warn1.robotId = "tb1";
            warn1.normalColor = Color.cyan;

            RobotWarningVisualizer warn2 = tb2.AddComponent<RobotWarningVisualizer>();
            warn2.agentManager = multiManager;
            warn2.robotId = "tb2";
            warn2.normalColor = new Color(1.0f, 0.5f, 0.0f);

            fpv.wsManager = ws;
            fpv.targetScreenRenderer = screenQuad.GetComponent<MeshRenderer>();

            switcher.wsManager = ws;
            switcher.agentManager = multiManager;
            switcher.godViewAnchor = godViewAnchor.transform;
            switcher.godViewOrthoSize = GodViewOrthoSize;
            switcher.defaultRobotId = "tb1";
            switcher.robotCockpits = new[]
            {
                new RobotCockpit { robotId = "tb1", robotRoot = tb1.transform, cockpitAnchor = cockpitAnchor.transform, fpvScreen = screenQuad },
                new RobotCockpit { robotId = "tb2", robotRoot = tb2.transform, cockpitAnchor = tb2CockpitAnchor.transform, fpvScreen = null },
            };

            // 7-2. T-007: 마우스 피킹 → 빙의
            RobotSelectionRaycaster picker = manager.AddComponent<RobotSelectionRaycaster>();
            picker.perspectiveSwitcher = switcher;
            picker.controllerInput = input;

            Camera mainCam = Camera.main;
            if (mainCam != null)
            {
                switcher.vrCameraRig = mainCam.transform;
                picker.pickCamera = mainCam;
                mainCam.transform.SetParent(null, true); // 이전 실행에서 콕핏에 붙은 상태 해제
                mainCam.transform.position = godViewAnchor.transform.position;
                mainCam.transform.rotation = godViewAnchor.transform.rotation;
            }

            // 7-3. PC 모니터 전용 탑다운 맵 카메라 (XR 활성 시에만 켜짐 → HMD와 화면 분리)
            //      GodView_Anchor 자식 → 씬 재생성 시 앵커와 함께 정리됨
            GameObject mapCamGo = new GameObject("Desktop_Map_Camera");
            mapCamGo.transform.SetParent(godViewAnchor.transform, false);
            Camera mapCam = mapCamGo.AddComponent<Camera>();
            mapCam.stereoTargetEye = StereoTargetEyeMask.None;
            mapCam.orthographic = true;
            mapCam.enabled = false;
            // 7-5. T-021: 컨트롤러 진동 경고
            XRHapticFeedback haptics = manager.AddComponent<XRHapticFeedback>();
            haptics.agentManager = multiManager;
            haptics.controllerInput = input;

            // 7-4. T-019: 경로 띠 + LiDAR 점
            PathRibbonVisualizer ribbons = manager.AddComponent<PathRibbonVisualizer>();
            ribbons.agentManager = multiManager;

            RobotVisibilityToggle visibility = manager.AddComponent<RobotVisibilityToggle>();
            visibility.agentManager = multiManager;

            DualDisplayController dual = manager.AddComponent<DualDisplayController>();
            dual.xrCamera = mainCam;
            dual.desktopMapCamera = mapCam;
            dual.mapAnchor = godViewAnchor.transform;
            dual.mapOrthoSize = GodViewOrthoSize;
            dual.picker = picker;
            dual.perspectiveSwitcher = switcher;

            // God-View(관제 맵)에서는 카메라 PIP 숨김 — 콕핏 시점에서만 표시
            fpv.perspectiveSwitcher = switcher;
            fpv.dualDisplay = dual;

            Debug.Log("[PhysicalAI] Dual TurtleBot3 Burger Scene Generation Completed Successfully!");
        }

        private static GameObject CreateCockpitAnchor(GameObject robot, string anchorName)
        {
            GameObject anchor = new GameObject(anchorName);
            anchor.transform.SetParent(robot.transform);
            anchor.transform.localPosition = CockpitLocalPosition;
            anchor.transform.localRotation = Quaternion.identity;
            return anchor;
        }

        private static void AddPickCollider(GameObject robot)
        {
            BoxCollider bc = robot.AddComponent<BoxCollider>();
            bc.isTrigger = true; // 물리 충돌 없음, 레이캐스트(QueryTriggerInteraction.Collide)만 반응
            bc.center = new Vector3(0f, PickColliderHeight * 0.5f, 0f);
            bc.size = new Vector3(PickColliderWidth, PickColliderHeight, PickColliderWidth);
        }
    }
}
