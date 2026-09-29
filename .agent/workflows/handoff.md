---
description: Claude가 작성한 handoff 작업 수행
---

1. 사용자가 지정한 `docs/handoff/T-xxx.md` 읽기.
2. `git switch agent/antigravity` (없으면 `git switch -c agent/antigravity`).
3. `수정 허용 파일`만 구현.
4. `powershell -ExecutionPolicy Bypass -File tools/unity_check.ps1` 실행. 에러 0까지 반복.
5. handoff 파일 `## 결과` 섹션 작성.
6. `docs/TASKS.md` 해당 행 상태 → `review`.
7. `git commit -m "[antigravity] <범위>: <내용>"`.
