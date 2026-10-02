// REPORT_5P.md → REPORT_5P.docx (docx-js). Markdown 하위 집합 변환기.
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, ShadingType,
  HeadingLevel, AlignmentType, ImageRun, Footer, PageNumber, LevelFormat, BorderStyle, PageBreak,
} = require("docx");

// node build_report.js <docs> [소스.md] [제목]  → 같은 이름 .docx
const DOCS = process.argv[2];
const SRC_NAME = process.argv[3] || "REPORT_5P.md";
const TITLE = process.argv[4] || "개발완료보고서 - MetaQuest VR 피지컬 AI AGV 디지털 트윈";
const SRC = path.join(DOCS, SRC_NAME);
const OUT = path.join(DOCS, SRC_NAME.replace(/\.md$/i, ".docx"));

const FONT = { ascii: "Malgun Gothic", eastAsia: "Malgun Gothic", hAnsi: "Malgun Gothic", cs: "Malgun Gothic" };
const MONO = { ascii: "Consolas", eastAsia: "Malgun Gothic", hAnsi: "Consolas", cs: "Consolas" };
const INK = "22272E", MUTED = "5B6470", HEAD_FILL = "2B3138", ZEBRA = "F3F5F7", CODE_FILL = "F1F3F5";
const PAGE_W = 11906, MARGIN = 850;                  // A4, 약 1.5cm 여백
const MULTI_IMAGE_MAX_H = 150;                       // 캡처 2장 행 최대 높이 (px)
const CONTENT_W = PAGE_W - 2 * MARGIN;              // DXA
const CONTENT_PX = Math.round(CONTENT_W / 1440 * 96);
const BODY = 18, SMALL = 16, CODE = 15;              // half-points (9pt / 8pt / 7.5pt)

function runs(text, base = {}) {
  // **굵게**, `코드` 처리
  const out = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0, m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), font: FONT, ...base }));
    const t = m[0];
    if (t.startsWith("**")) out.push(new TextRun({ text: t.slice(2, -2), bold: true, font: FONT, ...base }));
    else out.push(new TextRun({ text: t.slice(1, -1), font: MONO, ...base, size: (base.size || BODY) - 1 }));
    last = m.index + t.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), font: FONT, ...base }));
  return out;
}

// 촬영 캡처 슬롯: cap_x.jpg 없으면 cap_x.png, 그것도 없으면 placeholder_cap_x.png
function resolveImage(file) {
  if (fs.existsSync(file)) return file;
  const dir = path.dirname(file), base = path.basename(file).replace(/\.(jpg|jpeg|png)$/i, "");
  for (const alt of [base + ".png", base + ".jpg", "placeholder_" + base + ".png"]) {
    if (fs.existsSync(path.join(dir, alt))) return path.join(dir, alt);
  }
  throw new Error("image not found: " + file);
}

function imageSize(file) {
  const b = fs.readFileSync(file);
  if (b[0] === 0x89) return { w: b.readUInt32BE(16), h: b.readUInt32BE(20), type: "png" };
  let i = 2;                                         // JPEG SOF 탐색
  while (i < b.length) {
    const marker = b[i + 1], len = b.readUInt16BE(i + 2);
    if (marker >= 0xc0 && marker <= 0xc3) return { h: b.readUInt16BE(i + 5), w: b.readUInt16BE(i + 7), type: "jpg" };
    i += 2 + len;
  }
  throw new Error("image size: " + file);
}

