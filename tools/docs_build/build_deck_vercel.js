// PRESENTATION_10SLIDES_VERCEL.pptx — 제출용 발표자료 (별지3, 10장). 대본은 PRESENTATION_10SLIDES.md 슬라이드 노트.
// 발표 6단 구성: 문제 30초 · Agent 설명 1분 · 구조 1분 · 실제 시연 2분 30초 · 성과 30초 · 발전계획·BM 30초.
// 디자인: DESIGN (vercel).md — 종이색 #fafafa, 글자 #171717/#4d4d4d/#666666, 1px 헤어라인 #ebebeb, 반경 6px, 그림자 없음,
//         강조색 터미널 그린 #297a3a 하나, 라벨은 모노 대문자, ▲ 기호.
// 폰트: Geist Sans → Pretendard, Geist Mono → Cascadia Mono. 미설치 PC는 시스템 대체 폰트.
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const DOCS = process.argv[2];
const OUT = path.join(DOCS, "PRESENTATION_10SLIDES_VERCEL.pptx");
const A = f => path.join(DOCS, "assets", f);

const C = {
  paper: "FAFAFA", white: "FFFFFF", hair: "EBEBEB", ash: "C9C9C9", smoke: "A8A8A8",
  stone: "666666", charcoal: "4D4D4D", obsidian: "171717", carbon: "000000", green: "297A3A",
  red: "C53030",
};
const SANS = "Pretendard", MONO = "Cascadia Mono";
const W = 10, H = 5.625, M = 0.55;
const R = 0.06;                      // 6px 반경 (인치 환산 근사)
const TOTAL = 10;
const GAP = 0.2;

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.title = "멈추고, 알리고, 사람이 빼낸다";

const notes = {};
fs.readFileSync(path.join(DOCS, "PRESENTATION_10SLIDES.md"), "utf8").replace(/\r/g, "")
  .split("### [Slide ").slice(1).forEach(block => {
    const n = parseInt(block, 10);
    const m = block.match(/\*\*대본[^*]*\*\*:\s*"([\s\S]*?)"\s*$/m);
    if (m) notes[n] = m[1];
  });
const addNotes = (s, n) => { if (notes[n]) s.addNotes(notes[n]); };

// ---------- 부품 ----------
function canvas(dark = false) {
  const s = pres.addSlide();
  s.background = { color: dark ? C.obsidian : C.paper };
  return s;
}

function text(s, t, x, y, w, h, o = {}) {
  s.addText(t, { x, y, w, h, fontFace: o.mono ? MONO : SANS, fontSize: o.size || 11, color: o.color || C.obsidian,
    bold: o.bold || false, align: o.align || "left", valign: o.valign || "top", charSpacing: o.cs || 0,
    lineSpacingMultiple: o.lh || 1.15, margin: 0, isTextBox: true });
}

function label(s, t, x, y, w, color = C.green, size = 7.5) {
  text(s, t.toUpperCase(), x, y, w, 0.2, { mono: true, size, color, cs: 1, valign: "middle" });
}

// 상단: 발표 구간 칩 + 소요 시간 + 제목
function header(s, section, time, title, dark = false) {
  label(s, section, M, 0.45, 5, dark ? C.smoke : C.obsidian, 8.5);
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: W - M - 0.8, y: 0.43, w: 0.8, h: 0.24, rectRadius: 0.12,
    fill: { color: dark ? C.obsidian : C.white }, line: { color: dark ? C.charcoal : C.hair, width: 0.75 } });
  text(s, time, W - M - 0.8, 0.43, 0.8, 0.24, { mono: true, size: 7.5, color: dark ? C.smoke : C.stone, align: "center", valign: "middle" });
  text(s, title, M, 0.75, W - 2 * M, 0.6, { size: 26, color: dark ? C.white : C.obsidian, cs: -1, valign: "middle" });
}

