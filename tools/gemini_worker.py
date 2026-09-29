#!/usr/bin/env python3
"""
gemini_worker.py — Claude의 서브 워커.
대용량 파일/로그/PDF를 Gemini에 넘기고, 근거(file:line) 포함 압축 JSON만 콘솔에 출력.

사용 예:
  python tools/gemini_worker.py -t "WS 메시지 필드 목록" -g "ai_relay_server/*.py"
  python tools/gemini_worker.py --mode log -f build.log -t "컴파일 에러 원인"
  python tools/gemini_worker.py --mode spec -f docs/rules.pdf -t "심사 기준"
  git diff main | python tools/gemini_worker.py --mode review --stdin -t "스레드 안전성"
  python tools/gemini_worker.py --dry-run -g "PhysicalAI_AGV_VR/Assets/Scripts/*.cs" -t "구조"

환경변수:
  GEMINI_API_KEY   (필수, Google AI Studio 발급)
  GEMINI_MODEL     (선택, 기본 gemini-flash-latest)
  GEMINI_MODEL_PRO (선택, --pro 시 사용, 기본 gemini-pro-latest)
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time
from pathlib import Path
from typing import List, Literal

# Windows 콘솔 한글 깨짐 방지
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / ".agent_cache"

EXCLUDED_DIRS = {
    "Library", "Temp", "obj", "Logs", "Build", "Builds", "UserSettings",
    ".git", "__pycache__", ".venv", "venv", "ai_env", "node_modules", ".agent_cache",
}
TEXT_EXT = {
    ".py", ".cs", ".md", ".txt", ".log", ".json", ".yaml", ".yml", ".xml",
    ".launch", ".urdf", ".xacro", ".cfg", ".ini", ".toml", ".shader", ".hlsl",
    ".csv", ".sh", ".ps1", ".asmdef", ".uxml", ".uss",
}
UPLOAD_EXT = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".mp4"}
MAX_TEXT_BYTES = 8 * 1024 * 1024  # 파일 1개 상한 8MB

MODE_PROMPTS = {
    "summarize": "코드/문서를 분석해 질문에 답하라. 구조, 핵심 함수, 데이터 흐름 중심.",
    "log": "로그를 분석하라. 에러·예외·경고를 원인별로 묶고, 최초 발생 지점과 근본 원인을 추정하라. "
           "같은 에러 반복은 1건으로 합쳐라. errors 배열을 우선 채워라.",
    "spec": "문서에서 요구사항, 제약, 수치 기준, 평가 항목만 추출하라. 페이지 번호를 lines에 'p.N' 형식으로 기록.",
    "review": "diff/코드를 리뷰하라. 버그, 스레드/비동기 문제, 안전 로직 누락, 프로토콜 불일치만 지적. 스타일 지적 금지.",
}

SYSTEM_RULES = """너는 Claude(메인 엔지니어)의 서브 워커다. 파일을 수정하지 않는다. 읽고 압축만 한다.
프로젝트: ROS 2 Humble TurtleBot3 2대(tb1 Cyan 텔레옵, tb2 Orange 순찰) + Unity 6 URP MetaQuest VR 디지털 트윈.
규칙:
- 반드시 지정된 JSON 스키마로만 답한다.
- 모든 findings/errors에는 file과 lines(또는 line) 근거를 단다. 입력의 'L123|' 접두는 줄번호다.
- 입력에 없는 내용은 추측하지 말고 unknowns에 적는다.
- 전체 출력은 1000 토큰 이내. summary는 3문장 이내. 한국어로 작성.
"""


# ---------- 응답 스키마 ----------
def build_schema():
    from pydantic import BaseModel, Field

    class Finding(BaseModel):
        file: str
        lines: str = Field(description="예: 120-145 또는 p.3")
        claim: str
        confidence: Literal["high", "medium", "low"]

    class ErrorItem(BaseModel):
        file: str
        line: str
        message: str
        probable_cause: str

    class WorkerResult(BaseModel):
        summary: str
        findings: List[Finding]
        errors: List[ErrorItem]
        unknowns: List[str]
        next_actions: List[str]

    return WorkerResult


# ---------- 입력 수집 ----------
def is_excluded(p: Path) -> bool:
    return any(part in EXCLUDED_DIRS for part in p.parts)


def collect_paths(files: List[str], globs: List[str]) -> List[Path]:
    out: List[Path] = []
    for f in files:
        p = Path(f)
        if not p.is_absolute():
            p = (Path.cwd() / p)
        if p.is_file():
            out.append(p)
        else:
            print(f"[warn] 파일 없음: {f}", file=sys.stderr)
    for g in globs:
        for m in glob.glob(g, recursive=True):
            p = Path(m).resolve()
            if p.is_file() and not is_excluded(p):
                out.append(p)
    # 중복 제거, 순서 유지
    seen, uniq = set(), []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def rel(p: Path) -> str:
    try:
        return p.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def read_text_numbered(p: Path) -> str:
    raw = p.read_bytes()[:MAX_TEXT_BYTES]
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    width = len(str(len(lines)))
    body = "\n".join(f"L{str(i).rjust(width)}|{ln}" for i, ln in enumerate(lines, 1))
    return f"=== FILE: {rel(p)} ({len(lines)} lines) ===\n{body}\n"


def split_inputs(paths: List[Path]):
    texts, uploads = [], []
    for p in paths:
        ext = p.suffix.lower()
        if ext in UPLOAD_EXT:
            uploads.append(p)
        elif ext in TEXT_EXT or ext == "":
            texts.append(p)
        else:
            print(f"[skip] 미지원 확장자: {rel(p)}", file=sys.stderr)
    return texts, uploads


# ---------- Gemini 호출 ----------
def call_gemini(model: str, contents, schema, max_retries: int = 4):
    from google import genai
    from google.genai import types

    client = genai.Client()  # GEMINI_API_KEY 자동 사용
    cfg = types.GenerateContentConfig(
        system_instruction=SYSTEM_RULES,
        response_mime_type="application/json",
        response_schema=schema,
        temperature=0.2,
        max_output_tokens=4096,
    )
    delay = 5.0
    for attempt in range(1, max_retries + 1):
        try:
            return client, client.models.generate_content(model=model, contents=contents, config=cfg)
        except Exception as e:  # 429 / 503 재시도
            msg = str(e)
            retryable = any(k in msg for k in ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE", "500"))
            if not retryable or attempt == max_retries:
                raise
            print(f"[retry {attempt}/{max_retries}] {msg[:120]} → {delay:.0f}s 대기", file=sys.stderr)
            time.sleep(delay)
            delay *= 2
    raise RuntimeError("unreachable")


def upload_files(uploads: List[Path]):
    from google import genai

    client = genai.Client()
    refs = []
    for p in uploads:
        f = client.files.upload(file=str(p))
        # 처리 대기 (PDF/영상)
        for _ in range(60):
            state = getattr(getattr(f, "state", None), "name", "ACTIVE")
            if state != "PROCESSING":
                break
            time.sleep(2)
            f = client.files.get(name=f.name)
        refs.append((rel(p), f))
    return refs


def count_tokens(model: str, contents) -> int:
    from google import genai

    client = genai.Client()
    return client.models.count_tokens(model=model, contents=contents).total_tokens


# ---------- 메인 ----------
def main() -> int:
    ap = argparse.ArgumentParser(description="Gemini 서브 워커 (압축 JSON 출력)")
    ap.add_argument("-t", "--task", required=True, help="질문/지시")
    ap.add_argument("-f", "--file", action="append", default=[], help="파일 경로 (반복 가능)")
    ap.add_argument("-g", "--glob", action="append", default=[], help="glob 패턴 (반복 가능, ** 지원)")
    ap.add_argument("--stdin", action="store_true", help="표준입력을 추가 입력으로 사용 (diff 등)")
    ap.add_argument("--mode", choices=list(MODE_PROMPTS), default="summarize")
    ap.add_argument("--pro", action="store_true", help="Pro 모델 사용 (정밀 분석)")
    ap.add_argument("--max-input-tokens", type=int, default=900_000, help="입력 토큰 상한")
    ap.add_argument("--dry-run", action="store_true", help="API 호출 없이 수집 결과만 표시")
    args = ap.parse_args()

    paths = collect_paths(args.file, args.glob)
    texts, uploads = split_inputs(paths)
    stdin_text = sys.stdin.read() if args.stdin else ""

    if not texts and not uploads and not stdin_text:
        print(json.dumps({"error": "입력 없음. -f / -g / --stdin 중 하나 필요"}, ensure_ascii=False))
        return 2

    text_blob = "".join(read_text_numbered(p) for p in texts)
    if stdin_text:
        numbered = "\n".join(f"L{i}|{ln}" for i, ln in enumerate(stdin_text.splitlines(), 1))
        text_blob += f"=== STDIN ===\n{numbered}\n"

    if args.dry_run:
        print(json.dumps({
            "dry_run": True,
            "mode": args.mode,
            "text_files": [rel(p) for p in texts],
            "upload_files": [rel(p) for p in uploads],
            "stdin_chars": len(stdin_text),
            "approx_tokens": len(text_blob) // 3,
        }, ensure_ascii=False, indent=2))
        return 0

    if not os.environ.get("GEMINI_API_KEY") and not os.environ.get("GOOGLE_API_KEY"):
        print(json.dumps({"error": "GEMINI_API_KEY 미설정"}, ensure_ascii=False))
        return 2

    model = (os.environ.get("GEMINI_MODEL_PRO", "gemini-pro-latest") if args.pro
             else os.environ.get("GEMINI_MODEL", "gemini-flash-latest"))

    contents: list = []
    for name, f in upload_files(uploads):
        contents.append(f"=== ATTACHED: {name} ===")
        contents.append(f)
    if text_blob:
        contents.append(text_blob)
    contents.append(f"[모드] {MODE_PROMPTS[args.mode]}\n[질문] {args.task}")

    try:
        n = count_tokens(model, contents)
    except Exception as e:
        n = -1
        print(f"[warn] 토큰 계산 실패: {e}", file=sys.stderr)
    if n > args.max_input_tokens:
        print(json.dumps({"error": f"입력 {n} 토큰 > 상한 {args.max_input_tokens}. 범위를 좁혀라."},
                         ensure_ascii=False))
        return 3

    t0 = time.time()
    _, resp = call_gemini(model, contents, build_schema())
    elapsed = time.time() - t0

    try:
        result = json.loads(resp.text)
    except Exception:
        result = {"summary": resp.text, "findings": [], "errors": [], "unknowns": ["JSON 파싱 실패"],
                  "next_actions": []}

    usage = getattr(resp, "usage_metadata", None)
    result["_meta"] = {
        "model": model,
        "mode": args.mode,
        "input_tokens": getattr(usage, "prompt_token_count", n),
        "output_tokens": getattr(usage, "candidates_token_count", None),
        "sec": round(elapsed, 1),
        "sources": [rel(p) for p in texts + uploads] + (["<stdin>"] if stdin_text else []),
    }

    CACHE_DIR.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    (CACHE_DIR / f"{stamp}_{args.mode}.json").write_text(
        json.dumps({"task": args.task, **result}, ensure_ascii=False, indent=2), encoding="utf-8")

    # Claude가 읽는 출력: 압축 JSON 1줄
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
