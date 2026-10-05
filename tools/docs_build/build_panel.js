// PANEL_A0.pptx — 판넬형 보고서 (A0 세로 841×1189mm, 1장).
// 양식 참고: 학술대회·캡스톤 포스터 (남색 머리띠, 2단, 섹션 막대, 소제목 알약, 그림 캡션 띠, 표).
// 내용 원천: REPORT_5P.md · NIGHTLY_RESULT_20261003.md (수치는 실측·자동 시험 기록만 사용, 운영규정 제31조).
// 실행: node build_panel.js ../../docs  → 각 단 끝 y 좌표를 출력 (넘침 확인용).
const path = require("path");
const pptxgen = require("pptxgenjs");

const DOCS = process.argv[2];
const OUT = path.join(DOCS, "PANEL_A0.pptx");
const A = f => path.join(DOCS, "assets", f);

const W = 33.11, H = 46.81;          // A0 세로 (인치)
const M = 0.8, GAP = 0.8;
const COLW = (W - 2 * M - GAP) / 2;
const HEADER_H = 6.4, FOOTER_H = 1.6;
const BOTTOM = H - FOOTER_H - 0.5;
const FONT = "Pretendard";
const C = {
  navy: "0F2D4D", bar: "2E5A8C", teal: "6F9C8C", cap: "E6E8EB", ink: "1A1A1A", sub: "444444",
  hair: "C8CED6", thead: "4A7EC6", trow: "F2F4F7", red: "C53030", white: "FFFFFF", gold: "F2C14E",
};
const BODY = 25, SMALL = 21, LH = 1.3;

const pres = new pptxgen();
pres.defineLayout({ name: "A0P", width: W, height: H });
pres.layout = "A0P";
pres.title = "판넬형 보고서 — MetaQuest VR 피지컬 AI AGV 디지털 트윈";
const s = pres.addSlide();
s.background = { color: "F4F5F7" };

// ---------- 글자 폭 추정 (줄바꿈 높이 계산용) ----------
const em = ch => (/[ㄱ-힝·←-⇿①-⓿■-◿]/.test(ch) ? 1.0 : (/[A-Z0-9%$]/.test(ch) ? 0.62 : 0.5));
function lines(str, size, width) {
  const perLine = width * 72 / size;
  return str.split("\n").reduce((n, para) => {
    const w = [...para.replace(/\*\*/g, "")].reduce((a, ch) => a + em(ch), 0);
    return n + Math.max(1, Math.ceil(w / perLine * 0.97));
  }, 0);
}
const textH = (str, size, width, lh = LH) => lines(str, size, width) * size * lh / 72;

// **굵게** 표기 → pptx 런
function runs(str, o = {}) {
  return str.split(/(\*\*[^*]+\*\*)/).filter(Boolean).map(t => {
    const b = t.startsWith("**");
    return { text: b ? t.slice(2, -2) : t, options: { bold: b || o.bold || false, color: b ? (o.boldColor || C.navy) : (o.color || C.ink) } };
  });
}

