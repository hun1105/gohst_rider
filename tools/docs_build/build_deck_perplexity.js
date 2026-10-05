// PRESENTATION_PERPLEXITY.pptx — 대안 발표자료 (DESIGN (perplexity).md 기준). 슬라이드 순서·대본은 PRESENTATION_10SLIDES.md와 동일.
// 구성 아이디어: 왼쪽 레일 = 발표 6단 목차(현재 구간만 딥 틸 채움), 각 장은 "검색창 질문" → 답변 카드 → 출처 칩.
// 규칙: 양피지 캔버스 #faf8f5, 카드 #fdfbfa + 1px 그림자, 헤어라인 #d1d1cd, 글자 #27251e/#72706b/#92918b,
//       굵기 400·500만 (Bold 금지), 강조색은 딥 틸 #016a71 하나 — 채움(레일 활성·배지·검색창 테두리)에만, 본문 글자에는 쓰지 않음.
// 폰트: pplxSans → Pretendard(400) / Pretendard Medium(500).
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const DOCS = process.argv[2];
const OUT = path.join(DOCS, "PRESENTATION_PERPLEXITY.pptx");
const A = f => path.join(DOCS, "assets", f);

const C = {
  canvas: "FAF8F5", paper: "FDFBFA", rail: "F3F0EA", mist: "D1D1CD", ash: "92918B", graphite: "72706B",
  ink: "27251E", teal: "016A71", white: "FFFFFF",
};
const F = "Pretendard", FM = "Pretendard Medium";
const W = 10, H = 5.625, TOTAL = 10;
const RAIL = 1.75, X0 = RAIL + 0.42, XW = W - X0 - 0.45, GAP = 0.14;
const R_CARD = 0.17, R_INPUT = 0.125;

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.title = "멈추고, 알리고, 사람이 빼낸다 — Perplexity style";

const notes = {};
fs.readFileSync(path.join(DOCS, "PRESENTATION_10SLIDES.md"), "utf8").replace(/\r/g, "")
  .split("### [Slide ").slice(1).forEach(block => {
    const n = parseInt(block, 10);
    const m = block.match(/\*\*대본[^*]*\*\*:\s*"([\s\S]*?)"\s*$/m);
    if (m) notes[n] = m[1];
  });

const SECTIONS = [["문제", "0:30"], ["Agent 설명", "1:00"], ["구조", "1:00"], ["실제 시연", "2:30"], ["성과", "0:30"], ["발전 · BM", "0:30"]];

