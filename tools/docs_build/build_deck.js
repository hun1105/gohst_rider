// PRESENTATION_10SLIDES.pptx (pptxgenjs, 10장 — 대회 양식 10장 이내). 16:9, 10 x 5.625 in.
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const DOCS = process.argv[2];
const OUT = path.join(DOCS, "PRESENTATION_10SLIDES.pptx");
const A = f => path.join(DOCS, "assets", f);
// 촬영 캡처 슬롯: cap_x.jpg → cap_x.png → placeholder_cap_x.png
const CAP = name => [name + ".jpg", name + ".png", "placeholder_" + name + ".png"].map(A).find(p => fs.existsSync(p));

// 산업 현장 톤: 차콜 + 흰 바탕. 강조색은 의미 전용 (적=정지, 녹=탈출 경로)
const C = { dark: "1F242B", ink: "1F242B", slate: "4A5562", muted: "7A8490", panel: "EEF1F4", line: "D5DAE0",
            red: "C8102E", green: "1E8C45", white: "FFFFFF", onDark: "C9D0D8" };
const F = "Malgun Gothic", MONO = "Consolas";
const W = 10, H = 5.625, M = 0.5;

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.title = "멈추고, 알리고, 사람이 빼낸다 — 피지컬 AI AGV 디지털 트윈";

const notes = {};
fs.readFileSync(path.join(DOCS, "PRESENTATION_10SLIDES.md"), "utf8").replace(/\r/g, "")
  .split("### [Slide ").slice(1).forEach(block => {
    const n = parseInt(block, 10);
    const m = block.match(/\*\*대본[^*]*\*\*:\s*"([\s\S]*?)"\s*$/m);
    if (m) notes[n] = m[1];
  });

function chip(slide, text, x, y, color, opts = {}) {
  const w = opts.w || (0.16 + text.length * 0.085);
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h: 0.28, rectRadius: 0.06,
    fill: { color: opts.fill || color }, line: { color, width: 1 } });
  slide.addText(text, { x, y, w, h: 0.28, fontFace: MONO, fontSize: 10, bold: true, color: opts.textColor || C.white,
    align: "center", valign: "middle", margin: 0, isTextBox: true });
  return w;
}

function title(slide, tag, text, tagColor = C.slate) {
  chip(slide, tag, M, 0.38, tagColor);
  slide.addText(text, { x: M, y: 0.72, w: W - 2 * M, h: 0.62, fontFace: F, fontSize: 26, bold: true, color: C.ink,
    margin: 0, valign: "middle", isTextBox: true });
}

function body(slide, items, x, y, w, h, size = 13) {
  slide.addText(items.map((t, k) => ({ text: t, options: { bullet: true, breakLine: k < items.length - 1, paraSpaceAfter: 6 } })),
    { x, y, w, h, fontFace: F, fontSize: size, color: C.ink, valign: "top", margin: 0.02, isTextBox: true });
}

function addNotes(slide, n) { if (notes[n]) slide.addNotes(notes[n]); }

