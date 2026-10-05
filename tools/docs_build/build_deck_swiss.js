// PRESENTATION_SWISS.pptx — 대안 발표자료 "Swiss Safety". 대본은 docs/SCRIPT_SWISS.md (슬라이드 노트로 들어감).
//
// 디자인 출처 (docs/DESIGN_SOURCES.md에도 기록):
//  1) International Typographic Style (Swiss Style) — Josef Müller-Brockmann, 『Grid Systems in Graphic Design』(1981):
//     12단 격자, 왼쪽 정렬·오른쪽 흘림, 큰 산세리프 제목, 장식 없는 여백 위주 구성.
//  2) 안전색 — ISO 3864-1 (안전색·안전표지 설계 원칙)의 안전 노랑 + 검정 대비 조합. 색값은 RAL 1003 Signal Yellow 근사(#F5B800).
//  3) 한 장 한 메시지 — Garr Reynolds, 『Presentation Zen』(2008): 슬라이드는 핵심 한 문장, 세부는 말과 노트로.
//
// 규칙: 흰 바탕 / 검정 글자 / 회색 보조 / 강조는 안전 노랑 "채움"에만 (노랑 글자 금지 — 흰 바탕 대비 부족).
//       카드·그림자·테두리 상자 없음. 장당 요소 3~4개. 8pt 배수 간격.
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const DOCS = process.argv[2];
const OUT = path.join(DOCS, "PRESENTATION_SWISS.pptx");
const A = f => path.join(DOCS, "assets", f);

const C = { white: "FFFFFF", ink: "111111", gray: "6B6B6B", light: "A3A3A3", rule: "DDDDDD", yellow: "F5B800" };
const F = "Pretendard";
const W = 10, H = 5.625, M = 0.6, TOTAL = 10;
const CW = W - 2 * M;

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.title = "멈추고, 알리고, 사람이 빼낸다 — Swiss Safety";

const notes = {};
fs.readFileSync(path.join(DOCS, "SCRIPT_SWISS.md"), "utf8").replace(/\r/g, "")
  .split("### [Slide ").slice(1).forEach(block => {
    const n = parseInt(block, 10);
    const m = block.match(/\*\*대본[^*]*\*\*:\s*"([\s\S]*?)"\s*$/m);
    if (m) notes[n] = m[1];
  });

function t(s, text, x, y, w, h, o = {}) {
  s.addText(text, { x, y, w, h, fontFace: F, fontSize: o.size || 14, color: o.color || C.ink, bold: o.bold || false,
    align: o.align || "left", valign: o.valign || "top", charSpacing: o.cs || 0, lineSpacingMultiple: o.lh || 1.2,
    margin: 0, isTextBox: true });
}
const rule = (s, x, y, w, color = C.rule, pt = 0.75) => s.addShape(pres.shapes.LINE, { x, y, w, h: 0, line: { color, width: pt } });
const block = (s, x, y, w, h, color = C.yellow) => s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { color }, line: { color, width: 0 } });

function slide(n, section, time) {
  const s = pres.addSlide();
  s.background = { color: C.white };
  if (section) {
    t(s, section, M, 0.42, 5, 0.22, { size: 9, color: C.gray, valign: "middle", lh: 1 });
    t(s, time, W - M - 1.5, 0.42, 1.5, 0.22, { size: 9, color: C.gray, align: "right", valign: "middle", lh: 1 });
  }
  t(s, String(n).padStart(2, "0"), W - M - 0.5, H - 0.45, 0.5, 0.2, { size: 8, color: C.light, align: "right", lh: 1 });
  if (notes[n]) s.addNotes(notes[n]);
  return s;
}
const headline = (s, text, y = 0.9, size = 30) => t(s, text, M, y, CW, 1.2, { size, bold: true, cs: -1, lh: 1.15 });

// ---------- 1. 표지 ----------
{
  const s = slide(1);
  block(s, 6.9, 0, W - 6.9, H);
  t(s, "멈추고,\n알리고,\n사람이 빼낸다.", M, 0.9, 6.0, 3.0, { size: 46, bold: true, cs: -2, lh: 1.05 });
  t(s, "국립한국해양대학교  ·  [팀명]  ·  [발표자]", M, 4.75, 6.0, 0.25, { size: 10.5, color: C.gray, lh: 1 });
  t(s, "MetaQuest VR 기반\n피지컬 AI AGV\n원격 개입 &\n협착 방지 디지털 트윈", 7.25, 0.9, 2.4, 1.6, { size: 13, bold: true, lh: 1.3 });
  t(s, "제4회 경남 AI·SW 경진대회\n대학부 · 분야 32", 7.25, 4.55, 2.4, 0.5, { size: 9.5, lh: 1.35 });
}

