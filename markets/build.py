#!/usr/bin/env python3
"""Build markets/index.html (static, crawlable) from markets/data.json.

Run from anywhere:  python3 markets/build.py
Fails loudly (exit 1) if the data is malformed or contains internal-method terms,
so a bad update never gets published.
"""
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data.json"
OUT = HERE / "index.html"
SITE = "https://www.gotcommodities.com/"
PAGE_URL = "https://gotcommodities.github.io/got-homepage/markets/"

# Internal methodology must never appear on public pages.
FORBIDDEN = re.compile(
    r"elliott|\bwaves?\b|wave count|impulse|corrective|fibonacci|\bfib\b|retracement|extension target|"
    r"\bwave [1-5abc]\b|\bABC\b|zigzag|invalidation",
    re.I,
)
TAGS = {"Strong", "Firm", "Steady", "Mixed", "Soft", "Weak", "Volatile", "Pending"}
TAG_CLASS = {"Strong": "up", "Firm": "up", "Steady": "flat", "Mixed": "flat",
             "Soft": "down", "Weak": "down", "Volatile": "amber", "Pending": "flat"}

e = lambda s: html.escape(str(s if s is not None else ""), quote=True)


def fail(msg):
    print("BUILD FAILED:", msg, file=sys.stderr)
    sys.exit(1)


def validate(d):
    for k in ("edition", "overview", "groups"):
        if k not in d:
            fail(f"missing top-level key '{k}'")
    ids = set()
    for g in d["groups"]:
        for it in g.get("items", []):
            for k in ("id", "name", "v", "tag", "sum"):
                if k not in it:
                    fail(f"item in group '{g.get('id')}' missing '{k}'")
            if it["id"] in ids:
                fail(f"duplicate id {it['id']}")
            ids.add(it["id"])
            if it["tag"] not in TAGS:
                fail(f"{it['id']}: tag '{it['tag']}' not in {sorted(TAGS)}")
            if it.get("day") is not None and not isinstance(it["day"], (int, float)):
                fail(f"{it['id']}: 'day' must be a number or null")
    blob = json.dumps(d, ensure_ascii=False)
    m = FORBIDDEN.search(blob)
    if m:
        fail(f"internal-method term found in public data: '{m.group(0)}' — rewrite in plain market language")


def chg(day):
    if day is None:
        return '<span class="flat">—</span>'
    cls = "up" if day > 0 else "down" if day < 0 else "flat"
    arrow = "▲" if day > 0 else "▼" if day < 0 else "■"
    return f'<span class="{cls}">{arrow} {day:+.2f}%</span>'


def card(it):
    link = it.get("page")
    title = f'<a href="{e(link)}" target="_top">{e(it["name"])}</a>' if link else e(it["name"])
    go = f'<a class="go" href="{e(link)}" target="_top">Terminal →</a>' if link else ""
    src = ""
    if it.get("src"):
        src = (f'Source: <a href="{e(it["srcUrl"])}" rel="nofollow noopener" target="_blank">{e(it["src"])}</a>'
               if it.get("srcUrl") else f"Source: {e(it['src'])}")
    tc = TAG_CLASS.get(it["tag"], "flat")
    return f"""<article class="card" id="{e(it['id'])}">
  <div class="top"><h3>{title}</h3>{go}</div>
  <div class="meta mono">{e(it.get('ticker',''))} · {e(it.get('exch',''))}</div>
  <div class="px num"><span class="v">{e(it.get('u','') if it.get('u') in ('₹','$') else '')}{e(it['v'])}</span>
    <span class="d">{chg(it.get('day'))}</span><span class="m">{e(it.get('m',''))}</span></div>
  <span class="tag {tc}">{e(it['tag'])}</span>
  <p>{e(it['sum'])}</p>
  <div class="src">{src}</div>
</article>"""