// ---------- 부품 ----------
function t(s, text, x, y, w, h, o = {}) {
  s.addText(text, { x, y, w, h, fontFace: o.medium ? FM : F, fontSize: o.size || 11, color: o.color || C.ink,
    bold: false, align: o.align || "left", valign: o.valign || "top", lineSpacingMultiple: o.lh || 1.43,
    margin: 0, isTextBox: true });
}
function card(s, x, y, w, h, o = {}) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: o.r || R_CARD, fill: { color: o.fill || C.paper },
    line: { color: o.border || o.fill || C.paper, width: o.border ? 0.75 : 0 },
    shadow: o.flat ? undefined : { type: "outer", blur: 2, offset: 1, angle: 90, color: "000000", opacity: 0.08 } });
}
function pill(s, text, x, y, w, o = {}) {
  const h = o.h || 0.26;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: h / 2, fill: { color: o.fill || C.canvas },
    line: { color: o.fill ? o.fill : C.mist, width: o.fill ? 0 : 0.75 } });
  t(s, text, x, y, w, h, { size: o.size || 8.5, color: o.fill ? C.white : C.ink, align: "center", valign: "middle", medium: !!o.fill, lh: 1 });
}
function cite(s, n, x, y) {   // 출처 번호 (Perplexity 인용 표시)
  s.addShape(pres.shapes.OVAL, { x, y, w: 0.2, h: 0.2, fill: { color: C.rail }, line: { color: C.mist, width: 0.5 } });
  t(s, String(n), x, y, 0.2, 0.2, { size: 7, color: C.graphite, align: "center", valign: "middle", lh: 1 });
}
function image(s, file, x, y, w, pxW, pxH, alt) {
  const pad = 0.1, h = (w - 2 * pad) * pxH / pxW;
  card(s, x, y, w, h + 2 * pad);
  s.addImage({ path: A(file), x: x + pad, y: y + pad, w: w - 2 * pad, h, altText: alt });
  return h + 2 * pad;
}
// 검색창 (질문) — 틸 테두리가 "glow" 역할
function query(s, q, y = 0.45, o = {}) {
  const x = o.x || X0, w = o.w || XW, h = o.h || 0.62;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x - 0.04, y: y - 0.04, w: w + 0.08, h: h + 0.08, rectRadius: R_INPUT + 0.04,
    fill: { color: C.canvas }, line: { color: C.teal, width: 1.25, transparency: 55 } });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: R_INPUT, fill: { color: C.canvas }, line: { color: C.mist, width: 0.75 } });
  t(s, q, x + 0.22, y, w - 0.9, h, { size: o.size || 15, valign: "middle", lh: 1.2 });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + w - 0.52, y: y + (h - 0.38) / 2, w: 0.38, h: 0.38, rectRadius: R_INPUT, fill: { color: C.ink }, line: { color: C.ink, width: 0 } });
  t(s, "→", x + w - 0.52, y + (h - 0.38) / 2, 0.38, 0.38, { size: 12, color: C.canvas, align: "center", valign: "middle", lh: 1 });
  return y + h + 0.22;
}
function sources(s, list, y) {   // 하단 출처 칩 줄
  t(s, "출처", X0, y, 0.4, 0.26, { size: 8.5, color: C.ash, valign: "middle", lh: 1 });
  let x = X0 + 0.45;
  list.forEach((src, i) => {
    const w = 0.42 + src.length * 0.075;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h: 0.26, rectRadius: 0.13, fill: { color: C.paper }, line: { color: C.mist, width: 0.75 } });
    t(s, `${i + 1}  ${src}`, x, y, w, 0.26, { size: 8, color: C.graphite, align: "center", valign: "middle", lh: 1 });
    x += w + 0.1;
  });
}
function slide(n, active) {
  const s = pres.addSlide();
  s.background = { color: C.canvas };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: RAIL, h: H, fill: { color: C.rail }, line: { color: C.rail, width: 0 } });
  s.addShape(pres.shapes.LINE, { x: RAIL, y: 0, w: 0, h: H, line: { color: C.mist, width: 0.5 } });
  // 브랜드 마크: 삼각 표식 + 팀
  s.addShape(pres.shapes.ISOSCELES_TRIANGLE, { x: 0.3, y: 0.42, w: 0.2, h: 0.18, fill: { color: C.ink }, line: { color: C.ink, width: 0 } });
  t(s, "[팀명]", 0.6, 0.38, 1.1, 0.26, { size: 10.5, medium: true, valign: "middle", lh: 1 });
  t(s, "발표 순서", 0.3, 0.95, 1.3, 0.2, { size: 8, color: C.graphite, lh: 1 });
  SECTIONS.forEach(([name, time], i) => {
    const y = 1.22 + i * 0.42, on = i === active;
    if (on) s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.18, y: y - 0.04, w: RAIL - 0.36, h: 0.34, rectRadius: R_INPUT, fill: { color: C.teal }, line: { color: C.teal, width: 0 } });
    t(s, `${i + 1}  ${name}`, 0.32, y - 0.04, 1.0, 0.34, { size: 9.5, color: on ? C.white : C.graphite, valign: "middle", medium: on, lh: 1 });
    t(s, time, RAIL - 0.75, y - 0.04, 0.45, 0.34, { size: 8, color: on ? C.white : C.ash, align: "right", valign: "middle", lh: 1 });
  });
  t(s, "경남 AI·SW 경진대회 2026\n대학부 · 분야 32", 0.3, H - 0.95, 1.4, 0.4, { size: 7.5, color: C.ash, lh: 1.3 });
  t(s, String(n).padStart(2, "0") + " / " + TOTAL, 0.3, H - 0.42, 1.2, 0.2, { size: 8, color: C.graphite, lh: 1 });
  if (notes[n]) s.addNotes(notes[n]);
  return s;
}
const cols = (n, total = XW) => (total - (n - 1) * GAP) / n;
const lead = (s, text, y, h = 0.5) => { t(s, text, X0, y, XW, h, { size: 12.5, lh: 1.4 }); return y + h + 0.12; };