// ---------- 2. 문제 ----------
{
  const s = slide(2, "01  문제", "0:30");
  headline(s, "공장은 일주일에 6~10번 멈추고,\n한 번 멈추면 81분을 잃는다.");
  const cw = (CW - 2 * 0.4) / 3;
  // ① ③ Fluke Reliability 설문 2025, ② Siemens 「The True Cost of Downtime 2024」 — 원문 확인값
  // ③ 환율 1 USD = 1,348.6 KRW (ExchangeRate-API, 2026-10-04) → $1.7M ≈ 22.9억 원
  [["6~10회", "주당 정지 횟수", "2025년 제조업 응답자 48% ①"],
   ["81분", "정지 1건당 평균 시간", "생산 재개까지 걸리는 시간 ②"],
   ["23억 원", "시간당 정지 비용", "평균 $1.7M (1달러 1,349원 환산) ③"]].forEach(([big, lab, sub], i) => {
    const x = M + i * (cw + 0.4);
    rule(s, x, 2.6, cw, C.ink, 1.5);
    t(s, big, x, 2.72, cw, 0.85, { size: 44, bold: true, cs: -2, valign: "middle", lh: 1 });
    t(s, lab, x, 3.68, cw, 0.28, { size: 12.5, bold: true, lh: 1 });
    t(s, sub, x, 4.0, cw, 0.28, { size: 11, color: C.gray, lh: 1 });
  });
  t(s, "① ③ Fluke Reliability · Censuswide 설문 (미·영·독 600명), 2025.10.30 — “Nearly half (48%) report 6–10 downtime incidents weekly” / “an average cost of $1.7M per hour”\n" +
    "    https://www.fluke.com/en-us/learn/blog/condition-monitoring-and-alignment-software/unplanned-downtime-costs-manufacturers-up-to-852m-weekly\n" +
    "② Siemens (Senseye Predictive Maintenance), “The True Cost of Downtime 2024,” 11쪽 — “Now, it takes 81 minutes” (정지 후 생산 재개까지)\n" +
    "환율: 1 USD = 1,348.6 KRW (ExchangeRate-API, 2026-10-04 기준) → $1.7M ≈ 22.9억 원",
    M, 4.45, CW - 0.3, 0.8, { size: 7.5, color: C.gray, lh: 1.3 });
}

// ---------- 3. Agent ----------
{
  const s = slide(3, "02  Agent", "1:00");
  headline(s, "판단은 로봇이, 결정은 사람이.");
  t(s, "목표: AGV 2대 협착·충돌 0건, 막히면 출동 없이 원격 탈출", M, 1.62, CW, 0.3, { size: 13, color: C.gray, lh: 1 });
  const cw = (CW - 0.4) / 2;
  [["즉시 멈춘다", "전방 0.35m · AGV 간 0.3m 안이면 전진 지령 0"], ["경로를 그린다", "LiDAR로 찾은 탈출 방향을 영상 바닥에 표시"],
   ["클릭 한 번에 VR", "관제 맵에서 로봇을 누르면 그 로봇 운전석으로"], ["2대가 각자 순찰", "만나면 둘 다 멈추고 사람이 한 대를 비킨다"]].forEach(([h, d], i) => {
    const x = M + (i % 2) * (cw + 0.4), y = 2.4 + Math.floor(i / 2) * 1.2;
    rule(s, x, y, cw);
    t(s, String(i + 1).padStart(2, "0"), x, y + 0.16, 0.5, 0.3, { size: 12, color: C.light, lh: 1 });
    t(s, h, x + 0.55, y + 0.12, cw - 0.55, 0.36, { size: 17, bold: true, lh: 1 });
    t(s, d, x + 0.55, y + 0.55, cw - 0.55, 0.3, { size: 11.5, color: C.gray, lh: 1.2 });
  });
}

