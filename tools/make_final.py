"""
final/ 폴더 구성 — 운영규정 v1.0 별지 1~4·별표 6 기준 최종 산출물 모음
원본은 docs/ (단일 진실 원천). 먼저 tools/docs_build에서 npm run all 로 docx·pptx를 빌드한 뒤 실행.
실행: python tools/make_final.py
"""

import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
FINAL = os.path.join(ROOT, "final")

FILES = [
    ("REPORT_5P.docx", "01_개발완료보고서_REPORT_5P.docx"),
    ("REPORT_5P.md", "01_개발완료보고서_REPORT_5P.md"),
    ("TECH_SPEC_1P.docx", "02_기술설명서_및_소스코드정보_TECH_SPEC_1P.docx"),
    ("TECH_SPEC_1P.md", "02_기술설명서_및_소스코드정보_TECH_SPEC_1P.md"),
    ("VIDEO_SCRIPT_3MIN.md", "03_시연동영상_콘티_및_링크_VIDEO_SCRIPT_3MIN.md"),
    ("PRESENTATION_10SLIDES_VERCEL.pptx", "04_발표자료_PRESENTATION_10SLIDES.pptx"),
    ("PRESENTATION_10SLIDES.md", "04_발표자료_대본_PRESENTATION_10SLIDES.md"),
    ("PRESENTATION_PITCH.pptx", "04b_발표자료_대안_PITCH스타일.pptx"),
    ("PRESENTATION_PERPLEXITY.pptx", "04c_발표자료_대안_PERPLEXITY스타일.pptx"),
    # 04d_발표자료_대안_SWISS스타일.pptx 는 final/에서 직접 수정한 본이 원본 — 덮어쓰지 않음 (docs/PRESENTATION_SWISS.pptx 는 초기 생성본)
    ("SCRIPT_SWISS.md", "04d_발표자료_대본_SWISS스타일.md"),
    ("DESIGN_SOURCES.md", "08_디자인_참고출처_DESIGN_SOURCES.md"),
    ("CHECKLIST.md", "05_최종체크리스트_CHECKLIST.md"),
    ("SOURCE_AI_DISCLOSURE.docx", "06_출처_AI활용신고서_SOURCE_AI_DISCLOSURE.docx"),
    ("SOURCE_AI_DISCLOSURE.md", "06_출처_AI활용신고서_SOURCE_AI_DISCLOSURE.md"),
    ("PANEL_A0.pptx", "07_판넬형보고서_PANEL_A0.pptx"),
    # 01b 판넬(pptx·png)은 final/에서 직접 수정한 본이 원본 — 덮어쓰지 않음
]


def main():
    os.makedirs(FINAL, exist_ok=True)
    missing = []
    locked = []  # Word·PowerPoint에서 열려 있어 덮어쓰지 못한 파일
    for src, dst in FILES:
        p = os.path.join(DOCS, src)
        if not os.path.exists(p):
            missing.append(src)
            continue
        try:
            shutil.copy2(p, os.path.join(FINAL, dst))
        except PermissionError:
            locked.append(dst)
    # md가 참조하는 그림 (assets/...) — md를 final/에서 열어도 그림이 보이게
    assets = os.path.join(FINAL, "assets")
    shutil.copytree(os.path.join(DOCS, "assets"), assets, dirs_exist_ok=True)
    evidence = os.path.join(FINAL, "evidence")
    shutil.copytree(os.path.join(DOCS, "evidence"), evidence, dirs_exist_ok=True)
    for name in sorted(os.listdir(FINAL)):
        p = os.path.join(FINAL, name)
        size = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(p) for f in fs) if os.path.isdir(p) else os.path.getsize(p)
        print(f"{size / 1024:9.1f} KB  {name}{'/' if os.path.isdir(p) else ''}")
    if missing:
        print("MISSING:", missing)
    if locked:
        print("LOCKED (파일을 닫고 다시 실행):", locked)


if __name__ == "__main__":
    main()
