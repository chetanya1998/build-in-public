/* Mock screenshots and screenshot templates for the dashboard mockup.
 *
 *   Shots.raw(id)                         inner SVG of a mock capture (1280×800)
 *   Shots.render(shot, id, opts?)         { svg, w, h } for a capture or a styled copy
 *   Shots.TEMPLATES                       the ten templates and their options
 *   Shots.png(svg, w, h, scale)           Promise<Blob> of the image as a PNG
 *
 * The real dashboard renders templates the same way: the capture is embedded
 * in an SVG frame, so it stays sharp at any size and exports to PNG locally.
 */
(function () {
  const W0 = 1280, H0 = 800;
  const MONO = "'JetBrains Mono','SF Mono',Menlo,Consolas,monospace";
  const SANS = "Inter,'Geist',-apple-system,'Segoe UI',system-ui,sans-serif";
  const SERIF = "'Newsreader','Iowan Old Style',Georgia,serif";
  const HAND = "'Bradley Hand','Segoe Print','Marker Felt','Comic Sans MS',cursive";
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const T = (x, y, s, o = {}) => `<text x="${x}" y="${y}" font-family="${o.f || SANS}" font-size="${o.s || 14}" font-weight="${o.w || 400}" fill="${o.c || "#111"}"${o.a ? ` text-anchor="${o.a}"` : ""}${o.i ? ' font-style="italic"' : ""}${o.ls ? ` letter-spacing="${o.ls}"` : ""} xml:space="preserve">${esc(s)}</text>`;
  const R = (x, y, w, h, c, r = 0, extra = "") => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}" fill="${c}" ${extra}/>`;

  /* ------------------------------------------------------------ syntax highlighting */
  const KW = { py: "def|return|if|not|for|in|is|None|else|elif|import|from|class|lambda|and|or|with|as|True|False", ts: "import|from|export|async|function|const|let|await|return|if|as|new|throw|type" };
  const COL = { com: "#6a7390", str: "#c3e88d", kw: "#c792ea", num: "#f78c6c", fn: "#82aaff", type: "#ffcb6b", id: "#d6deeb", p: "#89ddff" };
  function highlight(line, lang) {
    const re = new RegExp(`(${lang === "py" ? "#" : "//"}.*$)|("""[^"]*"""|"(?:[^"\\\\]|\\\\.)*"|'(?:[^'\\\\]|\\\\.)*'|\`[^\`]*\`)|\\b(${KW[lang]})\\b|\\b(\\d+(?:\\.\\d+)?)\\b|([A-Za-z_]\\w*)(?=\\()|\\b([A-Z]\\w*)\\b|([A-Za-z_]\\w*)`, "g");
    let out = "", last = 0, m;
    const span = (c, s, it) => s ? `<tspan fill="${c}"${it ? ' font-style="italic"' : ""}>${esc(s)}</tspan>` : "";
    while ((m = re.exec(line))) {
      out += span(COL.p, line.slice(last, m.index));
      const [tok] = m;
      out += m[1] ? span(COL.com, tok, true) : m[2] ? span(COL.str, tok) : m[3] ? span(COL.kw, tok) : m[4] ? span(COL.num, tok) : m[5] ? span(COL.fn, tok) : m[6] ? span(COL.type, tok) : span(COL.id, tok);
      last = re.lastIndex;
    }
    return out + span(COL.p, line.slice(last));
  }

  /* ------------------------------------------------------------ editor, terminal and app captures */
  function editor({ file, other, lang, crumbs, tree, active, lines, status }) {
    let s = R(0, 0, W0, H0, "#1e1f26") + R(0, 0, W0, 40, "#16171d") + R(0, 40, 230, 732, "#191a21");
    s += T(18, 68, "EXPLORER", { s: 11, c: "#6b7080", ls: 1.2, w: 600 });
    tree.forEach(([name, depth], i) => { const y = 98 + i * 26; if (i === active) s += R(0, y - 18, 230, 26, "#2a2d3a"); s += T(18 + depth * 14, y, (depth ? "" : "▾ ") + name, { s: 13, c: i === active ? "#e6e6e6" : "#9aa0ad" }); });
    s += R(230, 0, 200, 40, "#1e1f26") + T(252, 26, file, { s: 13.5, c: "#e6e6e6" }) + R(230, 38, 200, 2, "#7aa2f7") + T(452, 26, other, { s: 13.5, c: "#6b7080" });
    s += T(252, 64, crumbs, { s: 12, c: "#6b7080" });
    lines.forEach((ln, i) => { const y = 104 + i * 28; s += T(292, y, String(i + 1), { s: 15, c: "#4b5263", a: "end", f: MONO }); s += `<text x="312" y="${y}" font-family="${MONO}" font-size="16.5" xml:space="preserve">${highlight(ln, lang)}</text>`; });
    s += R(0, 772, W0, 28, "#3b5bdb") + T(14, 791, "⎇ main", { s: 12.5, c: "#fff" }) + T(1266, 791, status, { s: 12.5, c: "#fff", a: "end" });
    return s;
  }
  function terminal(title, lines) {
    let s = R(0, 0, W0, H0, "#0e1014") + R(0, 0, W0, 38, "#1a1c22") + T(640, 25, title, { s: 13, c: "#8a8f98", a: "middle" });
    lines.forEach((segs, i) => { s += `<text x="26" y="${76 + i * 29}" font-family="${MONO}" font-size="16.5" xml:space="preserve">${segs.map(([c, t]) => `<tspan fill="${c}">${esc(t)}</tspan>`).join("")}</text>`; });
    return s;
  }
  const pill = (x, y, label, fg, bg) => { const w = label.length * 7.4 + 22; return R(x, y - 15, w, 24, bg, 12) + T(x + w / 2, y + 2, label, { s: 12.5, c: fg, w: 600, a: "middle" }); };
  function appChrome(active) {
    let s = R(0, 0, W0, H0, "#f6f7f9") + R(0, 0, W0, 56, "#fff") + R(0, 55, W0, 1, "#e5e7eb");
    s += R(24, 14, 28, 28, "#ef7d32", 7) + T(38, 34, "i", { s: 16, c: "#fff", w: 700, a: "middle" }) + T(64, 35, "invoice·ai", { s: 18, w: 700 });
    s += R(840, 14, 330, 28, "#f3f4f6", 8) + T(856, 33, "Search invoices, customers…", { s: 13, c: "#9ca3af" }) + `<circle cx="1230" cy="28" r="15" fill="#e5e7eb"/>` + T(1230, 33, "JD", { s: 11, c: "#6b7280", w: 600, a: "middle" });
    s += R(0, 56, 220, 744, "#fff") + R(219, 56, 1, 744, "#e5e7eb");
    ["Dashboard", "Invoices", "Upload", "Customers", "Billing", "Settings"].forEach((n, i) => { const y = 104 + i * 40; if (n === active) s += R(12, y - 22, 196, 34, "#fff4ec", 8); s += T(32, y, n, { s: 14, c: n === active ? "#c2561a" : "#4b5563", w: n === active ? 600 : 400 }); });
    return s;
  }
  function billing() {
    let s = appChrome("Billing") + T(252, 108, "Billing", { s: 28, w: 700 }) + T(252, 134, "Charges recorded from Stripe webhooks", { s: 14, c: "#6b7280" });
    [["Revenue this month", "$4,312", "#111"], ["Paid invoices", "87", "#111"], ["Duplicates blocked", "3", "#ef7d32"]].forEach(([l, v, c], i) => { const x = 252 + i * 336; s += R(x, 156, 316, 96, "#fff", 10, 'stroke="#e5e7eb"') + T(x + 20, 186, l, { s: 13, c: "#6b7280" }) + T(x + 20, 228, v, { s: 30, w: 700, c }); });
    s += R(252, 276, 1004, 492, "#fff", 10, 'stroke="#e5e7eb"') + T(276, 310, "Recent charges", { s: 16, w: 700 });
    ["DATE", "CUSTOMER", "INVOICE", "AMOUNT", "STATUS"].forEach((h, i) => s += T([276, 440, 640, 820, 1000][i], 350, h, { s: 11.5, c: "#9ca3af", w: 600, ls: .6 }));
    const rows = [["Nov 9, 15:14", "Acme Co", "INV-2041", "$49.00", ["Paid", "#15803d", "#dcfce7"]], ["Nov 9, 15:14", "Acme Co", "INV-2041", "$49.00", ["Retry ignored", "#c2410c", "#ffedd5"]],
      ["Nov 9, 13:02", "Northwind", "INV-2040", "$129.00", ["Paid", "#15803d", "#dcfce7"]], ["Nov 9, 11:47", "Globex", "INV-2039", "$49.00", ["Paid", "#15803d", "#dcfce7"]],
      ["Nov 8, 18:20", "Initech", "INV-2038", "$19.00", ["Refunded", "#4b5563", "#f3f4f6"]], ["Nov 8, 16:05", "Umbrella", "INV-2037", "$249.00", ["Paid", "#15803d", "#dcfce7"]],
      ["Nov 8, 09:31", "Hooli", "INV-2036", "$49.00", ["Failed", "#b91c1c", "#fee2e2"]]];
    rows.forEach((r, i) => { const y = 396 + i * 52; s += R(253, y - 30, 1002, 1, "#f1f2f4"); if (i === 1) s += R(253, y - 29, 1002, 51, "#fff7ed");
      s += T(276, y, r[0], { s: 14, c: "#4b5563" }) + T(440, y, r[1], { s: 14, w: 500 }) + T(640, y, r[2], { s: 14, c: "#6b7280", f: MONO }) + T(820, y, r[3], { s: 14, w: 600 }) + pill(1000, y - 4, ...r[4]); });
    return s;
  }
  function landing() {
    let s = R(0, 0, W0, H0, "#fbfaf8") + R(0, 63, W0, 1, "#ecebe6") + R(40, 20, 24, 24, "#1c1b19", 6) + T(76, 38, "Build in Public", { s: 16, w: 600 });
    ["How it works", "Docs", "GitHub"].forEach((l, i) => s += T(870 + i * 100, 38, l, { s: 14, c: "#6b6b6b" }));
    s += R(1150, 17, 96, 30, "#1c1b19", 15) + T(1198, 37, "Install", { s: 13.5, c: "#fff", a: "middle", w: 500 });
    s += T(80, 166, "OPEN SOURCE · FOR AI-ASSISTED BUILDERS", { s: 12, c: "#8a8780", ls: 1.4, w: 600 });
    s += T(80, 244, "Build your product", { f: SERIF, s: 64, c: "#1c1b19" }) + T(80, 318, "in public.", { f: SERIF, s: 64, c: "#8a8780", i: true });
    s += T(80, 376, "Your agent logs what you build. Every night you get a", { s: 18, c: "#5c5a55" }) + T(80, 404, "short list of posts worth sharing. You pick, it drafts.", { s: 18, c: "#5c5a55" });
    s += R(80, 440, 520, 64, "#141414", 12) + T(104, 478, "$ curl -fsSL bip.sh/install | sh", { s: 17, c: "#e6e6e6", f: MONO }) + R(556, 458, 26, 28, "#2b2b2b", 6);
    s += T(80, 540, "Works with Claude Code, Codex and Antigravity", { s: 13.5, c: "#8a8780" });
    s += R(700, 120, 500, 540, "#fff", 18, 'stroke="#ecebe6"') + T(732, 164, "Tonight's gist", { s: 16, w: 600 }) + T(1168, 164, "Nov 9", { s: 13, c: "#8a8780", a: "end" });
    [["A 504 cost one user $49 twice", "X · war story"], ["Deleting posts.json made it more reliable", "X · lesson"], ["How I review my agent's commits", "LinkedIn · behind the scenes"], ["Idempotency in 6 lines", "X · demo"]].forEach(([t, m], i) => {
      const y = 214 + i * 104; s += `<circle cx="746" cy="${y}" r="13" fill="#f4f3ef"/>` + T(746, y + 5, String(i + 1), { s: 13, c: "#8a8780", a: "middle", f: MONO }) + T(774, y + 2, t, { s: 15.5, w: 500 }) + T(774, y + 26, m, { s: 13, c: "#8a8780" }) + (i < 3 ? R(732, y + 50, 436, 1, "#f0efea") : ""); });
    s += R(0, 767, W0, 1, "#d6d3cc", 0, 'stroke-dasharray="6 6"') + T(1260, 790, "1366×768 fold", { s: 11, c: "#b9b6af", a: "end", f: MONO });
    return s;
  }
  function parser() {
    let s = appChrome("Upload") + T(252, 108, "Upload", { s: 28, w: 700 }) + T(252, 134, "receipt-0412.pdf · scanned, 1 page", { s: 14, c: "#6b7280" });
    s += R(252, 156, 420, 612, "#fff", 10, 'stroke="#e5e7eb"') + R(286, 182, 352, 560, "#fffdf8", 2, 'stroke="#eee7d9"');
    s += `<circle cx="560" cy="300" r="62" fill="#c8a27a" opacity=".16"/><circle cx="560" cy="300" r="62" fill="none" stroke="#b08458" stroke-opacity=".35" stroke-width="5"/><circle cx="530" cy="330" r="22" fill="#c8a27a" opacity=".12"/>`;
    s += T(462, 222, "CORNER CAFÉ & BAKERY", { s: 15, w: 700, a: "middle", f: MONO, c: "#333" }) + T(462, 244, "12 Elm St · 04/12 08:41", { s: 12, a: "middle", f: MONO, c: "#777" });
    const items = [["Flat white", "4.50"], ["Croissant x2", "7.00"], ["Oat milk", "0.60"], ["Sourdough loaf", "6.80"], ["Avocado toast", "11.50"], ["Orange juice", "4.20"], ["Cinnamon roll x2", "6.40"], ["Espresso x2", "6.00"], ["Granola bowl", "8.90"], ["Sparkling water", "2.80"], ["Muffin", "3.40"], ["Misc.", "1.50"]];
    items.forEach(([n, a], i) => { const y = 284 + i * 30; s += T(310, y, n, { s: 13.5, f: MONO, c: "#444" }) + T(614, y, a, { s: 13.5, f: MONO, c: "#444", a: "end" }); });
    s += R(310, 650, 304, 1, "#999", 0, 'stroke-dasharray="3 3"') + T(310, 680, "TOTAL", { s: 14, f: MONO, w: 700, c: "#222" }) + T(614, 680, "63.60", { s: 14, f: MONO, w: 700, c: "#222", a: "end" });
    s += R(696, 156, 560, 612, "#fff", 10, 'stroke="#e5e7eb"') + T(720, 190, "Extracted line items", { s: 16, w: 700 }) + pill(1100, 186, "11 of 12 found", "#15803d", "#dcfce7");
    ["ITEM", "QTY", "AMOUNT"].forEach((h, i) => s += T([744, 1044, 1196][i], 226, h, { s: 11.5, c: "#9ca3af", w: 600, ls: .6, a: i === 2 ? "end" : undefined }));
    items.forEach(([n, a], i) => { const y = 260 + i * 41, miss = i === 11, qty = /x2/.test(n) ? "2" : "1";
      if (miss) s += R(697, y - 26, 558, 40, "#fffbeb");
      s += R(697, y - 27, 558, 1, "#f1f2f4") + T(720, y, miss ? "!" : "✓", { s: 14, c: miss ? "#b45309" : "#16a34a", w: 700 }) + T(744, y, n.replace(/ x2$/, ""), { s: 14, c: miss ? "#92400e" : "#111" }) + T(1044, y, qty, { s: 14, c: "#6b7280" }) + T(1196, y, "$" + a, { s: 14, w: 600, a: "end", c: miss ? "#92400e" : "#111" });
      if (miss) s += pill(840, y - 4, "missed", "#b45309", "#fef3c7"); });
    return s;
  }

  const P = "#d6deeb", G = "#6b7280", Gr = "#4ade80", A = "#fbbf24", B = "#93c5fd", V = "#c4b5fd", Pr = "#7dd3fc";
  const RAW = {
    s1: () => editor({ file: "index.py", other: "nudge.py", lang: "py", crumbs: "src › buildinpublic › index.py › normalize_status", active: 3, status: "Ln 7, Col 22   UTF-8   Python 3.12",
      tree: [["src", 0], ["buildinpublic", 1], ["cli.py", 2], ["index.py", 2], ["journal.py", 2], ["nudge.py", 2], ["shots.py", 2], ["tests", 0], ["test_index.py", 1]],
      lines: ['def normalize_status(raw: str | None) -> str:', '    """Map every status we have ever written onto one list."""', '    if not raw:', '        return "draft"', '    s = raw.strip().lower()', '    return {', '        "drafted": "draft",', '        "suggested": "suggested",', '        "approved": "approved",', '        "scheduled": "scheduled",', '        "posted": "posted",', '        "skipped": "skipped",', '    }.get(s, "draft")', '', '', 'def rebuild(home: Path) -> list[dict]:', '    """posts.json is a cache: rebuild it from every post folder."""', '    posts = []', '    for folder in post_folders(home):', '        for f in sorted(folder.glob("*.md")):', '            posts.append(index_entry(f))', '    write_json(home / "posts.json", posts)', '    return posts'] }),
    s2: () => terminal("zsh — ~/Projects/build-in-public — 120×32", [
      [[Pr, "~/Projects/build-in-public"], [P, " $ buildinpublic posts"]], [[G, ""]],
      [[P, "1109-two-status-lists     "], [A, "draft      "], [P, "My tool had two opinions about one post"]],
      [[P, "1109-stripe-504           "], [V, "scheduled  "], [P, "A 504 cost one user $49 twice"]],
      [[P, "1109-webhooks-li          "], [B, "approved   "], [P, "Webhooks arrive at least twice"]],
      [[P, "1107-coffee-receipt       "], [Gr, "posted     "], [P, "Coffee-stained receipt, 11 of 12 line items"]],
      [[P, "1105-windows              "], [Gr, "posted     "], [P, "Windows took 64 minutes. Testing took 3 days."]],
      [[P, "1103-all-projects         "], [Gr, "posted     "], [P, "One journal for every project"]], [[G, ""]],
      [[G, "Indexed "], [P, "11 posts"], [G, " from 3 folders (2 repos + ~/.buildinpublic/posts)."]],
      [[G, "2 day(s) since last post."]], [[G, ""]],
      [[Pr, "~/Projects/build-in-public"], [P, " $ ▍"]]]),
    s3: () => editor({ file: "stripe.ts", other: "idempotency.ts", lang: "ts", crumbs: "api › webhooks › stripe.ts › handleInvoicePaid", active: 3, status: "Ln 6, Col 9   UTF-8   TypeScript",
      tree: [["api", 0], ["lib", 1], ["webhooks", 1], ["stripe.ts", 2], ["stripe.test.ts", 2], ["web", 0], ["app", 1], ["package.json", 0]],
      lines: ['import Stripe from "stripe";', 'import { db } from "../lib/db";', 'import { seen, markSeen, ok } from "../lib/idempotency";', '', 'export async function handleInvoicePaid(event: Stripe.Event) {', '  // Stripe retries any webhook that does not answer in 10s.', '  const key = `stripe:${event.id}`;', '  if (await seen(key)) return ok("duplicate");', '', '  const invoice = event.data.object as Stripe.Invoice;', '  await db.charges.insert({', '    id: key,', '    customer: invoice.customer,', '    amount: invoice.amount_paid,', '  });', '  await markSeen(key);', '  return ok();', '}'] }),
    s4: billing,
    s5: landing,
    s6: parser,
    s7: () => editor({ file: "line_items.py", other: "ocr.py", lang: "py", crumbs: "parser › line_items.py › group_rows", active: 2, status: "Ln 1, Col 1   UTF-8   Python 3.12",
      tree: [["parser", 0], ["ocr.py", 1], ["line_items.py", 1], ["receipts", 1], ["web", 0], ["app", 1], ["tests", 0]],
      lines: ['from dataclasses import dataclass', '', '', 'def group_rows(words: list[Word], gap: float = 0.6) -> list[Row]:', '    """Group OCR words into receipt rows by vertical overlap."""', '    rows: list[Row] = []', '    for w in sorted(words, key=lambda w: (w.top, w.left)):', '        row = next((r for r in rows if overlaps(r, w, gap)), None)', '        if row is None:', '            rows.append(Row([w]))', '        else:', '            row.add(w)', '    return [r for r in rows if r.has_amount()]', '', '', 'def overlaps(row: Row, w: Word, gap: float) -> bool:', '    top, bottom = row.span()', '    return w.top < bottom - gap * w.height and w.bottom > top'] }),
    s8: () => terminal("Windows PowerShell", [
      [[B, "PS C:\\Users\\you>"], [P, ' schtasks /query /tn "BuildInPublic*" /fo table']], [[G, ""]],
      [[P, "TaskName                       Next Run Time            Status"]], [[G, "=============================  =======================  ======"]],
      [[P, "\\BuildInPublic-sweep           11/5/2026 5:00:00 PM     "], [Gr, "Ready"]],
      [[P, "\\BuildInPublic-summary         11/6/2026 12:00:00 AM    "], [Gr, "Ready"]],
      [[P, "\\BuildInPublic-nudge           11/5/2026 6:00:00 PM     "], [Gr, "Ready"]], [[G, ""]],
      [[B, "PS C:\\Users\\you>"], [P, " buildinpublic schedule status"]],
      [[P, "sweep     every 30 min   "], [Gr, "ok"]], [[P, "summary   daily 00:00    "], [Gr, "ok"]], [[P, "nudge     hourly         "], [Gr, "ok"]], [[G, ""]],
      [[B, "PS C:\\Users\\you>"], [P, " ▍"]]]),
  };
  // what to point at in each capture, for the Spotlight template
  const REGIONS = {
    s1: { x: 296, y: 248, w: 470, h: 232, label: "One list of statuses" }, s2: { x: 14, y: 304, w: 980, h: 62, label: "Every post, from every folder" },
    s3: { x: 296, y: 254, w: 760, h: 62, label: "The two lines that stop a double charge" }, s4: { x: 254, y: 420, w: 1000, h: 50, label: "The retry, now ignored" },
    s5: { x: 66, y: 428, w: 548, h: 88, label: "One command to install" }, s6: { x: 698, y: 694, w: 556, h: 44, label: "The one it missed" },
    s7: { x: 296, y: 166, w: 760, h: 34, label: "Rows by vertical overlap" }, s8: { x: 14, y: 168, w: 900, h: 92, label: "Three jobs, all Ready" },
  };
  const raw = id => (RAW[id] || RAW.s4)();
  const CODE_LINES = { s1: 23, s3: 18, s7: 18 };
  const PHONE_X = { s1: 236, s3: 236, s7: 236, s4: 240, s5: 50, s6: 690, s2: 0, s8: 0 };

  /* ------------------------------------------------------------ templates */
  const BG = {
    dusk: ["#7f5af0", "#2cb1bc"], peach: ["#ffd3a5", "#fd6585"], ocean: ["#2193b0", "#6dd5ed"], mint: ["#d4fc79", "#96e6a1"],
    ink: ["#1f2023", "#3a3d44"], paper: ["#f3efe7"], snow: ["#ffffff"], night: ["#0f1117"],
  };
  const ASPECTS = { auto: null, "16:9": [1600, 900], "1.91:1": [1910, 1000], "1:1": [1400, 1400], "4:5": [1280, 1600] };
  const ASPECT_NOTES = { auto: "Natural size", "16:9": "Best for X", "1.91:1": "LinkedIn link size", "1:1": "Square, works everywhere", "4:5": "Tall, LinkedIn and X" };
  const TEMPLATES = [
    { key: "original", name: "Original", d: "As captured, nothing added.", opts: ["aspect", "bg"] },
    { key: "macos", name: "macOS window", d: "Window frame with a title, on a backdrop.", opts: ["aspect", "bg", "title", "pad", "radius", "shadow"] },
    { key: "browser", name: "Browser", d: "Browser frame with the page address.", opts: ["aspect", "bg", "url", "pad", "radius", "shadow"] },
    { key: "gradient", name: "Gradient", d: "Rounded screenshot floating on a gradient.", opts: ["aspect", "bg", "pad", "radius", "shadow"] },
    { key: "code", name: "Code card", d: "Just the code, in a dark card. Best for code.", opts: ["aspect", "bg", "title", "pad", "shadow"] },
    { key: "social", name: "Social card", d: "Headline and handle above the screenshot.", opts: ["aspect", "bg", "title", "handle", "radius"] },
    { key: "spotlight", name: "Spotlight", d: "Dims everything except one part, with a label.", opts: ["aspect", "bg", "label"] },
    { key: "beforeafter", name: "Before / after", d: "Two screenshots side by side, labelled.", opts: ["aspect", "bg", "other", "radius"] },
    { key: "phone", name: "Phone", d: "Inside a phone frame, cropped to fit.", opts: ["aspect", "bg"] },
    { key: "polaroid", name: "Polaroid", d: "A tilted photo with a handwritten caption.", opts: ["aspect", "bg", "title"] },
  ];
  const DEFAULT_BG = { original: "snow", macos: "dusk", browser: "ocean", gradient: "peach", code: "dusk", social: "snow", spotlight: "ink", beforeafter: "paper", phone: "mint", polaroid: "paper" };
  function defaults(shot, id, tpl) {
    return { aspect: tpl === "original" ? "auto" : tpl === "phone" || tpl === "polaroid" ? "4:5" : "16:9", bg: DEFAULT_BG[tpl], pad: 72, radius: 14, shadow: true,
      title: shot.cap, handle: "@you · building in public", url: shot.kind === "app" ? (shot.url || shot.cap) : "localhost:3000", label: (REGIONS[id] || {}).label || "Look here", other: shot.other || null };
  }

  let n = 0;
  function render(shot, id, o) {
    const base = shot.from || id, tpl = shot.tpl || "original";
    o = Object.assign(defaults(shot, base, tpl), shot.opts || {}, o || {});
    if (!shot.tpl && !o._force) return { svg: wrap(W0, H0, raw(base)), w: W0, h: H0, inner: raw(base) };
    return compose(base, o._tpl || tpl, o);
  }
  const wrap = (w, h, inner, defs = "") => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}"><defs>${defs}</defs>${inner}</svg>`;

  function compose(base, tpl, o) {
    const id = "t" + (++n);
    let [Wd, Hd] = ASPECTS[o.aspect] || (tpl === "original" ? [W0, H0] : [1600, 1000]);
    const W = Wd, H = Hd, pad = tpl === "original" ? 0 : +o.pad, rad = +o.radius;
    let defs = "", body = "";
    const bg = BG[o.bg] || BG.snow, dark = ["ink", "night", "dusk", "ocean"].includes(o.bg);
    defs += bg.length > 1 ? `<linearGradient id="${id}-bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${bg[0]}"/><stop offset="1" stop-color="${bg[1]}"/></linearGradient>` : "";
    defs += `<filter id="${id}-sh" x="-20%" y="-20%" width="140%" height="150%"><feDropShadow dx="0" dy="${Math.round(W / 70)}" stdDeviation="${Math.round(W / 50)}" flood-color="#000" flood-opacity=".32"/></filter>`;
    const bgFill = bg.length > 1 ? `url(#${id}-bg)` : bg[0];
    body += R(0, 0, W, H, bgFill);
    let k = 0;
    const img = (x, y, w, h, opt = {}) => { const c = `${id}-c${++k}`; defs += `<clipPath id="${c}"><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${opt.r || 0}"/></clipPath>`;
      return `<g clip-path="url(#${c})"><svg x="${x}" y="${y}" width="${w}" height="${h}" viewBox="${opt.vb || `0 0 ${W0} ${H0}`}" preserveAspectRatio="xMidYMid ${opt.slice ? "slice" : "meet"}">${raw(opt.base || base)}</svg></g>`; };
    const fit = (bw, bh, ar = W0 / H0) => bw / bh > ar ? [bh * ar, bh] : [bw, bw / ar];
    const sh = o.shadow ? ` filter="url(#${id}-sh)"` : "";
    const wrapText = (text, x, y, size, maxW, max, opt) => { const per = Math.max(8, Math.floor(maxW / (size * .52))); const words = String(text).split(/\s+/); const lines = [""];
      words.forEach(w => { if ((lines[lines.length - 1] + " " + w).trim().length > per && lines.length < max) lines.push(w); else lines[lines.length - 1] = (lines[lines.length - 1] + " " + w).trim(); });
      return { svg: lines.map((l, i) => T(x, y + i * size * 1.18, l, Object.assign({ s: size }, opt))).join(""), h: lines.length * size * 1.18 }; };

    if (tpl === "original") {
      const [w, h] = fit(W, H); body += img((W - w) / 2, (H - h) / 2, w, h);
    } else if (tpl === "gradient") {
      const [w, h] = fit(W - 2 * pad, H - 2 * pad), x = (W - w) / 2, y = (H - h) / 2;
      body += R(x, y, w, h, "#000", rad, sh) + img(x, y, w, h, { r: rad });
    } else if (tpl === "macos" || tpl === "browser") {
      const bar = tpl === "macos" ? Math.round(W / 34) : Math.round(W / 20);
      const [w, ih] = fit(W - 2 * pad, H - 2 * pad - bar), x = (W - w) / 2, y = (H - ih - bar) / 2;
      const chrome = tpl === "macos" ? "#26272d" : "#e9eaee";
      body += R(x, y, w, ih + bar, chrome, rad, sh) + img(x, y + bar, w, ih, { r: 0 });
      const dot = (cx, col) => `<circle cx="${cx}" cy="${y + bar / 2}" r="${bar * .17}" fill="${col}"/>`;
      if (tpl === "macos") body += dot(x + bar * .55, "#ff5f57") + dot(x + bar * 1.05, "#febc2e") + dot(x + bar * 1.55, "#28c840") + T(x + w / 2, y + bar * .63, o.title, { s: bar * .38, c: "#a9abb3", a: "middle" });
      else { const ty = y + bar * .5; body += dot(x + bar * .35, "#ff5f57") + dot(x + bar * .65, "#febc2e") + dot(x + bar * .95, "#28c840");
        body += R(x + bar * 1.4, y + bar * .2, w - bar * 2, bar * .6, "#fff", bar * .3) + T(x + bar * 1.75, ty + bar * .12, "🔒  " + o.url, { s: bar * .3, c: "#5f6368" }); }
    } else if (tpl === "code") {
      // crop to the code itself: the editor panel down to the last line
      const ch0 = Math.min(732, 64 + (CODE_LINES[base] || 22) * 28), vb = `236 44 1040 ${ch0}`, ar = 1040 / ch0, head = Math.round(W / 26);
      const [w, h] = fit(W - 2 * pad - 2 * head * .6, H - 2 * pad - head - head * .6, ar), cw = w + head * 1.2, ch = h + head * 1.6, x = (W - cw) / 2, y = (H - ch) / 2;
      body += R(x, y, cw, ch, "#1e1f26", 18, sh) + img(x + head * .6, y + head, w, h, { vb, r: 6 });
      const dot = (cx, col) => `<circle cx="${cx}" cy="${y + head / 2}" r="${head * .14}" fill="${col}"/>`;
      body += dot(x + head * .6, "#ff5f57") + dot(x + head * 1, "#febc2e") + dot(x + head * 1.4, "#28c840") + T(x + cw / 2, y + head * .62, o.title, { s: head * .34, c: "#7d8293", a: "middle", f: MONO });
    } else if (tpl === "social") {
      const fg = dark ? "#f4f4f5" : "#18181b", mute = dark ? "#a1a1aa" : "#71717a", m = Math.round(W / 24);
      const hl = wrapText(o.title, m, m + W / 26, W / 26, W - 2 * m, 2, { f: SERIF, c: fg });
      body += hl.svg;
      const hy = m + hl.h + W / 60; body += `<circle cx="${m + W / 80}" cy="${hy + W / 120}" r="${W / 80}" fill="#ffc98a"/>` + T(m + W / 80 * 2.6, hy + W / 70, o.handle, { s: W / 62, c: mute });
      const top = hy + W / 30, [w, h] = fit(W - 2 * m, H - top - m * .6 - W / 40), x = (W - w) / 2;
      body += R(x, top, w, h, "#000", rad, ` filter="url(#${id}-sh)"`) + img(x, top, w, h, { r: rad });
      body += T(W - m, H - m * .35, "Build in Public", { s: W / 80, c: mute, a: "end", w: 600 });
    } else if (tpl === "spotlight") {
      const [w, h] = fit(W, H), x = (W - w) / 2, y = (H - h) / 2, s = w / W0, r = REGIONS[base] || { x: 300, y: 200, w: 500, h: 200 };
      const rx = x + r.x * s, ry = y + r.y * s, rw = r.w * s, rh = r.h * s;
      body += img(x, y, w, h);
      defs += `<mask id="${id}-m"><rect width="${W}" height="${H}" fill="#fff"/><rect x="${rx}" y="${ry}" width="${rw}" height="${rh}" rx="${10 * s}" fill="#000"/></mask>`;
      body += `<rect width="${W}" height="${H}" fill="#000" opacity=".58" mask="url(#${id}-m)"/>` + `<rect x="${rx}" y="${ry}" width="${rw}" height="${rh}" rx="${10 * s}" fill="none" stroke="#ffd23f" stroke-width="${4 * s + 1}"/>`;
      const fs = Math.max(16, W / 52), lw = o.label.length * fs * .56 + fs * 1.4, below = ry + rh + fs * 2.6 < H, ly = below ? ry + rh + fs * .7 : ry - fs * 2.4, lx = Math.min(Math.max(rx, 12), W - lw - 12);
      body += R(lx, ly, lw, fs * 1.8, "#ffd23f", fs * .9) + T(lx + fs * .7, ly + fs * 1.25, o.label, { s: fs, w: 700, c: "#1a1a1a" });
    } else if (tpl === "beforeafter") {
      const side = W / H >= 1.2, gap = Math.round(W / 40), m = Math.round(W / 22), other = o.other || base;
      const bw = side ? (W - 2 * m - gap) / 2 : W - 2 * m, bh = side ? H - 2 * m : (H - 2 * m - gap) / 2;
      const [w, h] = fit(bw, bh);
      [[other, "Before"], [base, "After"]].forEach(([b, lab], i) => {
        const x = side ? m + i * (bw + gap) + (bw - w) / 2 : (W - w) / 2, y = side ? (H - h) / 2 : m + i * (bh + gap) + (bh - h) / 2, fs = Math.max(14, W / 70);
        body += R(x, y, w, h, "#000", rad, ` filter="url(#${id}-sh)"`) + img(x, y, w, h, { r: rad, base: b });
        body += R(x + fs, y + fs, lab.length * fs * .62 + fs * 1.4, fs * 1.8, i ? "#16a34a" : "#52525b", fs * .9) + T(x + fs * 1.7, y + fs * 2.25, lab, { s: fs, w: 700, c: "#fff" });
      });
    } else if (tpl === "phone") {
      const ph = H * .86, pw = ph * .49, x = (W - pw) / 2, y = (H - ph) / 2, b = pw * .045;
      body += R(x, y, pw, ph, "#111214", pw * .14, sh) + R(x + b * .4, y + b * .4, pw - b * .8, ph - b * .8, "#2a2b30", pw * .13);
      // phones show a narrow slice, so start it where the interesting part is
      const sw = pw - 2 * b, shh = ph - 2 * b, vbw = H0 * sw / shh, px = Math.min(W0 - vbw, PHONE_X[base] ?? 0);
      body += img(x + b, y + b, sw, shh, { r: pw * .11, vb: `${px} 0 ${vbw} ${H0}`, slice: true });
      body += R(x + pw / 2 - pw * .16, y + b * 1.6, pw * .32, pw * .085, "#000", pw * .045);
    } else if (tpl === "polaroid") {
      const cw = Math.min(W * .78, H * .78 * 1.05), [w, h] = fit(cw - cw * .08, cw), ch = h + cw * .08 + cw * .2, x = (W - cw) / 2, y = (H - ch) / 2;
      body += `<g transform="rotate(-3 ${W / 2} ${H / 2})">` + R(x, y, cw, ch, "#fffdf8", 4, ` filter="url(#${id}-sh)"`) + img(x + cw * .04, y + cw * .04, w, h) +
        T(x + cw / 2, y + cw * .04 + h + cw * .12, o.title, { s: cw * .05, f: HAND, c: "#2b2b2b", a: "middle" }) + `</g>` +
        `<rect x="${W / 2 - cw * .1}" y="${y - cw * .03}" width="${cw * .2}" height="${cw * .06}" fill="#f5e6a8" opacity=".85" transform="rotate(4 ${W / 2} ${y})"/>`;
    }
    return { svg: wrap(W, H, body, defs), w: W, h: H };
  }

  function png(svg, w, h, scale = 1) {
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml;charset=utf-8" })), im = new Image();
      im.onload = () => { const c = document.createElement("canvas"); c.width = Math.round(w * scale); c.height = Math.round(h * scale); const x = c.getContext("2d"); x.drawImage(im, 0, 0, c.width, c.height); URL.revokeObjectURL(url); c.toBlob(b => b ? resolve(b) : reject(new Error("toBlob failed")), "image/png"); };
      im.onerror = e => { URL.revokeObjectURL(url); reject(e); };
      im.src = url;
    });
  }

  window.Shots = { raw, render, compose, png, TEMPLATES, BG, ASPECTS, ASPECT_NOTES, REGIONS, defaults };
})();
