// PANEL_B4.pptx (+ PNG) — <별지 4> 개발완료보고서 "판넬형 보고서" (이미지 제출용, 세로 1장).
// 양식 참고: 운영규정 03-1 <별지 4>의 판넬형 예시 2종 (머리띠 → 프로젝트 개요 → 개발 세부 내용(3단계 + 시스템 구조도) → 구현 결과 → 기대 효과 → 바닥띠).
// 시스템 구조도는 예시의 5칸 흐름(입력 데이터 → 수집 서버 → AI 분석 모듈 → 위험도 판단 → 알림 대상)을 우리 파이프라인에 그대로 대응시킴.
// 내용 원천: REPORT_5P.md (수치는 실측·자동 시험 기록만, 운영규정 제31조).
const path = require("path");
const pptxgen = require("pptxgenjs");

const DOCS = process.argv[2];
const OUT = path.join(DOCS, "PANEL_B4.pptx");
const A = f => path.join(DOCS, "assets", f);

const W = 12, H = 17, M = 0.45;
const F = "Pretendard", SYM = "Segoe UI Symbol";
const C = {
  page: "EEF3FA", navy: "0B1E4A", navy2: "13306E", blue: "2563EB", blueSoft: "E8F0FE", sky: "93C5FD", line: "D6E2F3",
  ink: "111827", sub: "4B5563", white: "FFFFFF", arrow: "7BA7E8",
  purple: "7C3AED", purpleSoft: "F1EAFE", green: "16A34A", greenSoft: "E6F6EC",
  red: "E53935", redSoft: "FDECEC", amber: "F59E0B", amberSoft: "FEF3DC", ok: "22C55E", okSoft: "E7F8EE",
};

const pres = new pptxgen();
pres.defineLayout({ name: "PANEL", width: W, height: H });
pres.layout = "PANEL";
pres.title = "개발완료보고서(판넬형) — AGV 협착 방지 VR 원격 개입 AI Agent";
const s = pres.addSlide();
s.background = { color: C.page };

function t(text, x, y, w, h, o = {}) {
  s.addText(text, { x, y, w, h, fontFace: o.font || F, fontSize: o.size || 12, color: o.color || C.ink, bold: o.bold || false,
    italic: o.italic || false, align: o.align || "left", valign: o.valign || "top", lineSpacingMultiple: o.lh || 1.25,
    charSpacing: o.cs || 0, margin: 0, isTextBox: true });
}
function rr(x, y, w, h, fill, o = {}) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: o.r ?? 0.12,
    fill: { color: fill, transparency: o.tr || 0 }, line: { color: o.border || fill, width: o.border ? (o.bw || 0.75) : 0, transparency: o.btr || 0 } });
}
function circleNum(n, x, y, d, color) {
  s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color }, line: { color, width: 0 } });
  t(String(n), x, y, d, d, { size: d * 30, bold: true, color: C.white, align: "center", valign: "middle", lh: 1 });
}
function sectionHead(x, y, glyph, title, subtitle) {
  rr(x, y, 0.5, 0.5, C.navy2, { r: 0.08 });
  t(glyph, x, y, 0.5, 0.5, { size: 20, bold: true, color: C.white, align: "center", valign: "middle", lh: 1 });
  t(title, x + 0.65, y, 3.2, 0.5, { size: 24, bold: true, valign: "middle", lh: 1 });
  if (subtitle) t(subtitle, x + 0.65 + title.length * 0.27 + 0.2, y + 0.02, 7, 0.5, { size: 14, color: C.sub, valign: "middle", lh: 1 });
}
function arrow(x, y) {
  s.addShape(pres.shapes.RIGHT_ARROW, { x, y, w: 0.18, h: 0.2, fill: { color: C.arrow }, line: { color: C.arrow, width: 0 } });
}