// ---------- 1. 표지 ----------
{
  const s = slide(1, -1);
  t(s, "제4회 경남 AI·SW 경진대회 · 대학부 · 분야 32 제조 피지컬 AI", X0, 0.62, XW, 0.25, { size: 9, color: C.graphite, align: "center", lh: 1 });
  t(s, "멈추고, 알리고, 사람이 빼낸다", X0, 1.0, XW, 0.75, { size: 32, medium: true, align: "center", valign: "middle", lh: 1.1 });
  t(s, "MetaQuest VR 기반 피지컬 AI AGV 원격 개입 & 협착 방지 디지털 트윈", X0, 1.78, XW, 0.3, { size: 11, color: C.graphite, align: "center", lh: 1 });
  const qx = X0 + 0.45, qw = XW - 0.9;
  query(s, "멈춘 AGV, 현장에 가지 않고 빼낼 수 있을까?", 2.35, { x: qx, w: qw, h: 0.7, size: 15.5 });
  const chips = ["2D LiDAR", "Meta Quest 2", "TurtleBot3 × 2", "ROS 1 · ROS 2"];
  let cx = qx + 0.05;
  chips.forEach((c, i) => { const w = 0.35 + c.length * 0.085; pill(s, c, cx, 3.27, w, i === 1 ? { fill: C.teal } : {}); cx += w + 0.1; });
  const cw = cols(2, qw);
  [["로봇이 판단", "위험하면 즉시 정지, 원인과 탈출 경로 계산"], ["사람이 결정", "관제 맵 클릭 → VR 콕핏에서 직접 탈출"]].forEach(([h, d], i) => {
    const x = qx + i * (cw + GAP);
    card(s, x, 3.8, cw, 0.85);
    t(s, h, x + 0.2, 3.92, cw - 0.4, 0.26, { size: 11.5, medium: true, lh: 1.2 });
    t(s, d, x + 0.2, 4.2, cw - 0.4, 0.35, { size: 9.5, color: C.graphite, lh: 1.3 });
  });
  t(s, "국립한국해양대학교 · [팀명] · [발표자]", X0, 4.95, XW, 0.22, { size: 9, color: C.graphite, align: "center", lh: 1 });
}

// ---------- 2. 문제 ----------
{
  const s = slide(2, 0);
  let y = query(s, "AGV와 같은 통로를 쓰는 사람들은 어떤 문제를 겪고 있나?");
  y = lead(s, "현장 작업자는 부딪히고 끼이며, 관제사는 AGV가 멈출 때마다 현장으로 걸어가고, 그동안 라인이 선다.", y, 0.45);
  const cw = cols(3);
  [["53%", "산업용 로봇 재해 중 끼임 (부딪힘 34%)", 1], ["66명", "2024년 끼임 사고사망, 전년 대비 +22.2%", 2], ["$2.3M", "자동차 라인 시간당 정지 비용 최대", 3]].forEach(([big, lab, n], i) => {
    const x = X0 + i * (cw + GAP);
    card(s, x, y, cw, 1.55);
    t(s, big, x + 0.2, y + 0.16, cw - 0.4, 0.6, { size: 30, medium: true, valign: "middle", lh: 1 });
    t(s, lab, x + 0.2, y + 0.85, cw - 0.55, 0.5, { size: 9.5, color: C.graphite, lh: 1.35 });
    cite(s, n, x + cw - 0.36, y + 0.16);
  });
  y += 1.75;
  card(s, X0, y, XW, 0.82, { fill: C.canvas, border: C.mist, flat: true });
  t(s, "보급형 AGV의 한계", X0 + 0.2, y + 0.1, 3, 0.22, { size: 8.5, color: C.graphite, lh: 1 });
  t(s, "① 2D LiDAR 한 평면만 본다    ② 뒤를 못 봐 스스로 못 물러난다    ③ 멈추면 사람이 걸어가야 풀린다", X0 + 0.2, y + 0.36, XW - 0.4, 0.34, { size: 11, medium: true, valign: "middle", lh: 1.2 });
  sources(s, ["KOSHA 2011–2020", "고용노동부 2025", "Siemens 2024"], 4.95);
}

