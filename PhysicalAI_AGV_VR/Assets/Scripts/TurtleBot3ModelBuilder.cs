using UnityEngine;

namespace PhysicalAI.VR
{
    /// <summary>
    /// TurtleBot3 Burger의 실물 규격(3단 원형 플레이트, 다이나믹셀 휠, OpenCR, 라즈베리파이, 카메라)을
    /// 절차적으로 정밀 생성하는 3D 모델 빌더
    /// </summary>
    public static class TurtleBot3ModelBuilder
    {
        public static GameObject CreateTurtleBot3Burger(string name, Color accentColor, Vector3 position, Quaternion rotation)
        {
            GameObject root = new GameObject(name);
            root.transform.position = position;
            root.transform.rotation = rotation;

            // 기본 머티리얼 설정
            Material darkChassisMat = new Material(Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard"));
            darkChassisMat.color = new Color(0.12f, 0.12f, 0.12f);

            Material wheelMat = new Material(Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard"));
            wheelMat.color = new Color(0.05f, 0.05f, 0.05f);

            Material accentMat = new Material(Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard"));
            accentMat.color = accentColor;

            Material pcbMat = new Material(Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard"));
            pcbMat.color = new Color(0.08f, 0.35f, 0.15f); // OpenCR 녹색 기판

            Material lensMat = new Material(Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard"));
            lensMat.color = Color.cyan;

            // 1. 하단 1단 원형 플레이트 (Base Plate)
            GameObject tier1 = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            tier1.name = "Tier1_BasePlate";
            tier1.transform.SetParent(root.transform);
            tier1.transform.localPosition = new Vector3(0, 0.033f, 0);
            tier1.transform.localScale = new Vector3(0.35f, 0.008f, 0.35f);
            tier1.GetComponent<Renderer>().material = darkChassisMat;

            // 2. 좌/우 주행 바퀴 (DYNAMIXEL XL430 + 휠)
            GameObject leftWheel = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            leftWheel.name = "Wheel_Left";
            leftWheel.transform.SetParent(root.transform);
            leftWheel.transform.localPosition = new Vector3(-0.16f, 0.033f, 0);
            leftWheel.transform.localRotation = Quaternion.Euler(0, 0, 90);
            leftWheel.transform.localScale = new Vector3(0.07f, 0.02f, 0.07f);
            leftWheel.GetComponent<Renderer>().material = wheelMat;

            GameObject rightWheel = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            rightWheel.name = "Wheel_Right";
            rightWheel.transform.SetParent(root.transform);
            rightWheel.transform.localPosition = new Vector3(0.16f, 0.033f, 0);
            rightWheel.transform.localRotation = Quaternion.Euler(0, 0, 90);
            rightWheel.transform.localScale = new Vector3(0.07f, 0.02f, 0.07f);
            rightWheel.GetComponent<Renderer>().material = wheelMat;

            // 3. 캐스터 볼 (Caster Wheel)
            GameObject caster = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            caster.name = "Caster_Wheel";
            caster.transform.SetParent(root.transform);
            caster.transform.localPosition = new Vector3(0, 0.015f, -0.14f);
            caster.transform.localScale = new Vector3(0.03f, 0.03f, 0.03f);
            caster.GetComponent<Renderer>().material = wheelMat;

            // 4. 중단 2단 원형 플레이트 & OpenCR 제어 보드
            GameObject tier2 = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            tier2.name = "Tier2_OpenCRPlate";
            tier2.transform.SetParent(root.transform);
            tier2.transform.localPosition = new Vector3(0, 0.10f, 0);
            tier2.transform.localScale = new Vector3(0.35f, 0.008f, 0.35f);
            tier2.GetComponent<Renderer>().material = darkChassisMat;

            GameObject openCR = GameObject.CreatePrimitive(PrimitiveType.Cube);
            openCR.name = "OpenCR_1_0_Board";
            openCR.transform.SetParent(tier2.transform);
            openCR.transform.localPosition = new Vector3(0, 1.2f, 0);
            openCR.transform.localScale = new Vector3(0.45f, 0.8f, 0.65f);
            openCR.GetComponent<Renderer>().material = pcbMat;

            // 5. 상단 3단 플레이트 & 라즈베리파이 4 + 카메라 마운트
            GameObject tier3 = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            tier3.name = "Tier3_PiPlate";
            tier3.transform.SetParent(root.transform);
            tier3.transform.localPosition = new Vector3(0, 0.17f, 0);
            tier3.transform.localScale = new Vector3(0.35f, 0.008f, 0.35f);
            tier3.GetComponent<Renderer>().material = darkChassisMat;

            // 식별용 엑센트 링
            GameObject ring = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            ring.name = "Accent_Status_Ring";
            ring.transform.SetParent(tier3.transform);
            ring.transform.localPosition = new Vector3(0, 0.8f, 0);
            ring.transform.localScale = new Vector3(1.02f, 0.3f, 1.02f);
            ring.GetComponent<Renderer>().material = accentMat;

            // 파이캠 모듈
            GameObject camBox = GameObject.CreatePrimitive(PrimitiveType.Cube);
            camBox.name = "PiCamera_Module";
            camBox.transform.SetParent(tier3.transform);
            camBox.transform.localPosition = new Vector3(0, 3.0f, 0.35f);
            camBox.transform.localScale = new Vector3(0.18f, 2.5f, 0.12f);
            camBox.GetComponent<Renderer>().material = darkChassisMat;

            GameObject camLens = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            camLens.name = "Camera_Lens";
            camLens.transform.SetParent(camBox.transform);
            camLens.transform.localPosition = new Vector3(0, 0, 0.6f);
            camLens.transform.localRotation = Quaternion.Euler(90, 0, 0);
            camLens.transform.localScale = new Vector3(0.5f, 0.2f, 0.5f);
            camLens.GetComponent<Renderer>().material = lensMat;

            return root;
        }
    }
}