function card(s, x, y, w, h, o = {}) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: R,
    fill: { color: o.dark ? C.obsidian : o.fill || C.white },
    line: { color: o.border || (o.dark ? C.obsidian : C.hair), width: o.lineWidth || 0.75 } });
}

function hline(s, x, y, w, color = C.hair) {
  s.addShape(pres.shapes.LINE, { x, y, w, h: 0, line: { color, width: 0.75 } });
}

function pill(s, t, x, y, w, dark = false) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h: 0.26, rectRadius: 0.13,
    fill: { color: dark ? C.obsidian : C.white }, line: { color: dark ? C.obsidian : C.hair, width: 0.75 } });
  text(s, t, x, y, w, 0.26, { mono: true, size: 7.5, color: dark ? C.white : C.obsidian, align: "center", valign: "middle", cs: 1 });
}

function image(s, file, x, y, w, pxW, pxH, alt) {
  const h = w * pxH / pxW;
  card(s, x, y, w + 0.2, h + 0.2);
  s.addImage({ path: A(file), x: x + 0.1, y: y + 0.1, w, h, altText: alt });
  return h + 0.2;
}

function footer(s, n, dark = false) {
  text(s, "▲", M, H - 0.42, 0.2, 0.2, { size: 9, color: dark ? C.white : C.carbon });
  text(s, "GNICT 2026 · 대학부 32 · AGV DIGITAL TWIN", M + 0.25, H - 0.42, 5, 0.2, { mono: true, size: 7, color: dark ? C.smoke : C.stone, cs: 1 });
  text(s, String(n).padStart(2, "0") + " / " + TOTAL, W - M - 1.2, H - 0.42, 1.2, 0.2, { mono: true, size: 7, color: dark ? C.smoke : C.stone, align: "right" });
}

const cols = (n, total = W - 2 * M) => (total - (n - 1) * GAP) / n;

// ---------- 1. 표지 ----------
{
  const s = canvas();
  label(s, "제4회 경남 AI·SW 경진대회 · 대학부 · 분야 32 제조 피지컬 AI", M, 0.6, 7, C.obsidian, 8.5);
  text(s, "멈추고,\n알리고,\n사람이 빼낸다.", M, 1.0, 4.6, 2.6, { size: 42, cs: -2, lh: 0.95 });
  s.addShape(pres.shapes.ISOSCELES_TRIANGLE, { x: 5.25, y: 1.35, w: 1.7, h: 1.47, fill: { color: C.carbon }, line: { color: C.carbon, width: 0 } });
  const stack = [["PROBLEM", "AGV 협착 · 멈춤 출동"], ["AGENT", "LiDAR 판단 + 정지 우선"], ["INTERFACE", "VR 원격 개입"], ["HARDWARE", "TurtleBot3 × 2 (실물)"]];
  stack.forEach(([k, v], i) => {
    const y = 1.15 + i * 0.55;
    label(s, k, 7.55, y, 1.9, C.stone);
    text(s, v, 7.55, y + 0.2, 1.95, 0.25, { size: 11 });
  });
  text(s, "MetaQuest2 VR 기반 피지컬 AI AGV 원격 개입 & 협착 방지 디지털 트윈", M, 3.75, 5.6, 0.35, { size: 12.5, color: C.charcoal });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M, y: 4.3, w: 1.55, h: 0.36, rectRadius: R, fill: { color: C.obsidian }, line: { color: C.obsidian, width: 0.75 } });
  text(s, "▲  Live Demo", M, 4.3, 1.55, 0.36, { size: 10.5, color: C.white, align: "center", valign: "middle" });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M + 1.7, y: 4.3, w: 2.9, h: 0.36, rectRadius: R, fill: { color: C.paper }, line: { color: C.hair, width: 0.75 } });
  text(s, "국립한국해양대학교 · [팀명] · [발표자]", M + 1.7, 4.3, 2.9, 0.36, { size: 10, color: C.charcoal, align: "center", valign: "middle" });
  footer(s, 1);
  addNotes(s, 1);
}