// ---------- 3. Agent ----------
{
  const s = slide(3, 1);
  let y = query(s, "이 Agent의 목표와 역할, 핵심기능은?");
  const lw = 2.35;
  card(s, X0, y, lw, 1.12, { fill: C.ink, flat: true });
  t(s, "목표", X0 + 0.2, y + 0.14, lw - 0.4, 0.2, { size: 8.5, color: C.ash, lh: 1 });
  t(s, "AGV 2대 협착·충돌 0건,\n막히면 출동 없이 원격 탈출", X0 + 0.2, y + 0.4, lw - 0.4, 0.6, { size: 11.5, color: C.canvas, medium: true, lh: 1.35 });
  const ry = y + 1.26;
  card(s, X0, ry, lw, 1.95);
  [["Agent", "감시 · 정지 · 원인 · 경로 추천"], ["사람", "로봇 선택 · VR 조종 · 재개 승인"]].forEach(([k, v], i) => {
    const yy = ry + 0.16 + i * 0.68;
    pill(s, k, X0 + 0.2, yy, 0.72, i === 1 ? { fill: C.teal } : {});
    t(s, v, X0 + 0.2, yy + 0.33, lw - 0.4, 0.3, { size: 10.5, lh: 1.2 });
  });
  t(s, "자동 후진 · 자동 재개 없음", X0 + 0.2, ry + 1.55, lw - 0.4, 0.25, { size: 9, color: C.graphite, lh: 1 });
  const rx = X0 + lw + GAP, rw = XW - lw - GAP, cw = cols(2, rw), ch = 1.55;
  [["즉시 멈춘다", "전방 0.35m · AGV 간 0.3m → 전진 지령 0. 후진은 후방 0.20m 가드."],
   ["경로를 그린다", "LiDAR 72방향 탈출 경로를 영상 바닥·관제 맵에 표시, 돌 쪽 손 진동."],
   ["클릭 한 번에 VR", "관제 맵 클릭 → 그 로봇 콕핏, 그 로봇만 MANUAL, 그립 데드맨."],
   ["2대 AUTO", "각자 직진 순찰, 0.3m 안에서 만나면 둘 다 정지, 사람이 한 대를 비킨다."]].forEach(([h, d], i) => {
    const x = rx + (i % 2) * (cw + GAP), yy = y + Math.floor(i / 2) * (ch + GAP);
    card(s, x, yy, cw, ch);
    t(s, String(i + 1).padStart(2, "0"), x + 0.2, yy + 0.16, 0.5, 0.22, { size: 9, color: C.ash, lh: 1 });
    t(s, h, x + 0.2, yy + 0.42, cw - 0.4, 0.32, { size: 13, medium: true, lh: 1.1 });
    t(s, d, x + 0.2, yy + 0.82, cw - 0.4, 0.65, { size: 9.5, color: C.graphite, lh: 1.4 });
  });
}

// ---------- 4. Workflow ----------
{
  const s = slide(4, 2);
  let y = query(s, "어떤 순서로 판단하고, 어디서 사람에게 넘기나?");
  const steps = [["AUTO 순찰", "R 키 · 2대 직진 0.10 m/s"], ["위험 감지", "LiDAR 360° · odom 20 Hz"], ["정지 게이트", "전진 지령 0 · 원인 기록"],
    ["탈출 경로", "72방향 회랑 · 영상 투영"], ["VR 개입", "관제 맵 클릭 → 콕핏"], ["AUTO 재개", "사람이 R · 자동 재개 없음"]];
  const cw = cols(3), ch = 0.95;
  steps.forEach(([h, d], i) => {
    const x = X0 + (i % 3) * (cw + GAP), yy = y + Math.floor(i / 3) * (ch + GAP), human = i >= 4;
    card(s, x, yy, cw, ch);
    s.addShape(pres.shapes.OVAL, { x: x + 0.2, y: yy + 0.18, w: 0.3, h: 0.3, fill: { color: C.ink }, line: { color: C.ink, width: 0 } });
    t(s, String(i + 1), x + 0.2, yy + 0.18, 0.3, 0.3, { size: 9.5, color: C.canvas, align: "center", valign: "middle", medium: true, lh: 1 });
    t(s, h, x + 0.62, yy + 0.16, cw - 1.5, 0.34, { size: 12.5, medium: true, valign: "middle", lh: 1 });
    if (human) pill(s, "사람", x + cw - 0.78, yy + 0.2, 0.58, { fill: C.teal, h: 0.24, size: 8 });
    t(s, d, x + 0.2, yy + 0.58, cw - 0.4, 0.3, { size: 9.5, color: C.graphite, lh: 1.2 });
  });
  y += 2 * ch + GAP + 0.22;
  const bw = cols(3);
  [["조건", "전방 < 0.35m 또는 AGV 간 < 0.3m → 전진 차단"], ["방법", "5° × 72방향 회랑 여유 d(h), J = d(h) − 0.25·|h| 최대"], ["결과", "영상 바닥에 경로 띠·선회 화살표, 조작은 사람"]].forEach(([k, v], i) => {
    const x = X0 + i * (bw + GAP);
    card(s, x, y, bw, 1.1, { fill: C.canvas, border: C.mist, flat: true });
    t(s, k, x + 0.2, y + 0.14, bw - 0.4, 0.2, { size: 8.5, color: C.graphite, lh: 1 });
    t(s, v, x + 0.2, y + 0.4, bw - 0.4, 0.6, { size: 10.5, lh: 1.4 });
  });
  sources(s, ["VFH · Borenstein 1991", "Follow-the-Gap · Sezer 2012"], 4.95);
}