// ---------- 단(column) 커서 ----------
class Col {
  constructor(x) { this.x = x; this.y = HEADER_H + 0.7; }
  section(title) {
    this.y += 0.15;
    s.addShape(pres.shapes.RECTANGLE, { x: this.x, y: this.y, w: COLW, h: 1.05, fill: { color: C.bar }, line: { color: C.bar, width: 0 } });
    s.addText(title, { x: this.x + 0.3, y: this.y, w: COLW - 0.6, h: 1.05, fontFace: FONT, fontSize: 44, bold: true, color: C.white, valign: "middle", margin: 0 });
    this.y += 1.35;
  }
  sub(title) {
    const w = COLW * 0.82, x = this.x + (COLW - w) / 2;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: this.y, w, h: 0.72, rectRadius: 0.36, fill: { color: C.teal }, line: { color: C.teal, width: 0 } });
    s.addText(title, { x, y: this.y, w, h: 0.72, fontFace: FONT, fontSize: 30, bold: true, color: C.white, align: "center", valign: "middle", margin: 0 });
    this.y += 0.95;
  }
  heading(t) {
    s.addText(t, { x: this.x + 0.1, y: this.y, w: COLW - 0.2, h: 0.5, fontFace: FONT, fontSize: 28, bold: true, color: C.navy, valign: "middle", margin: 0 });
    this.y += 0.6;
  }
  bullets(items, size = BODY) {
    const bw = COLW - 0.75;
    items.forEach(it => {
      const h = textH(it, size, bw);
      s.addText("●", { x: this.x + 0.15, y: this.y + 0.02, w: 0.4, h: size / 72 * 1.2, fontFace: FONT, fontSize: size * 0.7, color: C.bar, margin: 0, valign: "middle" });
      s.addText(runs(it), { x: this.x + 0.6, y: this.y, w: bw, h, fontFace: FONT, fontSize: size, lineSpacingMultiple: LH, margin: 0, valign: "top" });
      this.y += h + 0.14;
    });
    this.y += 0.12;
  }
  caption(t) {
    s.addShape(pres.shapes.RECTANGLE, { x: this.x, y: this.y, w: COLW, h: 0.55, fill: { color: C.cap }, line: { color: C.cap, width: 0 } });
    s.addText(t, { x: this.x + 0.2, y: this.y, w: COLW - 0.4, h: 0.55, fontFace: FONT, fontSize: SMALL, color: C.ink, valign: "middle", margin: 0 });
    this.y += 0.8;
  }
  figure(file, pxW, pxH, cap, frac = 1) {
    const w = (COLW - 0.4) * frac, h = w * pxH / pxW, x = this.x + (COLW - w) / 2;
    s.addShape(pres.shapes.RECTANGLE, { x: this.x, y: this.y, w: COLW, h: h + 0.4, fill: { color: C.white }, line: { color: C.hair, width: 1 } });
    s.addImage({ path: A(file), x, y: this.y + 0.2, w, h, altText: cap });
    this.y += h + 0.4;
    this.caption(cap);
  }
  figures(list, cap, maxH = 99) {   // [[file, pxW, pxH, 라벨]] 가로 나란히, 같은 높이, 가운데 정렬
    const inner = COLW - 0.4, g = 0.3;
    const ratios = list.map(([, w, h]) => w / h), sum = ratios.reduce((a, b) => a + b, 0);
    const h = Math.min(maxH, (inner - g * (list.length - 1)) / sum);
    s.addShape(pres.shapes.RECTANGLE, { x: this.x, y: this.y, w: COLW, h: h + 1.0, fill: { color: C.white }, line: { color: C.hair, width: 1 } });
    let x = this.x + (COLW - (h * sum + g * (list.length - 1))) / 2;
    list.forEach(([file, , , label], i) => {
      const w = h * ratios[i];
      s.addImage({ path: A(file), x, y: this.y + 0.2, w, h, altText: label });
      s.addText(label, { x, y: this.y + h + 0.3, w, h: 0.5, fontFace: FONT, fontSize: SMALL, color: C.sub, align: "center", valign: "middle", margin: 0 });
      x += w + g;
    });
    this.y += h + 1.0;
    this.caption(cap);
  }
  table(title, rows, colFr, size = SMALL) {
    if (title) {
      s.addShape(pres.shapes.RECTANGLE, { x: this.x, y: this.y, w: COLW, h: 0.55, fill: { color: C.cap }, line: { color: C.cap, width: 0 } });
      s.addText(title, { x: this.x + 0.2, y: this.y, w: COLW - 0.4, h: 0.55, fontFace: FONT, fontSize: SMALL, color: C.ink, valign: "middle", margin: 0 });
      this.y += 0.6;
    }
    const tot = colFr.reduce((a, b) => a + b, 0), cw = colFr.map(f => COLW * f / tot);
    const rowH = rows.map(r => Math.max(...r.map((c, i) => textH(c, size, cw[i] - 0.25, 1.2))) + 0.22);
    const data = rows.map((r, ri) => r.map(c => ({
      text: ri === 0 ? c : runs(c),
      options: ri === 0
        ? { bold: true, color: C.white, fill: { color: C.thead }, align: "center" }
        : { fill: { color: ri % 2 ? C.white : C.trow } },
    })));
    s.addTable(data, { x: this.x, y: this.y, w: COLW, colW: cw, rowH, fontFace: FONT, fontSize: size, color: C.ink,
      valign: "middle", margin: [0.06, 0.1, 0.06, 0.1], border: { type: "solid", pt: 0.75, color: C.hair } });
    this.y += rowH.reduce((a, b) => a + b, 0) + 0.35;
  }
  stats(items) {   // [[큰 수치, 설명]]
    const g = 0.3, w = (COLW - g * (items.length - 1)) / items.length, h = 2.2;
    items.forEach(([big, lab], i) => {
      const x = this.x + i * (w + g), dark = i === 0;
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: this.y, w, h, rectRadius: 0.12, fill: { color: dark ? C.navy : C.white }, line: { color: dark ? C.navy : C.hair, width: 1 } });
      s.addText(big, { x: x + 0.15, y: this.y + 0.2, w: w - 0.3, h: 1.05, fontFace: FONT, fontSize: 54, bold: true, color: dark ? C.gold : C.navy, align: "center", valign: "middle", margin: 0 });
      s.addText(lab, { x: x + 0.15, y: this.y + 1.25, w: w - 0.3, h: 0.8, fontFace: FONT, fontSize: SMALL, color: dark ? C.white : C.sub, align: "center", valign: "top", margin: 0, lineSpacingMultiple: 1.15 });
    });
    this.y += h + 0.35;
  }
  space(d = 0.3) { this.y += d; }
}

