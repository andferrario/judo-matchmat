"""Self-contained HTML page listing every match, with athlete search."""

from __future__ import annotations

import html
import json
from dataclasses import asdict
from pathlib import Path

from .models import VideoIndex


def build(videos: list[VideoIndex], title: str = "Matches") -> str:
    data = [
        {
            "title": v.title,
            "matches": [{**asdict(m), "link": v.link(m)} for m in v.matches],
        }
        for v in sorted(videos, key=lambda v: v.title)
    ]
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return _TEMPLATE.replace("__TITLE__", html.escape(title)).replace("__DATA__", payload)


def write(results_dir: Path, title: str = "Matches") -> Path:
    videos = [VideoIndex.load(p) for p in sorted(results_dir.glob("*.json"))]
    out = results_dir / "index.html"
    out.write_text(build(videos, title), encoding="utf-8")
    return out


_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root { --bg:#fafaf9; --fg:#1c1917; --muted:#78716c; --line:#e7e5e4; --card:#fff;
        --white:#f5f5f4; --blue:#1d4ed8; --accent:#b91c1c; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#1c1917; --fg:#f5f5f4; --muted:#a8a29e; --line:#44403c; --card:#292524;
          --white:#44403c; --blue:#60a5fa; --accent:#f87171; }
}
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--fg);
       font:15px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width:960px; margin:0 auto; padding:24px 16px 64px; }
h1 { font-size:22px; margin:0 0 4px; }
.sub { color:var(--muted); margin:0 0 20px; }
input { width:100%; padding:12px 14px; font:inherit; color:inherit; background:var(--card);
        border:1px solid var(--line); border-radius:10px; margin-bottom:20px; }
input:focus { outline:2px solid var(--accent); outline-offset:1px; }
h2 { font-size:15px; margin:28px 0 8px; color:var(--muted); font-weight:600; }
.match { display:grid; grid-template-columns:72px 1fr auto; gap:12px; align-items:center;
         padding:10px 12px; background:var(--card); border:1px solid var(--line);
         border-radius:10px; margin-bottom:6px; }
.time { font-variant-numeric:tabular-nums; color:var(--muted); }
.who { min-width:0; }
.who b { font-weight:600; }
.who button { all:unset; cursor:pointer; border-bottom:1px dotted var(--muted); }
.who button:hover { color:var(--accent); }
.club { color:var(--muted); font-size:13px; }
.vs { color:var(--muted); margin:0 6px; }
.dot { display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:6px;
       border:1px solid var(--muted); vertical-align:middle; }
.dot.w { background:var(--white); } .dot.b { background:var(--blue); border-color:var(--blue); }
.meta { font-size:13px; color:var(--muted); margin-top:2px; }
a.play { color:var(--accent); text-decoration:none; font-weight:600; white-space:nowrap; }
a.play:hover { text-decoration:underline; }
.empty { color:var(--muted); padding:24px 0; }
@media (max-width:560px) {
  .match { grid-template-columns:1fr auto; }
  .time { grid-column:1 / -1; }
}
</style>
</head>
<body>
<main>
  <h1>__TITLE__</h1>
  <p class="sub" id="summary"></p>
  <input id="q" type="search" placeholder="Search athlete, club, category…" autocomplete="off">
  <div id="list"></div>
</main>
<script>
const DATA = __DATA__;
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const hms = (s) => { const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = s % 60;
  return (h ? h + ":" + String(m).padStart(2, "0") : m) + ":" + String(x).padStart(2, "0"); };
const fold = (s) => s.normalize("NFD").replace(/[\\u0300-\\u036f]/g, "").toLowerCase();
const total = DATA.reduce((n, v) => n + v.matches.length, 0);
$("#summary").textContent = `${total} matches in ${DATA.length} videos`;

function athlete(a, cls) {
  return `<span class="dot ${cls}"></span><button data-name="${esc(a.name)}"><b>${esc(a.name)}</b></button>`
       + (a.club ? ` <span class="club">${esc(a.club)}</span>` : "");
}

function render() {
  const words = fold($("#q").value).split(/\\s+/).filter(Boolean);
  let html = "", shown = 0;
  for (const v of DATA) {
    const rows = v.matches.filter((m) => {
      const hay = fold([m.white.name, m.white.club, m.blue.name, m.blue.club, m.category, m.round].join(" "));
      return words.every((w) => hay.includes(w));
    });
    if (!rows.length) continue;
    shown += rows.length;
    html += `<h2>${esc(v.title)}</h2>`;
    for (const m of rows) {
      html += `<div class="match"><span class="time">${hms(m.start)}</span>
        <div class="who">${athlete(m.white, "w")}<span class="vs">vs</span>${athlete(m.blue, "b")}
          <div class="meta">${esc([m.category, m.round].filter(Boolean).join(" · "))}</div></div>
        <a class="play" href="${esc(m.link)}" target="_blank" rel="noopener">Watch ▶</a></div>`;
    }
  }
  $("#list").innerHTML = html || `<p class="empty">No matches found.</p>`;
  if (words.length) $("#summary").textContent = `${shown} of ${total} matches`;
  else $("#summary").textContent = `${total} matches in ${DATA.length} videos`;
}

$("#q").addEventListener("input", render);
$("#list").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-name]");
  if (b) { $("#q").value = b.dataset.name; render(); window.scrollTo({ top: 0 }); }
});
render();
</script>
</body>
</html>
"""
