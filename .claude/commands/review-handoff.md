---
description: Antigravity 결과 리뷰 후 병합 판단
argument-hint: <T-xxx>
---

대상: $ARGUMENTS

1. `docs/handoff/$ARGUMENTS.md`의 `## 결과` 확인.
2. `git diff main...agent/antigravity --stat` 확인.
3. diff가 300줄 초과면: `git diff main...agent/antigravity | python tools/gemini_worker.py --mode review --stdin -t "handoff 수락 기준 위반, 안전 로직 침범, PROTOCOL 불일치"`
4. 수정 허용 파일 밖 변경 있으면 즉시 반려.
5. `tools/unity_check.ps1` 실행.
6. 판정: 병합 / 수정 요청(구체 항목) / 반려. TASKS.md 갱신.