// ---------- 5. AI · Tool · Data · Memory ----------
{
  const s = slide(5, 2);
  let y = query(s, "AI, Tool, Data, Memory는 각각 무엇인가?");
  const iw = 4.3;
  const ih = image(s, "fig_architecture_body.png", X0, y, iw, 1512, 718, "시스템 아키텍처");
  t(s, "안전 게이트를 통과한 속도만 /cmd_vel로 나간다 · 20 Hz", X0, y + ih + 0.1, iw, 0.22, { size: 8.5, color: C.graphite, lh: 1 });
  const rx = X0 + iw + 0.3, rw = XW - iw - 0.3;
  [["AI", "LiDAR 기하 추론 · 곡률 궤적. LLM 미사용, 같은 입력 → 같은 판단"], ["Tool", "ROS /cmd_vel · /odom · /scan (rosbridge), 카메라, Unity, Quest 2"],
   ["Data", "실시간 LiDAR 360° · 휠 odom · 640×480 영상. 학습 데이터 없음"], ["Memory", "로봇별 AUTO/MANUAL · 정지 원인 · 운행 이력 JSONL"]].forEach(([k, v], i) => {
    const yy = y + i * 0.95;
    t(s, k, rx, yy, rw, 0.28, { size: 13, medium: true, lh: 1 });
    t(s, v, rx, yy + 0.32, rw, 0.48, { size: 9.5, color: C.graphite, lh: 1.35 });
    if (i < 3) s.addShape(pres.shapes.LINE, { x: rx, y: yy + 0.86, w: rw, h: 0, line: { color: C.mist, width: 0.5 } });
  });
}

// ---------- 6. 실제 시연 ① ----------
{
  const s = slide(6, 3);
  let y = query(s, "실제로 입력 → 판단 → Tool → 결과가 어떻게 이어지나?");
  pill(s, "LIVE", W - 0.45 - 0.62, y - 0.05, 0.62, { fill: C.teal, h: 0.24, size: 8 });
  const head = ["", "입력", "판단 (Agent)", "Tool 호출", "결과"];
  const rows = [
    ["자율 순찰", "관제 PC  R", "로봇 간 0.3m · 전방 0.35m 감시", "/cmd_vel 0.10 m/s", "2대 주행 → 접근 시 정지"],
    ["정지·알림", "작업자 진입", "전방 0.35m 안 → 전진 차단", "/cmd_vel 0 · STOP", "지도 적색 · 원인 · 경로 띠"],
    ["VR 개입", "관제 맵 클릭", "그 로봇만 MANUAL · 탈출 방향", "Quest 콕핏 · 손 진동", "그립 + 스틱으로 탈출"],
    ["안전장치", "그립 놓기 · 과속", "데드맨 · 0.15 m/s · 워치독 0.5s", "/cmd_vel 0 또는 제한", "즉시 정지 · 속도 제한"],
    ["재개", "관제 PC  R", "사람 승인 시에만 AUTO", "/cmd_vel 0.10 m/s", "순찰 복귀"],
  ];
  const cw = [1.0, 1.1, 1.95, 1.43, 1.6];
  card(s, X0, y + 0.22, XW, 0.36 + rows.length * 0.5 + 0.1);
  let x = X0 + 0.15;
  head.forEach((h, i) => { t(s, h, x, y + 0.3, cw[i], 0.24, { size: 8.5, color: C.graphite, valign: "middle", lh: 1 }); x += cw[i]; });
  rows.forEach((r, ri) => {
    const yy = y + 0.6 + ri * 0.5;
    s.addShape(pres.shapes.LINE, { x: X0 + 0.15, y: yy, w: XW - 0.3, h: 0, line: { color: C.mist, width: 0.5 } });
    let cx = X0 + 0.15;
    r.forEach((c, ci) => {
      t(s, c, cx, yy + 0.02, cw[ci] - 0.08, 0.46, { size: ci === 0 ? 10.5 : 9.3, color: ci === 0 || ci === 4 ? C.ink : C.graphite, medium: ci === 0 || ci === 4, valign: "middle", lh: 1.2 });
      cx += cw[ci];
    });
  });
  t(s, "화면 4분할: 관제 맵 · Quest 콕핏 · 릴레이 터미널 · 실물 캠 — 라이브 불가 시 시연 영상으로 대체", X0, 4.98, XW, 0.22, { size: 8.5, color: C.graphite, lh: 1 });
}

