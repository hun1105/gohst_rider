// PRESENTATION_PITCH.pptx — 대안 발표자료 (Pitch "Simple Sales Deck" 템플릿 느낌). 슬라이드 순서·대본은 PRESENTATION_10SLIDES.md와 동일.
// 디자인: 흰 캔버스, 아주 큰 검정 글자, 상단 "A × B / 날짜" 띠, 복숭아·라벤더 파스텔 원, 검정 기기 프레임 안의 화면.
// 발표 6단 구성: 문제 30초 · Agent 1분 · 구조 1분 · 실제 시연 2분 30초 · 성과 30초 · 발전계획·BM 30초.
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const DOCS = process.argv[2];
const OUT = path.join(DOCS, "PRESENTATION_PITCH.pptx");
const A = f => path.join(DOCS, "assets", f);

const C = {
  white: "FFFFFF", ink: "111111", gray: "6B6B6B", mute: "9A9A9A", line: "E6E6E6", soft: "F5F5F7",
  peach: "FFB27A", peachSoft: "FFE3CF", lav: "B7B4E4", lavSoft: "E7E5F7", device: "1C1C1E",
};
const FONT = "Pretendard";
const W = 10, H = 5.625, M = 0.55, TOTAL = 10, GAP = 0.18;

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.title = "멈추고, 알리고, 사람이 빼낸다 — Pitch style";

const notes = {};
fs.readFileSync(path.join(DOCS, "PRESENTATION_10SLIDES.md"), "utf8").replace(/\r/g, "")
  .split("### [Slide ").slice(1).forEach(block => {
    const n = parseInt(block, 10);
    const m = block.match(/\*\*대본[^*]*\*\*:\s*"([\s\S]*?)"\s*$/m);
    if (m) notes[n] = m[1];
  });

// ---------- 부품 ----------
function t(s, text, x, y, w, h, o = {}) {
  s.addText(text, { x, y, w, h, fontFace: FONT, fontSize: o.size || 12, color: o.color || C.ink, bold: o.bold || false,
    align: o.align || "left", valign: o.valign || "top", charSpacing: o.cs || 0, lineSpacingMultiple: o.lh || 1.15,
    margin: 0, isTextBox: true });
}
function circle(s, x, y, d, color) {
  s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color }, line: { color, width: 0 } });
}
function box(s, x, y, w, h, color, o = {}) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: o.r || 0.14, fill: { color },
    line: { color: o.border || color, width: o.border ? 0.75 : 0 } });
}
function device(s, file, x, y, w, pxW, pxH, alt) {   // 검정 기기 프레임 안 화면
  const pad = 0.07, iw = w - 2 * pad, ih = iw * pxH / pxW;
  box(s, x, y, w, ih + 2 * pad, C.device, { r: 0.16 });
  s.addImage({ path: A(file), x: x + pad, y: y + pad, w: iw, h: ih, altText: alt });
  return ih + 2 * pad;
}
function slide(n, section, time) {
  const s = pres.addSlide();
  s.background = { color: C.white };
  t(s, "[팀명] × 경남 AI·SW 경진대회 2026", M, 0.32, 5, 0.25, { size: 10.5, cs: 0.5, valign: "middle" });
  t(s, "2026. 10", W - M - 2, 0.32, 2, 0.25, { size: 10.5, align: "right", valign: "middle" });
  if (section) {
    t(s, section, M, 0.72, 6, 0.22, { size: 9, color: C.gray, cs: 1.5, valign: "middle" });
    t(s, time, W - M - 1.5, 0.72, 1.5, 0.22, { size: 9, color: C.gray, align: "right", valign: "middle" });
  }
  t(s, String(n).padStart(2, "0") + " / " + TOTAL, W - M - 1, H - 0.38, 1, 0.2, { size: 8, color: C.mute, align: "right" });
  if (notes[n]) s.addNotes(notes[n]);
  return s;
}
const title = (s, text, y = 1.0, size = 30, w = W - 2 * M) => text.includes("\n")
  ? t(s, text, M, 1.08, w, 1.2, { size, bold: true, cs: -1, lh: 1.05 })
  : t(s, text, M, y, w, 0.75, { size, bold: true, cs: -1, valign: "middle" });
