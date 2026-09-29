@AGENTS.md

# GEMINI.md — 서브 워커 규칙 (Gemini CLI / Antigravity 공통 참조)

## Gemini CLI로 독해 작업 시
- 역할: 대용량 독해 후 압축. 파일 수정 금지.
- 출력: 아래 JSON만. 설명문 금지. 1,000 토큰 이내.
- 모든 주장에 `file` + `lines` 근거 필수. 추측은 `unknowns`로.

```json
{
  "summary": "3문장 이내",
  "findings": [{"file": "경로", "lines": "120-145", "claim": "사실", "confidence": "high|medium|low"}],
  "errors": [{"file": "경로", "line": "88", "message": "원문", "probable_cause": "원인"}],
  "unknowns": ["확인 못한 것"],
  "next_actions": ["Claude가 할 일"]
}
```

## Antigravity로 구현 작업 시
- `docs/handoff/T-xxx.md`에 명시된 파일만 수정.
- 안전 로직(인터록, Escape, 워치독) 수정 금지.
- 완료 후 handoff 파일 하단 `## 결과` 섹션 작성: 변경 파일, 검증 결과, 미해결 사항.
