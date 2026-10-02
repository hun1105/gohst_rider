# 야간 작업 결과 — 2026-10-02

> 커밋하지 않음. 아침 검토 후 커밋.
> 진행 순서: 2(AUTO) → 3(화면 분리) → 1(문서). 문서가 실제 구현·시험 결과를 서술하도록 문서를 마지막에 작성.

## 검증 결과
| 항목 | 결과 |
|---|---|
| `python ai_relay_server/test_real_bridge.py` | **43/43 PASS** (기존 25 + AUTO 18) |
| 시뮬레이션 모드 회귀 (실기 미연결) | 영상·텔레메트리 정상, `mode=MANUAL` |
| `tools/unity_check.ps1` | `UNITY_CHECK OK (warnings: 0)` |
| 영상 오버레이 대비 (실제 TB2 프레임, 최악 배경) | 배너 6.86:1, 안내 4.56:1 (WCAG AA ≥ 4.5) — 수정 전 2.66:1 |
| 탑다운 맵 적색 경고 | Unity 배치 플레이 렌더로 ON/OFF 위상 확인 |
| `REPORT_5P.docx` | Word 렌더 5쪽, 스킬 validator PASS |
| `PRESENTATION_10SLIDES.pptx` | PowerPoint 렌더 10장 전수 확인, validator PASS, 노트 10장 |

## 요청과 다르게 처리한 사실관계
| 요청 문구 | 실제 | 문서 반영 |
|---|---|---|
| ustreamer **하드웨어 MJPEG** | TB2 드라이버가 MJPEG 미제공(`driver gave us YUYV`) → YUYV 캡처 + CPU JPEG | "YUYV → CPU JPEG 인코딩" |
| **31ms** 초저지연 | 측정한 적 없음 (측정값: 15.7 fps 수신, OpenCV 연결 141 ms) | 지연 수치 미기재 |
| 18/18 PASS | 오늘 기준 43/43 | 43/43 |

## 1. 문서 (T-018)
- 개정: `docs/REPORT_5P.md`, `docs/TECH_SPEC_1P.md`, `docs/PRESENTATION_10SLIDES.md`, `docs/VIDEO_SCRIPT_3MIN.md` — 3-Step Escape 전면 삭제, 정지·알림 + LiDAR 탈출 경로 + AUTO 흐름.
- 신규: `docs/REPORT_5P.docx` (A4 5쪽, 그림 2개), `docs/PRESENTATION_10SLIDES.pptx` (16:9 10장, 발표 대본은 슬라이드 노트).
- 신규 그림: `docs/assets/` (실제 카메라 오버레이 2, 탑다운 렌더 2).
- 정리: `SUBMISSION_GUIDE.md`, `docs/T-012_REAL_BRIDGE_GUIDE.md`, `docs/TB2_CAMERA_STREAM_GUIDE.md`의 Escape 서술 갱신. `tools/package_submission.ps1`에 docx·pptx·assets 포함.
- **직접 채울 것**: 표지·보고서의 `팀명 · 발표자`. 보고서 4.3 현장 확인의 "촬영 리허설에서 확인 예정" 행은 리허설 후 결과로 교체.
- 빌드 스크립트(재생성용): 세션 스크래치 `build/build_report.js`, `build/build_deck.js` — md 수정 후 다시 빌드하려면 요청.

## 2. AUTO 자율 배회 (T-016)
- `docs/PROTOCOL.md`: `AUTO` 명령, `mode`·`auto_state` 필드, AUTO 규칙.
- `ai_relay_server/ros2_multi_turtlebot_relay.py`: AUTO 상태머신 (CRUISE 0.10 m/s / AVOID 0.6m 조향 / RETURN 1.5m / STUCK: 인터록·막다른 길·AVOID 6s). STUCK 자동 재개 없음. 주행 입력·STOP → MANUAL. 클라이언트 해제 → AUTO 해제.
- `ai_relay_server/test_real_bridge.py`: [9]~[9e] + [8] AUTO 시험 18항목.
- Unity: `AGVControllerInput.cs` (R 키 / 좌 Y = AUTO 재개, 우 B = 시점 전환), `TurtleBotMultiAgentManager.cs` (`mode`·`auto_state` 파싱), `GodViewSidebarHUD.cs` (AUTO 상태, STUCK 적색), `RobotWarningVisualizer.cs` (STUCK도 적색).
- **주의**: 퀘스트 Y 버튼이 시점 전환에서 AUTO 재개로 바뀜. 시점 전환은 B만.

## 3. PC ↔ HMD 화면 분리·HUD (T-017)
- 신규 `Scripts/DualDisplayController.cs`: XR 활성 시 PC 모니터 = 전용 탑다운 맵 카메라(Target Eye None, 직교), HMD = 기존 카메라. 마우스 피킹을 맵 카메라로 전환, 콕핏 중에도 맵 클릭 허용.
- `RobotSelectionRaycaster.cs` (`allowPickInCockpit`), `Editor/SceneSetupAutomation.cs` (`Desktop_Map_Camera` 생성).
- HUD 수정 (impeccable 감사): 오버레이 배너 대비 2.66 → 6.86:1, 하단 안내 어두운 띠, 화살표 외곽선, 경고 중 보조 문구 숨김. 맵 직교 크기 6 → 4 (로봇 마커 판독), 점멸 OFF 위상 청록 → 어두운 적색.
- 신규 `Editor/HudPreviewCapture.cs`: 배치 플레이 렌더 캡처 도구 (`.agent_cache/hud_preview_*.png`).
- **미검증**: 헤드셋 연결 상태의 화면 분리·썸스틱. 지난 Play 로그는 `XR_ERROR_FORM_FACTOR_UNAVAILABLE` (헤드셋 미연결). Quest Link 연결 후 Play로 확인 필요.

## 아침에 할 일
1. Unity 열기 → 씬 자동 재생성 확인 → Ctrl+S 저장 (새 맵 카메라·설정 반영).
2. `run_relay_tb2_as_tb1.bat` → Unity Play → `R` → 바퀴 든 상태로 AUTO 확인 → 바닥 시험.
3. Quest Link 연결 → Play → 콘솔 `[DualDisplay] XR=ON → PC 모니터: 탑다운 맵 전용` 확인.
4. 보고서·발표자료의 팀명 기입, 리허설 결과 반영.