// ---------- 머리띠 ----------
s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: W, h: HEADER_H, fill: { color: C.navy }, line: { color: C.navy, width: 0 } });
s.addShape(pres.shapes.RECTANGLE, { x: 0, y: HEADER_H - 0.18, w: W, h: 0.18, fill: { color: C.bar }, line: { color: C.bar, width: 0 } });
s.addText([{ text: "2026 제4회\n", options: { color: C.gold, bold: true } }, { text: "경남 AI·SW 경진대회\n대학부 · 분야 32 제조 피지컬 AI", options: { color: C.white } }],
  { x: M, y: 0.6, w: 6.0, h: 2.3, fontFace: FONT, fontSize: 26, margin: 0, valign: "top", lineSpacingMultiple: 1.15 });
s.addText("MetaQuest VR 기반 피지컬 AI AGV\n원격 개입 & 협착 방지 디지털 트윈", { x: 6.6, y: 0.45, w: W - 6.6 - 5.4, h: 2.5,
  fontFace: FONT, fontSize: 64, bold: true, color: C.white, align: "center", valign: "middle", margin: 0, lineSpacingMultiple: 1.05 });
s.addText("Remote VR Intervention and Entrapment Prevention for Physical-AI AGVs with a Digital Twin", { x: 6.6, y: 3.0, w: W - 6.6 - 5.4, h: 0.7,
  fontFace: FONT, fontSize: 30, color: "DCE6F2", align: "center", valign: "middle", margin: 0 });
s.addText("[팀명] · [팀장명]*, [팀원명]*", { x: 6.6, y: 3.8, w: W - 6.6 - 5.4, h: 0.75, fontFace: FONT, fontSize: 36, color: C.white, align: "center", valign: "middle", margin: 0 });
s.addText("*국립한국해양대학교 [학부/학과]", { x: 6.6, y: 4.6, w: W - 6.6 - 5.4, h: 0.6, fontFace: FONT, fontSize: 26, color: "DCE6F2", align: "center", valign: "middle", margin: 0 });
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: W - M - 4.4, y: 0.9, w: 4.4, h: 4.0, rectRadius: 0.2, fill: { color: "16395F" }, line: { color: "3B6A9C", width: 1.5 } });
s.addText([{ text: "LIVE DEMO\n", options: { bold: true, color: C.gold, fontSize: 30 } },
  { text: "TurtleBot3 × 2\nMeta Quest 2\nUnity 6 · ROS 1/2", options: { color: C.white, fontSize: 24 } }],
  { x: W - M - 4.4, y: 0.9, w: 4.4, h: 4.0, fontFace: FONT, align: "center", valign: "middle", margin: 0, lineSpacingMultiple: 1.25 });

// ---------- 왼쪽 단 ----------
const L = new Col(M);
L.section("1. 프로젝트 현황");
L.table(null, [
  ["항목", "내용"],
  ["제목", "MetaQuest VR 기반 피지컬 AI 원격 개입 & AGV 협착 방지 디지털 트윈"],
  ["요약", "2D LiDAR·카메라만 단 보급형 AGV가 위험하면 스스로 멈추고, 정지 원인과 탈출 경로를 화면에 그려 관제사를 부른다. 관제사가 지도에서 로봇을 누르면 VR로 그 로봇 운전석에 들어가 빼낸 뒤 순찰을 다시 맡긴다."],
  ["구분 / 분야", "대학부 / 32 (3-2. 제조 피지컬 AI — MetaQuest2 VR 기반 피지컬 AI Agent)"],
  ["팀명", "[팀명] (국립한국해양대학교)"],
  ["팀원 · 역할", "[팀장명]: [역할] / [팀원명]: [역할]"],
  ["저장소", "https://github.com/hun1105/gohst_rider"],
], [1, 3.6]);

