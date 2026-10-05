# <별지 1> AI Agent 기술설명서

| 항목 | 기재 내용 |
|---|---|
| 팀명 / 부문 / 주제 | [팀명] (국립한국해양대학교) / 대학부 / 3-2. 제조 피지컬 AI — MetaQuest2 VR 기반 피지컬 AI Agent (분야코드 32) |
| 작품명 | MetaQuest 2 VR 디지털 트윈 기반 피지컬 AI AGV 원격 개입 & 협착 방지 시스템 |
| 해결 문제 | 사람·AGV 혼재 통로의 끼임·부딪힘(산업용 로봇 재해 53%·34%). 후방을 못 보는 AGV는 막히면 비상정지하고, 관리자가 현장에 갈 때까지 통로가 막힘 |
| 대상사용자 | 물류센터·스마트팩토리 AGV 관제사(PC), 원격 조작자(Meta Quest 2), AGV와 같은 통로를 쓰는 현장 작업자 |
| Agent Goal | AGV 2대 운용 중 협착·충돌 0건(목표). 위험하면 먼저 정지하고 정지 원인과 LiDAR 탈출 경로를 화면에 제시, 현장 출동 없이 VR 원격 개입으로 무사고 탈출·순찰 재개 |
| 사용 AI/LLM/모델 | LiDAR 기하 추론(전·후방 섹터 최소거리, 로봇 폭 회랑 탈출 방향 `argmax[d(h) − 0.25·\|h\|]`, 곡률 25개 원호 궤적 추천 — VFH·DWA 계열), 로봇별 AUTO 상태기계, YOLOv8n 회랑 검출(사전학습, 선택 기능·현장 미검증). LLM 미사용 |
| 사용 Tool/API/Data/장비 | TurtleBot3 Burger 2대(ROS 1 Noetic·ROS 2 Humble), LDS-02 360° LiDAR, Pi Camera v2, rosbridge(`/cmd_vel`·`/odom`·`/scan`), ustreamer(MJPEG), Python asyncio 릴레이(WebSocket 20 Hz), Unity 6 + OpenXR, Meta Quest 2 |
| Memory/State/Feedback 구현 | - State: 로봇별 AUTO/MANUAL·STUCK·정지 원인, 위치 원점, 운행 이력 로그(이벤트 + 1 Hz JSONL) - Feedback: 영상 경로 띠·선회 화살표·적색 배너, 관제 맵 적색 표시, 방향 진동 |
| 핵심 Workflow (End-to-End 동작시나리오) | ① 관제사가 `R` → 두 AGV AUTO 직진 ② 릴레이가 20 Hz로 odom·LiDAR 수신 ③ 전방 0.35m 또는 로봇 간 0.3m 판단 → 정지·STUCK, 원인 기록 ④ LiDAR 탈출·선회 경로 계산 → 영상·지도 표시 ⑤ 관제 맵 클릭 → 그 로봇 콕핏 즉시 진입(그 로봇만 MANUAL) ⑥ 그립 데드맨 + 양손 스틱으로 후진·선회 탈출(`/cmd_vel`) ⑦ `R`로 AUTO 재개, 정지 이력은 로그에 남음 |
| 핵심기능 3~5개 | 1) 자동 후진 없는 정지·알림 안전 게이트(속도 상한 0.15 m/s, 전방 0.35m·후방 0.20m, 통신 두절 정지) 2) LiDAR 탈출·선회 경로 계산과 카메라 영상 투영 3) 관제 맵 클릭 → VR 콕핏 원격 개입(그립 데드맨·진동) 4) AGV 2대 동시 AUTO와 로봇 간 만남 정지 |
| 기존자산/ 8일 신규개발분 | - 기존자산: TurtleBot3·OpenCR·ROS 드라이버, rosbridge_server, ustreamer, YOLOv8 가중치, Unity·OpenXR - 8일신규개발: 다중 로봇 릴레이(ROS 1·2), 안전 게이트, 탈출·선회 경로·영상 투영, 로봇별 AUTO, 관제 맵·VR 콕핏·진동, E2E 시험 78항목, 보정 도구 |
| 대표 테스트 5건 결과 | TC-01 전방 0.35m 전진 차단 PASS · TC-02 2대 만남 둘 다 정지(자동 시험) PASS · TC-03 관제 맵 ↔ VR 콕핏 전환 PASS · TC-04 Quest·키보드 → 실물 바퀴(0.15 m/s 제한) PASS · TC-05 AUTO 정지 → 수동 탈출(자동 시험) PASS — 자동 시험 78/78, 10회 반복 무결점 |
| 현재 완성도 Level | Level 3 (MVP) — 실물 TurtleBot3 2대 연동, End-to-End 동작 |
| 소스코드/저장소(경로) | https://github.com/hun1105/gohst_rider (공개, 브랜치 `agent/claude`) / 제출 ZIP `source_code.zip`. `ai_relay_server/` 릴레이, `PhysicalAI_AGV_VR/Assets/` Unity, `launch/` 실행 |
| 정보출처 및 기타 | 안전보건공단 로봇 재해(2011~2020), 고용노동부 2024 사망사고, Siemens Downtime 2024, ISO 3691-4, VDI 2710-5. AI·오픈소스는 출처·AI 활용 신고서 |