// ---------- 2. 문제 (30초) — 누구의 어떤 문제 ----------
{
  const s = canvas();
  header(s, "1 · Problem — 누구의 어떤 문제", "0:30", "AGV와 같은 통로를 쓰는 사람들");
  const who = [
    ["현장 작업자", "AGV와 부딪히고 끼인다"],
    ["관제사·관리자", "멈출 때마다 현장 출동"],
    ["공장", "통로가 막히면 라인이 선다"],
  ];
  const lw = 2.75;
  label(s, "WHO · 사용자", M, 1.55, lw);
  who.forEach(([k, v], i) => {
    const y = 1.85 + i * 0.68;
    card(s, M, y, lw, 0.58, { dark: i === 1 });
    text(s, k, M + 0.18, y + 0.08, lw - 0.36, 0.22, { size: 11.5, bold: true, color: i === 1 ? C.white : C.obsidian });
    text(s, v, M + 0.18, y + 0.31, lw - 0.36, 0.22, { size: 9.5, color: i === 1 ? C.ash : C.charcoal });
  });

  const rx = M + lw + GAP, rw = W - M - rx, cw = cols(3, rw);
  label(s, "WHAT · 근거", rx, 1.55, rw);
  const stats = [
    ["53%", "로봇 재해 중 끼임", "KOSHA 2011–2020"],
    ["66명", "2024 끼임 사망 +22.2%", "고용노동부 2025"],
    ["$2.3M/h", "자동차 라인 정지 최대", "Siemens 2024"],
  ];
  stats.forEach(([big, head, src], k) => {
    const x = rx + k * (cw + GAP), y = 1.85;
    card(s, x, y, cw, 1.95);
    text(s, big, x + 0.16, y + 0.16, cw - 0.32, 0.6, { size: 26, cs: -1.5, valign: "middle" });
    text(s, head, x + 0.16, y + 0.85, cw - 0.32, 0.45, { size: 10, color: C.charcoal });
    hline(s, x + 0.16, y + 1.5, cw - 0.32);
    label(s, src, x + 0.16, y + 1.58, cw - 0.32, C.stone, 6.5);
  });
  card(s, M, 4.02, W - 2 * M, 0.85, { border: C.obsidian });
  label(s, "보급형 AGV의 한계", M + 0.2, 4.12, 3);
  text(s, "① 2D LiDAR 한 평면만 본다   ② 뒤를 못 봐 스스로 못 물러난다   ③ 멈추면 사람이 걸어가야 풀린다",
    M + 0.2, 4.38, W - 2 * M - 0.4, 0.35, { size: 11.5, valign: "middle" });
  footer(s, 2);
  addNotes(s, 2);
}