// ================= 머리띠 =================
s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: W, h: 3.9, fill: { color: C.navy }, line: { color: C.navy, width: 0 } });
s.addShape(pres.shapes.OVAL, { x: 6.4, y: -2.2, w: 7.5, h: 7.5, fill: { color: C.blue, transparency: 82 }, line: { color: C.blue, width: 0 } });
s.addShape(pres.shapes.OVAL, { x: 8.6, y: 0.9, w: 5.0, h: 5.0, fill: { color: C.sky, transparency: 88 }, line: { color: C.sky, width: 0 } });
t("제4회 경남 AI·SW 경진대회 2026", M + 0.15, 0.42, 4.6, 0.4, { size: 17, bold: true, color: C.sky, valign: "middle", lh: 1 });
rr(M + 4.55, 0.46, 1.15, 0.33, C.sky, { r: 0.16 });
t("AI Agent", M + 4.55, 0.46, 1.15, 0.33, { size: 12, bold: true, color: C.navy, align: "center", valign: "middle", lh: 1 });
t("MetaQuest VR 기반 피지컬 AI AGV\n원격 개입 & 협착 방지 디지털 트윈", M + 0.15, 0.95, 7.75, 1.6,
  { size: 33, bold: true, color: C.white, valign: "middle", cs: -1, lh: 1.15 });
t("2D LiDAR로 위험을 판단해 스스로 멈추고, 정지 원인과 탈출 경로를 알린 뒤\n관제사가 VR로 들어가 직접 빼내는 피지컬 AI 에이전트", M + 0.15, 2.7, 7.6, 0.7, { size: 15, color: "DCE6F5", lh: 1.35 });
t([{ text: "팀명", options: { color: C.sky, bold: true } }, { text: "  |  [팀명]        ", options: { color: C.white } },
   { text: "팀원", options: { color: C.sky, bold: true } }, { text: "  |  [팀장명]  [팀원명]  [팀원명]", options: { color: C.white } }],
  M + 0.15, 3.42, 7.6, 0.35, { size: 14, valign: "middle", lh: 1 });
// 오른쪽: 떠 있는 상태 카드 (예시의 "Your AI Business Partner" 카드 대응)
rr(8.35, 0.5, 3.2, 2.35, C.navy2, { tr: 15, border: "60A5FA", bw: 1, r: 0.15 });
t("현장의 AI 안전 파트너", 8.6, 0.65, 2.8, 0.35, { size: 14, bold: true, color: C.white, valign: "middle", lh: 1 });
["위험 감지 (LiDAR 360°)", "즉시 정지 (전진 차단)", "탈출 경로 표시", "VR 원격 개입"].forEach((v, i) => {
  const y = 1.12 + i * 0.41;
  s.addShape(pres.shapes.OVAL, { x: 8.62, y: y + 0.04, w: 0.26, h: 0.26, fill: { color: C.blue }, line: { color: C.sky, width: 0.75 } });
  t("✓", 8.62, y + 0.04, 0.26, 0.26, { font: SYM, size: 10, bold: true, color: C.white, align: "center", valign: "middle", lh: 1 });
  t(v, 9.0, y, 2.5, 0.34, { size: 12, color: C.white, valign: "middle", lh: 1 });
});
t("“ 멈추고, 알리고,\n사람이 빼낸다 ”", 8.35, 3.0, 3.2, 0.8, { size: 17, italic: true, bold: true, color: C.sky, align: "right", lh: 1.2 });

// ================= 1. 프로젝트 개요 =================
let y0 = 4.05;
rr(M, y0, W - 2 * M, 2.7, C.white, { border: C.line });
sectionHead(M + 0.25, y0 + 0.2, "1", "프로젝트 개요", "(개발배경, 목표 시스템 등)");
const ov = [
  "사람과 AGV가 같은 통로를 쓰는 현장에서 사고는 끼임·부딪힘에 몰린다. 산업용 로봇 재해의 53%가 끼임, 34%가 부딪힘이다.",
  "보급형 AGV는 2D LiDAR 한 평면만 보고 뒤를 못 봐, 막히면 비상정지 후 관리자가 현장까지 걸어가야 풀린다.",
  "본 프로젝트는 LiDAR로 위험을 판단해 즉시 멈추고, 원인과 탈출 경로를 알린 뒤, 관제사가 VR로 원격 탈출시키는 AI Agent를 목표로 함.",
  "실물 TurtleBot3 2대(ROS 1·ROS 2)와 Unity 관제 맵·Meta Quest 2 콕핏까지 동작하는 MVP를 완성함.",
];
ov.forEach((v, i) => {
  const y = y0 + 0.88 + i * 0.44;
  circleNum(i + 1, M + 0.3, y + 0.02, 0.32, C.navy2);
  t(v, M + 0.8, y, 7.35, 0.42, { size: 11.5, valign: "middle", lh: 1.2 });
});
rr(8.75, y0 + 0.25, 2.55, 2.2, C.blueSoft, { r: 0.12 });
t("“ 현장에 가지 않아도,\n멈춘 로봇을\n빼낼 수 있다 ”", 8.85, y0 + 0.4, 2.35, 1.05, { size: 14, bold: true, color: C.navy2, align: "center", lh: 1.3 });
s.addShape(pres.shapes.LINE, { x: 9.6, y: y0 + 1.7, w: 0.85, h: 0, line: { color: C.navy2, width: 1.25 } });
t("관제석에서 클릭 한 번,\nVR로 바로 복구", 8.85, y0 + 1.92, 2.35, 0.45, { size: 10.5, color: C.blue, align: "center", lh: 1.25 });