// ---------- 4. 구조 ① Workflow ----------
{
  const s = slide(4, "03  구조 — Workflow", "0:30");
  headline(s, "여섯 단계. 넷은 로봇이, 둘은 사람이.");
  const steps = ["순찰", "감지", "정지", "경로", "VR 개입", "재개"];
  const cw = CW / 6, y = 2.55;
  block(s, M + 4 * cw, y - 0.12, 2 * cw, 1.5);
  steps.forEach((name, i) => {
    const x = M + i * cw;
    t(s, String(i + 1), x + 0.15, y, cw - 0.3, 0.6, { size: 34, bold: true, cs: -1, lh: 1 });
    t(s, name, x + 0.15, y + 0.75, cw - 0.3, 0.35, { size: 15, bold: i >= 4, lh: 1 });
  });
  rule(s, M, y + 1.55, CW, C.ink, 1.5);
  t(s, "로봇", M + 0.15, y + 1.65, 2, 0.25, { size: 10, color: C.gray, lh: 1 });
  t(s, "사람", M + 4 * cw + 0.15, y + 1.65, 2, 0.25, { size: 10, color: C.gray, lh: 1 });
}

// ---------- 5. 구조 ② AI · Tool · Data · Memory ----------
{
  const s = slide(5, "03  구조 — AI · Tool · Data · Memory", "0:30");
  headline(s, "LLM 없이, LiDAR 기하로 판단한다.");
  const rows = [["AI", "LiDAR 72방향 여유 공간 계산 → 가장 넓고 덜 도는 방향"], ["Tool", "ROS /cmd_vel · /odom · /scan, Unity, Meta Quest 2"],
    ["Data", "실시간 LiDAR 360° · 휠 odom · 카메라 영상"], ["Memory", "로봇별 모드 · 정지 원인 · 운행 이력"]];
  rows.forEach(([k, v], i) => {
    const y = 2.2 + i * 0.68;
    rule(s, M, y, CW);
    t(s, k, M, y + 0.16, 1.6, 0.4, { size: 17, bold: true, lh: 1 });
    t(s, v, M + 1.8, y + 0.18, CW - 1.8, 0.4, { size: 13.5, color: C.gray, lh: 1 });
  });
}

// ---------- 6. 실제 시연 ① ----------
{
  const s = slide(6, "04  실제 시연", "2:30");
  headline(s, "실물 두 대로 보여드립니다.");
  block(s, M, 1.68, 0.62, 0.26);
  t(s, "LIVE", M, 1.68, 0.62, 0.26, { size: 9, bold: true, align: "center", valign: "middle", lh: 1 });
  const cols = [["입력", "관제 맵에서\n멈춘 로봇 클릭"], ["판단", "그 로봇만 MANUAL\n탈출 방향 계산"], ["Tool", "Quest 콕핏 전환\n/cmd_vel 제한"], ["결과", "그립 + 스틱으로\n사람이 빼낸다"]];
  const cw = CW / 4;
  cols.forEach(([k, v], i) => {
    const x = M + i * cw;
    rule(s, x, 2.45, cw - 0.2, C.ink, 1.5);
    t(s, k, x, 2.6, cw - 0.2, 0.3, { size: 11, color: C.gray, lh: 1 });
    t(s, v, x, 2.95, cw - 0.45, 0.9, { size: 15, bold: true, lh: 1.3 });
    if (i < 3) t(s, "→", x + cw - 0.24, 2.95, 0.22, 0.4, { size: 16, color: C.light, lh: 1 });
  });
  t(s, "시연 순서   순찰 → 정지·알림 → VR 개입 → 안전장치 → 재개", M, 4.55, CW, 0.3, { size: 12, color: C.gray, lh: 1 });
}

// ---------- 7. 실제 시연 ② ----------
{
  const s = slide(7, "04  실제 시연 — 화면", "2:30");
  const iw = 5.3, ih = iw * 480 / 640;
  s.addImage({ path: A("overlay_stop_path.jpg"), x: M, y: 0.9, w: iw, h: ih, altText: "콕핏 화면: 정지 배너와 탈출 경로" });
  const rx = M + iw + 0.45, rw = W - M - rx;
  t(s, "멈춘 이유와\n빠져나갈 길이\n보인다.", rx, 0.9, rw, 1.6, { size: 24, bold: true, cs: -1, lh: 1.15 });
  [["빨간 띠", "왜 멈췄는가"], ["초록 띠", "어디로 빠져나갈까"], ["화살표", "어느 쪽으로 돌까"]].forEach(([k, v], i) => {
    const y = 2.85 + i * 0.6;
    rule(s, rx, y, rw);
    t(s, k, rx, y + 0.13, 1.1, 0.3, { size: 12.5, bold: true, lh: 1 });
    t(s, v, rx + 1.15, y + 0.13, rw - 1.15, 0.3, { size: 12.5, color: C.gray, lh: 1 });
  });
}