// ---------- 3. Agent 설명 (1분) — 목표 · 역할 · 핵심기능 ----------
{
  const s = canvas();
  header(s, "2 · Agent — 목표 · 역할 · 핵심기능", "1:00", "판단은 로봇이, 결정은 사람이");
  const gw = 2.75;
  card(s, M, 1.55, gw, 1.5, { dark: true });
  label(s, "GOAL · 목표", M + 0.2, 1.7, gw - 0.4, C.smoke);
  text(s, "AGV 2대 운용 중\n협착·충돌 0건,\n막히면 출동 없이 원격 탈출", M + 0.2, 2.0, gw - 0.4, 0.95, { size: 12.5, color: C.white });

  card(s, M, 3.2, gw, 1.67);
  label(s, "ROLE · 역할 분담", M + 0.2, 3.32, gw - 0.4);
  text(s, "Agent  감시 · 정지 · 원인 · 경로 추천", M + 0.2, 3.62, gw - 0.4, 0.3, { size: 10 });
  hline(s, M + 0.2, 3.98, gw - 0.4);
  text(s, "사람  로봇 선택 · VR 조종 · 재개 승인", M + 0.2, 4.08, gw - 0.4, 0.3, { size: 10 });
  hline(s, M + 0.2, 4.44, gw - 0.4);
  text(s, "자동 후진·자동 재개 없음", M + 0.2, 4.52, gw - 0.4, 0.25, { size: 9.5, color: C.green, bold: true });

  const rx = M + gw + GAP, rw = W - M - rx, cw = cols(2, rw), ch = 1.57;
  const feats = [
    ["01 · STOP", "위험하면 즉시 멈춘다", "전방 0.35m · AGV 간 0.3m → 전진 지령 0. 후진은 후방 0.20m 가드."],
    ["02 · NOTIFY", "원인과 탈출 경로를 그린다", "LiDAR 72방향 탈출 경로를 영상 바닥·관제 맵에 표시, 돌 쪽 손 진동."],
    ["03 · TAKE OVER", "클릭 한 번에 VR 콕핏", "관제 맵 클릭 → 그 로봇만 MANUAL → 그립 데드맨 + 양손 스틱."],
    ["04 · MULTI-AGV", "2대 AUTO와 만남 처리", "각자 직진 순찰, 0.3m 안에서 만나면 둘 다 정지, 사람이 한 대를 비킨다."],
  ];
  feats.forEach(([k, h, t], i) => {
    const x = rx + (i % 2) * (cw + GAP), y = 1.55 + Math.floor(i / 2) * (ch + 0.15);
    card(s, x, y, cw, ch);
    label(s, k, x + 0.2, y + 0.15, cw - 0.4);
    text(s, h, x + 0.2, y + 0.42, cw - 0.4, 0.3, { size: 13.5 });
    text(s, t, x + 0.2, y + 0.8, cw - 0.4, 0.7, { size: 9.5, color: C.charcoal });
  });
  footer(s, 3);
  addNotes(s, 3);
}

// ---------- 4. 구조 ① Workflow (구조 1분 중 30초) ----------
{
  const s = canvas();
  header(s, "3 · Architecture — Workflow", "0:30", "순찰 → 정지 → 경로 → 개입 → 재개");
  const steps = [
    ["01", "AUTO 순찰", "R 키, 2대 직진 0.10 m/s"],
    ["02", "위험 감지", "LiDAR 360° · odom 20 Hz"],
    ["03", "정지 게이트", "전진 0 · 원인 기록"],
    ["04", "탈출 경로", "72방향 회랑 · 영상 투영"],
    ["05", "VR 개입", "클릭 → 콕핏 · 데드맨"],
    ["06", "AUTO 재개", "사람이 R · 자동 재개 없음"],
  ];
  const cw = cols(6), y = 1.65;
  steps.forEach(([n, h, t], i) => {
    const x = M + i * (cw + GAP), dark = i === 2 || i === 4;
    card(s, x, y, cw, 1.45, { dark });
    label(s, n, x + 0.14, y + 0.14, cw - 0.28, dark ? C.smoke : C.stone);
    text(s, h, x + 0.14, y + 0.42, cw - 0.28, 0.3, { size: 12.5, color: dark ? C.white : C.obsidian });
    text(s, t, x + 0.14, y + 0.8, cw - 0.28, 0.55, { size: 8.5, color: dark ? C.ash : C.charcoal });
    if (i < steps.length - 1) text(s, "›", x + cw, y + 0.5, GAP, 0.4, { size: 16, color: C.smoke, align: "center", valign: "middle" });
  });
  text(s, "Agent 구간: 01–04 · 사람 구간: 05–06", M, 3.2, 5, 0.22, { mono: true, size: 7.5, color: C.stone });

  const by = 3.55, bw = cols(3);
  const cmr = [
    ["CONDITION · 조건", "전방 < 0.35m 또는 AGV 간 중심 < 0.3m → 전진 지령 차단"],
    ["METHOD · 방법", "5° × 72방향 로봇 폭 회랑 여유 d(h), 0.5m 미만 제외, J = d − 0.25·|h| 최대"],
    ["RESULT · 결과", "최적 방향을 FPV 바닥 경로 띠·선회 화살표로 투영, 조작은 사람"],
  ];
  cmr.forEach(([k, v], i) => {
    const x = M + i * (bw + GAP);
    card(s, x, by, bw, 1.3, { border: i === 2 ? C.green : C.hair, lineWidth: i === 2 ? 1.2 : 0.75 });
    label(s, k, x + 0.18, by + 0.14, bw - 0.36);
    text(s, v, x + 0.18, by + 0.44, bw - 0.36, 0.8, { size: 10 });
  });
  footer(s, 4);
  addNotes(s, 4);
}

