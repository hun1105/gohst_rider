---
description: Antigravity에 넘길 handoff 문서 작성
argument-hint: <작업 설명>
---

작업: $ARGUMENTS

1. `docs/TASKS.md`에서 다음 ID(T-xxx) 확인.
2. 관련 기존 코드 구조 파악 (필요 시 gemini_worker 사용).
3. `docs/handoff/_TEMPLATE.md` 복사 → `docs/handoff/T-xxx.md` 작성.
   - 수정 허용 파일 명시.
   - 의존 클래스의 public API(필드/메서드 시그니처) 그대로 기재.
   - 수락 기준은 체크 가능한 문장으로.
4. TASKS.md에 행 추가 (담당: antigravity, 상태: todo).
5. 사용자에게 Antigravity에 붙여넣을 한 줄 지시문 출력:
   `/handoff docs/handoff/T-xxx.md 수행`