// ---------- 8. 성과 ----------
{
  const s = slide(8, "05  성과", "0:30");
  headline(s, "멈춤은 같아도, 푸는 방법이 바뀐다.");
  const cw = (CW - 0.4) / 2;
  [["Before", "비상정지 후 관리자가 현장까지 걸어간다"], ["After", "관제석에서 클릭 한 번, VR로 바로 빼낸다"]].forEach(([k, v], i) => {
    const x = M + i * (cw + 0.4);
    if (i === 1) block(s, x, 1.95, cw, 1.15);
    t(s, k, x + 0.2, 2.07, cw - 0.4, 0.25, { size: 10.5, color: i ? C.ink : C.gray, lh: 1 });
    t(s, v, x + 0.2, 2.4, cw - 0.4, 0.6, { size: 15.5, bold: i === 1, color: i ? C.ink : C.gray, lh: 1.3 });
  });
  const sw = CW / 3;
  [["78/78", "E2E 자동 시험"], ["10회", "반복 무결점"], ["0건", "300초 부하 안전 위반"]].forEach(([big, lab], i) => {
    const x = M + i * sw;
    t(s, big, x, 3.45, sw - 0.2, 0.6, { size: 30, bold: true, cs: -1, valign: "middle", lh: 1 });
    t(s, lab, x, 4.08, sw - 0.2, 0.3, { size: 11, color: C.gray, lh: 1 });
  });
  t(s, "사용자 검증: 팀원이 관제사·조작자 역할로 실물 2대 확인. 외부 사용자 평가와 현장 정지 시간 측정은 다음 단계.", M, 4.85, CW, 0.25, { size: 9, color: C.gray, lh: 1 });
}

// ---------- 9. 한계 · 보완 ----------
{
  const s = slide(9, "06  발전계획 — 현장 적용 전 보완", "0:30");
  headline(s, "현장에 들이기 전에 고칠 다섯 가지.");
  [["높이 사각", "깊이 카메라 융합"], ["위치 누적 오차", "SLAM 위치 보정"], ["통신 두절", "로봇 측 정지 감시"], ["보안", "인증 · 암호화 · 망 분리"], ["효과 실측", "파일럿 라인에서 정지 시간 측정"]].forEach(([a, b], i) => {
    const y = 1.95 + i * 0.58;
    rule(s, M, y, CW);
    t(s, a, M, y + 0.14, 3.2, 0.32, { size: 15, bold: true, lh: 1 });
    t(s, "→  " + b, M + 3.4, y + 0.14, CW - 3.4, 0.32, { size: 14, color: C.gray, lh: 1 });
  });
}

// ---------- 10. 기대효과 · BM ----------
{
  const s = slide(10, "06  발전계획 — 비즈니스모델", "0:30");
  headline(s, "기존 AGV에 얹는\n안전 개입 레이어.");
  const cw = (CW - 2 * 0.4) / 3;
  [["개조 패키지", "기체 교체 없이 SW 설치"], ["관제 구독", "로봇 대수 기준 구독"], ["원격 개입 센터", "여러 현장을 한 관제석에서"]].forEach(([h, d], i) => {
    const x = M + i * (cw + 0.4);
    rule(s, x, 2.45, cw, C.ink, 1.5);
    t(s, h, x, 2.6, cw, 0.35, { size: 16, bold: true, lh: 1 });
    t(s, d, x, 3.0, cw, 0.3, { size: 12, color: C.gray, lh: 1 });
  });
  block(s, 0, 3.75, W, 1.2);
  t(s, "로봇은 멈추고 알리고, 판단은 사람이 내린다.", M, 3.75, CW, 1.2, { size: 22, bold: true, cs: -1, valign: "middle", lh: 1 });
  t(s, "구상 단계 — 가격·매출은 파일럿 이후 산정 · 시장 AGV·AMR 2030년 $22B (LogisticsIQ 2024)", M, 5.1, CW - 0.6, 0.2, { size: 8, color: C.light, lh: 1 });
}

pres.writeFile({ fileName: OUT }).then(f => console.log("written", f, "notes", Object.keys(notes).length));