function tableFrom(rows) {
  const header = rows[0], body = rows.slice(1);
  const n = header.length;
  const weight = header.map((_, c) => Math.max(...rows.map(r => (r[c] || "").replace(/\*\*|`/g, "").length), 4));
  const total = weight.reduce((a, b) => a + b, 0);
  let widths = weight.map(w => Math.max(900, Math.round(CONTENT_W * w / total)));
  const scale = CONTENT_W / widths.reduce((a, b) => a + b, 0);
  widths = widths.map(w => Math.floor(w * scale));
  widths[n - 1] += CONTENT_W - widths.reduce((a, b) => a + b, 0);
  const cell = (text, c, isHead, zebra) => new TableCell({
    width: { size: widths[c], type: WidthType.DXA },
    shading: isHead ? { type: ShadingType.CLEAR, fill: HEAD_FILL, color: "auto" }
                    : zebra ? { type: ShadingType.CLEAR, fill: ZEBRA, color: "auto" } : undefined,
    margins: { top: 50, bottom: 50, left: 90, right: 90 },
    children: [new Paragraph({ children: runs(text, { size: SMALL, color: isHead ? "FFFFFF" : INK, bold: isHead || undefined }) })],
  });
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: widths,
    rows: [
      new TableRow({ tableHeader: true, cantSplit: true, children: header.map((t, c) => cell(t, c, true, false)) }),
      ...body.map((r, i) => new TableRow({ cantSplit: true, children: header.map((_, c) => cell(r[c] || "", c, false, i % 2 === 1)) })),
    ],
  });
}

const lines = fs.readFileSync(SRC, "utf8").replace(/\r/g, "").split("\n");
const children = [];
let i = 0;
let listInstance = 0;
// 표 셀 안 리터럴 파이프는 GitHub 규칙대로 \| 로 쓴다
const splitRow = l => l.trim().replace(/^\||\|$/g, "").split(/(?<!\\)\|/).map(s => s.trim().replace(/\\\|/g, "|"));

while (i < lines.length) {
  const line = lines[i];
  if (line.startsWith("# ")) {
    children.push(new Paragraph({ spacing: { after: 120 }, children: [new TextRun({ text: line.slice(2), bold: true, size: 34, color: INK, font: FONT })] }));
  } else if (line.startsWith("## ")) {
    children.push(new Paragraph({ heading: HeadingLevel.HEADING_1, keepNext: true, keepLines: true, spacing: { before: 260, after: 100 }, children: runs(line.slice(3), { size: 26, bold: true, color: INK }) }));
  } else if (line.startsWith("### ")) {
    children.push(new Paragraph({ heading: HeadingLevel.HEADING_2, keepNext: true, keepLines: true, spacing: { before: 160, after: 60 }, children: runs(line.slice(4), { size: 21, bold: true, color: INK }) }));
  } else if (line.trim() === "<!-- pagebreak -->") {
    children.push(new Paragraph({ children: [new PageBreak()] }));   // 표지 분리 (양식: 표지 제외 5쪽)
  } else if (line.trim() === "---") {
    // 구분선 생략 (섹션 제목 여백으로 구분)
  } else if (line.startsWith("```")) {
    i++;
    const block = [];
    while (i < lines.length && !lines[i].startsWith("```")) block.push(lines[i++]);
    block.forEach((l, k) => children.push(new Paragraph({
      shading: { type: ShadingType.CLEAR, fill: CODE_FILL, color: "auto" },
      spacing: { before: k === 0 ? 80 : 0, after: k === block.length - 1 ? 120 : 0, line: 250 },
      indent: { left: 120, right: 120 },
      children: [new TextRun({ text: l.length ? l : " ", font: MONO, size: CODE, color: INK })],
    })));
  } else if (line.startsWith("|")) {
    const rows = [];
    while (i < lines.length && lines[i].startsWith("|")) {
      if (!/^\|\s*:?-{2,}/.test(lines[i])) rows.push(splitRow(lines[i]));
      i++;
    }
    children.push(tableFrom(rows));
    children.push(new Paragraph({ spacing: { after: 60 }, children: [] }));
    continue;
  } else if (/^!\[/.test(line.trim())) {
    const found = [...line.matchAll(/!\[([^\]]*)\]\(([^)]+)\)/g)];
    const imgs = found.map(m => resolveImage(path.join(DOCS, m[2])));
    // ![alt|85](...) → 본문 폭의 85%
    const pct = found.length === 1 && /\|(\d+)$/.test(found[0][1]) ? parseInt(found[0][1].match(/\|(\d+)$/)[1], 10) / 100 : 1;
    const gap = 8, each = Math.floor((CONTENT_PX * pct - gap * (imgs.length - 1)) / imgs.length);
    const parts = [];
    imgs.forEach((f, k) => {
      const s = imageSize(f);
      let iw = each, ih = Math.round(each * s.h / s.w);
      if (imgs.length > 1 && ih > MULTI_IMAGE_MAX_H) { iw = Math.round(iw * MULTI_IMAGE_MAX_H / ih); ih = MULTI_IMAGE_MAX_H; }
      parts.push(new ImageRun({ type: s.type, data: fs.readFileSync(f), transformation: { width: iw, height: ih },
        altText: { title: path.basename(f), description: path.basename(f), name: path.basename(f) } }));
      if (k < imgs.length - 1) parts.push(new TextRun({ text: " ", font: FONT }));
    });
    children.push(new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 100, after: 40 }, children: parts }));
  } else if (/^\*[^*].*\*$/.test(line.trim())) {
    children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 140 },
      children: [new TextRun({ text: line.trim().slice(1, -1), italics: true, size: SMALL, color: MUTED, font: FONT })] }));
  } else if (/^- /.test(line)) {
    children.push(new Paragraph({ numbering: { reference: "bullets", level: 0 }, spacing: { after: 40 }, children: runs(line.slice(2), { size: BODY, color: INK }) }));
  } else if (/^\d+\. /.test(line)) {
    if (!/^\d+\. /.test(lines[i - 1] || "")) listInstance++;   // 새 번호 목록은 1부터
    children.push(new Paragraph({ numbering: { reference: "numbers", level: 0, instance: listInstance }, spacing: { after: 40 }, children: runs(line.replace(/^\d+\. /, ""), { size: BODY, color: INK }) }));
  } else if (line.trim().length) {
    children.push(new Paragraph({ spacing: { after: 50 }, children: runs(line.replace(/\s{2}$/, ""), { size: BODY, color: INK }) }));
  }
  i++;
}

const doc = new Document({
  creator: "PhysicalAI AGV Team",
  title: TITLE,
  styles: {
    default: { document: { run: { font: FONT, size: BODY, color: INK }, paragraph: { spacing: { line: 276 } } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FONT, size: 26, bold: true, color: INK }, paragraph: { outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FONT, size: 21, bold: true, color: INK }, paragraph: { outlineLevel: 1 } },
    ],
  },
  numbering: { config: [
    { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 240 } } } }] },
    { reference: "numbers", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 300 } } } }] },
  ] },
  sections: [{
    properties: { page: { margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [new TextRun({ children: [PageNumber.CURRENT], size: 16, color: MUTED, font: FONT })] })] }) },
    children,
  }],
});

Packer.toBuffer(doc).then(buf => { fs.writeFileSync(OUT, buf); console.log("written", OUT, buf.length); });
