// PRESENTATION_10SLIDES_VERCEL.pptx — Vercel 스타일 변형 (DESIGN (vercel).md 기준). 내용·대본은 PRESENTATION_10SLIDES.md와 동일.
// 규칙: 종이색 캔버스 #fafafa, 글자 #171717/#4d4d4d/#666666, 1px 헤어라인 #ebebeb, 반경 6px, 그림자 없음,
//       강조색은 터미널 그린 #297a3a 하나, 제목 굵기 400대, 라벨은 모노 대문자, ▲ 기호.
// 폰트: Geist Sans → Pretendard (Inter 계열 한글), Geist Mono → Cascadia Mono. 미설치 PC는 시스템 대체 폰트.
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

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.title = "멈추고, 알리고, 사람이 빼낸다 — Vercel style";

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

function eyebrow(s, text, x, y, color = C.obsidian, w = 6) {
  s.addText(text.toUpperCase(), { x, y, w, h: 0.22, fontFace: MONO, fontSize: 8.5, color, charSpacing: 1.2,
    margin: 0, valign: "middle", isTextBox: true });
}

function heading(s, text, y = 0.78, size = 28, color = C.obsidian, w = W - 2 * M) {
  s.addText(text, { x: M, y, w, h: 0.62, fontFace: SANS, fontSize: size, color, charSpacing: -1,
    margin: 0, valign: "middle", isTextBox: true });
}

function card(s, x, y, w, h, opts = {}) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: R,
    fill: { color: opts.dark ? C.obsidian : opts.fill || C.white }, line: { color: opts.dark ? C.obsidian : opts.border || C.hair, width: opts.lineWidth || 0.75 } });
}

function body(s, text, x, y, w, h, opts = {}) {
  s.addText(text, { x, y, w, h, fontFace: SANS, fontSize: opts.size || 11.5, color: opts.color || C.charcoal,
    margin: 0, valign: "top", lineSpacingMultiple: 1.2, isTextBox: true, bold: opts.bold || false });
}

function footer(s, n, dark = false) {
  s.addText("▲", { x: M, y: H - 0.42, w: 0.2, h: 0.2, fontFace: SANS, fontSize: 9, color: dark ? C.white : C.carbon, margin: 0, isTextBox: true });
  s.addText("GNICT 2026 · 대학부 32 · AGV DIGITAL TWIN", { x: M + 0.25, y: H - 0.42, w: 5, h: 0.2, fontFace: MONO, fontSize: 7,
    color: dark ? C.smoke : C.stone, charSpacing: 1, margin: 0, isTextBox: true });
  s.addText(String(n).padStart(2, "0") + " / 10", { x: W - M - 1.2, y: H - 0.42, w: 1.2, h: 0.2, fontFace: MONO, fontSize: 7,
    color: dark ? C.smoke : C.stone, align: "right", margin: 0, isTextBox: true });
}

// ---------- 1. 표지 (Hero) ----------
{
  const s = canvas();
  eyebrow(s, "제4회 경남 AI·SW 경진대회 · 대학부 · 분야 32", M, 0.6);
  s.addText("멈추고,\n알리고,\n사람이 빼낸다.", { x: M, y: 1.0, w: 4.6, h: 2.6, fontFace: SANS, fontSize: 42, color: C.obsidian,
    charSpacing: -2, lineSpacingMultiple: 0.95, margin: 0, valign: "top", isTextBox: true });
  s.addShape(pres.shapes.ISOSCELES_TRIANGLE, { x: 5.25, y: 1.35, w: 1.7, h: 1.47, fill: { color: C.carbon }, line: { color: C.carbon, width: 0 } });
  const stack = [["PROBLEM", "AGV 협착·교착"], ["AGENT", "LiDAR 판단 + 정지 우선"], ["INTERFACE", "VR 원격 개입"], ["HARDWARE", "TurtleBot3 × 2"]];
  stack.forEach(([k, v], i) => {
    const y = 1.15 + i * 0.55;
    s.addText(k, { x: 7.55, y, w: 1.9, h: 0.2, fontFace: MONO, fontSize: 7.5, color: C.stone, charSpacing: 1.2, margin: 0, isTextBox: true });
    s.addText(v, { x: 7.55, y: y + 0.2, w: 1.95, h: 0.25, fontFace: SANS, fontSize: 11, color: C.obsidian, margin: 0, isTextBox: true });
  });
  body(s, "MetaQuest2 VR 기반 피지컬 AI AGV 원격 개입 & 협착 방지 디지털 트윈", M, 3.75, 5.4, 0.35, { size: 12.5 });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M, y: 4.3, w: 1.55, h: 0.36, rectRadius: R, fill: { color: C.obsidian }, line: { color: C.obsidian, width: 0.75 } });
  s.addText("▲  Live Demo", { x: M, y: 4.3, w: 1.55, h: 0.36, fontFace: SANS, fontSize: 10.5, color: C.white, align: "center", valign: "middle", margin: 0, isTextBox: true });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M + 1.7, y: 4.3, w: 2.9, h: 0.36, rectRadius: R, fill: { color: C.paper }, line: { color: C.hair, width: 0.75 } });
  s.addText("국립한국해양대학교 · [팀명] · [발표자]", { x: M + 1.7, y: 4.3, w: 2.9, h: 0.36, fontFace: SANS, fontSize: 10, color: C.charcoal, align: "center", valign: "middle", margin: 0, isTextBox: true });
  footer(s, 1);
  addNotes(s, 1);
}

