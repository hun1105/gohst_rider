# Meta Quest 2 연동 및 유니티(Unity) 빌드/실행 가이드

본 문서는 유니티를 처음 다루거나 메타퀘스트 2 빌드가 익숙하지 않은 개발자를 위한 완전 가이드입니다.

---

## 1. 개발 권장 환경 및 설치 소프트웨어

| 소프트웨어 | 권장 버전 | 비고 |
| :--- | :--- | :--- |
| **Unity Hub** | 최신 버전 | 공식 홈페이지 설치 |
| **Unity Editor** | **2022.3 LTS** (예: 2022.3.20f1 이상) | Quest 2 가장 안정적 |
| **Unity 모듈** | **Android Build Support** (OpenJDK, Android SDK/NDK) | 단독 실행 빌드 시 필수 |
| **Meta Quest SDK** | **Meta XR All-in-One SDK** | Unity Asset Store 무료 다운로드 |
| **PC 연결 앱** | **Meta Quest Link 앱** (PC용) | USB 케이블/Air Link 연결용 |

---

## 2. Meta Quest 2 개발자 모드 켜기 (최초 1회)

1. 스마트폰 **Meta Quest 앱** 실행 $\rightarrow$ 메타 계정 로그인.
2. 기기 메뉴 $\rightarrow$ 내 퀘스트 2 선택 $\rightarrow$ **헤드셋 설정** 클릭.
3. **개발자 모드(Developer Mode)** 항목 진입 $\rightarrow$ **토글 ON**. (개발자 등록 필요 시 이름/신용카드 등록 절차 진행).
4. PC와 Quest 2를 USB-C 케이블로 연결 $\rightarrow$ 퀘스트 내부 화면에서 **"USB 디버깅 항상 허용"** 클릭.

---

## 3. 핵심 팁: 8일 단기 완성 추천 개발 방식 (Link vs APK)

> [!TIP]
> **해커톤/경진대회 기간에는 무조건 [방식 A: Quest Link]로 개발하세요!**  
> APK 빌드는 1번 빌드에 5~10분이 걸리지만, Quest Link 방식은 Unity 에디터에서 **Play(▶) 버튼만 누르면 1초 만에 퀘스트 2 화면에서 즉시 테스트**할 수 있습니다.

### [방식 A] Quest Link / Air Link (에디터 즉시 실행 - 초고속 반복)
1. PC에서 **Meta Quest Link** 프로그램 실행.
2. Quest 2 착용 후 퀵 설정 메뉴에서 **Quest Link** 실행 $\rightarrow$ PC 화면 연결.
3. Unity 에디터 상단 **Play(▶)** 클릭 $\rightarrow$ 퀘스트 2 화면에서 바로 VR 3D 공간 및 컨트롤러 조작 가능!

### [방식 B] Standalone APK 빌드 (최종 제출 시 퀘스트 단독 탑재용)
1. Unity 메뉴: `File` $\rightarrow$ `Build Settings...`
2. Platform을 **Android**로 선택 $\rightarrow$ **Switch Platform** 클릭.
3. `Texture Compression`: **ASTC** 설정.
4. `Run Device`: 연결된 **Oculus Quest 2** 선택.
5. **Build and Run** 클릭 $\rightarrow$ APK 생성 및 퀘스트 내부 자동 설치/실행.

---

## 4. 유니티 프로젝트 초기 씬(Scene) 구성 단계

1. **XR 플러그인 활성화**:
   - `Edit` $\rightarrow$ `Project Settings` $\rightarrow$ `XR Plug-in Management`
   - PC 탭 및 Android 탭 모두 **Oculus** (또는 OpenXR) 체크.

2. **메타 XR 프리팹 배치**:
   - 기존 `Main Camera` 삭제.
   - Project 창 검색: `OVRCameraRig` 프리팹을 씬의 `(0, 0, 0)` 위치에 드래그&드롭.

3. **스크립트 및 오브젝트 세팅**:
   - 빈 GameObject 생성 $\rightarrow$ 이름을 `[PhysicalAI_Manager]` 로 지정.
   - `WebSocketManager.cs` 컴포넌트 추가 $\rightarrow$ Server Uri에 `ws://<PC_IP>:9090` 입력.
   - `AGVControllerInput.cs` 컴포넌트 추가 $\rightarrow$ WsManager 슬롯에 자기 자신 연결.
   - `PerspectiveSwitcher.cs` 추가 $\rightarrow$ `OVRCameraRig` 연결 및 GodView/Cockpit 위치 지정.

4. **FPV 영상 화면(스크린) 배치**:
   - 3D Object $\rightarrow$ `Quad` 생성 (이름: `FPV_Screen`).
   - Quad 크기 조정 (X: 1.6, Y: 0.9, Z: 1).
   - `FPVStreamReceiver.cs` 추가 $\rightarrow$ `Target Screen Renderer`에 Quad의 MeshRenderer 할당.