// ---------- 5. 구조 ② AI · Tool · Data · Memory (구조 1분 중 30초) ----------
{
  const s = canvas();
  header(s, "3 · Architecture — AI · Tool · Data · Memory", "0:30", "로봇 두 대, 릴레이 하나, 화면 둘");
  const ih = image(s, "fig_architecture_body.png", M, 1.55, 4.9, 1512, 718, "시스템 아키텍처");
  text(s, "안전 게이트를 통과한 속도만 /cmd_vel로 나간다 · 20 Hz", M, 1.55 + ih + 0.08, 5.1, 0.2, { mono: true, size: 6.5, color: C.stone, cs: 0.6 });
  const items = [
    ["AI", "LiDAR 기하 추론 (VFH·Follow-the-Gap 계열) · 곡률 궤적 (DWA 계열) · LLM 미사용"],
    ["TOOL", "ROS /cmd_vel · /odom · /scan (rosbridge) · ustreamer 카메라 · WebSocket · Unity · Quest 2"],
    ["DATA", "실시간 LiDAR 360° · 휠 odom · 640×480 영상 · 학습 데이터 수집 없음"],
    ["MEMORY", "로봇별 AUTO/MANUAL · 정지 원인 · 위치 원점 · 운행 이력 JSONL"],
  ];
  const rx = M + 5.3, rw = W - M - rx, ch = 0.78;
  items.forEach(([k, v], i) => {
    const y = 1.55 + i * (ch + 0.1);
    card(s, rx, y, rw, ch);
    label(s, k, rx + 0.16, y + 0.1, rw - 0.32);
    text(s, v, rx + 0.16, y + 0.32, rw - 0.32, 0.44, { size: 8.5 });
  });
  footer(s, 5);
  addNotes(s, 5);
}

// ---------- 6. 실제 시연 ① 입력 → 판단 → Tool → 결과 (2분 30초 중) ----------
{
  const s = canvas();
  header(s, "4 · Live Demo — 입력 → 판단 → Tool → 결과", "2:30", "실물 2대로 보여드리는 한 바퀴");
  const head = ["막", "입력", "판단 (Agent)", "Tool 호출", "결과"];
  const rows = [
    ["① 자율 순찰", "관제 PC  R", "로봇 간 0.3m · 전방 0.35m 감시", "/cmd_vel 0.10 m/s 직진", "2대 주행 → 접근 시 둘 다 정지"],
    ["② 정지·알림", "작업자 진입", "전방 0.35m 안 → 전진 차단", "/cmd_vel 0 · 텔레메트리 STOP", "지도 적색 · 원인 표시 · 경로 띠"],
    ["③ VR 개입", "관제 맵 클릭", "그 로봇만 MANUAL · 탈출 방향 산출", "Quest 콕핏 · 손 방향 진동", "그립 + 스틱으로 후진·선회 탈출"],
    ["④ 안전장치", "그립 놓기 · 과속", "데드맨 · 상한 0.15 m/s · 워치독 0.5s", "/cmd_vel 0 또는 제한", "즉시 정지 · 속도 제한"],
    ["⑤ 재개", "관제 PC  R", "사람 승인 시에만 AUTO", "/cmd_vel 0.10 m/s", "순찰 복귀"],
  ];
  const cw = [1.25, 1.35, 2.35, 2.0, 1.95], x0 = M, y0 = 1.5, rh = 0.56;
  card(s, M, y0, W - 2 * M, 0.38 + rows.length * rh + 0.08);
  let x = x0 + 0.15;
  head.forEach((h, i) => { label(s, h, x, y0 + 0.1, cw[i] - 0.1, C.stone); x += cw[i]; });
  hline(s, M + 0.15, y0 + 0.36, W - 2 * M - 0.3);
  rows.forEach((r, ri) => {
    const y = y0 + 0.42 + ri * rh;
    let cx = x0 + 0.15;
    r.forEach((c, ci) => {
      text(s, c, cx, y, cw[ci] - 0.12, rh - 0.08, { size: ci === 0 ? 10.5 : 9.5, bold: ci === 0, valign: "middle",
        color: ci === 4 ? C.green : (ci === 0 ? C.obsidian : C.charcoal) });
      cx += cw[ci];
    });
    if (ri < rows.length - 1) hline(s, M + 0.15, y + rh - 0.03, W - 2 * M - 0.3);
  });
  text(s, "화면 4분할: 관제 맵 · Quest 콕핏 · 릴레이 터미널 로그 · 실물 로봇 캠  —  라이브 불가 시 시연 영상 2~4막으로 대체", M, 4.92, W - 2 * M, 0.2,
    { mono: true, size: 7, color: C.stone, cs: 0.4 });
  footer(s, 6);
  addNotes(s, 6);
}