// ---------- 1. 표지 ----------
{
  const s = pres.addSlide(); s.background = { color: C.dark };
  chip(s, "대학부 · 32 제조 피지컬 AI · MetaQuest2 VR", M, 0.6, C.slate, { fill: C.dark, textColor: C.onDark, w: 3.3 });
  s.addText("멈추고, 알리고,\n사람이 빼낸다", { x: M, y: 1.05, w: 5.4, h: 1.9, fontFace: F, fontSize: 38, bold: true,
    color: C.white, margin: 0, valign: "top", isTextBox: true });
  s.addText("MetaQuest VR 기반 피지컬 AI AGV 원격 개입 & 협착 방지 디지털 트윈", { x: M, y: 3.0, w: 5.3, h: 0.7,
    fontFace: F, fontSize: 14, color: C.onDark, margin: 0, isTextBox: true });
  chip(s, "STOP", M, 3.85, C.red);
  chip(s, "ESCAPE →", M + 0.65, 3.85, C.green);
  chip(s, "TAKE OVER", M + 1.65, 3.85, C.slate, { fill: C.dark, textColor: C.onDark });
  s.addText("2026 제4회 경남 AI·SW 경진대회   |   국립한국해양대학교 [팀명] · [발표자]", { x: M, y: 4.85, w: 5.4, h: 0.3, fontFace: F, fontSize: 11,
    color: C.muted, margin: 0, isTextBox: true });
  s.addImage({ path: CAP("cap_field_robot"), x: 5.9, y: 1.1, w: 3.6, h: 2.025, altText: "현장 사진: TurtleBot3와 장애물" });
  s.addText("실물 TurtleBot3 2대 · AUTO 배회 구역", { x: 5.9, y: 3.2, w: 3.6, h: 0.3, fontFace: F, fontSize: 9,
    color: C.muted, margin: 0, isTextBox: true });
  addNotes(s, 1);
}

// ---------- 2. 배경·문제 (공식 통계) ----------
{
  const s = pres.addSlide(); s.background = { color: C.white };
  title(s, "01 PROBLEM", "사람과 AGV가 같은 통로를 쓸 때");
  const stats = [
    ["53%", "끼임", "산업용 로봇 재해 1위 · 부딪힘 34%", "안전보건공단, 2011~2020 재해자 355명"],
    ["66명", "2024년 끼임 사망", "전년 대비 +22.2%", "고용노동부, 2024 재해조사 대상 사망사고"],
    ["$2.3M", "시간당 라인 정지 비용", "자동차 최대 · FMCG $36k/h", "Siemens, True Cost of Downtime 2024"],
  ];
  const cw = (W - 2 * M - 2 * 0.3) / 3;
  stats.forEach(([big, head, sub, src], k) => {
    const x = M + k * (cw + 0.3), y = 1.6;
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: cw, h: 3.0, fill: { color: C.panel }, line: { color: C.panel } });
    s.addText(big, { x: x + 0.25, y: y + 0.25, w: cw - 0.5, h: 0.9, fontFace: MONO, fontSize: 40, bold: true, color: k === 0 ? C.red : C.ink, margin: 0, isTextBox: true });
    s.addText(head, { x: x + 0.25, y: y + 1.2, w: cw - 0.5, h: 0.4, fontFace: F, fontSize: 16, bold: true, color: C.ink, margin: 0, isTextBox: true });
    s.addText(sub, { x: x + 0.25, y: y + 1.65, w: cw - 0.5, h: 0.5, fontFace: F, fontSize: 12, color: C.slate, margin: 0, valign: "top", isTextBox: true });
    s.addText(src, { x: x + 0.25, y: y + 2.35, w: cw - 0.5, h: 0.5, fontFace: F, fontSize: 9, color: C.muted, margin: 0, valign: "top", isTextBox: true });
  });
  s.addText("멈춘 AGV는 사람이 걸어올 때까지 통로를 막는다 — 사고와 정지 비용이 같은 지점에서 생긴다.", { x: M, y: 4.85, w: W - 2 * M, h: 0.4,
    fontFace: F, fontSize: 13, bold: true, color: C.ink, margin: 0, isTextBox: true });
  addNotes(s, 2);
}