L.section("2. 프로젝트 개요");
L.heading("2.1 문제");
L.bullets([
  "**사람과 AGV가 같은 통로를 쓰는 곳에서 사고는 끼임·부딪힘에 몰리고 [1][2], 멈춘 라인은 곧 비용이다 [3].**",
]);
L.stats([["53%", "로봇 재해 중 끼임\nKOSHA 2011–2020"], ["66명", "2024 끼임 사망\n고용노동부"], ["$2.3M/h", "자동차 라인 정지 최대\nSiemens 2024"]]);
L.bullets([
  "**① 높이 사각지대**: 2D LiDAR는 바닥 약 0.17m 한 평면만 본다.",
  "**② 자율 후진의 역설**: 뒤를 못 보니 스스로 물러날 수 없어 비상정지로 끝난다.",
  "**③ 물리적 출동**: 멈춘 로봇은 관리자가 걸어가야 풀리고, 그동안 통로가 막힌다 [6][7].",
]);
L.heading("2.2 사용자");
L.table(null, [
  ["사용자", "장비", "하는 일"],
  ["관제사", "PC 관제 맵", "여러 AGV를 지도로 보며 멈춘 로봇을 고른다"],
  ["원격 조작자", "Meta Quest 2", "고른 로봇의 1인칭 운전석에서 직접 빼낸다"],
  ["현장 작업자", "—", "AGV와 같은 통로를 쓰는 보호 대상"],
], [1.1, 1.1, 2.8]);
L.heading("2.3 목표");
L.bullets([
  "AGV 2대 운용 중 **작업자 협착·충돌 0건**, 봉착 시 **현장 출동 없이 원격 탈출**.",
  "**판단은 로봇이** (정지·원인·탈출 경로 계산), **움직임 결정은 근거를 본 사람이** 내린다.",
]);

L.section("3. 개발 세부 내용");
L.heading("3.1 시스템 구조 — 3 Tier");
L.bullets([
  "**현장** TurtleBot3 2대 (TB1 ROS 1 · TB2 ROS 2) ↔ **AI 릴레이** Python asyncio 20 Hz ↔ **트윈·VR** Unity 6 관제 맵 + Quest 2 콕핏. **안전 게이트를 통과한 속도만 /cmd_vel로 나간다.**",
]);
L.figure("fig_architecture.png", 1512, 855, "[그림 1] 시스템 아키텍처 — Unity ↔ AI 릴레이 ↔ TurtleBot3", 0.78);
L.heading("3.2 활용 데이터");
L.bullets([
  "**실시간 센서**: LiDAR 360° (무효값 0.0 제외, 0.12m 하한), 휠 odom, 640×480 영상 15.7 fps. 학습 데이터 수집·라벨링 없음.",
  "**사전학습 모델**: YOLOv8n (COCO) 회랑 검출 — 현장 미검증, 실시간 판단은 LiDAR가 맡음.",
  "**운행 이력**: 릴레이 이벤트 로그 + 1 Hz 텔레메트리 JSONL (정지 원인·모드·경로 신뢰도).",
]);

L.heading("3.3 AI · Tool · 알고리즘");
L.table(null, [
  ["Agent 요소", "구현"],
  ["Goal · Planning", "협착·충돌 0건 / 순찰 → 위험 감지 → 정지 → 탈출 경로 → 수동 개입 → 재개"],
  ["Reasoning", "LiDAR 섹터 거리 · 로봇 폭 회랑 · 곡률 궤적 · 로봇 간 거리 (LLM 미사용)"],
  ["Tool Use", "ROS /cmd_vel · /odom · /scan (rosbridge), ustreamer 카메라, WebSocket, Unity"],
  ["Memory · Feedback", "로봇별 모드 · 정지 원인 · 운행 이력 / 영상 경로 띠 · 적색 경고 · 손 진동"],
], [1.25, 3.4]);

// ---------- 오른쪽 단 ----------
const Rt = new Col(M + COLW + GAP);
Rt.heading("3.3 (계속) 정지 · 탈출 판단 — 조건 → 방법 → 결과");
Rt.bullets([
  "**조건**: 전방 < 0.35m 또는 로봇 간 중심 < 0.3m → 전진 지령 0, 정지·알림 (후진은 후방 0.20m 가드).",
  "**방법**: 5° × 72방향 로봇 폭 회랑 여유 d(h), 0.5m 미만 제외, **J = d(h) − 0.25·|h|** 최대 방향 (VFH [4] · Follow-the-Gap [5] 계열).",
  "**결과**: 그 방향을 영상 바닥에 경로 띠·선회 화살표로 투영, 조작은 사람.",
]);
Rt.figure("fig_escape_planner.png", 1885, 829, "[그림 2] 탈출 방향 계산 예 — 전방 상자 + 우측 벽 → 좌 40° 선택", 0.62);
Rt.heading("3.4 단계별 개발 내용");
Rt.table(null, [
  ["단계", "내용"],
  ["1. 기반", "메시지 규격(PROTOCOL.md), 릴레이 골격, Unity 트윈 씬 자동 생성"],
  ["2. 실물 연동", "rosbridge 다중 로봇 링크 (ROS 1·2 혼용), 속도 상한·LiDAR 가드·통신 두절 정지, 카메라"],
  ["3. 안전 판단", "자동 후진 삭제 → 정지·알림, LiDAR 탈출 경로, 로봇별 AUTO, 만남 시 둘 다 정지"],
  ["4. 원격 개입", "관제 맵 클릭 빙의, PC·HMD 분리, 그립 데드맨·양손 조작·진동, 영상 경로 투영"],
  ["5. 검증", "가짜 rosbridge E2E 자동 시험 78항목, 10회 반복, 300초 부하, 실물 TB1·TB2 주행"],
], [1.05, 3.6]);