// ---------- 2. 배경·문제 ----------
{
  const s = canvas();
  eyebrow(s, "01 — Problem", M, 0.5);
  heading(s, "사람과 AGV가 같은 통로를 쓸 때");
  const stats = [
    ["53%", "끼임 재해", "산업용 로봇 사고 1위\n부딪힘 34%가 뒤를 잇는다", "KOSHA · 2011–2020 · n=355"],
    ["66", "2024년 끼임 사망자", "전국 산업현장 압착 사망\n전년 대비 +22.2% 급증", "고용노동부 · 2024 재해조사 통계"],
    ["$2.3M", "시간당 라인 정지 비용", "자동차·배터리 공장 최대치\nFMCG 평균 $36,000/h", "Siemens Senseye · Downtime 2024"],
  ];
  const cw = (W - 2 * M - 2 * 0.2) / 3;
  stats.forEach(([big, head, sub, src], k) => {
    const x = M + k * (cw + 0.2), y = 1.65;
    card(s, x, y, cw, 2.85);
    s.addText(big, { x: x + 0.22, y: y + 0.2, w: cw - 0.44, h: 0.85, fontFace: SANS, fontSize: 40, color: C.obsidian, charSpacing: -2, margin: 0, valign: "middle", isTextBox: true });
    s.addText(head, { x: x + 0.22, y: y + 1.1, w: cw - 0.44, h: 0.3, fontFace: SANS, fontSize: 13, color: C.obsidian, margin: 0, isTextBox: true });
    body(s, sub, x + 0.22, y + 1.45, cw - 0.44, 0.6, { size: 10.5 });
    s.addShape(pres.shapes.LINE, { x: x + 0.22, y: y + 2.3, w: cw - 0.44, h: 0, line: { color: C.hair, width: 0.75 } });
    s.addText(src.toUpperCase(), { x: x + 0.22, y: y + 2.38, w: cw - 0.44, h: 0.3, fontFace: MONO, fontSize: 6.5, color: C.stone, charSpacing: 0.6, margin: 0, isTextBox: true });
  });
  body(s, "멈춘 AGV는 사람이 걸어올 때까지 통로를 막는다. 사고와 정지 비용은 같은 지점에서 생긴다.", M, 4.65, W - 2 * M, 0.3, { size: 11, color: C.obsidian });
  footer(s, 2);
  addNotes(s, 2);
}