// ---------- 3. 보급형 AGV 3대 한계 ----------
{
  const s = pres.addSlide(); s.background = { color: C.white };
  title(s, "02 LIMITS", "보급형 AGV의 3대 한계");
  const cols = [
    ["01", "높이 사각지대", "2D LiDAR는 한 평면(Burger 바닥 약 0.17m)만 본다. 선반 돌출물·상체는 놓친다. 3D LiDAR는 중소 현장에 부담."],
    ["02", "자율 후진의 역설", "막혔다고 뒤를 못 보는 로봇이 스스로 물러나면 뒤쪽 보행자를 친다. 그래서 비상정지 후 통로가 막힌다."],
    ["03", "물리적 출동", "멈춘 로봇은 관리자가 현장까지 걸어가 조작해야 풀린다. 그동안 같은 통로의 흐름이 멈춘다."],
  ];
  const cw = (W - 2 * M - 2 * 0.3) / 3;
  cols.forEach(([n, head, txt], k) => {
    const x = M + k * (cw + 0.3), y = 1.65;
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: cw, h: 3.35, fill: { color: C.panel }, line: { color: C.panel } });
    s.addText(n, { x: x + 0.25, y: y + 0.25, w: 1.2, h: 0.6, fontFace: MONO, fontSize: 30, bold: true, color: C.line, margin: 0, isTextBox: true });
    s.addText(head, { x: x + 0.25, y: y + 0.95, w: cw - 0.5, h: 0.5, fontFace: F, fontSize: 20, bold: true, color: k === 1 ? C.red : C.ink, margin: 0, isTextBox: true });
    s.addText(txt, { x: x + 0.25, y: y + 1.55, w: cw - 0.5, h: 1.6, fontFace: F, fontSize: 12.5, color: C.slate, margin: 0, valign: "top", isTextBox: true });
  });
  addNotes(s, 3);
}

// ---------- 3. 접근 ----------
{
  const s = pres.addSlide(); s.background = { color: C.white };
  title(s, "03 SOLUTION", "솔루션: 정지 우선 + VR 원격 개입");
  const steps = [
    ["STOP", C.red, "위험하면 멈춘다", "LiDAR 전방 0.35m · 로봇 간 0.3m · 비전 검출 → 즉시 속도 0. 보이지 않는 뒤로 스스로 물러나지 않는다."],
    ["NOTIFY", C.slate, "원인·탈출 방향 표시", "정지 원인과 360° LiDAR로 계산한 탈출 경로를 카메라 화면·관제 지도·사이드바에 동시에 띄운다."],
    ["TAKE OVER", C.green, "사람이 VR로 빼낸다", "관제 맵 클릭 → 그 로봇 콕핏으로 즉시 전환(그 로봇만 MANUAL) → 그립 데드맨 + 양손 스틱으로 빼낸 뒤 AUTO 재개."],
  ];
  const cw = 2.75, gap = 0.37;
  steps.forEach(([tag, col, head, txt], k) => {
    const x = M + k * (cw + gap), y = 1.75;
    chip(s, tag, x, y, col);
    s.addText(head, { x, y: y + 0.45, w: cw, h: 0.5, fontFace: F, fontSize: 17, bold: true, color: C.ink, margin: 0, isTextBox: true });
    s.addText(txt, { x, y: y + 1.0, w: cw, h: 2.0, fontFace: F, fontSize: 12.5, color: C.slate, margin: 0, valign: "top", isTextBox: true });
    if (k < 2) s.addShape(pres.shapes.RIGHT_ARROW, { x: x + cw + 0.05, y: y + 0.55, w: 0.27, h: 0.3, fill: { color: C.line }, line: { color: C.line } });
  });
  addNotes(s, 4);
}

// ---------- 4. 구조 ----------
{
  const s = pres.addSlide(); s.background = { color: C.white };
  title(s, "04 ARCHITECTURE", "시스템 아키텍처");
  // fig_architecture_body.png: 1512×718 (tools/make_figures.py)
  const w = 8.8, h = w * 718 / 1512;
  s.addImage({ path: A("fig_architecture_body.png"), x: (W - w) / 2, y: 1.42, w, h, altText: "시스템 아키텍처: Unity, AI 릴레이, TurtleBot3" });
  addNotes(s, 5);
}