const cols = (n, total = W - 2 * M) => (total - (n - 1) * GAP) / n;

// ---------- 1. 표지 ----------
{
  const s = slide(1);
  circle(s, 4.6, 0.75, 2.9, C.peach);
  circle(s, 7.0, 2.9, 3.4, C.lav);
  device(s, "overlay_stop_path.jpg", 4.95, 1.25, 3.0, 640, 480, "VR 콕핏 화면");
  device(s, "topdown_warning_on.png", 7.55, 2.45, 1.9, 720, 720, "관제 맵");
  t(s, "멈추고,\n알리고,\n사람이 빼낸다.", M, 2.2, 4.4, 2.6, { size: 40, bold: true, cs: -2, lh: 1.0, valign: "bottom" });
  t(s, "MetaQuest VR 기반 피지컬 AI AGV\n원격 개입 & 협착 방지 디지털 트윈", M, 1.0, 4.1, 0.6, { size: 11, color: C.gray });
  t(s, "국립한국해양대학교 · [발표자] · 대학부 32", M, 4.95, 4.4, 0.25, { size: 10, color: C.gray });
}

// ---------- 2. 문제 ----------
{
  const s = slide(2, "01  PROBLEM — 누구의 어떤 문제", "0:30");
  title(s, "AGV와 같은 통로를 쓰는 사람들");
  const who = [["현장 작업자", "부딪히고 끼인다"], ["관제사·관리자", "멈출 때마다 출동"], ["공장", "통로가 막히면 라인이 선다"]];
  who.forEach(([k, v], i) => {
    const y = 1.95 + i * 0.62;
    circle(s, M, y + 0.06, 0.32, i === 1 ? C.peach : C.lav);
    t(s, k, M + 0.48, y, 2.4, 0.24, { size: 12.5, bold: true });
    t(s, v, M + 0.48, y + 0.26, 2.4, 0.22, { size: 10, color: C.gray });
  });
  const rx = 3.45, cw = cols(3, W - M - rx);
  const stats = [["53%", "로봇 재해 중 끼임", "KOSHA 2011–2020", C.peachSoft], ["66명", "2024 끼임 사망 +22.2%", "고용노동부", C.lavSoft], ["$2.3M", "자동차 라인 시간당 정지 비용 최대", "Siemens 2024", C.soft]];
  stats.forEach(([big, lab, src, col], i) => {
    const x = rx + i * (cw + GAP);
    box(s, x, 1.9, cw, 2.0, col);
    t(s, big, x + 0.2, 2.05, cw - 0.4, 0.7, { size: 30, bold: true, cs: -1.5, valign: "middle" });
    t(s, lab, x + 0.2, 2.85, cw - 0.4, 0.5, { size: 10 });
    t(s, src, x + 0.2, 3.5, cw - 0.4, 0.2, { size: 7.5, color: C.gray });
  });
  t(s, "보급형 AGV는  ① 한 평면만 보고   ② 뒤를 못 봐 스스로 못 물러나고   ③ 멈추면 사람이 걸어가야 풀린다.", M, 4.35, W - 2 * M, 0.4, { size: 12.5, bold: true, valign: "middle" });
}