// ---------- 3. 3대 한계 (출처 및 표준 규격 명시) ----------
{
  const s = canvas();
  eyebrow(s, "02 — Limits", M, 0.5);
  heading(s, "보급형 AGV가 풀지 못한 세 가지");
  const cols = [
    ["01", "높이 사각지대", "2D LiDAR는 한 평면(Burger 바닥 약 0.17m)만 스캔. 선반 돌출물, 포크, 작업자 상체는 놓친다. 3D LiDAR는 중소 현장에 부담이 크다.", "ISO 3691-4:2020 · 무인 산업차량 안전요건"],
    ["02", "자율 후진의 역설", "규격은 주행 방향의 사람 감지·보호를 요구한다. 후방 감지 없는 로봇이 스스로 물러날 수 없으니 결국 비상정지로 끝난다.", "ISO 3691-4 · ANSI/ITSDF B56.5 · 주행 방향 보호"],
    ["03", "물리적 출동", "정지된 AGV는 관리자가 현장까지 가서 확인·조작해야 풀린다. 그동안 같은 통로와 라인이 멈춘다.", "Siemens · True Cost of Downtime 2024"],
  ];
  const cw = (W - 2 * M - 2 * 0.2) / 3;
  cols.forEach(([n, head, txt, src], k) => {
    const x = M + k * (cw + 0.2), y = 1.65, dark = k === 1;
    card(s, x, y, cw, 3.05, { dark });
    s.addText(n, { x: x + 0.22, y: y + 0.22, w: 1, h: 0.25, fontFace: MONO, fontSize: 9, color: dark ? C.smoke : C.stone, charSpacing: 1.2, margin: 0, isTextBox: true });
    s.addText(head, { x: x + 0.22, y: y + 0.55, w: cw - 0.44, h: 0.45, fontFace: SANS, fontSize: 18, color: dark ? C.white : C.obsidian, charSpacing: -0.6, margin: 0, isTextBox: true });
    body(s, txt, x + 0.22, y + 1.15, cw - 0.44, 1.35, { size: 10.5, color: dark ? C.ash : C.charcoal });
    s.addShape(pres.shapes.LINE, { x: x + 0.22, y: y + 2.55, w: cw - 0.44, h: 0, line: { color: dark ? C.charcoal : C.hair, width: 0.75 } });
    s.addText(src.toUpperCase(), { x: x + 0.22, y: y + 2.62, w: cw - 0.44, h: 0.3, fontFace: MONO, fontSize: 6.5, color: dark ? C.smoke : C.stone, charSpacing: 0.6, margin: 0, isTextBox: true });
  });
  footer(s, 3);
  addNotes(s, 3);
}

// ---------- 4. 솔루션 + 대응 프로세스 패러다임 전환 비교 ----------
{
  const s = canvas();
  eyebrow(s, "03 — Solution", M, 0.5);
  heading(s, "정지 우선, 그리고 VR 원격 개입");
  const steps = [
    ["STOP", "위험하면 즉시 멈춘다", "전방 0.35m · AGV 간 1.0m → 속도 즉시 0. 자동 후진 없음."],
    ["NOTIFY", "원인과 탈출 경로를 그린다", "정지 원인 + LiDAR 360° 탈출 경로를 영상 바닥에 투영."],
    ["TAKE OVER", "사람이 VR로 즉각 빼낸다", "관제 맵 클릭 → VR 콕핏 텔레포트 → 그립 데드맨 조종."],
  ];
  steps.forEach(([tag, head, txt], k) => {
    const y = 1.6 + k * 0.95;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M, y, w: 1.05, h: 0.26, rectRadius: 0.13, fill: { color: k === 2 ? C.obsidian : C.white }, line: { color: k === 2 ? C.obsidian : C.hair, width: 0.75 } });
    s.addText(tag, { x: M, y, w: 1.05, h: 0.26, fontFace: MONO, fontSize: 7.5, color: k === 2 ? C.white : C.obsidian, align: "center", valign: "middle", charSpacing: 1, margin: 0, isTextBox: true });
    s.addText(head, { x: M + 1.25, y: y - 0.04, w: 3.3, h: 0.3, fontFace: SANS, fontSize: 14, color: C.obsidian, margin: 0, isTextBox: true });
    body(s, txt, M + 1.25, y + 0.3, 3.3, 0.5, { size: 10 });
  });

  // 우측: Before vs After 대응 프로세스 비교 카드
  const rx = 5.25, rw = W - M - rx;
  card(s, rx, 1.55, rw, 1.4, { fill: C.white, border: C.hair });
  s.addText("CONVENTIONAL AGV · 기존 대응 방식", { x: rx + 0.2, y: 1.68, w: rw - 0.4, h: 0.22, fontFace: MONO, fontSize: 7.5, color: C.stone, charSpacing: 1, margin: 0, isTextBox: true });
  body(s, "• 위험 감지: 단순 E-STOP 급정지 (통로 마비)\n• 복구 방식: 관리자 현장 출동 (도착까지 통로 정체)\n• 2차 위험: 사각지대 맹목적 후진 시 보행자 2차 협착 발생", rx + 0.2, 1.95, rw - 0.4, 0.85, { size: 9.5, color: C.charcoal });

  card(s, rx, 3.08, rw, 1.52, { fill: C.white, border: C.green, lineWidth: 1.2 });
  s.addText("PHYSICAL AI SOLUTION · 본 제안 솔루션", { x: rx + 0.2, y: 3.22, w: rw - 0.4, h: 0.22, fontFace: MONO, fontSize: 7.5, color: C.green, charSpacing: 1, margin: 0, isTextBox: true });
  body(s, "• 안전 게이트: 전방 0.35m · AGV 간 1.0m 전진 지령 차단 (릴레이)\n• 시각적 안내: LiDAR 탈출 방향·선회 경로를 FPV 영상 바닥에 투영\n• 원격 개입: 관제 클릭 → 그 로봇 콕핏 즉시 전환 (그 로봇만 MANUAL)\n• 복귀: 후진·회전 수동 탈출 → Y/R로 AUTO 재개 (자동 재개 없음)", rx + 0.2, 3.48, rw - 0.4, 1.0, { size: 9.5, color: C.obsidian });

  footer(s, 4);
  addNotes(s, 4);
}