Rt.section("4. 구현 결과");
Rt.heading("4.1 기능 구현");
Rt.table(null, [
  ["기능", "구현 내용", "검증"],
  ["정지·알림", "전방 0.35m · 로봇 간 0.3m 전진 차단, 후진·회전은 허용", "TC-01 PASS"],
  ["2대 AUTO", "각자 직진 0.10 m/s, 만나면 둘 다 정지, 자동 재개 없음", "TC-02·05 자동 PASS"],
  ["VR 원격 개입", "관제 맵 클릭 → 그 로봇 콕핏 즉시 전환, 그 로봇만 MANUAL", "TC-03 PASS"],
  ["원격 조종 안전", "그립 데드맨 · 상한 0.15 m/s · 워치독 0.5s · 연결 해제 정지", "TC-04 PASS"],
], [1.15, 2.75, 1.2]);
Rt.stats([["78/78", "E2E 자동 시험"], ["10회", "반복 무결점"], ["0건", "300초 부하 안전 위반"]]);
Rt.heading("4.2 대시보드 — 관제 맵 · VR 콕핏");
Rt.figures([["overlay_stop_path.jpg", 640, 480, "콕핏: 정지 배너 · 탈출 경로"], ["topdown_warning_on.png", 720, 720, "관제 맵: 적색 경고"]],
  "[그림 3] 정지 시 화면 — 멈춘 이유와 빠져나갈 길이 보인다", 3.6);
Rt.bullets([
  "관제 맵: 로봇별 상태 카드 (AUTO/MANUAL/STOP · 정지 원인), 휠 줌·드래그, 사이드바 위치·크기 조절.",
]);

Rt.section("5. 기대효과");
Rt.bullets([
  "**기대효과**: 출동 대신 관제석에서 복구 → 통로 정체 감소, 정지 원인·경로 기록으로 사고 원인 추적.",
  "**성과**: 3D LiDAR 없이 2D LiDAR·카메라·SW로 정지 판단과 VR 원격 탈출 구현, ROS 1·2 실물 2대 동시 운용.",
  "**한계**: 높이 사각 · odom 누적 오차 · rosbridge 무인증 · 정지 시간(MTBI) 현장 미측정 → 깊이 카메라 · SLAM · 인증 · 파일럿 실측.",
]);

Rt.section("참고문헌");
Rt.bullets([
  "[1] KOSHA 산업용 로봇 재해 분석 2011~2020. [2] 고용노동부, 2024년 재해조사 대상 사망사고 발생현황 (2025). [3] Siemens, The True Cost of Downtime 2024.",
  "[4] Borenstein & Koren, The Vector Field Histogram, IEEE T-RA, 1991. [5] Sezer & Gokasan, Follow the Gap Method, RAS, 2012. [6] AutoInspect, arXiv:2404.12785, 2024. [7] VDI 2710 Blatt 5.",
], 18);

// ---------- 바닥띠 ----------
s.addShape(pres.shapes.RECTANGLE, { x: 0, y: H - FOOTER_H, w: W, h: FOOTER_H, fill: { color: C.white }, line: { color: C.hair, width: 1 } });
s.addText("국립한국해양대학교", { x: M, y: H - FOOTER_H, w: 10, h: FOOTER_H, fontFace: FONT, fontSize: 40, bold: true, color: C.navy, valign: "middle", margin: 0 });
s.addText("소스코드 https://github.com/hun1105/gohst_rider", { x: W - M - 16, y: H - FOOTER_H, w: 16, h: FOOTER_H, fontFace: FONT, fontSize: 26, color: C.sub, align: "right", valign: "middle", margin: 0 });

console.log(`left end y=${L.y.toFixed(2)}  right end y=${Rt.y.toFixed(2)}  limit=${BOTTOM.toFixed(2)}`);
pres.writeFile({ fileName: OUT }).then(f => console.log("written", f));