// ---------- 3. Agent ----------
{
  const s = slide(3, "02  AGENT — 목표 · 역할 · 핵심기능", "1:00");
  title(s, "판단은 로봇이,\n결정은 사람이.", 1.0, 28, 3.6);
  t(s, "목표 — AGV 2대 운용 중 협착·충돌 0건,\n막히면 출동 없이 원격 탈출.", M, 2.35, 3.4, 0.6, { size: 11, color: C.gray });
  box(s, M, 3.1, 3.25, 1.75, C.soft);
  t(s, "AGENT", M + 0.2, 3.23, 1.4, 0.2, { size: 8, color: C.gray, cs: 1.5 });
  t(s, "감시 · 정지 · 원인 · 경로 추천", M + 0.2, 3.45, 2.9, 0.3, { size: 12, bold: true });
  t(s, "HUMAN", M + 0.2, 3.87, 1.4, 0.2, { size: 8, color: C.gray, cs: 1.5 });
  t(s, "로봇 선택 · VR 조종 · 재개 승인", M + 0.2, 4.09, 2.9, 0.3, { size: 12, bold: true });
  t(s, "자동 후진 · 자동 재개 없음", M + 0.2, 4.5, 2.9, 0.22, { size: 9.5, color: C.gray });
  const rx = 4.15, cw = cols(2, W - M - rx), ch = 1.62;
  const feats = [
    ["01", "즉시 멈춘다", "전방 0.35m · AGV 간 0.3m → 전진 지령 0. 후진은 후방 0.20m 가드.", C.peach],
    ["02", "경로를 그린다", "LiDAR 72방향 탈출 경로를 영상 바닥·관제 맵에, 돌 쪽 손 진동.", C.lav],
    ["03", "클릭 한 번에 VR", "관제 맵 클릭 → 그 로봇 콕핏, 그 로봇만 MANUAL, 그립 데드맨.", C.lav],
    ["04", "2대 AUTO", "각자 직진 순찰, 0.3m 안에서 만나면 둘 다 정지.", C.peach],
  ];
  feats.forEach(([n, h, d, col], i) => {
    const x = rx + (i % 2) * (cw + GAP), y = 1.0 + Math.floor(i / 2) * (ch + GAP);
    box(s, x, y, cw, ch, C.white, { border: C.line });
    circle(s, x + 0.2, y + 0.2, 0.42, col);
    t(s, n, x + 0.2, y + 0.2, 0.42, 0.42, { size: 10, bold: true, align: "center", valign: "middle" });
    t(s, h, x + 0.75, y + 0.24, cw - 0.9, 0.35, { size: 14, bold: true, valign: "middle" });
    t(s, d, x + 0.2, y + 0.78, cw - 0.4, 0.75, { size: 9.5, color: C.gray });
  });
}

// ---------- 4. Workflow ----------
{
  const s = slide(4, "03  ARCHITECTURE — WORKFLOW", "0:30");
  title(s, "순찰 → 정지 → 경로 → 개입 → 재개");
  const steps = [["AUTO 순찰", "R 키 · 2대 직진"], ["위험 감지", "LiDAR · odom 20 Hz"], ["정지 게이트", "전진 0 · 원인 기록"], ["탈출 경로", "72방향 · 영상 투영"], ["VR 개입", "클릭 · 콕핏 · 데드맨"], ["AUTO 재개", "사람이 R"]];
  const cw = cols(6), y = 2.0;
  s.addShape(pres.shapes.LINE, { x: M + cw / 2, y: y + 0.3, w: W - 2 * M - cw, h: 0, line: { color: C.line, width: 1.5 } });
  steps.forEach(([h, d], i) => {
    const x = M + i * (cw + GAP), human = i >= 4;
    circle(s, x + cw / 2 - 0.3, y, 0.6, human ? C.lav : C.peach);
    t(s, String(i + 1), x + cw / 2 - 0.3, y, 0.6, 0.6, { size: 14, bold: true, align: "center", valign: "middle" });
    t(s, h, x, y + 0.75, cw, 0.3, { size: 12.5, bold: true, align: "center" });
    t(s, d, x, y + 1.08, cw, 0.4, { size: 9, color: C.gray, align: "center" });
  });
  circle(s, M, 3.72, 0.16, C.peach); t(s, "Agent", M + 0.24, 3.68, 1, 0.22, { size: 9, color: C.gray, valign: "middle" });
  circle(s, M + 1.1, 3.72, 0.16, C.lav); t(s, "사람", M + 1.34, 3.68, 1, 0.22, { size: 9, color: C.gray, valign: "middle" });
  box(s, M, 4.05, W - 2 * M, 0.85, C.soft);
  t(s, "조건  전방 < 0.35m 또는 AGV 간 < 0.3m → 전진 차단     방법  72방향 회랑 여유 d(h), J = d − 0.25·|h| 최대     결과  영상 바닥 경로 띠 · 조작은 사람",
    M + 0.25, 4.05, W - 2 * M - 0.5, 0.85, { size: 10, valign: "middle" });
}