// ================= 2. 개발 세부 내용 =================
y0 = 6.9;
rr(M, y0, W - 2 * M, 4.9, C.white, { border: C.line });
sectionHead(M + 0.25, y0 + 0.2, "2", "개발 세부 내용", "|  시스템 구조 / 활용 데이터 / AI 알고리즘 / 3단계 개발 내용");
const stages = [
  ["1단계: 감지", "LiDAR 360° 스캔, 휠 오도메트리, 카메라 영상을 20 Hz 고정 주기로 수집", C.blue, C.blueSoft],
  ["2단계: 판단", "전방 0.35m · AGV 간 0.3m 정지 게이트, LiDAR 72방향 탈출 경로 계산", C.purple, C.purpleSoft],
  ["3단계: 알림 및 개입", "관제 맵 적색 경고 → 클릭 → VR 콕핏에서 원격 탈출 → AUTO 재개", C.green, C.greenSoft],
];
stages.forEach(([h, d, col, soft], i) => {
  const y = y0 + 0.9 + i * 1.2;
  rr(M + 0.25, y, 3.55, 1.08, soft, { r: 0.1 });
  circleNum(i + 1, M + 0.38, y + 0.27, 0.52, col);
  t(h, M + 1.05, y + 0.1, 2.7, 0.36, { size: 14.5, bold: true, color: col, valign: "middle", lh: 1 });
  t(d, M + 1.05, y + 0.48, 2.65, 0.55, { size: 10, color: C.sub, lh: 1.25 });
});
// --- 시스템 구조도 (예시의 5칸 흐름) ---
const sx = M + 4.0, sw = W - M - 0.25 - sx;
rr(sx, y0 + 0.82, 1.5, 0.36, C.navy2, { r: 0.18 });
t("시스템 구조도", sx, y0 + 0.82, 1.5, 0.36, { size: 12, bold: true, color: C.white, align: "center", valign: "middle", lh: 1 });
const bw = (sw - 4 * 0.24) / 5, by = y0 + 1.3, bh = 2.5;
const cols = [
  { title: "센서 / 입력\n데이터", list: [[null, "LiDAR 360°"], [null, "휠 odom"], [null, "Pi 카메라"], [null, "Quest 입력"], [null, "관제 클릭"]] },
  { title: "AI 릴레이\n서버", icon: "02", bullets: ["rosbridge 연동", "ROS 1·2 통합", "20 Hz 고정 주기", "통신 두절 감시"] },
  { title: "AI 판단\n모듈", icon: "03", bullets: ["LiDAR 섹터 거리", "72방향 탈출 경로", "곡률 궤적 추천", "AGV 간 거리"] },
  { title: "안전 게이트 /\n위험도 판단", icon: "04", levels: [["정지", C.red, C.redSoft], ["주의", C.amber, C.amberSoft], ["주행", C.ok, C.okSoft]] },
  { title: "관제사 / VR /\n로봇", icon: "05", bullets: ["관제 맵 경고", "정지 원인 표시", "VR 콕핏 전환", "손 방향 진동", "/cmd_vel 지령"] },
];
cols.forEach((c, i) => {
  const x = sx + i * (bw + 0.24);
  rr(x, by, bw, bh, C.white, { border: C.line, r: 0.08 });
  t(c.title, x + 0.05, by + 0.08, bw - 0.1, 0.5, { size: 10.5, bold: true, color: C.navy2, align: "center", valign: "middle", lh: 1.15 });
  if (c.list) {
    c.list.forEach(([ic, v], k) => {
      const yy = by + 0.68 + k * 0.35;
      s.addShape(pres.shapes.RECTANGLE, { x: x + 0.16, y: yy + 0.12, w: 0.07, h: 0.07, fill: { color: C.navy2 }, line: { color: C.navy2, width: 0 } });
      t(v, x + 0.34, yy, bw - 0.4, 0.3, { size: 9.5, valign: "middle", lh: 1 });
    });
  } else {
    t(c.icon, x, by + 0.62, bw, 0.45, { size: 22, bold: true, color: C.sky, align: "center", valign: "middle", lh: 1 });
    if (c.bullets) c.bullets.forEach((v, k) => t("• " + v, x + 0.1, by + 1.2 + k * 0.25, bw - 0.15, 0.25, { size: 9, valign: "middle", lh: 1 }));
    if (c.levels) c.levels.forEach(([v, col, soft], k) => {
      const yy = by + 1.22 + k * 0.38;
      rr(x + 0.12, yy, bw - 0.24, 0.32, soft, { r: 0.06 });
      s.addShape(pres.shapes.OVAL, { x: x + 0.2, y: yy + 0.06, w: 0.2, h: 0.2, fill: { color: col }, line: { color: col, width: 0 } });
      t(v, x + 0.48, yy, bw - 0.6, 0.32, { size: 10.5, bold: true, color: col, valign: "middle", lh: 1 });
    });
  }
  if (i < 4) arrow(x + bw + 0.03, by + bh / 2 - 0.1);
});
t("정지: 전방 < 0.35m · AGV 간 < 0.3m (전진 지령 0)   주의: 경로 신뢰도 노랑   주행: 경로 녹색", sx, by + bh + 0.05, sw, 0.22, { size: 8.5, color: C.sub, lh: 1 });
const bars = [[null, "활용 데이터", "실시간 LiDAR 360° 스캔, 휠 오도메트리, 640×480 카메라 영상, 운행 이력 JSONL (학습 데이터 수집 없음)"],
  [null, "활용 기술", "Python asyncio, rosbridge (ROS 1 Noetic · ROS 2 Humble), Unity 6 + OpenXR, Meta Quest 2, VFH · Follow-the-Gap 계열 기하 추론"]];