// ---------- 5. 아키텍처 (3대 Tier 포괄적 그룹핑) ----------
{
  const s = canvas();
  eyebrow(s, "04 — Architecture", M, 0.5);
  heading(s, "로봇 두 대, 릴레이 하나, 화면 둘");
  const fw = 5.8, fh = fw * 718 / 1512;
  card(s, M, 1.55, fw + 0.24, fh + 0.24);
  s.addImage({ path: A("fig_architecture_body.png"), x: M + 0.12, y: 1.67, w: fw, h: fh, altText: "시스템 아키텍처" });

  const tiers = [
    ["TIER 1 · PHYSICAL FIELD", "TurtleBot3 × 2 (ROS 1 · ROS 2)\nLDS-02 LiDAR · Pi Camera 15.7 fps"],
    ["TIER 2 · AI RELAY AGENT", "Python asyncio · 20 Hz rosbridge\nLiDAR 기하 추론 · 안전 게이트"],
    ["TIER 3 · DIGITAL TWIN & VR", "Unity 6 + OpenXR (PC·HMD 분리)\nPC 관제 맵 · Quest 2 콕핏"],
  ];
  tiers.forEach(([k, v], i) => {
    const x = 6.85, y = 1.55 + i * 1.02;
    card(s, x, y, 2.6, 0.92);
    s.addText(k, { x: x + 0.15, y: y + 0.12, w: 2.3, h: 0.2, fontFace: MONO, fontSize: 7.5, color: C.green, charSpacing: 1.0, margin: 0, isTextBox: true });
    body(s, v, x + 0.15, y + 0.35, 2.35, 0.5, { size: 9.5, color: C.obsidian });
  });
  footer(s, 5);
  addNotes(s, 5);
}

// ---------- 6. AI Agent 6요소 ----------
{
  const s = canvas();
  eyebrow(s, "05 — AI Agent", M, 0.5);
  heading(s, "AI Agent 6요소");
  const items = [
    ["GOAL", "AGV 2대 협착·충돌 0건, 봉착 시 무사고 탈출"],
    ["PLANNING", "순찰 → 위험 감지 → 인터록 정지 → 탈출 경로 → 수동 개입 → 재개"],
    ["REASONING", "360° LiDAR 섹터 거리 · 로봇 폭 회랑 · 곡률 원호 · AGV 간 거리"],
    ["TOOL USE", "ROS /cmd_vel · /odom · /scan, ustreamer, WebSocket, Unity"],
    ["MEMORY", "로봇별 AUTO/MANUAL, 정지 원인, 배회·위치 원점, 운행 이력"],
    ["FEEDBACK", "영상 경로 띠 · 선회 화살표 · 적색 경고 · 손 방향 진동"],
  ];
  const cw = (W - 2 * M - 2 * 0.2) / 3, ch = 1.35;
  items.forEach(([k, v], i) => {
    const x = M + (i % 3) * (cw + 0.2), y = 1.6 + Math.floor(i / 3) * (ch + 0.2);
    card(s, x, y, cw, ch, { dark: i === 0 });
    s.addText(k, { x: x + 0.2, y: y + 0.18, w: cw - 0.4, h: 0.2, fontFace: MONO, fontSize: 8, color: i === 0 ? C.smoke : C.green, charSpacing: 1.2, margin: 0, isTextBox: true });
    body(s, v, x + 0.2, y + 0.48, cw - 0.4, ch - 0.6, { size: 11, color: i === 0 ? C.white : C.obsidian });
  });
  footer(s, 6);
  addNotes(s, 6);
}

