# SUBMISSION_GUIDE — 촬영·제출 사용 가이드

> 대상: 시연영상 녹화 → 제출 패키징 담당자. 기준 문서: `docs/VIDEO_SCRIPT_3MIN.md`, `docs/PROTOCOL.md`.

## 1. 촬영 전 기동 순서
| 순서 | 작업 | 확인 |
|---|---|---|
| 1 | 릴레이 서버 실행: `python ai_relay_server/ros2_multi_turtlebot_relay.py` | 9090 포트 리슨 로그 |
| 2 | TurtleBot3 tb1·tb2 전원·ROS 2 연결 | 오도메트리 수신 |
| 3 | Unity 컴파일 확인: `powershell -ExecutionPolicy Bypass -File tools/unity_check.ps1` | `UNITY_CHECK OK` |
| 4 | Quest 2 Link 연결 → Unity Play | God-View + 우측 사이드바 카드 2장 |
| 5 | 녹화 3종 동시 시작 (노트북 / Quest 미러 / 실기체 폰) | 박수 1회로 싱크 마커 |

## 2. 필수 노출 장면 체크리스트 (4)
| # | 장면 | 반드시 화면에 보일 것 | 콘티 |
|---|---|---|---|
| 1 | 탑다운 관제 맵 동기화 | 실물 회전 → 지도 마커 동기 회전, 사이드바 값 갱신 | Scene 1 |
| 2 | AUTO 자율 배회 | `AUTO·CRUISE` → 장애물 0.6m `AVOID` 조향 → 구역 `RETURN` | Scene 2 |
| 3 | 봉착 정지·알림 | 적색 차체·위험 원판, 영상 적색 배너 + 녹색 탈출 경로, 사이드바 정지 원인 | Scene 3 |
| 4 | AUTO 봉착 → VR 수동 탈출 | `AUTO·STUCK` 정지·적색 경고 → 지도 클릭 → 콕핏 후진·회전 → Y로 AUTO 재개 | Scene 3~4 |

- 매 장면 **입력 → AI 판단 → 실행 → 피드백** 4단이 한 컷에 보여야 함.
- 실기체 PIP에서 바퀴 정지·후진이 식별 가능해야 함.

## 3. 실제 동작값 (나레이션과 일치시킬 것)
| 항목 | 코드 값 | 출처 |
|---|---|---|
| 장애물 정지 | 즉시 정지, 자동 후진·회전 없음 (전진 차단, 수동 후진·회전 허용) | T-015 |
| AUTO | 0.10 m/s, 회피 0.6m, 배회 반경 1.5m, AVOID 6s → STUCK | `AUTO_*` (T-016) |
| 탈출 경로 | 로봇 폭 회랑 반폭 0.12m, 여유 0.5m 이상, 회전 감점 0.25/rad | `escape_planner.py` |
| 워치독 | 0.5 s 무입력 → 정지 | `CMD_VEL_WATCHDOG_TIMEOUT_S` |
| 로봇 간 안전거리 | 1.0 m | `AGV_SAFETY_RADIUS_M` |

## 4. 제출 패키징
```powershell
powershell -ExecutionPolicy Bypass -File tools/package_submission.ps1 -VideoPath "D:\녹화\final.mp4" -TeamName "팀명"
```
| 옵션 | 기본값 | 의미 |
|---|---|---|
| `-VideoPath` | 없음 | 최종 영상 복사 |
| `-TeamName` | `PhysicalAI_AGV_VR` | 출력 폴더명 접두 |
| `-MaxZipMB` | 200 | ZIP 용량 경고 한도 |

출력: `dist/<팀명>_<일시>/`
- `source_code.zip` — `.gitignore` 준수 (Library/, `*.pt`, `__pycache__` 제외), `docs/handoff/` 제외.
- `docs/` — 보고서·기술설명서·발표자료·콘티·PROTOCOL·본 가이드. pandoc 설치 시 PDF 동시 생성.
- `video/` — 영상.
- `MANIFEST.txt` — SHA256, 커밋 해시, 미커밋 여부.

## 5. 제출 직전 확인
- [ ] 미커밋 경고 없음 (`git status` 깨끗).
- [ ] `.meta` 누락 경고 없음.
- [ ] ZIP 용량 한도 이내.
- [ ] YOLO 가중치(`yolov8n.pt`)는 ZIP 제외됨 → 보고서에 다운로드 방법 명시.
- [ ] 영상 길이 3:00 이내.