// ---------- 4. AI Agent 6요소 ----------
{
  const s = pres.addSlide(); s.background = { color: C.white };
  title(s, "05 AI AGENT", "AI Agent 6요소");
  // fig_agent_loop.png: 1512×781 (tools/make_figures.py)
  const fw = 4.6, fh = fw * 781 / 1512;
  s.addImage({ path: A("fig_agent_loop.png"), x: M, y: 1.55, w: fw, h: fh, altText: "AI Agent 루프: 인지, 추론, 계획, 실행, 피드백과 사람 개입" });
  s.addText("Goal → 인지 → 추론 → 계획 → 실행 → 피드백, 20 Hz 루프 + 사람 개입", { x: M, y: 1.55 + fh + 0.06, w: fw, h: 0.26,
    fontFace: F, fontSize: 9, color: C.muted, margin: 0, isTextBox: true });
  const rows = [
    ["Goal", "AGV 2대 협착·충돌 0건, 봉착 시 무사고 탈출"],
    ["Planning", "순찰 배회 → 위험 감지 → 인터록 정지 → 탈출 경로 산출 → 수동 개입"],
    ["Reasoning", "360° LiDAR 섹터 거리·로봇 폭 회랑 + YOLOv8 회랑 검출"],
    ["Tool Use", "ROS 2 /cmd_vel·/odom·/scan, ustreamer, WebSocket, Unity"],
    ["Memory", "AUTO/MANUAL, 정지 사유, 배회 원점, 운행 이력 로그"],
    ["Feedback", "영상 경로 띠·적색 배너, 3D 적색 차체·원판, 사이드바, 진동"],
  ].map((r, i) => r.map((t, c) => ({ text: t, options: c === 0
    ? { bold: true, color: C.white, fill: { color: i === 0 ? C.red : C.dark }, fontFace: MONO, fontSize: 10 }
    : { color: C.ink, fill: { color: i % 2 ? C.white : C.panel } } })));
  s.addTable(rows, { x: 5.3, y: 1.55, w: W - M - 5.3, colW: [1.05, W - M - 5.3 - 1.05], rowH: 0.52, fontFace: F, fontSize: 10.5,
    border: { type: "solid", color: C.line, pt: 0.75 }, valign: "middle" });
  addNotes(s, 6);
}

// ---------- 6. 탈출 경로 알고리즘 ----------
{
  const s = pres.addSlide(); s.background = { color: C.white };
  title(s, "06 ALGORITHM", "핵심 알고리즘", C.green);
  const steps = [
    ["1", "충돌 가드", "전방 0.35m 전진·후방 0.20m 후진 차단, 로봇 간 0.3m"],
    ["2", "탈출 방향", "5° 72방향, 로봇 폭 회랑 d(h), argmax[d − 0.25|h|]"],
    ["3", "궤적·선회 추천", "곡률 25개 원호 충돌 검사, 막히면 제자리 선회"],
    ["4", "VR 텔레옵", "그립 데드맨, 좌 선회·우 직진/후진, 방향 진동"],
  ];
  steps.forEach(([n, head, txt], k) => {
    const y = 1.5 + k * 0.78;
    s.addShape(pres.shapes.OVAL, { x: M, y, w: 0.36, h: 0.36, fill: { color: C.green }, line: { color: C.green } });
    s.addText(n, { x: M, y, w: 0.36, h: 0.36, fontFace: MONO, fontSize: 12, bold: true, color: C.white, align: "center", valign: "middle", margin: 0, isTextBox: true });
    s.addText(head, { x: M + 0.5, y: y - 0.04, w: 3.0, h: 0.3, fontFace: F, fontSize: 12.5, bold: true, color: C.ink, margin: 0, isTextBox: true });
    s.addText(txt, { x: M + 0.5, y: y + 0.27, w: 3.0, h: 0.42, fontFace: F, fontSize: 9.5, color: C.slate, margin: 0, valign: "top", isTextBox: true });
  });
  // fig_escape_planner.png: 실제 plan_escape 계산 결과 (tools/make_figures.py)
  const fw = 5.3, fh = fw * 7 / 16;
  s.addImage({ path: A("fig_escape_planner.png"), x: W - M - fw, y: 1.45, w: fw, h: fh, altText: "탈출 경로 알고리즘 계산 예" });
  s.addText("실제 plan_escape 계산 예 — 전방 상자·우측 벽 상황에서 좌 40° 선택", { x: W - M - fw, y: 1.45 + fh + 0.05, w: fw, h: 0.26,
    fontFace: F, fontSize: 9, color: C.muted, margin: 0, isTextBox: true });
  s.addText([
    { text: "관련 기법  ", options: { bold: true, color: C.ink } },
    { text: "VFH(Borenstein·Koren, 1991)·Follow-the-Gap(Sezer·Gokasan, 2012) 계열 국소 반응형. ", options: { color: C.slate } },
    { text: "영상 투영  ", options: { bold: true, color: C.ink } },
    { text: "추천 궤적·선회 방향을 핀홀 모델(렌즈 0.16m, 62.2°)로 카메라 화면 바닥에 그린다. 자동 후진 없음 — 결과는 사람에게 방향만 제시.", options: { color: C.slate } },
  ], { x: M, y: 4.62, w: W - 2 * M, h: 0.72, fontFace: F, fontSize: 10, margin: 0, valign: "top", isTextBox: true });
  addNotes(s, 7);
}