bars.forEach(([ic, k, v], i) => {
  const yb = by + bh + 0.33 + i * 0.45;
  rr(sx, yb, sw, 0.38, C.blueSoft, { r: 0.08 });
  t(k, sx + 0.2, yb, 1.2, 0.38, { size: 11.5, bold: true, color: C.navy2, valign: "middle", lh: 1 });
  t(v, sx + 1.6, yb, sw - 1.7, 0.38, { size: 9, color: C.ink, valign: "middle", lh: 1.1 });
});

// ================= 3. 구현 결과 =================
y0 = 11.95;
rr(M, y0, W - 2 * M, 2.7, C.white, { border: C.line });
s.addShape(pres.shapes.RECTANGLE, { x: M + 0.25, y: y0 + 0.2, w: 0.5, h: 0.5, fill: { color: C.navy2 }, line: { color: C.navy2, width: 0 } });
t("3", M + 0.25, y0 + 0.2, 0.5, 0.5, { size: 20, bold: true, color: C.white, align: "center", valign: "middle", lh: 1 });
t("구현 결과", M + 0.9, y0 + 0.2, 3, 0.5, { size: 24, bold: true, valign: "middle", lh: 1 });
const doneTop = 0.8;
const done = ["전방 0.35m · AGV 간 0.3m 정지 게이트 (전진만 차단)", "LiDAR 탈출 경로를 영상 바닥 · 관제 맵에 표시", "관제 맵 클릭 → VR 콕핏 전환, 그립 데드맨 조종", "2대 AUTO 순찰, 만나면 둘 다 정지", "자동 시험 78/78, 300초 부하 안전 위반 0건"];
done.forEach((v, i) => {
  const y = y0 + doneTop + i * 0.27;
  t("✔", M + 0.3, y, 0.3, 0.28, { font: SYM, size: 11, bold: true, color: C.blue, valign: "middle", lh: 1 });
  t(v, M + 0.62, y, 3.6, 0.28, { size: 10, valign: "middle", lh: 1 });
});
rr(M + 0.25, y0 + 2.2, 3.95, 0.38, C.blueSoft, { r: 0.08 });
t("✔  실물 TurtleBot3 2대 기준 핵심 기능 중심 구현", M + 0.4, y0 + 2.2, 3.75, 0.38, { size: 10.5, bold: true, color: C.navy2, valign: "middle", lh: 1 });
// 화면 2개 (예시의 대시보드 + 모바일 대응)
const px = M + 4.4, pw = 3.7, ih = 1.95, iw = ih * 640 / 480;
rr(px, y0 + 0.2, pw, 0.32, C.navy2, { r: 0.16 });
t("VR 콕핏 화면 (실제 출력)", px, y0 + 0.2, pw, 0.32, { size: 11, bold: true, color: C.white, align: "center", valign: "middle", lh: 1 });
rr(px + (pw - iw) / 2 - 0.06, y0 + 0.6, iw + 0.12, ih + 0.12, "0F172A", { r: 0.08 });
s.addImage({ path: A("overlay_stop_path.jpg"), x: px + (pw - iw) / 2, y: y0 + 0.66, w: iw, h: ih, altText: "VR 콕핏 화면" });
const qx = px + pw + 0.25, qw = W - M - 0.25 - qx;
rr(qx, y0 + 0.2, qw, 0.32, C.navy2, { r: 0.16 });
t("관제 맵 화면 (실제 출력)", qx, y0 + 0.2, qw, 0.32, { size: 11, bold: true, color: C.white, align: "center", valign: "middle", lh: 1 });
rr(qx + (qw - ih) / 2 - 0.06, y0 + 0.6, ih + 0.12, ih + 0.12, "0F172A", { r: 0.08 });
s.addImage({ path: A("topdown_warning_on.png"), x: qx + (qw - ih) / 2, y: y0 + 0.66, w: ih, h: ih, altText: "관제 맵 화면" });