// ---------- 5. AI · Tool · Data · Memory ----------
{
  const s = slide(5, "03  ARCHITECTURE — AI · TOOL · DATA · MEMORY", "0:30");
  title(s, "로봇 두 대, 릴레이 하나, 화면 둘");
  circle(s, -0.6, 3.2, 2.6, C.peachSoft);
  const fw = 5.0, fh = fw * 718 / 1512;
  box(s, M, 1.9, fw + 0.24, fh + 0.24, C.white, { border: C.line });
  s.addImage({ path: A("fig_architecture_body.png"), x: M + 0.12, y: 2.02, w: fw, h: fh, altText: "시스템 아키텍처" });
  t(s, "안전 게이트를 통과한 속도만 /cmd_vel로 · 20 Hz", M, 1.9 + fh + 0.34, fw, 0.2, { size: 8.5, color: C.gray });
  const items = [["AI", "LiDAR 기하 추론 · 곡률 궤적 · LLM 미사용"], ["Tool", "ROS /cmd_vel · /odom · /scan · 카메라 · Unity · Quest 2"], ["Data", "실시간 LiDAR 360° · 휠 odom · 640×480 영상"], ["Memory", "로봇별 모드 · 정지 원인 · 운행 이력 JSONL"]];
  const rx = 6.2, rw = W - M - rx;
  items.forEach(([k, v], i) => {
    const y = 1.9 + i * 0.68;
    t(s, k, rx, y, rw, 0.26, { size: 14, bold: true });
    t(s, v, rx, y + 0.28, rw, 0.32, { size: 9.5, color: C.gray });
    if (i < items.length - 1) s.addShape(pres.shapes.LINE, { x: rx, y: y + 0.62, w: rw, h: 0, line: { color: C.line, width: 0.75 } });
  });
}

// ---------- 6. 실제 시연 ① ----------
{
  const s = slide(6, "04  LIVE DEMO — 입력 → 판단 → TOOL → 결과", "2:30");
  title(s, "실물 2대로 보여드리는 한 바퀴");
  const head = ["", "입력", "판단 (Agent)", "Tool 호출", "결과"];
  const rows = [
    ["자율 순찰", "관제 PC  R", "로봇 간 0.3m · 전방 0.35m 감시", "/cmd_vel 0.10 m/s", "2대 주행 → 접근 시 둘 다 정지"],
    ["정지·알림", "작업자 진입", "전방 0.35m 안 → 전진 차단", "/cmd_vel 0 · STOP", "지도 적색 · 원인 · 경로 띠"],
    ["VR 개입", "관제 맵 클릭", "그 로봇만 MANUAL · 탈출 방향", "Quest 콕핏 · 손 진동", "그립 + 스틱으로 탈출"],
    ["안전장치", "그립 놓기 · 과속", "데드맨 · 0.15 m/s · 워치독 0.5s", "/cmd_vel 0 또는 제한", "즉시 정지 · 속도 제한"],
    ["재개", "관제 PC  R", "사람 승인 시에만 AUTO", "/cmd_vel 0.10 m/s", "순찰 복귀"],
  ];
  const cw = [1.55, 1.35, 2.3, 1.75, 1.95], y0 = 1.85, rh = 0.5;
  let x = M;
  head.forEach((h, i) => { t(s, h, x, y0, cw[i], 0.25, { size: 8.5, color: C.gray, cs: 1 }); x += cw[i]; });
  rows.forEach((r, ri) => {
    const y = y0 + 0.32 + ri * rh;
    if (ri % 2 === 0) box(s, M - 0.1, y - 0.02, W - 2 * M + 0.2, rh - 0.04, C.soft, { r: 0.1 });
    let cx = M;
    r.forEach((c, ci) => {
      if (ci === 0) { circle(s, cx, y + 0.13, 0.2, ri === 2 ? C.lav : C.peach); t(s, c, cx + 0.3, y, cw[0] - 0.3, rh - 0.04, { size: 11, bold: true, valign: "middle" }); }
      else t(s, c, cx, y, cw[ci] - 0.1, rh - 0.04, { size: 9.5, color: ci === 4 ? C.ink : C.gray, bold: ci === 4, valign: "middle" });
      cx += cw[ci];
    });
  });
  t(s, "화면 4분할: 관제 맵 · Quest 콕핏 · 릴레이 터미널 · 실물 캠  —  라이브 불가 시 시연 영상으로 대체", M, 4.85, W - 2 * M, 0.2, { size: 8, color: C.gray });
}