// ---------- 7. 실제 시연 ② 화면에서 보이는 것 ----------
{
  const s = canvas();
  header(s, "4 · Live Demo — 화면 근거", "2:30", "멈춘 이유와 빠져나갈 길이 보인다");
  const w1 = 2.3;
  const h1 = image(s, "overlay_stop_path.jpg", M, 1.55, w1, 640, 480, "콕핏 영상 위 정지 배너와 경로");
  const x2 = M + w1 + 0.2 + GAP;
  image(s, "topdown_warning_on.png", x2, 1.55, h1 - 0.2, 720, 720, "관제 맵 적색 경고");
  const x3 = x2 + (h1 - 0.2) + 0.2 + GAP, rw = W - M - x3;
  const caps = [
    ["COCKPIT", "영상 바닥에 추천 궤적 띠 · 선회 화살표 · 적색 정지 배너"],
    ["GOD-VIEW", "멈춘 로봇은 적색 차체 · 위험 원판, 사이드바에 정지 원인"],
    ["TERMINAL", "[AUTO] … STUCK · [INTERLOCK] 이벤트 = 판단 → Tool 호출 기록"],
  ];
  caps.forEach(([k, v], i) => {
    const y = 1.55 + i * 0.75;
    label(s, k, x3, y, rw);
    text(s, v, x3, y + 0.24, rw, 0.45, { size: 9.5, color: C.charcoal });
  });
  const ey = 1.55 + h1 + 0.15;
  const eh = image(s, "fig_escape_planner.png", M, ey, 2.6, 1885, 829, "탈출 경로 계산 예");
  text(s, "plan_escape · 전방 상자 + 우측 벽 → 좌 40° 선택 (실제 계산 결과 그림)", M + 3.0, ey + 0.1, W - 2 * M - 3.0, 0.4, { size: 10 });
  text(s, "그림은 실제 출력 예시 · 발표 당일 라이브 화면이 우선", M + 3.0, ey + 0.5, W - 2 * M - 3.0, 0.2, { mono: true, size: 7, color: C.stone });
  footer(s, 7);
  addNotes(s, 7);
}