// ---------- 7. 핵심 알고리즘 (조건 · 방법 · 결과 3단 논문식 약소화) ----------
{
  const s = canvas();
  eyebrow(s, "06 — Algorithm", M, 0.5);
  heading(s, "판단은 기하로, 결정은 사람에게");
  const steps = [
    ["01 · CONDITION (조건)", "전방 장애물 d < 0.35m 또는 AGV 간 거리 < 1.0m\n→ 전진 명령 즉시 차단 (vx = 0), 정지·알림 상태 진입"],
    ["02 · METHOD (방법)", "360° LiDAR 72방향 회랑 폭(w=0.24m) 여유 d(h) 탐색\n목적 함수: argmax [d(h) - 0.25|h|] (최대 여유 & 최소 회전)"],
    ["03 · RESULT (결과)", "최적 방위각 → FPV 바닥 가이드라인·선회 화살표 투영\n전진 차단 유지, 후진(후방 0.20m 가드)·회전은 사람이 조작"],
  ];
  steps.forEach(([k, v], i) => {
    const y = 1.62 + i * 0.95;
    s.addText(k, { x: M, y, w: 3.7, h: 0.22, fontFace: MONO, fontSize: 8.5, color: C.green, charSpacing: 1.2, margin: 0, isTextBox: true });
    body(s, v, M, y + 0.25, 3.7, 0.62, { size: 10, color: C.obsidian });
    if (i < steps.length - 1) s.addShape(pres.shapes.LINE, { x: M, y: y + 0.88, w: 3.7, h: 0, line: { color: C.hair, width: 0.75 } });
  });
  const fw = 5.0, fh = fw * 829 / 1885;
  card(s, 4.55, 1.55, fw + 0.24, fh + 0.24);
  s.addImage({ path: A("fig_escape_planner.png"), x: 4.67, y: 1.67, w: fw, h: fh, altText: "탈출 경로 계산 예" });
  s.addText("PLAN_ESCAPE · 전방 상자 + 우측 벽 → 좌 40° 선택", { x: 4.55, y: 1.55 + fh + 0.32, w: fw + 0.24, h: 0.2, fontFace: MONO, fontSize: 6.5, color: C.stone, charSpacing: 0.6, margin: 0, isTextBox: true });
  body(s, "VFH · Follow-the-Gap 계열 국소 반응형. 경로는 카메라 영상 바닥에 핀홀 모델(렌즈 0.16m, 62.2°)로 투영. 자동 후진 없음.", 4.55, 4.3, fw + 0.24, 0.5, { size: 9.5 });
  footer(s, 7);
  addNotes(s, 7);
}