// ---------- 9. 검증 ----------
{
  const s = pres.addSlide(); s.background = { color: C.white };
  title(s, "07 RESULT", "정량 실증: Test Case 5종");
  const stats = [["78/78", "자동화 시험 통과", "가짜 rosbridge E2E"], ["2대", "실물 TurtleBot3", "ROS 1 + ROS 2 동시"], ["20 Hz", "제어·텔레메트리", "영상 15.7 fps 실측"]];
  stats.forEach(([big, label, sub], k) => {
    const x = M + k * 3.05;
    s.addText(big, { x, y: 1.4, w: 2.85, h: 0.6, fontFace: MONO, fontSize: 30, bold: true, color: k === 0 ? C.green : C.ink, margin: 0, isTextBox: true });
    s.addText(`${label} · ${sub}`, { x, y: 2.0, w: 2.85, h: 0.28, fontFace: F, fontSize: 10, color: C.slate, margin: 0, isTextBox: true });
  });
  const rows = [
    ["TC", "시나리오", "근거 (자동 시험 / 실물)", "결과"],
    ["TC-01", "전방 0.35m 전진 차단 + STOP 경고", "0.3m → STOP·reason, 전진 0 / 실물 차단 확인", "PASS"],
    ["TC-02", "타 AGV 0.3m 회피", "2대 AUTO 만남 → 둘 다 정지·비켜주기 (자동)", "PASS"],
    ["TC-03", "God-View ↔ VR 콕핏", "클릭 즉시 전환 / Quest 표출 확인", "PASS"],
    ["TC-04", "Quest·키보드 → 실물 바퀴", "0.15 m/s 제한·워치독 / Quest·WASD 구동", "PASS"],
    ["TC-05", "AUTO 봉착 정지 → 수동 후진 탈출", "STUCK·자동 재개 없음·입력 시 MANUAL", "PASS"],
  ].map((r, i) => r.map((t, c) => ({ text: t, options: i === 0 ? { bold: true, color: C.white, fill: { color: C.dark } }
    : { color: c === 3 ? C.green : C.ink, bold: c === 3 || c === 0 || undefined, fill: { color: i % 2 ? C.white : C.panel } } })));
  s.addTable(rows, { x: M, y: 2.5, w: W - 2 * M, colW: [0.8, 3.0, 4.4, 0.8], rowH: 0.42, fontFace: F, fontSize: 10.5, border: { type: "solid", color: C.line, pt: 0.75 }, valign: "middle" });
  addNotes(s, 8);
}

