# 에이전트 킷 — Claude × Gemini × Antigravity

## 구조
```
                 ┌──────────────── 사용자 ────────────────┐
                 │                                          │
          Claude Code (지휘·안전로직·리뷰)          Antigravity (UI·보일러플레이트 구현)
            │        │         │                         ▲
            │        │         └── docs/handoff/T-xxx.md ─┘
            │        └── tools/unity_check.ps1 ── 실패 시 ──┐
            └── tools/gemini_worker.py ◀───────────────────┘
                       │ (AI Studio API 키)
                  Gemini: 로그·PDF·대형 코드 → 압축 JSON (file:line 근거)
```

## 파일
| 파일 | 읽는 에이전트 | 용도 |
|---|---|---|
| `AGENTS.md` | 전원 | 공통 규칙, 역할, 금지사항 |
| `CLAUDE.md` | Claude Code | 위임 조건, 검증 규칙 |
| `GEMINI.md` | Gemini CLI, Antigravity | 출력 스키마, 구현 제약 |
| `.agent/rules/`, `.agent/workflows/` | Antigravity | 워크스페이스 규칙, `/handoff` 워크플로 |
| `.claude/settings.json` | Claude Code | 워커 자동 허용, Library 읽기 차단 |
| `.claude/commands/` | Claude Code | `/gread`, `/delegate`, `/review-handoff` |
| `tools/gemini_worker.py` | Claude | 대용량 → 압축 JSON |
| `tools/unity_check.ps1` | Claude, Antigravity | 배치 컴파일 검증 |
| `docs/TASKS.md`, `docs/handoff/` | 전원 | 작업 보드, 인계서 |
| `docs/PROTOCOL.md` | 전원 (수정은 Claude) | WS 메시지 규격 |

## 설치 (20분)
1. (권장) 프로젝트를 `C:\dev\gn2026_agv` 로 이동. OneDrive 밖.
2. zip 내용을 프로젝트 루트에 풀기 (숨김 폴더 `.claude`, `.agent` 포함 확인).
3. `powershell -ExecutionPolicy Bypass -File setup_agents.ps1`
4. Unity 경로가 표준 위치가 아니면: `setx UNITY_EXE "D:\Unity\6000.0.xx\Editor\Unity.exe"`
5. Claude Code: 프로젝트 루트에서 `claude` 실행 → `/memory` 로 CLAUDE.md 로드 확인.
6. Antigravity: 프로젝트 루트를 워크스페이스로 열기 → 규칙 패널에서 `00-project` 확인.

## 일일 사용법
| 상황 | 할 일 |
|---|---|
| 새 기능 시작 | Claude: `/delegate GodViewSidebarHUD 구현` 또는 직접 구현 |
| Antigravity 작업 | Antigravity 채팅: `/handoff docs/handoff/T-003.md 수행` |
| 결과 병합 | Claude: `/review-handoff T-003` |
| 로그·문서 분석 | Claude: `/gread .agent_cache/unity_build.log 에러 원인` |
| 컴파일 확인 | Unity 에디터 닫고 `tools/unity_check.ps1` |

## 워커 직접 사용
```powershell
python tools/gemini_worker.py -g "ai_relay_server/*.py" -t "YOLO 인터록 발동 조건"
python tools/gemini_worker.py --mode log -f ros.log -t "tb2 오도메트리 끊김 원인"
python tools/gemini_worker.py --mode spec -f 대회요강.pdf -t "심사 항목과 배점" --pro
git diff main | python tools/gemini_worker.py --mode review --stdin -t "안전 로직 누락"
```
- 기본 모델 `gemini-flash-latest`, `--pro` 시 `gemini-pro-latest`. 환경변수 `GEMINI_MODEL`로 교체.
- 전체 결과는 `.agent_cache/*.json` 저장. Claude는 콘솔 1줄만 읽음.

## 주의
- Unity 배치 컴파일은 **에디터가 닫혀 있어야** 동작.
- Unity는 git worktree 비추천 (worktree마다 Library 재임포트 10분+). 브랜치 전환만 사용.
- AI Studio 무료 티어: 입력이 제품 개선에 쓰일 수 있음. 대회 비공개 코드면 결제 연결(유료 티어) 검토.
- 무료 티어 분당 요청 한도 → 워커가 429 시 자동 재시도(최대 4회).
- `.agent/` 폴더 규칙 위치는 Antigravity 버전에 따라 다를 수 있음. 규칙 패널에 안 보이면 설정 > Rules에 `00-project.md` 내용 붙여넣기.