// ---------- 8. 정량 실증 (5대 현장 시나리오별 검증 체계) ----------
{
  const s = canvas();
  eyebrow(s, "07 — Verification", M, 0.5);
  heading(s, "5대 현장 시나리오 검증 · 73/73");

  const scenarios = [
    ["SCENARIO 01", "정면 돌발 장애물 봉착", "전방 0.3m 급정지, 전진 차단 / 후진·선회 수동 허용"],
    ["SCENARIO 02", "AGV 대향 마주침 교착", "2대 대향 접근 (거리 < 1.0m) → 양방향 STUCK 정지"],
    ["SCENARIO 03", "사방 협착 및 막다른 길", "사방 통과 여유 0.5m 미만 → STUCK(dead end), 자동 재개 없음"],
    ["SCENARIO 04", "VR 원격 텔레포트 개입", "관제 맵 클릭 → 콕핏 즉시 전환(그 로봇만 MANUAL) → 양손 탈출"],
    ["SCENARIO 05", "센서 결측치 방어 대응", "LD08 무효값 0.0 제외, 명령·odom 0.5s / scan 1.0s 끊김 시 정지"],
  ];
  const lw = 5.2;
  card(s, M, 1.55, lw, 3.15);
  scenarios.forEach(([tag, head, desc], i) => {
    const y = 1.68 + i * 0.58;
    s.addText(tag, { x: M + 0.2, y, w: 1.1, h: 0.2, fontFace: MONO, fontSize: 7.5, color: C.green, charSpacing: 0.8, margin: 0, isTextBox: true });
    s.addText(head, { x: M + 1.35, y, w: 1.6, h: 0.2, fontFace: SANS, fontSize: 10, color: C.obsidian, bold: true, margin: 0, isTextBox: true });
    s.addText(desc, { x: M + 0.2, y: y + 0.22, w: lw - 0.4, h: 0.25, fontFace: SANS, fontSize: 8.5, color: C.charcoal, margin: 0, isTextBox: true });
    if (i < scenarios.length - 1) s.addShape(pres.shapes.LINE, { x: M + 0.2, y: y + 0.52, w: lw - 0.4, h: 0, line: { color: C.hair, width: 0.5 } });
  });

  const stats = [["73/73", "가상 브리지 자동 시험"], ["2대", "실물 TurtleBot3"], ["20 Hz", "제어 릴레이 주기"], ["15.7 fps", "실측 영상 수신"]];
  stats.forEach(([big, label], i) => {
    const x = 6.05 + (i % 2) * 1.7, y = 1.55 + Math.floor(i / 2) * 1.6;
    card(s, x, y, 1.55, 1.45);
    s.addText(big, { x: x + 0.15, y: y + 0.22, w: 1.25, h: 0.6, fontFace: SANS, fontSize: 26, color: C.obsidian, charSpacing: -1.5, margin: 0, isTextBox: true });
    s.addText(label.toUpperCase(), { x: x + 0.15, y: y + 0.95, w: 1.25, h: 0.35, fontFace: MONO, fontSize: 7, color: C.stone, charSpacing: 0.8, margin: 0, isTextBox: true });
  });
  footer(s, 8);
  addNotes(s, 8);
}

// ---------- 9. 시스템 한계 및 기술적 과제 ----------
{
  const s = canvas();
  eyebrow(s, "08 — Limitations", M, 0.5);
  heading(s, "시스템 한계 및 기술적 과제");
  const limits = [
    ["01", "2D LiDAR 단일 평면 한계", "지상 0.17m 평면만 스캔하여 상부 돌출 적재물과 천장 행잉 케이블 미감지.", "향후 과제: RGB-D 심도 카메라 및 상부 초음파 센서 다중 융합"],
    ["02", "산업 현장 통신 음영 구역", "공장 내 대형 철골 구조물 차폐 및 Wi-Fi 음영 구역에서 원격 제어 지연 발생 위험.", "향후 과제: 이음5G(Private 5G) 인프라 연계 및 로봇 온디바이스 비상 SLAM"],
    ["03", "다대 로봇 동시 교착 병목", "3대 이상 다중 AGV가 좁은 병목 구간에서 동시 교착 시 1인 작업자 순차 개입 대기 발생.", "향후 과제: VDA 5050 상위 플릿 매니저 연동 및 교착 우선순위 자동 배차"],
  ];
  const cw = (W - 2 * M - 2 * 0.2) / 3;
  limits.forEach(([n, head, txt, roadmap], k) => {
    const x = M + k * (cw + 0.2), y = 1.65;
    card(s, x, y, cw, 3.05);
    s.addText(n, { x: x + 0.22, y: y + 0.22, w: 1, h: 0.25, fontFace: MONO, fontSize: 9, color: C.stone, charSpacing: 1.2, margin: 0, isTextBox: true });
    s.addText(head, { x: x + 0.22, y: y + 0.55, w: cw - 0.44, h: 0.45, fontFace: SANS, fontSize: 16, color: C.obsidian, charSpacing: -0.6, margin: 0, isTextBox: true });
    body(s, txt, x + 0.22, y + 1.15, cw - 0.44, 1.0, { size: 10, color: C.charcoal });
    s.addShape(pres.shapes.LINE, { x: x + 0.22, y: y + 2.2, w: cw - 0.44, h: 0, line: { color: C.hair, width: 0.75 } });
    s.addText("ROADMAP", { x: x + 0.22, y: y + 2.28, w: cw - 0.44, h: 0.18, fontFace: MONO, fontSize: 7, color: C.green, charSpacing: 0.8, margin: 0, isTextBox: true });
    body(s, roadmap, x + 0.22, y + 2.48, cw - 0.44, 0.5, { size: 9, color: C.obsidian });
  });
  footer(s, 9);
  addNotes(s, 9);
}

