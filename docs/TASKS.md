# TASKS — 작업 보드

상태: `todo` → `doing` → `review` → `done` / `blocked`
담당: `claude` / `antigravity` / `gemini` / `human`

| ID | 작업 | 담당 | 상태 | 브랜치 | handoff |
|---|---|---|---|---|---|
| T-001 | 에이전트 킷 설치·동작 확인 | human | done | main | - |
| T-002 | PROTOCOL.md 현행 필드 채우기 (코드 추출 확정) | claude | done | main | - |
| T-003 | GodViewSidebarHUD.cs | antigravity | done | main | - |
| T-004 | RobotWarningVisualizer.cs | antigravity | done | main | - |
| T-005 | 3-Step Escape 상태머신 (로봇 노드) | claude | done | main | - |
| T-006 | cmd_vel 워치독 (0.5s 무입력 정지) | claude | done | main | - |
| T-007 | 마우스 피킹 및 다중 로봇 VR 빙의 전환 | claude | done | main | - |
| T-008 | 대회 제출물 4종(기술설명서, 보고서, 영상콘티, 발표자료) | antigravity | done | main | - |
| T-009 | tb3_dynamic_detector 하드코딩 경로 → TB3_MAP_DIR | claude | done | main | docs/NIGHTLY_RESULT_20261001.md |
| T-010 | 제출 ZIP 패키징 스크립트 캐시 제외 강화 | claude | done | main | docs/NIGHTLY_RESULT_20261001.md |
| T-011 | 실기×VR 현장 가이드 + check_tb3_connection.sh | claude | review | agent/claude | docs/TB3_VR_FIELD_GUIDE.md |
| T-012 | 실기체 rosbridge 브리지 (odom·scan 수신, cmd_vel 송신, LiDAR 가드) — G1~G3 | claude | review | agent/claude | docs/T-012_REAL_BRIDGE_GUIDE.md |
| T-013 | OpenXR(1.17.1) + Quest 컨트롤러 입력 + WS 재접속·프레임 조립 + 카메라 PIP (PC/HMD 화면 분리는 미착수) | claude | review | agent/claude | - |
| T-014 | TB2 카메라 8080 스트리밍 (레거시 스택+ustreamer, systemd) + 릴레이 카메라 재접속 | claude | review | agent/claude | docs/TB2_CAMERA_STREAM_GUIDE.md |
| T-015 | 장애물 정지·알림(3-Step Escape 삭제) + LiDAR 추천 탈출 경로 영상 오버레이 + 탑다운 God-View + 인터록 적색 차체·위험 원판 | claude | review | agent/claude | docs/PROTOCOL.md |
| T-016 | AUTO 자율 배회 (CRUISE/AVOID/RETURN/STUCK, 1.5m 구역, R·Y 재개) + E2E 시험 | claude | review | agent/claude | docs/PROTOCOL.md |
| T-017 | PC 탑다운 맵 ↔ Quest HMD 화면 분리 (DualDisplayController) + HUD 시각 검증 | claude | review | agent/claude | docs/NIGHTLY_RESULT_20261002.md |
| T-018 | 제출 문서 4종 개정 + REPORT_5P.docx·PRESENTATION_10SLIDES.pptx 빌드 | claude | review | agent/claude | docs/NIGHTLY_RESULT_20261002.md |
| T-019 | 경로 추천(곡률 샘플링 궤적)·예상 궤적·신뢰도 색 + Unity 경로 띠·LiDAR 점 + RESET_POSE 원점 재설정 | claude | review | agent/claude | docs/PROTOCOL.md |
| T-020 | 카메라 영상 위 LiDAR 경로 원근 투영(핀홀, Burger·Pi Cam v2 제원) + 보정 격자 + 콕핏에서 바닥 띠 숨김 | claude | review | agent/claude | - |
| T-021 | Quest 그립 데드맨 + 우측 트리거 가속 + 컨트롤러 햅틱 경고(정지·근접·YELLOW·데드맨 안내) | claude | review | agent/claude | - |
| T-022 | 운영진 5대 제출물·6요소·TC-01~05 동기화(보고서·기술설명서 docx·12장 덱·콘티) + 패키징 제출 기준 검사 + 릴레이 운행 이력 로그 | claude | review | agent/claude | docs/evidence/ |
| T-023 | 현장 수정: 레거시 Horizontal 축 고정 좌회전 제거, 로컬 3.5m/s 미리보기 이동 off(앞뒤 튕김), SmoothDamp 추종, OpenXR 햅틱 경로·그립 확인 진동·H 시험 진동, 양손 조작(좌 스틱 선회·우 스틱 직진/후진·동시 곡선, 트리거 가속 제거, F1 입력 진단), PC↔VR 전환(XR 즉시 컷·runInBackground·착용 상태 배너), XR 늦은 활성 시 God-View 직교 투영 해제(HMD 무화면 수정) | claude | review | agent/claude | - |
| T-024 | 제자리 선회 후 직진 추천(PIVOT): path 필드 4종, 영상 선회 화살표, 지도 선회 호·직진 띠, 선회 방향 손 진동, 화면 수치 제거 | claude | review | agent/claude | docs/PROTOCOL.md |
| T-025 | 실물 2대: AUTO 로봇별(tb2 포함), 콕핏 진입 = 그 로봇 MANUAL, 1.0m 만남 둘 다 정지·비켜주기, camera_robot, launch/ 폴더(TB1 기동·2대 릴레이 bat) | claude | review | agent/claude | docs/PROTOCOL.md, launch/README.md |
| T-026 | TB1 실물 세팅: SD 부트 설정(olleh Wi-Fi, ubuntu/user, rosbridge 자동 설치) → 172.30.1.58 고정 IP(netplan, cloud-init 네트워크 관리 끔, 재부팅 유지 확인)·ROS 토픽 확인, 깨진 sudoers(NUL 바이트) 복구, LD08 range_min=0.0 무효값 하한 0.12m 수정 | claude | review | agent/claude | launch/ |
| T-027 | 공식 양식 기준 최종 산출물: 보고서(표지+5쪽 목차), 기술설명서 14항목 1쪽, 발표 10장, 콘티 5막 2:50, 별지2 출처·AI 신고서, 검증된 통계(KOSHA·고용노동부·Siemens) 반영, 패키징 대학부_32_팀장명.zip·비밀정보 검사 | claude | review | agent/claude | docs/SOURCE_AI_DISCLOSURE.md |
| T-028 | 릴레이 스트레스 10회(730/730)·300초 부하 시험(soak_test.py), 제어 루프 고정 주기 15.8→20 Hz, JPEG 인코딩 스레드화, 패키징 사전 검증 | claude | review | agent/claude | docs/NIGHTLY_RESULT_20261003.md |
| T-029 | Unity 맵 실측 1:1 초협소 통로(0.712×2.317 m, 벽 4면, 랙·작업자 제거), 스폰 1.50m 대향(Unity·릴레이 동일), God-View 3.5m·직교 1.45, 가상 tb2 순찰 통로 내 축소 | claude | review | agent/claude | docs/PROTOCOL.md |
