---
description: Gemini 워커로 대용량 맥락 압축 후 검증
argument-hint: <대상 경로/glob> <질문>
---

대상과 질문: $ARGUMENTS

1. 대상이 로그면 `--mode log`, PDF/문서면 `--mode spec`, 코드면 `--mode summarize`.
2. 실행: `python tools/gemini_worker.py --mode <모드> -g "<대상>" -t "<질문>"`
3. JSON의 `confidence: high` findings 중 핵심 3개만 해당 라인 범위로 Read 검증.
4. 검증 결과를 5줄 이내로 보고. 틀린 항목은 명시.