// ---------- 7. 실제 시연 ② ----------
{
  const s = slide(7, "04  LIVE DEMO — 화면 근거", "2:30");
  title(s, "멈춘 이유와\n빠져나갈 길이 보인다.", 1.0, 26, 3.6);
  circle(s, 4.3, 1.0, 2.7, C.peach);
  circle(s, 7.4, 2.6, 2.9, C.lav);
  device(s, "overlay_stop_path.jpg", 4.55, 1.35, 2.9, 640, 480, "콕핏 화면");
  device(s, "topdown_warning_on.png", 7.75, 1.95, 1.75, 720, 720, "관제 맵");
  const caps = [["COCKPIT", "영상 바닥 경로 띠 · 선회 화살표 · 정지 배너"], ["GOD-VIEW", "적색 차체 · 위험 원판 · 사이드바 정지 원인"], ["TERMINAL", "[AUTO] STUCK · [INTERLOCK] = 판단 → Tool 기록"]];
  caps.forEach(([k, v], i) => {
    const y = 2.6 + i * 0.6;
    t(s, k, M, y, 3.5, 0.2, { size: 8, color: C.gray, cs: 1.5 });
    t(s, v, M, y + 0.22, 3.6, 0.3, { size: 10.5 });
  });
  t(s, "실제 출력 예시 · 발표 당일 라이브 화면이 우선", 4.55, 4.85, 4.9, 0.2, { size: 8, color: C.gray });
}

// ---------- 8. 성과 ----------
{
  const s = slide(8, "05  IMPACT — BEFORE / AFTER · 검증 · 효과", "0:30");
  title(s, "멈춤은 같아도, 푸는 방법이 바뀐다");
  const bw = 2.6;
  box(s, M, 1.9, bw, 2.0, C.soft);
  t(s, "BEFORE", M + 0.2, 2.02, bw - 0.4, 0.2, { size: 8, color: C.gray, cs: 1.5 });
  t(s, "비상정지 → 통로 마비\n관리자 현장 출동\n정지 이유 기록 없음", M + 0.2, 2.32, bw - 0.4, 1.4, { size: 11.5, lh: 1.5, color: C.gray });
  box(s, M + bw + GAP, 1.9, bw, 2.0, C.peachSoft);
  t(s, "AFTER", M + bw + GAP + 0.2, 2.02, bw - 0.4, 0.2, { size: 8, color: C.ink, cs: 1.5 });
  t(s, "전진만 차단\n관제석에서 VR로 탈출\n원인·경로가 로그에 남음", M + bw + GAP + 0.2, 2.32, bw - 0.4, 1.4, { size: 11.5, lh: 1.5, bold: true });
  const rx = M + 2 * bw + 2 * GAP + 0.15, rw = W - M - rx;
  [["78/78", "E2E 자동 시험"], ["10회", "반복 무결점"], ["0건", "300초 부하 안전 위반"]].forEach(([big, lab], i) => {
    const y = 1.9 + i * 0.68;
    t(s, big, rx, y, 1.5, 0.5, { size: 24, bold: true, cs: -1, valign: "middle" });
    t(s, lab, rx + 1.55, y, rw - 1.55, 0.5, { size: 10, color: C.gray, valign: "middle" });
  });
  box(s, M, 4.1, W - 2 * M, 0.78, C.lavSoft);
  t(s, "사용자 검증 — 팀원이 관제사·VR 조작자 역할로 실물 TB1·TB2 확인. 외부 사용자 평가와 현장 정지 시간(MTBI) 측정은 다음 단계.",
    M + 0.25, 4.1, W - 2 * M - 0.5, 0.78, { size: 10.5, valign: "middle" });
}