// ---------- 8. 성과 (30초) — Before / After · 검증 · 효과 ----------
{
  const s = canvas();
  header(s, "5 · Impact — Before / After · 검증 · 효과", "0:30", "멈춤은 같아도, 푸는 방법이 바뀐다");
  const bw = cols(2, 5.3);
  const ba = [
    ["BEFORE · 기존 보급형 AGV", ["단순 비상정지 → 통로 마비", "관리자 현장 출동 후 수동 조작", "정지 이유 기록 없음"], false],
    ["AFTER · 본 시스템", ["전진만 차단, 후진·회전은 허용", "관제석에서 클릭 → VR로 바로 탈출", "정지 원인·경로가 화면·로그에 남음"], true],
  ];
  ba.forEach(([k, list, on], i) => {
    const x = M + i * (bw + GAP);
    card(s, x, 1.55, bw, 2.1, { border: on ? C.green : C.hair, lineWidth: on ? 1.2 : 0.75 });
    label(s, k, x + 0.18, 1.68, bw - 0.36, on ? C.green : C.stone);
    text(s, list.map(t => "• " + t).join("\n"), x + 0.18, 2.0, bw - 0.36, 1.5, { size: 10.5, lh: 1.45, color: on ? C.obsidian : C.charcoal });
  });
  card(s, M, 3.8, 5.3, 1.07);
  label(s, "사용자 검증 · 사실 그대로", M + 0.18, 3.9, 5);
  text(s, "팀원이 관제사·VR 조작자 역할로 실물 TB1·TB2 정지·주행·콕핏 전환 확인.\n외부 사용자 평가와 현장 정지 시간(MTBI) 측정은 아직 하지 않음.",
    M + 0.18, 4.16, 4.95, 0.65, { size: 9.5, color: C.charcoal });

  const rx = M + 5.3 + GAP, rw = W - M - rx, sw = cols(2, rw);
  const stats = [["78/78", "E2E 자동 시험"], ["10회", "반복 무결점"], ["0건", "300초 부하 안전 위반"], ["20 Hz", "제어·텔레메트리"]];
  stats.forEach(([big, lab], i) => {
    const x = rx + (i % 2) * (sw + GAP), y = 1.55 + Math.floor(i / 2) * 1.0;
    card(s, x, y, sw, 0.88, { dark: i === 0 });
    text(s, big, x + 0.15, y + 0.1, sw - 0.3, 0.45, { size: 20, cs: -1, valign: "middle", color: i === 0 ? C.white : C.obsidian });
    label(s, lab, x + 0.15, y + 0.58, sw - 0.3, i === 0 ? C.smoke : C.stone, 6.5);
  });
  card(s, rx, 3.6, rw, 1.27, { border: C.obsidian });
  label(s, "효과", rx + 0.16, 3.7, rw - 0.32);
  text(s, "• 출동 대기 없이 원격 복구\n• 3D LiDAR 없이 기존 기체 + SW\n• ROS 1·2 혼합 2대를 한 화면에", rx + 0.16, 3.95, rw - 0.32, 0.88, { size: 9.5, lh: 1.3 });
  footer(s, 8);
  addNotes(s, 8);
}

// ---------- 9. 발전계획 ① 한계와 현장 적용 전 보완점 (30초 중) ----------
{
  const s = canvas();
  header(s, "6 · Next — 한계 · 현장 적용 전 보완점", "0:30", "현장에 들이기 전에 고칠 것");
  const rows = [
    ["높이 사각", "2D LiDAR는 바닥 약 0.17m 한 평면만 본다", "깊이 카메라 융합"],
    ["위치 누적 오차", "휠 odom 누적 → 시작 위치 재설정으로 보정", "SLAM 위치 보정"],
    ["통신 두절", "ROS 1 로봇은 마지막 속도 유지 여부가 펌웨어 의존", "로봇 측 정지 감시 노드"],
    ["보안", "rosbridge 인증 없음 → 시연망 분리 운용", "인증 · 암호화 · 망 분리"],
    ["효과 실측", "정지 시간 단축(MTBI)은 아직 현장 측정 전", "파일럿 라인 계측"],
  ];
  const cw = [1.7, 4.4, 2.8], y0 = 1.55, rh = 0.6;
  card(s, M, y0, W - 2 * M, 0.38 + rows.length * rh + 0.05);
  [["한계", 0], ["현재 상태", 1], ["보완 방법", 2]].forEach(([h, i]) => {
    label(s, h, M + 0.18 + cw.slice(0, i).reduce((a, b) => a + b, 0), y0 + 0.1, cw[i], C.stone);
  });
  hline(s, M + 0.18, y0 + 0.36, W - 2 * M - 0.36);
  rows.forEach((r, ri) => {
    const y = y0 + 0.42 + ri * rh;
    let x = M + 0.18;
    r.forEach((c, ci) => {
      text(s, c, x, y, cw[ci] - 0.15, rh - 0.1, { size: ci === 0 ? 11 : 10, bold: ci === 0, valign: "middle",
        color: ci === 2 ? C.green : (ci === 0 ? C.obsidian : C.charcoal) });
      x += cw[ci];
    });
    if (ri < rows.length - 1) hline(s, M + 0.18, y + rh - 0.05, W - 2 * M - 0.36);
  });
  footer(s, 9);
  addNotes(s, 9);
}