// ---------- 11. 피지컬 AI 차별성·산업 파급력 ----------
{
  const s = pres.addSlide(); s.background = { color: C.white };
  title(s, "08 IMPACT", "산업·경제적 기대효과");
  const block = (x, head, col, items) => {
    chip(s, head, x, 1.6, col);
    items.forEach(([h, t], k) => {
      const y = 2.05 + k * 1.05;
      s.addShape(pres.shapes.RECTANGLE, { x, y, w: 4.3, h: 0.9, fill: { color: C.panel }, line: { color: C.panel } });
      s.addText(h, { x: x + 0.2, y: y + 0.1, w: 3.9, h: 0.3, fontFace: F, fontSize: 13, bold: true, color: C.ink, margin: 0, isTextBox: true });
      s.addText(t, { x: x + 0.2, y: y + 0.42, w: 3.9, h: 0.42, fontFace: F, fontSize: 10.5, color: C.slate, margin: 0, valign: "top", isTextBox: true });
    });
  };
  block(M, "PHYSICAL AI", C.dark, [
    ["행동하는 AI", "답을 말하지 않고 바퀴를 움직이고 멈춘다. 판단 → /cmd_vel → 실물 반응."],
    ["정지 우선 안전 게이트", "모든 판단은 속도 상한·LiDAR 가드·워치독을 통과해야만 실물로 나간다."],
    ["사람-로봇 협업 개입", "막히면 사람을 부르고, 경로 근거를 화면에 그려 원격 판단을 돕는다."],
  ]);
  block(5.2, "INDUSTRY", C.green, [
    ["기존 AGV 개조형 확산", "2D LiDAR·카메라만 사용. 보급형 AGV에 소프트웨어로 붙인다."],
    ["1인 다대 원격 관제", "관제사가 지도로 여러 대를 보다 막힌 로봇에만 VR로 들어간다."],
    ["조선·항만·제조 현장 확장", "사람과 장비가 같은 동선을 쓰는 경남 주력 산업 현장에 맞춘다."],
  ]);
  addNotes(s, 9);
}

// ---------- 12. 한계·다음 단계 ----------
{
  const s = pres.addSlide(); s.background = { color: C.dark };
  chip(s, "09 CONCLUSION", M, 0.38, C.slate, { fill: C.dark, textColor: C.onDark });
  s.addText("결론 · 한계와 발전계획", { x: M, y: 0.72, w: W - 2 * M, h: 0.62, fontFace: F, fontSize: 26, bold: true, color: C.white, margin: 0, isTextBox: true });
  const col = (x, head, items) => {
    s.addText(head, { x, y: 1.6, w: 4.2, h: 0.36, fontFace: F, fontSize: 14, bold: true, color: C.white, margin: 0, isTextBox: true });
    s.addText(items.map((t, k) => ({ text: t, options: { bullet: true, breakLine: k < items.length - 1, paraSpaceAfter: 5 } })),
      { x, y: 2.05, w: 4.2, h: 1.7, fontFace: F, fontSize: 12, color: C.onDark, margin: 0, valign: "top", isTextBox: true });
  };
  col(M, "대회 기간 8일 성과", ["실물 2대(ROS 1·2) 원격 관제·VR 개입", "정지 우선 안전 게이트 + LiDAR 경로", "E2E 자동 시험 78항목 통과"]);
  col(5.3, "현장 적용 전 보완", ["비전 인터록 현장 검증·높이 사각 보완", "SLAM 위치 보정, 로봇 측 정지 감시", "정지 시간 단축 효과 현장 측정"]);
  s.addText("로봇은 멈추고 알리고, 판단은 사람이 화면 근거를 보고 내린다.", { x: M, y: 4.25, w: W - 2 * M, h: 0.5, fontFace: F, fontSize: 17,
    bold: true, color: C.white, margin: 0, isTextBox: true });
  s.addText("감사합니다 · 질의응답", { x: M, y: 4.8, w: 3, h: 0.35, fontFace: F, fontSize: 12, color: C.muted, margin: 0, isTextBox: true });
  addNotes(s, 10);
}

pres.writeFile({ fileName: OUT }).then(f => console.log("written", f, "notes", Object.keys(notes).length));
