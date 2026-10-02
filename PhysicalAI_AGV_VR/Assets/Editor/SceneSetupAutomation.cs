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

        // God-View: 게임 맵식 수직 탑다운 (두 로봇 스폰 (0,0)·(1.8,5) 중간 상공, 화면 위쪽 = +Z)
        private static readonly Vector3 GodViewPosition = new Vector3(0.9f, 15f, 2.5f);
        private static readonly Vector3 GodViewEuler = new Vector3(90f, 0f, 0f);

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

            // 1. 바닥 생성 (Warehouse Floor: 30m x 30m)
            GameObject floor = GameObject.CreatePrimitive(PrimitiveType.Plane);
            floor.name = "Warehouse_Floor";
            floor.transform.position = Vector3.zero;
            floor.transform.localScale = new Vector3(3, 1, 3);
            Material floorMat = new Material(Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard"));
            floorMat.color = new Color(0.2f, 0.22f, 0.25f);
            floor.GetComponent<Renderer>().material = floorMat;

            // 2. 창고 환경 구성 (선반 랙, 파렛트, 작업자 모델)
            GameObject env = new GameObject("Warehouse_Environment");
            Material rackMat = new Material(Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard"));
            rackMat.color = new Color(0.15f, 0.35f, 0.65f); // 물류 랙 블루

            Material boxMat = new Material(Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard"));
            boxMat.color = new Color(0.72f, 0.52f, 0.35f); // 박스/파렛트 브라운

            Material vestMat = new Material(Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard"));
            vestMat.color = new Color(1.0f, 0.6f, 0.0f); // 형광 주황 안전조끼

            // 좌/우 랙 배치
            for (int z = -4; z <= 12; z += 4)
            {
                // 좌측 랙
                GameObject rackL = GameObject.CreatePrimitive(PrimitiveType.Cube);
                rackL.name = $"Rack_L_{z}";
                rackL.transform.SetParent(env.transform);
                rackL.transform.position = new Vector3(-3.5f, 1.5f, z);
                rackL.transform.localScale = new Vector3(1.2f, 3.0f, 2.8f);
                rackL.GetComponent<Renderer>().material = rackMat;

                // 좌측 랙 박스 적재
                GameObject boxL = GameObject.CreatePrimitive(PrimitiveType.Cube);
                boxL.name = $"Box_L_{z}";
                boxL.transform.SetParent(env.transform);
                boxL.transform.position = new Vector3(-3.5f, 3.3f, z);
                boxL.transform.localScale = new Vector3(0.9f, 0.6f, 1.8f);
                boxL.GetComponent<Renderer>().material = boxMat;

                // 우측 랙
                GameObject rackR = GameObject.CreatePrimitive(PrimitiveType.Cube);
                rackR.name = $"Rack_R_{z}";
                rackR.transform.SetParent(env.transform);
                rackR.transform.position = new Vector3(3.5f, 1.5f, z);
                rackR.transform.localScale = new Vector3(1.2f, 3.0f, 2.8f);
                rackR.GetComponent<Renderer>().material = rackMat;
            }

            // 전방 물류 작업자 (Worker Placeholder with Safety Vest)
            GameObject worker = new GameObject("Warehouse_Worker_Target");
            worker.transform.SetParent(env.transform);
            worker.transform.position = new Vector3(0.0f, 0.0f, 8.5f);

            GameObject workerBody = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            workerBody.name = "Worker_Body";
            workerBody.transform.SetParent(worker.transform);
            workerBody.transform.localPosition = new Vector3(0, 0.9f, 0);
            workerBody.transform.localScale = new Vector3(0.45f, 0.9f, 0.45f);
            workerBody.GetComponent<Renderer>().material = vestMat;

            GameObject workerHead = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            workerHead.name = "Worker_Head";
            workerHead.transform.SetParent(worker.transform);
            workerHead.transform.localPosition = new Vector3(0, 1.65f, 0);
            workerHead.transform.localScale = new Vector3(0.3f, 0.3f, 0.3f);
            workerHead.GetComponent<Renderer>().material = boxMat;

            // 3. TurtleBot3 Burger 2대 생성
            // TB1: 주행 AGV (Cyan 포인트)
            GameObject tb1 = TurtleBot3ModelBuilder.CreateTurtleBot3Burger(
                "TurtleBot3_TB1_Main", 
                Color.cyan, 
                Vector3.zero, 
                Quaternion.identity
            );

            // TB2: 보조/순찰 AGV (Orange 포인트)
            GameObject tb2 = TurtleBot3ModelBuilder.CreateTurtleBot3Burger(
                "TurtleBot3_TB2_Patrol", 
                new Color(1.0f, 0.5f, 0.0f), 
                new Vector3(1.8f, 0.0f, 4.0f), 
                Quaternion.Euler(0, 180, 0)
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

            DualDisplayController dual = manager.AddComponent<DualDisplayController>();
            dual.xrCamera = mainCam;
            dual.desktopMapCamera = mapCam;
            dual.mapAnchor = godViewAnchor.transform;
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