// ---------- 10. 발전계획 ② 기대효과 · 비즈니스모델 · 결론 ----------
{
  const s = canvas(true);
  header(s, "6 · Next — 기대효과 · 비즈니스모델", "0:30", "기존 AGV에 얹는 안전 개입 레이어", true);
  const bm = [
    ["01 · 개조 패키지", "기존 2D LiDAR AGV에 릴레이 + 관제·VR SW 설치. 기체 교체 없음."],
    ["02 · 관제 구독", "로봇 대수 기준 관제·원격 개입 SW 구독, 정지 원인 로그 리포트."],
    ["03 · 원격 개입 센터", "여러 현장의 멈춘 로봇을 한 관제석에서 VR로 복구하는 운영 서비스."],
  ];
  const cw = cols(3);
  bm.forEach(([k, v], i) => {
    const x = M + i * (cw + GAP);
    card(s, x, 1.55, cw, 1.3, { dark: true, border: C.charcoal });
    label(s, k, x + 0.18, 1.68, cw - 0.36, C.smoke);
    text(s, v, x + 0.18, 1.98, cw - 0.36, 0.8, { size: 10, color: C.white });
  });
  text(s, "구상 단계 · 가격·매출 수치는 파일럿 이후 산정", M, 2.92, 6, 0.2, { mono: true, size: 7, color: C.smoke, cs: 0.4 });

  const ew = cols(2);
  card(s, M, 3.22, ew, 1.15, { dark: true, border: C.charcoal });
  label(s, "시장", M + 0.18, 3.32, ew - 0.36, C.smoke);
  text(s, "$22B", M + 0.18, 3.55, 1.3, 0.45, { size: 22, bold: true, color: C.white, valign: "middle" });
  text(s, "AGV·AMR 2030 전망\nLogisticsIQ 2024", M + 1.5, 3.58, ew - 1.7, 0.6, { size: 9, color: C.ash });
  const ex = M + ew + GAP;
  card(s, ex, 3.22, ew, 1.15, { dark: true, border: C.charcoal });
  label(s, "기대효과", ex + 0.18, 3.32, ew - 0.36, C.smoke);
  text(s, "• 협착 위험 구간에서 로봇이 먼저 멈춤\n• 멈춘 로봇 원격 복구로 통로 정체 감소\n• 판단 근거 기록 → 사고 원인 추적", ex + 0.18, 3.55, ew - 0.36, 0.8, { size: 9.5, color: C.white, lh: 1.25 });

  text(s, "▲  로봇은 멈추고 알리고, 판단은 사람이 내린다.", M, 4.55, W - 2 * M, 0.32, { size: 13, bold: true, color: C.white, valign: "middle" });
  footer(s, 10, true);
  addNotes(s, 10);
}

pres.writeFile({ fileName: OUT }).then(f => console.log("written", f, "notes", Object.keys(notes).length));
