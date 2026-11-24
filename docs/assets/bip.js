/* Bip, the Build in Public mascot: a soft 3D toy drawn as SVG.
 *
 * One drawing routine shared by the desk-pet mockup, the dashboard mockup and
 * the character sheet. Bip is a squishy jelly blob with bunny ears and little
 * feet, lit from the top left like a claymation figure: gradient shading, a
 * felt texture, glossy eyes and a soft contact shadow. Every part is still a
 * shape, so ears, face, feet and squash stay fully animatable.
 *
 *   Bip.draw(svg, { mood, theme, stage, scarf, hats, phones, fx,
 *                   sx, sy, feet, earAlt, look, blink, facing, frame })
 *   Bip.live(svg, () => opts)        breathes, blinks and wiggles on its own
 *
 * The <svg> needs viewBox="0 0 200 190". For the desk pet,
 * scripts/build_sprites.py renders each frame to a PNG with the same code.
 *
 * Bip.mascot(el, { who: "bip" | "sarthak", mood, ... }) renders either Bip or
 * Sarthak's charcoal buddy (static poses in design/mascot/), so pages can offer both.
 */
(function () {
  const NS = "http://www.w3.org/2000/svg";
  const THEMES = {
    peach:    { b: "#ffc98a", hi: "#fff3e0", sh: "#e0934a", k: "#ffb7bd", kd: "#ef8794", c: "#ff8f9c", e: "#2b2140", sclera: false },
    mint:     { b: "#a6e9c4", hi: "#f1fff7", sh: "#5bb98a", k: "#ffb7bd", kd: "#ef8794", c: "#ff8f9c", e: "#1f2b2a", sclera: false },
    sky:      { b: "#a9d3ff", hi: "#f2f8ff", sh: "#5f9fe6", k: "#ffc2cf", kd: "#f08aa3", c: "#ff8fa8", e: "#1c2440", sclera: false },
    lilac:    { b: "#d4b9ff", hi: "#f8f2ff", sh: "#9a77e6", k: "#ffb3d6", kd: "#ea7fb4", c: "#ff8fb8", e: "#2b2140", sclera: false },
    charcoal: { b: "#4b4e58", hi: "#8d919d", sh: "#24262d", k: "#ff9fab", kd: "#d9707f", c: "#ff8fa0", e: "#1a1b20", sclera: true },
  };
  // ear poses in degrees (left, right); 0 = straight up
  const EARS = { up: [-12, 12], perk: [-3, 3], back: [-36, 36], droop: [-62, 62], flop: [-12, 82], tilt: [-30, 5], proud: [-6, 6], twitch: [-12, 12], listen: [-2, -10] };
  const MOODS = {
    idle:      { eyes: "open",    mouth: "smile", ears: "up" },
    editing:   { eyes: "line",    mouth: "flat",  ears: "back",   prop: "laptop" },
    reading:   { eyes: "down",    mouth: "tiny",  ears: "tilt",   prop: "book", scan: true },
    testing:   { eyes: "open",    mouth: "o",     ears: "perk",   prop: "flask", look: 1 },
    waiting:   { eyes: "open",    mouth: "smile", ears: "perk",   prop: "sign", fx: "q", bounce: true },
    sleepy:    { eyes: "line",    mouth: "flat",  ears: "droop",  fx: "zz", hat: "nightcap" },
    curious:   { eyes: "open",    mouth: "o",     ears: "twitch", prop: "spark", look: 1, brows: "up" },
    idea:      { eyes: "open",    mouth: "smile", ears: "perk",   prop: "card" },
    happy:     { eyes: "happy",   mouth: "open",  ears: "up",     anim: "hop", wiggle: true },
    surprised: { eyes: "big",     mouth: "o",     ears: "perk",   fx: "bang", anim: "boing", brows: "high" },
    proud:     { eyes: "content", mouth: "smug",  ears: "proud",  prop: "star", wiggle: true },
    thinking:  { eyes: "up",      mouth: "flat",  ears: "tilt",   fx: "dots", brows: "one" },
    confused:  { eyes: ["open", "line"], mouth: "wavy", ears: "flop", fx: "q", brows: "tilt" },
    giggle:    { eyes: "happy",   mouth: "cat",   ears: "up",     anim: "giggle", wiggle: true },
    dizzy:     { eyes: "dizzy",   mouth: "wavy",  ears: "flop",   fx: "orbit", anim: "wobble" },
    petted:    { eyes: "content", mouth: "cat",   ears: "droop",  anim: "purr", fx: "hearts" },
    party:     { eyes: "happy",   mouth: "open",  ears: "proud",  hat: "party", anim: "dance", wiggle: true },
    listening: { eyes: "open",    mouth: "tiny",  ears: "listen", fx: "note" },
  };
  const CLIP_NAMES = ["none", "bud", "flower", "two flowers"];
  const PHONE_MOODS = ["editing", "reading", "testing", "thinking"];
  // Sarthak's charcoal buddy: seven rendered poses, mapped onto Bip's moods
  const POSE = { idle: "notebook", editing: "notebook", reading: "detective", testing: "detective", waiting: "thinking", sleepy: "sleepy",
    curious: "detective", idea: "notebook", happy: "excited", surprised: "excited", proud: "shipped", thinking: "thinking", confused: "grumpy",
    giggle: "excited", dizzy: "thinking", petted: "excited", party: "shipped", listening: "thinking" };
  const POSES = ["notebook", "shipped", "excited", "thinking", "detective", "grumpy", "sleepy"];

  let uid = 0;
  const f = n => +n.toFixed(2);

  function svg(o = {}) {
    const moodName = MOODS[o.mood] ? o.mood : "idle", M = MOODS[moodName], T = THEMES[o.theme] || THEMES.peach;
    const id = o._id || "b" + (++uid);
    const scarf = o.scarf === undefined ? { c: "#ef7d32", d: "#b9581b" } : o.scarf;
    const stage = o.stage ?? 2, frame = o.frame || 0, alt = frame % 6 < 3;
    const sx = o.sx ?? 1, sy = o.sy ?? 1, look = (M.look ?? (M.scan ? (Math.floor(frame / 10) % 2 ? 1 : -1) : (o.look || 0)));
    const blink = o.blink && ["open", "up", "big"].includes(Array.isArray(M.eyes) ? "x" : M.eyes);
    let [la, ra] = EARS[M.ears];
    if (M.ears === "twitch" && frame % 14 < 2) ra += 18;
    if (M.wiggle && o.earAlt) { la -= 9; ra += 9; }
    if (moodName === "listening" && o.earAlt) ra -= 5;
    const hat = M.hat && o.hats !== false ? M.hat : (o.phones && PHONE_MOODS.includes(moodName) ? "phones" : null);
    const u = s => `url(#${id}-${s})`;

    const defs = `<defs>
      <radialGradient id="${id}-body" cx="36%" cy="26%" r="78%"><stop offset="0" stop-color="${T.hi}"/><stop offset=".42" stop-color="${T.b}"/><stop offset="1" stop-color="${T.sh}"/></radialGradient>
      <radialGradient id="${id}-ear" cx="34%" cy="22%" r="85%"><stop offset="0" stop-color="${T.hi}"/><stop offset=".5" stop-color="${T.b}"/><stop offset="1" stop-color="${T.sh}"/></radialGradient>
      <linearGradient id="${id}-inner" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${T.k}"/><stop offset="1" stop-color="${T.kd}"/></linearGradient>
      <radialGradient id="${id}-foot" cx="40%" cy="30%" r="80%"><stop offset="0" stop-color="${T.b}"/><stop offset="1" stop-color="${T.sh}"/></radialGradient>
      <radialGradient id="${id}-eye" cx="38%" cy="30%" r="75%"><stop offset="0" stop-color="#55476f"/><stop offset=".55" stop-color="${T.sclera ? "#20222a" : T.e}"/><stop offset="1" stop-color="#120d1c"/></radialGradient>
      <radialGradient id="${id}-cheek"><stop offset="0" stop-color="${T.c}" stop-opacity=".8"/><stop offset="1" stop-color="${T.c}" stop-opacity="0"/></radialGradient>
      <radialGradient id="${id}-shadow"><stop offset="0" stop-color="#000" stop-opacity=".2"/><stop offset="1" stop-color="#000" stop-opacity="0"/></radialGradient>
      <linearGradient id="${id}-scarf" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${scarf?.c || "#000"}"/><stop offset="1" stop-color="${scarf?.d || "#000"}"/></linearGradient>
      <linearGradient id="${id}-dark" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#454a57"/><stop offset="1" stop-color="#1c1f27"/></linearGradient>
      <filter id="${id}-blur" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="3"/></filter>
      <filter id="${id}-felt" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency=".95" numOctaves="2" seed="7" stitchTiles="stitch"/><feColorMatrix type="saturate" values="0"/><feComponentTransfer><feFuncA type="table" tableValues="0 .16"/></feComponentTransfer></filter>
      <clipPath id="${id}-clip"><path d="${BODY}"/></clipPath>
    </defs>`;

    // ears (behind the body), rotating around their base
    const ear = (x, deg) => `<g transform="translate(${x} 72) rotate(${deg})">
        <path d="M-15 8 C-19 -28 -11 -60 0 -62 C11 -60 19 -28 15 8 Z" fill="${u("ear")}"/>
        <path d="M-7.5 2 C-9.5 -24 -5.5 -48 0 -50 C5.5 -48 9.5 -24 7.5 2 Z" fill="${u("inner")}" opacity=".95"/>
        <path d="M-10 -20 C-11 -38 -6 -54 -2 -56" stroke="#fff" stroke-opacity=".45" stroke-width="3" fill="none" stroke-linecap="round"/></g>`;
    const feet = [-1, 1].map(s => { const up = o.feet === s ? 6 : 0; return `<ellipse cx="${100 + s * 27}" cy="${172 - up}" rx="20" ry="10.5" fill="${u("foot")}"/>`; }).join("");

    // face
    const fx = 100 + look * 5, ey = 106;
    const eye = (kind, x) => {
      const c = T.e;
      if (kind === "line") return `<path d="M${x - 9} 110 Q${x} 115 ${x + 9} 110" stroke="${c}" stroke-width="3.6" fill="none" stroke-linecap="round"/>`;
      if (kind === "happy") return `<path d="M${x - 9} 111 Q${x} 98 ${x + 9} 111" stroke="${c}" stroke-width="3.6" fill="none" stroke-linecap="round"/>`;
      if (kind === "content") return `<path d="M${x - 9} 104 Q${x} 114 ${x + 9} 104" stroke="${c}" stroke-width="3.6" fill="none" stroke-linecap="round"/>`;
      if (kind === "dizzy") return `<path d="M${x} ${ey} m-8 0 a8 8 0 1 1 8 8 a5 5 0 1 1 -5 -5 a2 2 0 1 1 2 2" stroke="${c}" stroke-width="3" fill="none" stroke-linecap="round"/>`;
      const big = kind === "big", up = kind === "up" ? -5 : 0, down = kind === "down" ? 4 : 0;
      const rx = big ? 13 : 10, ry = big ? 16 : down ? 8 : 13, cy = ey + up + down;
      let s = "";
      if (T.sclera) {
        s += `<ellipse cx="${x}" cy="${cy}" rx="${rx + 3}" ry="${ry + 1}" fill="#f6f1e8"/><circle cx="${x + look * 2}" cy="${cy + 2 + (up ? -3 : 0)}" r="${big ? 9 : 7.5}" fill="${u("eye")}"/>
              <circle cx="${x - 2 + look * 2}" cy="${cy - 2}" r="2.6" fill="#fff"/>`;
      } else {
        s += `<ellipse cx="${x}" cy="${cy}" rx="${rx}" ry="${ry}" fill="${u("eye")}"/>
              <ellipse cx="${x - 3.5}" cy="${cy - 5}" rx="${big ? 4.6 : 3.8}" ry="${big ? 5.2 : 4.2}" fill="#fff"/><circle cx="${x + 4}" cy="${cy + 5}" r="${big ? 2.6 : 1.9}" fill="#fff" opacity=".85"/>`;
        if (big) s += `<path d="M${x + 5} ${cy - 9} l1.4 3 3 1.4 -3 1.4 -1.4 3 -1.4 -3 -3 -1.4 3 -1.4z" fill="#fff"/>`;
      }
      if (down) s += `<path d="M${x - rx - 1} ${cy - 4} Q${x} ${cy - 11} ${x + rx + 1} ${cy - 4}" stroke="${c}" stroke-width="3" fill="none" stroke-linecap="round"/>`;
      return s;
    };
    const [le, re] = Array.isArray(M.eyes) ? M.eyes : [M.eyes, M.eyes];
    const brow = (x, dy, tilt) => `<path d="M${x - 7} ${88 + dy + tilt} Q${x} ${84 + dy} ${x + 7} ${88 + dy - tilt}" stroke="${T.e}" stroke-opacity=".75" stroke-width="2.6" fill="none" stroke-linecap="round"/>`;
    let brows = "";
    if (M.brows === "high") brows = brow(fx - 22, -6, 0) + brow(fx + 22, -6, 0);
    if (M.brows === "up") brows = brow(fx - 22, -1, 0) + brow(fx + 22, -1, 0);
    if (M.brows === "one") brows = brow(fx + 22, -4, 1.5);
    if (M.brows === "tilt") brows = brow(fx - 22, 1, -2) + brow(fx + 22, -3, 2);
    const mo = { // mouths at (fx, 128)
      smile: `<path d="M${fx - 8} 126 Q${fx} 134 ${fx + 8} 126" stroke="${T.e}" stroke-width="3.4" fill="none" stroke-linecap="round"/>`,
      open: `<path d="M${fx - 10} 124 Q${fx} 142 ${fx + 10} 124 Z" fill="#3a1f2e"/><ellipse cx="${fx}" cy="133.5" rx="5.2" ry="3.2" fill="#ff7d8f"/>`,
      o: `<ellipse cx="${fx}" cy="130" rx="5" ry="6" fill="#3a1f2e"/>`,
      flat: `<path d="M${fx - 6} 129 L${fx + 6} 129" stroke="${T.e}" stroke-width="3.2" stroke-linecap="round"/>`,
      wavy: `<path d="M${fx - 10} 129 q5 -5 10 0 t10 0" stroke="${T.e}" stroke-width="3" fill="none" stroke-linecap="round"/>`,
      smug: `<path d="M${fx - 8} 130 Q${fx + 2} 132 ${fx + 9} 124" stroke="${T.e}" stroke-width="3.2" fill="none" stroke-linecap="round"/>`,
      cat: `<path d="M${fx - 10} 126 q5 6 10 0 q5 6 10 0" stroke="${T.e}" stroke-width="3" fill="none" stroke-linecap="round"/>`,
      tiny: `<ellipse cx="${fx}" cy="130" rx="3" ry="3.2" fill="#3a1f2e"/>`,
    }[M.mouth];
    const face = `<ellipse cx="${fx - 36}" cy="124" rx="13" ry="7.5" fill="${u("cheek")}"/><ellipse cx="${fx + 36}" cy="124" rx="13" ry="7.5" fill="${u("cheek")}"/>
      ${blink ? eye("line", fx - 22) + eye("line", fx + 22) : eye(le, fx - 22) + eye(re, fx + 22)}${brows}${mo}`;

    // body: shading, felt, shine
    const body = `<path d="${BODY}" fill="${u("body")}"/>
      <g clip-path="${u("clip")}">
        <ellipse cx="100" cy="166" rx="78" ry="20" fill="${T.sh}" opacity=".35" filter="${u("blur")}"/>
        <rect x="20" y="48" width="160" height="124" filter="${u("felt")}" style="mix-blend-mode:multiply"/>
      </g>
      <ellipse cx="66" cy="76" rx="20" ry="9" transform="rotate(-22 66 76)" fill="#fff" opacity=".55" filter="${u("blur")}"/>
      <circle cx="84" cy="64" r="3.4" fill="#fff" opacity=".8"/>`;

    // scarf in the project's colour
    const scarfSvg = scarf ? `<g clip-path="${u("clip")}"><path d="M18 136 Q100 152 182 136 L182 154 Q100 170 18 154 Z" fill="${u("scarf")}"/>
        ${[30, 44, 58, 72, 86, 100, 114, 128, 142, 156, 170].map(x => { const y = 137 + 8 * (1 - ((x - 100) / 82) ** 2); return `<path d="M${x} ${f(y + 1)} v15" stroke="#000" stroke-opacity=".09" stroke-width="2.2" stroke-linecap="round"/>`; }).join("")}
        <path d="M18 138 Q100 154 182 138" stroke="#fff" stroke-opacity=".3" stroke-width="2.5" fill="none"/>
        <path d="M18 154 Q100 170 182 154" stroke="#000" stroke-opacity=".14" stroke-width="3" fill="none"/></g>
      <g transform="rotate(8 136 150)"><rect x="128" y="146" width="17" height="34" rx="6" fill="${u("scarf")}"/>
        <path d="M131 156 h11 M131 164 h11 M131 172 h11" stroke="#000" stroke-opacity=".1" stroke-width="2"/>
        <path d="M131 180 v5 M136.5 180 v6 M142 180 v5" stroke="${scarf.d}" stroke-width="2.4" stroke-linecap="round"/></g>` : "";

    // hats
    let hatSvg = "";
    if (hat === "phones") hatSvg = `<path d="M30 116 C24 34 176 34 170 116" stroke="url(#${id}-dark)" stroke-width="9" fill="none" stroke-linecap="round"/>
      <path d="M34 100 C34 46 166 46 166 100" stroke="#fff" stroke-opacity=".18" stroke-width="2.5" fill="none" stroke-linecap="round"/>
      <rect x="12" y="92" width="25" height="42" rx="11" fill="url(#${id}-dark)"/><rect x="163" y="92" width="25" height="42" rx="11" fill="url(#${id}-dark)"/>
      <rect x="17" y="98" width="6" height="20" rx="3" fill="#fff" opacity=".15"/>`;
    if (hat === "party") hatSvg = `<path d="M100 6 L80 60 Q100 67 120 60 Z" fill="#ff5a7a"/><path d="M93 24 L107 24 L111 36 L89 36 Z M85 46 L115 46 L118 54 L82 54 Z" fill="#ffd23f"/>
      <path d="M100 6 L84 52" stroke="#fff" stroke-opacity=".35" stroke-width="3" stroke-linecap="round"/><circle cx="100" cy="7" r="7.5" fill="#ffd23f"/><circle cx="97.5" cy="4.5" r="2.4" fill="#fff" opacity=".7"/>`;
    if (hat === "nightcap") hatSvg = `<path d="M58 66 Q66 26 110 22 Q150 20 162 50 Q142 40 136 66 Z" fill="#3f51b5"/><path d="M76 40 Q100 26 140 30" stroke="#fff" stroke-opacity=".2" stroke-width="3" fill="none" stroke-linecap="round"/>
      <rect x="54" y="56" width="88" height="16" rx="8" fill="#f4f1ea"/><circle cx="162" cy="52" r="9" fill="#f4f1ea"/>`;

    // streak flower clip at the base of the right ear
    const flower = (x, y, c, r) => [0, 72, 144, 216, 288].map(a => `<circle cx="${f(x + Math.cos(a * Math.PI / 180) * r)}" cy="${f(y + Math.sin(a * Math.PI / 180) * r)}" r="${r * .75}" fill="${c}"/>`).join("") + `<circle cx="${x}" cy="${y}" r="${r * .6}" fill="#ffd23f"/>`;
    const clip = stage === 1 ? `<path d="M140 70 q-8 -10 2 -14 q6 8 -2 14z" fill="#4cc584"/><circle cx="143" cy="62" r="4.5" fill="#ff8fb8"/>`
      : stage === 2 ? flower(141, 66, "#ff8fb8", 5.5) : stage >= 3 ? flower(138, 66, "#ff8fb8", 5.5) + flower(154, 76, "#ffa94d", 4.4) : "";

    // props held in front or beside
    let prop = "";
    if (M.prop === "laptop") prop = `<path d="M56 124 L144 124 L148 168 L52 168 Z" fill="url(#${id}-dark)"/><path d="M60 128 L140 128" stroke="#fff" stroke-opacity=".12" stroke-width="2"/>
      <circle cx="100" cy="146" r="5" fill="#9fb2ff" opacity="${alt ? .95 : .45}"/><rect x="42" y="166" width="116" height="9" rx="4.5" fill="#c3c9d3"/><rect x="42" y="166" width="116" height="3" rx="1.5" fill="#fff" opacity=".5"/>`;
    if (M.prop === "book") prop = `<path d="M50 140 Q76 130 100 140 L100 172 Q76 162 50 172 Z" fill="#e0742a"/><path d="M150 140 Q124 130 100 140 L100 172 Q124 162 150 172 Z" fill="#c95f1c"/>
      <path d="M54 137 Q78 128 100 137 L100 166 Q78 157 54 166 Z" fill="#fffdf7"/><path d="M146 137 Q122 128 100 137 L100 166 Q122 157 146 166 Z" fill="#f3efe6"/>
      <path d="M62 144 Q78 139 94 145 M62 151 Q78 146 94 152 M106 145 Q122 139 138 144 M106 152 Q122 146 138 151" stroke="#c9c3b6" stroke-width="2" fill="none"/>`;
    if (M.prop === "flask") prop = `<path d="M158 98 h14 v20 l16 30 a9 9 0 0 1 -8 13 h-30 a9 9 0 0 1 -8 -13 l16 -30 z" fill="#e8f2fb" fill-opacity=".75" stroke="#9fb0c0" stroke-width="2"/>
      <path d="M148 140 h34 l6 10 a9 9 0 0 1 -8 11 h-30 a9 9 0 0 1 -8 -11 z" fill="#4cc584"/><circle cx="${alt ? 160 : 170}" cy="${alt ? 146 : 140}" r="2.6" fill="#fff" opacity=".8"/><circle cx="${alt ? 172 : 162}" cy="${alt ? 136 : 132}" r="1.8" fill="#fff" opacity=".7"/>
      <rect x="160" y="100" width="3" height="16" rx="1.5" fill="#fff" opacity=".7"/>`;
    if (M.prop === "sign") { const b = M.bounce && alt ? -3 : 0; prop = `<path d="M170 ${150 + b} L170 ${64 + b}" stroke="#b87a43" stroke-width="5" stroke-linecap="round"/>
      <rect x="146" y="${20 + b}" width="48" height="44" rx="10" fill="#fffdf7" stroke="#e6e0d4" stroke-width="2"/><text x="170" y="${54 + b}" text-anchor="middle" font-family="ui-rounded, system-ui, sans-serif" font-weight="800" font-size="32" fill="#4c6ef5">?</text>`; }
    if (M.prop === "card") prop = `<g transform="rotate(10 166 120)"><rect x="150" y="100" width="32" height="40" rx="5" fill="#fffdf7" stroke="#e6e0d4" stroke-width="2"/><path d="M157 112 h18 M157 120 h14 M157 128 h18" stroke="#c9c3b6" stroke-width="2.4" stroke-linecap="round"/></g>`;
    if (M.prop === "spark") prop = alt || o.still ? `<path d="M170 22 l4 10 10 4 -10 4 -4 10 -4 -10 -10 -4 10 -4z" fill="#ffd23f"/><circle cx="186" cy="20" r="3" fill="#ffd23f"/>` : `<path d="M170 26 l3 7 7 3 -7 3 -3 7 -3 -7 -7 -3 7 -3z" fill="#ffd23f" opacity=".7"/>`;
    if (M.prop === "star") prop = `<path d="M170 18 l5.3 10.8 11.9 1.7 -8.6 8.4 2 11.8 -10.6 -5.6 -10.6 5.6 2 -11.8 -8.6 -8.4 11.9 -1.7z" fill="#ffc23a" stroke="#f0a400" stroke-width="1.5" stroke-linejoin="round"/>`;

    let fxs = "";
    if (o.fx) {
      const t = (x, y, s, c, sz = 22) => `<text x="${x}" y="${y}" font-family="ui-rounded, system-ui, sans-serif" font-weight="800" font-size="${sz}" fill="${c}">${s}</text>`;
      fxs = { zz: t(158, 40, "z", "#9aa0ad") + t(172, 22, "z", "#9aa0ad", 15), bang: t(166, 44, "!", "#ff5a7a", 30), q: M.prop === "sign" ? "" : t(164, 44, "?", "#4c6ef5", 28),
        dots: t(154, 46, "···", "#9aa0ad", 26), note: t(162, 44, "♪", "#4c6ef5", 26), hearts: t(150, 44, "♥", "#ff5a7a", 22) + t(168, 26, "♥", "#ff8fa8", 15),
        orbit: `<path d="M62 30 l2.4 5 5 2.4 -5 2.4 -2.4 5 -2.4 -5 -5 -2.4 5 -2.4z M138 22 l2 4 4 2 -4 2 -2 4 -2 -4 -4 -2 4 -2z" fill="#ffc23a"/>` }[M.fx] || "";
    }

    const shadow = `<ellipse cx="100" cy="181" rx="${f(64 * sx)}" ry="8" fill="${u("shadow")}"/>`;
    const squash = `translate(100 182) scale(${f(sx)} ${f(sy)}) translate(-100 -182)`;
    const flip = o.facing < 0 ? ` transform="translate(200 0) scale(-1 1)"` : "";
    return `${defs}${shadow}<g${flip}><g transform="${squash}">${ear(70, la)}${ear(130, ra)}${feet}${body}${scarfSvg}${face}${clip}${hatSvg}${prop}</g>${fxs}</g>`;
  }
  // a soft rounded blob: wider at the bottom, rounder on top
  const BODY = "M25 120 C25 74 52 52 100 52 C148 52 175 74 175 120 C175 154 150 170 100 170 C50 170 25 154 25 120 Z";

  function ensure(el) {
    if (!el.getAttribute("viewBox")) el.setAttribute("viewBox", "0 0 200 190");
    if (!el._bipId) el._bipId = "b" + (++uid);
    return el._bipId;
  }
  function draw(el, o = {}) { const id = ensure(el); el.innerHTML = svg(Object.assign({}, o, { _id: id })); }

  // Sarthak's buddy (or Bip) in any container: <span> for an <img>, or the svg itself for Bip
  function mascot(el, o = {}) {
    if (o.who === "sarthak") {
      const src = `${Bip.assetBase}mascot/${POSE[o.mood] || "notebook"}.webp`;
      let img = el.querySelector("img.sarthak");
      if (!img) { el.innerHTML = ""; img = new Image(); img.className = "sarthak"; img.alt = ""; img.decoding = "async"; img.draggable = false; el.append(img); }
      if (img.getAttribute("src") !== src) img.src = src;
      return;
    }
    let s = el.tagName.toLowerCase() === "svg" ? el : el.querySelector("svg.bip");
    if (!s) { el.innerHTML = ""; s = document.createElementNS(NS, "svg"); s.setAttribute("class", "bip"); el.append(s); }
    draw(s, o);
  }

  // Breathes (CSS), blinks and wiggles on its own; redraws only when something changed.
  let styled = false;
  function live(el, getOpts) {
    if (!styled) {
      styled = true;
      const st = document.createElement("style");
      st.textContent = `.bip-live{transform-origin:50% 95%;animation:bip-breathe 2.8s ease-in-out infinite}
        @keyframes bip-breathe{50%{transform:scale(1.025,.972)}}
        .bip-live img.sarthak{width:100%;height:100%;object-fit:contain;display:block}
        :root[data-theme="dark"] img.sarthak{filter:drop-shadow(0 0 .6px rgba(255,255,255,.45)) drop-shadow(0 0 10px rgba(255,255,255,.06))}
        @media (prefers-color-scheme: dark){:root:not([data-theme="light"]) img.sarthak{filter:drop-shadow(0 0 .6px rgba(255,255,255,.45)) drop-shadow(0 0 10px rgba(255,255,255,.06))}}
        @media (prefers-reduced-motion: reduce){.bip-live{animation:none}}`;
      document.head.append(st);
    }
    el.classList.add("bip-live");
    let last = "", frame = 0, blinkUntil = 0, stopped = false;
    const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const tick = () => {
      if (stopped) return;
      const now = performance.now(), o = getOpts() || {}, M = MOODS[o.mood] || MOODS.idle; frame++;
      if (!reduce && Math.random() < .02) blinkUntil = now + 140;
      const moving = !reduce && (M.wiggle || M.ears === "twitch" || M.prop || M.scan || o.who === "sarthak");
      const st = { frame: moving ? frame >> 1 : 0, earAlt: !reduce && M.wiggle && Math.floor(now / 170) % 2 === 0, blink: now < blinkUntil };
      const key = JSON.stringify([o, st]);
      if (key !== last) { last = key; mascot(el, Object.assign({}, o, st)); }
    };
    tick();
    const iv = setInterval(tick, 80);
    return { stop() { stopped = true; clearInterval(iv); }, redraw() { last = ""; tick(); } };
  }

  window.Bip = { draw, svg, live, mascot, MOODS, THEMES, CLIP_NAMES, POSE, POSES, assetBase: "" };
})();