// ---------- 7. 실제 시연 ② ----------
{
  const s = slide(7, 3);
  let y = query(s, "멈췄을 때 화면에는 무엇이 보이나?");
  const w1 = 2.85;
  const h1 = image(s, "overlay_stop_path.jpg", X0, y, w1, 640, 480, "콕핏 화면");
  image(s, "topdown_warning_on.png", X0 + w1 + GAP, y, h1, 720, 720, "관제 맵");
  const rx = X0 + w1 + GAP + h1 + 0.25, rw = W - 0.45 - rx;
  [["콕핏", "영상 바닥 경로 띠 · 선회 화살표 · 정지 배너"], ["관제 맵", "적색 차체 · 위험 원판 · 사이드바 정지 원인"], ["터미널", "[AUTO] STUCK · [INTERLOCK] = 판단 → Tool 기록"]].forEach(([k, v], i) => {
    const yy = y + i * 0.95;
    t(s, k, rx, yy, rw, 0.26, { size: 12, medium: true, lh: 1 });
    t(s, v, rx, yy + 0.3, rw, 0.6, { size: 9.5, color: C.graphite, lh: 1.35 });
  });
  t(s, "콕핏: 정지 배너 · 탈출 경로", X0, y + h1 + 0.1, w1, 0.2, { size: 8.5, color: C.graphite, align: "center", lh: 1 });
  t(s, "관제 맵: 적색 경고", X0 + w1 + GAP, y + h1 + 0.1, h1, 0.2, { size: 8.5, color: C.graphite, align: "center", lh: 1 });
  t(s, "실제 출력 예시 · 발표 당일 라이브 화면이 우선", X0, 4.98, XW, 0.22, { size: 8.5, color: C.ash, lh: 1 });
}

// ---------- 8. 성과 ----------
{
  const s = slide(8, 4);
  let y = query(s, "무엇이 달라졌고, 어떻게 검증했나?");
  const bw = 2.2;
  card(s, X0, y, bw, 1.75, { fill: C.canvas, border: C.mist, flat: true });
  t(s, "Before", X0 + 0.2, y + 0.14, bw - 0.4, 0.22, { size: 8.5, color: C.graphite, lh: 1 });
  t(s, "비상정지 → 통로 마비\n관리자 현장 출동\n정지 이유 기록 없음", X0 + 0.2, y + 0.45, bw - 0.4, 1.2, { size: 10.5, color: C.graphite, lh: 1.6 });
  card(s, X0 + bw + GAP, y, bw, 1.75);
  t(s, "After", X0 + bw + GAP + 0.2, y + 0.14, bw - 0.4, 0.22, { size: 8.5, color: C.graphite, lh: 1 });
  t(s, "전진만 차단\n관제석에서 VR로 탈출\n원인·경로가 로그에 남음", X0 + bw + GAP + 0.2, y + 0.45, bw - 0.4, 1.2, { size: 10.5, medium: true, lh: 1.6 });
  const rx = X0 + 2 * (bw + GAP), rw = XW - 2 * (bw + GAP);
  [["78/78", "E2E 자동 시험"], ["10회", "반복 무결점"], ["0건", "300초 부하 안전 위반"]].forEach(([big, lab], i) => {
    const yy = y + i * 0.6;
    t(s, big, rx + 0.1, yy, 1.2, 0.5, { size: 22, medium: true, valign: "middle", lh: 1 });
    t(s, lab, rx + 1.35, yy, rw - 1.35, 0.5, { size: 9.5, color: C.graphite, valign: "middle", lh: 1.2 });
  });
  y += 1.95;
  card(s, X0, y, XW, 0.9);
  pill(s, "사용자 검증", X0 + 0.2, y + 0.14, 1.0, { fill: C.teal, h: 0.24, size: 8 });
  t(s, "팀원이 관제사·VR 조작자 역할로 실물 TB1·TB2 확인. 외부 사용자 평가와 현장 정지 시간(MTBI) 측정은 다음 단계.", X0 + 0.2, y + 0.46, XW - 0.4, 0.35, { size: 10, lh: 1.3 });
}