// ---------- 9. 한계 · 보완 ----------
{
  const s = slide(9, "06  NEXT — 한계 · 현장 적용 전 보완점", "0:30");
  title(s, "현장에 들이기 전에 고칠 것");
  const rows = [
    ["높이 사각", "2D LiDAR 바닥 약 0.17m 한 평면", "깊이 카메라 융합"],
    ["위치 누적 오차", "휠 odom 누적 → 시작 위치 재설정", "SLAM 위치 보정"],
    ["통신 두절", "ROS 1 로봇 정지 동작이 펌웨어 의존", "로봇 측 정지 감시 노드"],
    ["보안", "rosbridge 인증 없음 → 망 분리", "인증 · 암호화"],
    ["효과 실측", "정지 시간(MTBI) 현장 측정 전", "파일럿 라인 계측"],
  ];
  rows.forEach(([a, b, c], i) => {
    const y = 1.9 + i * 0.6;
    circle(s, M, y + 0.15, 0.22, i % 2 ? C.lav : C.peach);
    t(s, a, M + 0.4, y, 2.0, 0.52, { size: 12.5, bold: true, valign: "middle" });
    t(s, b, M + 2.5, y, 3.6, 0.52, { size: 10.5, color: C.gray, valign: "middle" });
    t(s, "→  " + c, M + 6.2, y, 2.7, 0.52, { size: 11, bold: true, valign: "middle" });
    if (i < rows.length - 1) s.addShape(pres.shapes.LINE, { x: M, y: y + 0.56, w: W - 2 * M, h: 0, line: { color: C.line, width: 0.75 } });
  });
}

// ---------- 10. 기대효과 · BM · 결론 ----------
{
  const s = slide(10, "06  NEXT — 기대효과 · 비즈니스모델", "0:30");
  title(s, "기존 AGV에 얹는 안전 개입 레이어");
  const bm = [["개조 패키지", "기존 2D LiDAR AGV에 릴레이 + 관제·VR SW. 기체 교체 없음.", C.peachSoft], ["관제 구독", "로봇 대수 기준 SW 구독, 정지 원인 리포트.", C.lavSoft], ["원격 개입 센터", "여러 현장의 멈춘 로봇을 한 관제석에서 복구.", C.soft]];
  const cw = cols(3);
  bm.forEach(([k, v, col], i) => {
    const x = M + i * (cw + GAP);
    box(s, x, 1.85, cw, 1.35, col);
    t(s, k, x + 0.2, 1.98, cw - 0.4, 0.3, { size: 13, bold: true });
    t(s, v, x + 0.2, 2.35, cw - 0.4, 0.75, { size: 9.5, color: C.gray });
  });
  t(s, "구상 단계 · 가격·매출 수치는 파일럿 이후 산정  |  시장: AGV·AMR 2030년 $22B (LogisticsIQ 2024)", M, 3.3, W - 2 * M, 0.22, { size: 8.5, color: C.gray });
  t(s, "로봇은 멈추고 알리고,\n판단은 사람이 내린다.", M, 3.65, 6.5, 1.2, { size: 28, bold: true, cs: -1, lh: 1.05, valign: "middle" });
  circle(s, 7.3, 3.45, 1.3, C.peach);
  circle(s, 8.05, 3.85, 1.1, C.lav);
}

pres.writeFile({ fileName: OUT }).then(f => console.log("written", f, "notes", Object.keys(notes).length));
