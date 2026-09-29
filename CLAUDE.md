@AGENTS.md

# CLAUDE.md — 오케스트레이터 규칙

## 역할
설계, 작업 분해, 안전 로직 구현, 통합, 리뷰.

## 토큰 절약: Gemini 선위임 규칙
아래 조건이면 **직접 Read 금지**. 먼저 워커 실행:

| 조건 | 명령 |
|---|---|
| 로그(`*.log`, ROS 로그, Unity Editor.log) | `python tools/gemini_worker.py --mode log -f <경로> -t "<질문>"` |
| PDF·논문·대회 규정 | `python tools/gemini_worker.py --mode spec -f <경로> -t "<질문>"` |
| 파일 1개 > 400줄, 또는 파일 10개 이상 탐색 | `python tools/gemini_worker.py --mode summarize -g "<glob>" -t "<질문>"` |
| 큰 diff 리뷰 | `git diff main | python tools/gemini_worker.py --mode review --stdin -t "<관점>"` |
| Unity 컴파일 확인 | `powershell -ExecutionPolicy Bypass -File tools/unity_check.ps1` |

## 검증 규칙 (워커 결과 맹신 금지)
- 워커 JSON의 `file`, `lines`는 수정 전 반드시 해당 범위만 `Read`(offset/limit)로 확인.
- `confidence: low` 항목은 근거로 쓰지 않음.
- 수정 대상 파일은 직접 읽음. 요약만 보고 편집 금지.

## 위임 규칙 (Antigravity)
- 단순 UI, 보일러플레이트, 씬 자동화 확장 → Antigravity.
- 위임 시 `docs/handoff/T-xxx.md` 작성 (템플릿: `docs/handoff/_TEMPLATE.md`).
- 수정 허용 파일 목록을 반드시 명시.

## 작업 시작 시
1. `docs/TASKS.md` 확인.
2. 필요 시 워커로 맥락 압축.
3. 계획 5줄 이내 제시 후 구현.