// ================= 4. 기대 효과 =================
y0 = 14.8;
rr(M, y0, W - 2 * M, 1.35, C.white, { border: C.line });
rr(M + 0.25, y0 + 0.18, 0.5, 0.5, C.navy2, { r: 0.08 });
t("4", M + 0.25, y0 + 0.18, 0.5, 0.5, { size: 20, bold: true, color: C.white, align: "center", valign: "middle", lh: 1 });
t("기대 효과", M + 0.9, y0 + 0.18, 3, 0.5, { size: 24, bold: true, valign: "middle", lh: 1 });
t("멈춘 AGV를 현장 출동 없이 관제석에서 복구해 통로 정체를 줄이고, 정지 원인·경로 기록으로 사고 원인을 추적할 수 있다. 3D LiDAR 없이 기존 2D 기체에 소프트웨어로 얹어 중소 현장 도입 부담이 낮다. 향후 깊이 카메라 · 마커 위치 보정 · PLC 연동으로 확장한다.",
  M + 0.3, y0 + 0.72, 8.25, 0.6, { size: 10, lh: 1.25 });
s.addShape(pres.shapes.LINE, { x: 9.15, y: y0 + 0.3, w: 0, h: 0.85, line: { color: C.line, width: 1 } });
t("로봇은 멈추고 알리고,\n판단은 사람이 내린다.", 9.3, y0 + 0.3, 2.1, 0.85, { size: 12, bold: true, color: C.navy2, valign: "middle", lh: 1.3 });

// ================= 바닥띠 =================
rr(M, 16.3, W - 2 * M, 0.55, C.blueSoft, { r: 0.08 });
t([{ text: "국립한국해양대학교 · [팀명]", options: { bold: true, color: C.navy2 } }],
  M + 0.25, 16.3, 4.0, 0.55, { size: 12, valign: "middle", lh: 1 });
t([{ text: "소스코드  ", options: { color: C.sub } }, { text: "github.com/hun1105/gohst_rider", options: { color: C.ink } }],
  M + 4.1, 16.3, 4.2, 0.55, { size: 11.5, valign: "middle", lh: 1 });
t("대학부 · 분야 32 제조 피지컬 AI", W - M - 3.4, 16.3, 3.15, 0.55, { size: 11.5, color: C.navy2, bold: true, align: "right", valign: "middle", lh: 1 });

pres.writeFile({ fileName: OUT }).then(f => console.log("written", f));