// ---------- 10. 시장 분석, 솔루션 비교 및 결론 ----------
{
  const s = canvas(true);
  eyebrow(s, "09 — Market & Impact", M, 0.45, C.smoke);
  s.addText("시장 분석, 솔루션 비교 및 결론", { x: M, y: 0.72, w: W - 2 * M, h: 0.45, fontFace: SANS, fontSize: 24, color: C.white,
    charSpacing: -1, margin: 0, isTextBox: true });

  // 상단: 시장 지표 카드 3개
  const mstats = [
    ["$22B", "AGV·AMR 시장 2030년 전망 (AGV 연 18% · AMR 연 30%, LogisticsIQ 2024)"],
    ["53%", "산업용 로봇 재해 중 끼임 (KOSHA 2011–2020)"],
    ["$2.3M/h", "자동차 라인 비계획 정지 비용 최대치 (Siemens 2024)"],
  ];
  const mcw = (W - 2 * M - 2 * 0.2) / 3;
  mstats.forEach(([big, sub], i) => {
    const x = M + i * (mcw + 0.2);
    card(s, x, 1.25, mcw, 0.85, { dark: true, border: C.charcoal });
    s.addText(big, { x: x + 0.15, y: 1.35, w: mcw - 0.3, h: 0.35, fontFace: SANS, fontSize: 18, color: C.white, bold: true, margin: 0, isTextBox: true });
    s.addText(sub, { x: x + 0.15, y: 1.72, w: mcw - 0.3, h: 0.3, fontFace: SANS, fontSize: 8, color: C.ash, margin: 0, isTextBox: true });
  });

  // 중단: 3사 경쟁 비교표
  const tableY = 2.25;
  card(s, M, tableY, W - 2 * M, 2.1, { dark: true, border: C.charcoal });
  const rows = [
    ["비교 항목", "기존 보급형 AGV", "고가 완전자율 AMR", "본 제안 Physical AI (VR Twin)"],
    ["도입 방식", "기체 단위 도입", "고가 센서 기체 신규 도입", "기존 기체 + 소프트웨어 (2D LiDAR·카메라)"],
    ["정지 복구", "관리자 현장 출동", "자체 재탐색 (복잡 환경 교착 가능)", "관제석에서 VR 원격 개입"],
    ["안전 메커니즘", "단순 범퍼/2D E-STOP (정지 후 수동 복구)", "3D 센서 자율 판단 (센서 오인 위험)", "정지 우선 인터록 + 인간 최종 승인"],
  ];
  rows.forEach((r, ri) => {
    const ry = tableY + 0.12 + ri * 0.48;
    const isHeader = ri === 0;
    r.forEach((cell, ci) => {
      const cx = M + 0.15 + (ci === 0 ? 0 : 1.4 + (ci - 1) * 2.45);
      const cw = ci === 0 ? 1.3 : 2.35;
      const highlight = ci === 3;
      s.addText(cell, { x: cx, y: ry, w: cw, h: 0.35, fontFace: isHeader ? MONO : SANS, fontSize: isHeader ? 8 : (highlight ? 9.5 : 8.5),
        color: isHeader ? C.smoke : (highlight ? C.green : (ci === 0 ? C.ash : C.white)), bold: highlight || isHeader, margin: 0, valign: "middle", isTextBox: true });
    });
    if (ri < rows.length - 1) s.addShape(pres.shapes.LINE, { x: M + 0.15, y: ry + 0.44, w: W - 2 * M - 0.3, h: 0, line: { color: C.charcoal, width: 0.5 } });
  });

  // 하단 맺음말
  s.addText("▲  로봇은 멈추고 알리고, 판단은 사람이 내린다 — 완전 무인의 환상 대신, 가장 안전하고 현실적인 피지컬 AI.", {
    x: M, y: 4.5, w: W - 2 * M, h: 0.32, fontFace: SANS, fontSize: 11, color: C.white, bold: true, margin: 0, isTextBox: true
  });

  footer(s, 10, true);
  addNotes(s, 10);
}

pres.writeFile({ fileName: OUT }).then(f => console.log("written", f, "notes", Object.keys(notes).length));