// ---------- 9. 한계 · 보완 ----------
{
  const s = slide(9, 5);
  let y = query(s, "현장에 들이기 전에 무엇을 보완해야 하나?");
  const rows = [["높이 사각", "2D LiDAR 바닥 약 0.17m 한 평면", "깊이 카메라 융합"], ["위치 누적 오차", "휠 odom 누적 → 시작 위치 재설정", "SLAM 위치 보정"],
    ["통신 두절", "ROS 1 로봇 정지 동작이 펌웨어 의존", "로봇 측 정지 감시 노드"], ["보안", "rosbridge 인증 없음 → 망 분리 운용", "인증 · 암호화"], ["효과 실측", "정지 시간(MTBI) 현장 측정 전", "파일럿 라인 계측"]];
  card(s, X0, y, XW, 0.3 + rows.length * 0.56 + 0.1);
  [["한계", 0.2], ["현재 상태", 1.95], ["보완 방법", 5.15]].forEach(([h, dx]) => t(s, h, X0 + dx, y + 0.1, 2, 0.22, { size: 8.5, color: C.graphite, lh: 1 }));
  rows.forEach(([a, b, c], i) => {
    const yy = y + 0.38 + i * 0.56;
    s.addShape(pres.shapes.LINE, { x: X0 + 0.2, y: yy, w: XW - 0.4, h: 0, line: { color: C.mist, width: 0.5 } });
    t(s, a, X0 + 0.2, yy, 1.7, 0.56, { size: 11.5, medium: true, valign: "middle", lh: 1 });
    t(s, b, X0 + 1.95, yy, 3.1, 0.56, { size: 10, color: C.graphite, valign: "middle", lh: 1.2 });
    t(s, "→  " + c, X0 + 5.15, yy, XW - 5.35, 0.56, { size: 10.5, valign: "middle", lh: 1.2 });
  });
}

// ---------- 10. 기대효과 · BM ----------
{
  const s = slide(10, 5);
  let y = query(s, "어떻게 확산하고, 무엇으로 사업화하나?");
  const cw = cols(3);
  [["개조 패키지", "기존 2D LiDAR AGV에 릴레이 + 관제·VR SW 설치. 기체 교체 없음."], ["관제 구독", "로봇 대수 기준 SW 구독, 정지 원인 로그 리포트."], ["원격 개입 센터", "여러 현장의 멈춘 로봇을 한 관제석에서 VR로 복구."]].forEach(([h, d], i) => {
    const x = X0 + i * (cw + GAP);
    card(s, x, y, cw, 1.3);
    t(s, h, x + 0.2, y + 0.16, cw - 0.4, 0.3, { size: 12.5, medium: true, lh: 1.1 });
    t(s, d, x + 0.2, y + 0.55, cw - 0.4, 0.7, { size: 9.5, color: C.graphite, lh: 1.4 });
  });
  y += 1.42;
  pill(s, "구상 단계", X0, y, 0.9, { fill: C.teal, h: 0.24, size: 8 });
  t(s, "가격·매출 수치는 파일럿 이후 산정  ·  시장: AGV·AMR 2030년 $22B (LogisticsIQ 2024)", X0 + 1.02, y, XW - 1.02, 0.24, { size: 9, color: C.graphite, valign: "middle", lh: 1 });
  y += 0.5;
  card(s, X0, y, XW, 1.2, { fill: C.ink, flat: true });
  t(s, "로봇은 멈추고 알리고, 판단은 사람이 내린다.", X0 + 0.3, y, XW - 0.6, 1.2, { size: 20, color: C.canvas, medium: true, valign: "middle", lh: 1.2 });
}

pres.writeFile({ fileName: OUT }).then(f => console.log("written", f, "notes", Object.keys(notes).length));
