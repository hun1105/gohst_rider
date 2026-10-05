# [출처·AI 활용 신고서 (별지2) 초안] VR 원격 개입형 AGV 협착 방지 디지털 트윈

**팀명**: [팀명]  **신청 구분 / 분야**: 대학부 / 32  **작성일**: 2026-10-06

> 공식 별지2 양식이 따로 있으면 아래 내용을 양식 칸에 옮겨 적는다. 라이선스는 각 프로젝트 공개 표기 기준.

## 1. 생성형 AI 활용
| 도구 | 제공사 | 활용 범위 | 사람 검토 |
|---|---|---|---|
| Claude Code (Claude) | Anthropic | 설계 검토, 릴레이·안전 로직·Unity 스크립트 코드 작성 보조, 자동 시험 작성, 문서 초안·빌드 스크립트 | 팀원이 요구사항 지정, 실물 시험·코드 리뷰 후 반영 |
| Gemini | Google | 대용량 로그·문서 요약 보조 | 요약 결과는 원문 대조 후 사용 |
| Antigravity | Google | 단순 UI·보일러플레이트 구현 보조 | 팀원 리뷰 후 병합 |

- 실행 중(런타임)에는 생성형 AI·외부 클라우드 API를 호출하지 않는다. 판단은 LiDAR 기하 알고리즘과 상태기계가 로컬에서 수행.

## 2. 오픈소스·외부 소프트웨어
| 이름 | 용도 | 라이선스 |
|---|---|---|
| ROS 1 Noetic / ROS 2 Humble | 로봇 미들웨어 | BSD-3-Clause / Apache-2.0 |
| TurtleBot3 패키지, OpenCR 펌웨어, LD08 드라이버 (ROBOTIS) | 로봇 구동·LiDAR | Apache-2.0 |
| rosbridge_suite | ROS ↔ WebSocket | BSD-3-Clause |
| ustreamer | 카메라 MJPEG 스트리밍 | GPL-3.0 (로봇에서 별도 프로세스로 실행, 소스 미포함) |
| OpenCV, NumPy | 영상 처리·기하 계산 | Apache-2.0, BSD-3-Clause |
| websockets (Python) | WebSocket 서버·클라이언트 | BSD-3-Clause |
| Ultralytics YOLOv8 (선택 기능) | 회랑 물체 검출 | AGPL-3.0 (기본 실행 `--no-ai`로 미사용) |
| Unity 6, Unity OpenXR Plugin, Input System, URP | 디지털 트윈·VR | Unity 이용약관 / Unity Companion License |
| matplotlib | 보고서 도식 생성 | PSF 기반 (matplotlib License) |
| docx, pptxgenjs (npm) | 제출 문서 빌드 | MIT |

## 3. 데이터·모델
| 이름 | 용도 | 출처·조건 |
|---|---|---|
| 실시간 센서 데이터 (LiDAR·오도메트리·카메라) | 판단 입력 | 팀 보유 로봇에서 직접 수집, 외부 데이터셋 없음 |
| YOLOv8n 사전학습 가중치 (COCO) | 선택 기능 | Ultralytics 배포 (AGPL-3.0), COCO 주석 CC BY 4.0 |

## 4. 통계·문헌 출처 (보고서·발표 인용)
| 내용 | 출처 |
|---|---|
| 산업용 로봇 재해 끼임 53%·부딪힘 34% (2011~2020, 355명) | 안전보건공단(KOSHA) 분석, 뉴스톱 「2023 중대재해 예방 팩트체크」 인용 |
| 2024년 끼임 사고사망 66명 (+22.2%) | 고용노동부 「2024년 재해조사 대상 사망사고 발생현황」 잠정결과 (2025-03-11) |
| 비계획 정지 비용 (자동차 시간당 최대 230만 달러 등) | Siemens 「The True Cost of Downtime 2024」 |
| VFH, Follow-the-Gap 알고리즘 | Borenstein & Koren (1991), Sezer & Gokasan (2012) |
| 사람 개입 간 평균 시간(MTBI) 정의 | AutoInspect, arXiv:2404.12785 (2024) |
| AGV 인수 시험 가용률 항목 | VDI 2710 Blatt 5 |