def build(d):
    ed = d["edition"]
    items = [it for g in d["groups"] for it in g["items"]]
    priced = [it for it in items if isinstance(it.get("day"), (int, float))]
    ups = sorted([i for i in priced if i["day"] > 0], key=lambda i: -i["day"])[:3]
    downs = sorted([i for i in priced if i["day"] < 0], key=lambda i: i["day"])[:3]

    tape = "".join(
        f'<span class="tk"><span class="s">{e(it.get("ticker") or it["name"])}</span>'
        f'{e(it.get("u","") if it.get("u") in ("₹","$") else "")}{e(it["v"])} {chg(it.get("day"))}</span>'
        for it in items if it.get("v") not in (None, "—"))
    tape_html = (f'<div class="strip" aria-label="Price tape"><div class="strip-track">{tape}{tape}</div></div>'
                 if tape else "")

    def mover_rows(lst):
        if not lst:
            return '<div class="flat">—</div><div></div>'
        return "".join(f'<a href="#{e(i["id"])}">{e(i["name"])}</a><span>{chg(i["day"])}</span>' for i in lst)

    overview = "".join(f"<p>{e(p)}</p>" for p in d["overview"])
    watch = "".join(f"<div><h4>{e(w.get('title',''))}</h4><p>{e(w.get('body',''))}</p></div>"
                    for w in d.get("watchItems", []))
    watch_box = (f'<h3 class="box-title">On the radar</h3><div class="briefs">{watch}</div>' if watch else "")
    rail = "".join(f'<a href="#g-{e(g["id"])}"><b>§</b>{e(g["name"])}</a>' for g in d["groups"])
    sections = "".join(
        f'<section class="page" id="g-{e(g["id"])}"><div class="pagehead"><h2>{e(g["name"])}</h2>'
        f'<span class="code">{len(g["items"])}</span></div><div class="deskgrid">'
        + "".join(card(it) for it in g["items"]) + "</div></section>"
        for g in d["groups"])
    faq = d.get("faq", [])
    faq_html = ""
    if faq:
        faq_html = ('<section class="page" id="faq"><div class="pagehead"><h2>Questions readers ask</h2></div>'
                    + "".join(f'<details class="faq"><summary>{e(q["q"])}</summary><p>{e(q["a"])}</p></details>' for q in faq)
                    + "</section>")

    ld = {
        "@context": "https://schema.org", "@type": "WebPage",
        "name": "GOT Markets — India & Digital Assets Desk",
        "url": PAGE_URL, "dateModified": ed.get("isoDate", ""),
        "description": " ".join(d["overview"])[:300],
        "publisher": {"@type": "Organization", "name": "GOT Commodities", "url": SITE},
    }
    if faq:
        ld["mainEntity"] = {"@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q["q"], "acceptedAnswer": {"@type": "Answer", "text": q["a"]}} for q in faq]}
    ld_json = json.dumps(ld, ensure_ascii=False).replace("</", "<\\/")

    return TEMPLATE.format(
        date=e(ed.get("date", "")), status=e(ed.get("statusDate", "")), session=e(ed.get("sessionCovered", "")),
        note=e(ed.get("note", "")), tape=tape_html, overview=overview, watch=watch_box,
        ups=mover_rows(ups), downs=mover_rows(downs), rail=rail, sections=sections, faq=faq_html,
        desc=e(" ".join(d["overview"])[:155]), ld=ld_json, count=len(items),
    )


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GOT Markets — India &amp; Digital Assets Desk</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="https://gotcommodities.github.io/got-homepage/markets/">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,700;8..60,800&family=JetBrains+Mono:wght@400;500;700&display=swap">
<script type="application/ld+json">{ld}</script>
<style>
:root{{color-scheme:dark;--ink:#0b0d10;--sheet:#11151a;--rule:#26303a;--paper:#e9e4d6;--dim:#9aa3ad;--amber:#f5a524;--cyan:#4fd1e0;--up:#3ddc84;--down:#ff5d5d;--flat:#c9c3b3;
--f-serif:"Source Serif 4",Georgia,serif;--f-mono:"JetBrains Mono",ui-monospace,Menlo,Consolas,monospace}}
*{{box-sizing:border-box}}
body{{background:var(--ink);color:var(--paper);font-family:var(--f-serif);font-size:17px;line-height:1.55;margin:0}}
a{{color:var(--cyan);text-decoration:none;border-bottom:1px solid color-mix(in srgb,var(--cyan) 35%,transparent)}}
a:focus-visible,summary:focus-visible{{outline:2px solid var(--amber);outline-offset:2px}}
.wrap{{max-width:1240px;margin:0 auto;padding-inline:16px}}
.mono{{font-family:var(--f-mono)}}.num{{font-variant-numeric:tabular-nums}}
h1,h2,h3,h4{{margin:0;text-wrap:balance}} p{{margin:0 0 .85em}}
.up{{color:var(--up)}}.down{{color:var(--down)}}.flat{{color:var(--flat)}}.amber{{color:var(--amber)}}
.status{{font-family:var(--f-mono);font-size:12px;color:var(--dim);border-bottom:1px solid var(--rule);background:#080a0c}}
.status .wrap{{display:flex;flex-wrap:wrap;gap:6px 18px;padding-block:7px}}
.status b{{color:var(--amber);font-weight:500}}
.dot{{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--up);margin-right:6px;box-shadow:0 0 8px var(--up)}}
.mast{{text-align:center;padding-block:22px 10px}}
.nameplate{{font-family:var(--f-mono);font-weight:700;font-size:clamp(34px,8vw,84px);line-height:1;color:var(--amber);letter-spacing:-.03em}}
.nameplate span{{color:var(--cyan)}}
.motto{{font-family:var(--f-mono);font-size:12.5px;text-transform:uppercase;letter-spacing:.14em;color:var(--dim);margin-top:10px}}
.folio{{display:flex;flex-wrap:wrap;justify-content:space-between;gap:8px;border-top:3px double var(--rule);border-bottom:1px solid var(--rule);margin-top:14px;padding-block:7px;font-family:var(--f-mono);font-size:12px;color:var(--dim);text-transform:uppercase}}
.folio .c{{color:var(--paper);font-weight:700}}
.rail{{position:sticky;top:0;z-index:5;background:rgba(11,13,16,.96);border-bottom:1px solid var(--rule)}}
.rail .wrap{{display:flex;gap:4px;overflow-x:auto;padding-block:6px;scrollbar-width:none}}
.rail a{{flex:0 0 auto;font-family:var(--f-mono);font-size:12px;border:1px solid transparent;color:var(--paper);padding:4px 9px;white-space:nowrap}}
.rail a b{{color:var(--amber);font-weight:500;margin-right:5px}}
.strip{{border-bottom:1px solid var(--rule);background:#0d1014;overflow:hidden}}
.strip-track{{display:flex;gap:28px;padding:8px 0;width:max-content;animation:tape 80s linear infinite;font-family:var(--f-mono);font-size:13px}}
.strip:hover .strip-track{{animation-play-state:paused}}
@keyframes tape{{to{{transform:translateX(-50%)}}}}
@media (prefers-reduced-motion:reduce){{.strip-track{{animation:none}}.strip{{overflow-x:auto}}}}
.tk{{white-space:nowrap}}.tk .s{{color:var(--dim);margin-right:6px}}
.page{{padding-block:30px 10px;border-bottom:3px double var(--rule)}}
.pagehead{{display:flex;align-items:baseline;justify-content:space-between;gap:12px;border-bottom:1px solid var(--paper);padding-bottom:6px;margin-bottom:20px}}
.pagehead h2{{font-weight:800;font-size:clamp(24px,4vw,36px)}}
.code{{font-family:var(--f-mono);color:var(--ink);background:var(--amber);padding:2px 8px;font-size:14px;font-weight:700}}
.lead{{display:grid;grid-template-columns:minmax(0,2fr) minmax(0,1fr);gap:26px}}
.lead .side{{border-left:1px solid var(--rule);padding-left:22px}}
@media (max-width:900px){{.lead{{grid-template-columns:1fr}}.lead .side{{border-left:0;padding-left:0;border-top:1px solid var(--rule);padding-top:18px}}}}
.body{{max-width:68ch}}.body p{{font-size:18px}}
.box-title{{font-family:var(--f-mono);font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--amber);border-bottom:1px solid var(--rule);padding-bottom:6px;margin:0 0 12px;font-weight:500}}
.mv{{display:grid;grid-template-columns:1fr auto;gap:6px 10px;font-family:var(--f-mono);font-size:13px;margin-bottom:18px}}
.mv a{{color:var(--paper);border:0}}
.briefs>div{{padding-block:10px;border-bottom:1px solid var(--rule)}}.briefs h4{{font-size:16px}}.briefs p{{font-size:15px;margin:0;color:var(--flat)}}
.deskgrid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:18px}}
@media (max-width:420px){{.deskgrid{{grid-template-columns:1fr}}}}
.card{{background:var(--sheet);border:1px solid var(--rule);padding:16px;display:flex;flex-direction:column;gap:8px;min-width:0;scroll-margin-top:60px}}
.card .top{{display:flex;justify-content:space-between;align-items:baseline;gap:10px}}
.card h3{{font-size:21px;font-weight:800}}.card h3 a{{color:var(--paper);border:0}}
.card .go{{font-family:var(--f-mono);font-size:11.5px;white-space:nowrap}}
.card .meta{{font-size:11.5px;color:var(--dim);overflow-wrap:anywhere}}
.card .px{{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 14px;font-family:var(--f-mono);border-top:1px dashed var(--rule);border-bottom:1px dashed var(--rule);padding-block:8px}}
.card .px .v{{font-size:23px;font-weight:700;color:var(--amber)}}.card .px .d{{font-size:13px}}.card .px .m{{font-size:12px;color:var(--dim)}}
.tag{{font-family:var(--f-mono);font-size:10.5px;text-transform:uppercase;letter-spacing:.1em;padding:2px 7px;border:1px solid currentColor;align-self:flex-start}}
.card p{{font-size:15.5px;margin:0;line-height:1.5}}
.src{{font-family:var(--f-mono);font-size:11.5px;color:var(--dim);margin-top:auto}}
.faq{{border-bottom:1px solid var(--rule);padding-block:10px}}.faq summary{{cursor:pointer;font-weight:700}}.faq p{{margin:8px 0 0;color:var(--flat)}}
.ad{{border:1px solid var(--rule);min-height:90px;display:flex;align-items:center;justify-content:center;font-family:var(--f-mono);font-size:12px;color:var(--dim);margin-block:22px}}
footer{{font-family:var(--f-mono);font-size:12px;color:var(--dim);padding-block:22px 40px}}
</style>
</head>
<body>
<div class="status"><div class="wrap"><span><span class="dot"></span><b>LIVE DESK</b></span><span>{status}</span><span>Session: {session}</span><span>{count} markets</span></div></div>
<header class="wrap mast">
  <h1 class="nameplate">GOT<span>·</span>MARKETS</h1>
  <div class="motto">India equities &amp; digital assets · after the bell</div>
  <div class="folio"><span>{date}</span><span class="c">India &amp; Digital Assets Desk</span><span><a href="https://www.gotcommodities.com/" target="_top">Commodities desk →</a></span></div>
</header>
<nav class="rail" aria-label="Sections"><div class="wrap">{rail}</div></nav>
{tape}
<main class="wrap">
<section class="page" id="overview">
  <div class="pagehead"><h2>The session</h2><span class="code">{date}</span></div>
  <div class="lead">
    <div class="body">{overview}<div class="mono" style="font-size:11.5px;color:var(--dim)">{note}</div></div>
    <aside class="side">
      <h3 class="box-title">Biggest gainers</h3><div class="mv num">{ups}</div>
      <h3 class="box-title">Biggest decliners</h3><div class="mv num">{downs}</div>
      {watch}
    </aside>
  </div>
</section>
<div class="ad" aria-label="Advertisement">Advertisement</div>
{sections}
{faq}
</main>
<footer class="wrap">
  <p>Prices are last closes from public sources (NSE/BSE closes for equities; crypto at time of update, IST). Commentary is informational only and is not investment advice or a recommendation to buy or sell any security. GOT Commodities is not a SEBI-registered investment adviser or research analyst.</p>
  <p>© GOT Commodities · <a href="https://www.gotcommodities.com/" target="_top">gotcommodities.com</a></p>
</footer>
</body>
</html>
"""

if __name__ == "__main__":
    try:
        data = json.loads(DATA.read_text(encoding="utf-8"))
    except Exception as ex:  # noqa: BLE001
        fail(f"data.json is not valid JSON: {ex}")
    validate(data)
    OUT.write_text(build(data), encoding="utf-8")
    print(f"OK: wrote {OUT} ({OUT.stat().st_size} bytes)")
