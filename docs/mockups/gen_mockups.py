import re, sys, pathlib, json
SRC = pathlib.Path(sys.argv[1])      # original project/ folder (read-only copy)
OUT = pathlib.Path(sys.argv[2])      # output project/ folder
ICONS = pathlib.Path(sys.argv[3])    # phosphor regular dir
main = (SRC / "Main.dc.html").read_text()

def icon(name, cls="i"):
    d = re.search(r'<path d="([^"]+)"', (ICONS / f"{name}.svg").read_text()).group(1)
    return f'<svg class="{cls}" viewBox="0 0 256 256" fill="currentColor"><path d="{d}"/></svg>'

head, rest = main.split("<!-- CENTER STAGE -->")
stage_orig, right_orig = rest.split("<!-- RIGHT RAIL -->")
# right_orig ends with closing of body+root+</x-dc>...; we rebuild closing ourselves
tail = main[main.index("</x-dc>"):]
CLOSE = "\n  </div>\n</div>\n\n"

EXTRA_CSS = """
.chip.attention{color:var(--attn)}
.lab{white-space:nowrap}
.sw2{width:26px;height:26px;border-radius:5px;border:1px solid rgba(255,255,255,.14)}
.row{display:flex;align-items:center;gap:8px}
.lab{font-size:11px;color:var(--muted)}
.val{font-family:"Ubuntu Mono",monospace;font-size:12px;color:var(--text)}
.spin{display:inline-flex;align-items:center;height:28px;border:1px solid var(--border);border-radius:6px;background:var(--bg);overflow:hidden}
.spin .btn{width:26px;height:26px;border-radius:0}
.spin .val{min-width:34px;text-align:center}
.sw{position:relative;width:34px;height:20px;border-radius:10px;background:var(--border);flex:none}
.sw::after{content:"";position:absolute;top:3px;left:3px;width:14px;height:14px;border-radius:50%;background:var(--muted)}
.sw.on{background:var(--accent)}
.sw.on::after{left:17px;background:var(--onacc)}
.scale{position:relative;flex:1;height:4px;border-radius:2px;background:var(--border)}
.scale .fill{position:absolute;left:0;top:0;height:4px;border-radius:2px;background:var(--accent)}
.scale .knob{position:absolute;top:-6px;width:16px;height:16px;border-radius:50%;background:var(--text);border:2px solid var(--accent);margin-left:-8px}
.dd{display:flex;align-items:center;justify-content:space-between;height:28px;padding:0 8px;border:1px solid var(--border);border-radius:6px;background:var(--bg);font-size:12px;color:var(--text);flex:1}
.seg{display:flex;border:1px solid var(--border);border-radius:6px;overflow:hidden;background:var(--bg)}
.seg span{padding:0 10px;height:26px;display:inline-flex;align-items:center;font-size:12px;color:var(--muted);white-space:nowrap}
.seg span.on{background:var(--soft);color:var(--accent)}
.tbtn{flex:none;display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:6px;border:1px solid var(--border);background:var(--bg);color:var(--muted);font-size:12px;font-weight:700}
.tbtn.on{background:var(--soft);color:var(--accent);border-color:var(--soft)}
.cap-thumb{border-radius:4px;border:1px solid var(--border);height:64px;overflow:hidden;position:relative}
.cap-thumb.sel{outline:2px solid var(--accent);outline-offset:2px}
.cap-name{font-size:11px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:4px}
.badge{position:absolute;width:26px;height:26px;border-radius:50%;background:#e5484d;color:#fff;font-size:13px;font-weight:700;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 6px rgba(0,0,0,.35)}
.toast{position:absolute;left:50%;bottom:16px;transform:translateX(-50%);display:inline-flex;align-items:center;gap:10px;height:34px;padding:0 14px;border-radius:8px;background:var(--surface);border:1px solid var(--border);font-size:12px;color:var(--text);box-shadow:0 8px 24px rgba(0,0,0,.4)}
.toast b{color:var(--accent);font-weight:500}
.dlg{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:600px;background:var(--surface);border:1px solid var(--border);border-radius:12px;box-shadow:0 30px 80px rgba(0,0,0,.6);display:flex;flex-direction:column;overflow:hidden}
.prow{display:flex;align-items:center;gap:12px;min-height:44px;padding:0 14px;border-top:1px solid var(--border)}
.prow:first-child{border-top:none}
.prow .t{flex:1;font-size:13px;color:var(--text)}
.prow .s{font-size:11px;color:var(--muted);display:block;margin-top:1px}
.pgroup{border:1px solid var(--border);border-radius:10px;background:var(--bg);overflow:hidden}
.ptitle{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin:14px 0 6px}
"""
def with_css(doc):
    return doc.replace("</style>\n</helmet>", EXTRA_CSS + "</style>\n</helmet>", 1)

def set_active(doc, labels):
    doc = doc.replace('class="btn active" aria-label="Arrow"', 'class="btn" aria-label="Arrow"')
    for l in labels:
        doc = doc.replace(f'class="btn" aria-label="{l}"', f'class="btn active" aria-label="{l}"', 1)
    return doc

def set_title(doc, name, sub, chip_text="Ready", chip_cls=""):
    doc = doc.replace('line-height:18px">Untitled<', f'line-height:18px">{name}<', 1)
    doc = doc.replace('Edit · 1920×1080 · PNG · 1 layer · unsaved', sub, 1)
    doc = doc.replace('<div class="chip"><span class="dot"></span>Ready</div>', f'<div class="chip{chip_cls}"><span class="dot"></span>{chip_text}</div>', 1)
    return doc

def set_zoom(doc, z):
    return doc.replace('<span class="zv">100%</span>', f'<span class="zv">{z}</span>').replace("color:var(--text)\">100%</div>", f"color:var(--text)\">{z}</div>")

# ---- a fake captured app window used on the stage -------------------------
def fake_window(extra="", w=620, h=400, title="example.com — capture"):
    return f'''<div style="width:{w}px;height:{h}px;border-radius:8px;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,.45);background:#eef1f4;position:relative">
        <div style="height:34px;background:#dfe4ea;display:flex;align-items:center;gap:7px;padding:0 12px">
          <span style="width:11px;height:11px;border-radius:50%;background:#ff5f57"></span><span style="width:11px;height:11px;border-radius:50%;background:#febc2e"></span><span style="width:11px;height:11px;border-radius:50%;background:#28c840"></span>
          <span style="margin-left:10px;font-size:12px;color:#5b6572">{title}</span>
        </div>
        <div style="display:flex;height:{h-34}px">
          <div style="width:150px;background:#f4f6f9;border-right:1px solid #e2e7ee;padding:16px 12px;display:flex;flex-direction:column;gap:10px">
            <div style="height:9px;width:70%;background:#cdd5e0;border-radius:3px"></div><div style="height:9px;width:90%;background:#dde3ec;border-radius:3px"></div><div style="height:9px;width:60%;background:#dde3ec;border-radius:3px"></div><div style="height:9px;width:80%;background:#dde3ec;border-radius:3px"></div>
          </div>
          <div style="flex:1;padding:22px 24px;position:relative">
            <div style="height:16px;width:55%;background:#c6cedb;border-radius:4px;margin-bottom:16px"></div>
            <div style="height:9px;width:92%;background:#e2e7ee;border-radius:3px;margin-bottom:9px"></div>
            <div style="height:9px;width:86%;background:#e2e7ee;border-radius:3px;margin-bottom:9px"></div>
            <div style="height:9px;width:70%;background:#e2e7ee;border-radius:3px;margin-bottom:24px"></div>
            <div style="display:flex;flex-direction:column;gap:10px;width:70%">
              <div style="height:30px;border:1px solid #d7dfea;border-radius:6px;background:#fff;display:flex;align-items:center;padding:0 10px;font-size:11px;color:#8a94a3">user@example.com</div>
              <div style="height:30px;border:1px solid #d7dfea;border-radius:6px;background:#fff;display:flex;align-items:center;padding:0 10px;font-size:11px;color:#8a94a3;position:relative">••••••••••••</div>
              <div style="height:30px;width:120px;border-radius:6px;background:#0091ff;color:#fff;font-size:12px;font-weight:500;display:flex;align-items:center;justify-content:center">Sign in</div>
            </div>
          </div>
        </div>
        {extra}
      </div>'''

def stage(inner, hud="100%", more=""):
    return f'''<!-- CENTER STAGE -->
    <div style="flex:1;min-width:0;background:var(--stage);position:relative;display:flex;align-items:center;justify-content:center">
      {inner}
      <div style="position:absolute;left:16px;bottom:16px;display:inline-flex;align-items:center;gap:6px;height:28px;padding:0 10px;border-radius:6px;background:rgba(38,42,48,.9);border:1px solid var(--border);font-family:'Ubuntu Mono',monospace;font-size:12px;color:var(--text)">{hud}</div>
      {more}
    </div>

    '''

right_head = right_orig.split('<div style="margin:4px 0 10px">')[0]   # collapse btn + panel switch (Layers active)
def panel_switch(active):
    h = right_head.replace('class="btn active" aria-label="Layers"', 'class="btn" aria-label="Layers"')
    return h.replace(f'class="btn" aria-label="{active}"', f'class="btn active" aria-label="{active}"', 1)

colour_card = right_orig[right_orig.index('<hr class="hair">\n      <div class="cap" style="margin-top:8px">Colour</div>'):right_orig.index('<div style="flex:1"></div>\n      <div class="cap">Navigator</div>')]
navigator = right_orig[right_orig.index('<div class="cap">Navigator</div>'):right_orig.index('\n  </div>\n</div>')]

def build(name, stage_html, right_html, actives, title, sub, chip="Ready", chip_cls="", zoom="100%", overlay=""):
    doc = head + stage_html + "<!-- RIGHT RAIL -->\n    " + right_html + CLOSE.replace("\n  </div>\n</div>\n\n", f"\n  </div>\n{overlay}</div>\n\n") + tail
    doc = with_css(doc); doc = set_active(doc, actives); doc = set_title(doc, title, sub, chip, chip_cls); doc = set_zoom(doc, zoom)
    doc = doc.replace("<title>Studio Editor — optimized</title>", f"<title>{name}</title>")
    (OUT / f"{name}.dc.html").write_text(doc)

# =========================== 1. Captures panel + step/callout annotations =====
badges = ''.join(f'<div class="badge" style="left:{x}px;top:{y}px">{n}</div>' for n,(x,y) in enumerate([(176,108),(176,148),(176,188)],1))
callout = '''<div style="position:absolute;left:330px;top:100px;background:#e5484d;color:#fff;font-size:12px;font-weight:500;padding:6px 10px;border-radius:6px;box-shadow:0 2px 8px rgba(0,0,0,.3)">Enter your work e-mail first</div>
<svg width="40" height="40" viewBox="0 0 40 40" style="position:absolute;left:300px;top:112px"><path d="M40,6 L8,14 L28,22 Z" fill="#e5484d"/></svg>
<div style="position:absolute;left:176px;top:62px;font-family:Ubuntu;font-weight:700;font-size:16px;color:#e5484d;text-shadow:0 1px 2px rgba(0,0,0,.25)">Login form</div>
<div style="position:absolute;left:170px;top:52px;width:112px;height:28px;border:1px dashed var(--accent);border-radius:2px"></div>
<div style="position:absolute;left:166px;top:48px;width:8px;height:8px;background:#fff;border:1px solid var(--accent)"></div><div style="position:absolute;left:278px;top:48px;width:8px;height:8px;background:#fff;border:1px solid var(--accent)"></div><div style="position:absolute;left:166px;top:76px;width:8px;height:8px;background:#fff;border:1px solid var(--accent)"></div><div style="position:absolute;left:278px;top:76px;width:8px;height:8px;background:#fff;border:1px solid var(--accent)"></div>'''
grads = ["linear-gradient(135deg,#8fb7e8,#eef1f4)","linear-gradient(160deg,#2a3b55,#c98b6b)","linear-gradient(135deg,#1f2e3f,#5b6572)","linear-gradient(135deg,#eef1f4,#c6cedb)","linear-gradient(135deg,#3f5f74,#0f1115)","linear-gradient(135deg,#d6409f,#6e56cf)","linear-gradient(135deg,#46a758,#eef1f4)","linear-gradient(135deg,#ffb224,#f76b15)"]
names = ["LinShot_24.png","LinShot_23.png","LinShot_22.png","Screenshot_2026-10-08.png","LinShot_21.png","LinShot_20.png","invoice-crop.png","LinShot_19.png"]
cells = ''.join(f'<div><div class="cap-thumb{" sel" if i==0 else ""}" style="background:{g}"></div><div class="cap-name">{n}</div></div>' for i,(g,n) in enumerate(zip(grads,names)))
captures_panel = f'''{panel_switch("Captures")}
      <div class="row" style="justify-content:space-between;margin:4px 2px 8px"><span class="cap" style="margin:0">24 captures</span><div class="row" style="gap:2px"><button class="btn" aria-label="Refresh" style="width:26px;height:26px">{icon("arrows-clockwise")}</button><button class="btn danger" aria-label="Delete selected" style="width:26px;height:26px">{icon("trash")}</button></div></div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px 6px;margin-bottom:10px">{cells}</div>
      <div class="lab" style="margin:0 2px 8px">Double-click opens · Delete removes</div>
      {colour_card}<div style="flex:1"></div>
      {navigator}'''
build("Captures", stage(fake_window(badges + callout)), captures_panel, ["Step number"], "LinShot_24.png", "Edit · 1440×900 · PNG · 5 layers · unsaved", "Captured")

# =========================== 2. Props panel + redaction ========================
pix = '''<div style="position:absolute;left:176px;top:150px;width:240px;height:30px;border-radius:6px;background:repeating-conic-gradient(#9aa3ad 0 25%,#c7ced6 0 50%) 0 0/10px 10px;filter:saturate(.6)"></div>
<div style="position:absolute;left:174px;top:148px;width:244px;height:34px;border:1px dashed var(--accent);border-radius:4px"></div>
<div style="position:absolute;left:170px;top:106px;width:252px;height:36px;border:3px solid #e5484d;border-radius:6px"></div>'''
props_panel = f'''{panel_switch("Props")}
      <div class="cap" style="margin-top:6px">Blur · active tool</div>
      <div class="card" style="display:flex;flex-direction:column;gap:10px">
        <div class="row"><span class="lab" style="width:64px">Mode</span><div class="seg"><span class="on">Pixelate</span><span>Blur</span></div></div>
        <div class="row"><span class="lab" style="width:64px">Block</span><div class="scale"><div class="fill" style="width:36%"></div><div class="knob" style="left:36%"></div></div><span class="val" style="width:28px;text-align:right">12</span></div>
      </div>
      <div class="cap" style="margin-top:10px">Shapes · line, arrow, box, circle</div>
      <div class="card" style="display:flex;flex-direction:column;gap:10px">
        <div class="row"><span class="lab" style="width:64px">Width</span><div class="spin"><button class="btn" aria-label="Thinner">{icon("minus")}</button><span class="val">4 px</span><button class="btn" aria-label="Thicker">{icon("plus")}</button></div></div>
        <div class="row"><span class="lab" style="width:64px">Shadow</span><div class="sw on"></div><span class="lab">on</span></div>
        <div class="row"><span class="lab" style="width:64px">Intensity</span><div class="scale"><div class="fill" style="width:60%"></div><div class="knob" style="left:60%"></div></div><span class="val" style="width:28px;text-align:right">.60</span></div>
        <div class="row"><span class="lab" style="width:64px">Universal</span><div class="sw"></div><span class="lab">all tools</span></div>
      </div>
      <div class="cap" style="margin-top:10px">Text</div>
      <div class="card" style="display:flex;flex-direction:column;gap:10px">
        <div class="row"><div class="dd">Ubuntu {icon("caret-down")}</div><div class="spin"><button class="btn" aria-label="Smaller">{icon("minus")}</button><span class="val">18</span><button class="btn" aria-label="Larger">{icon("plus")}</button></div></div>
        <div class="row"><div class="tbtn on">B</div><div class="tbtn" style="font-style:italic;font-weight:400">I</div><div class="sw on"></div><span class="lab">shadow</span></div>
      </div>
      <div style="flex:1"></div>
      <button class="btn" style="width:100%;justify-content:flex-start;gap:8px;padding:0 8px;font-size:12px;color:var(--text)">{icon("gear")} Preferences…</button>'''
build("Props", stage(fake_window(pix)), props_panel, ["Blur"], "LinShot_24.png", "Edit · 1440×900 · PNG · 3 layers · unsaved", "Captured")

# =========================== 3. Empty state + delayed countdown ===============
empty = f'''<div style="display:flex;flex-direction:column;align-items:center;gap:12px;color:var(--muted)">
        <div style="width:48px;height:48px;color:var(--muted)"><svg viewBox="0 0 256 256" fill="currentColor" style="width:48px;height:48px"><path d="{re.search(r'<path d="([^"]+)"', (ICONS/'camera.svg').read_text()).group(1)}"/></svg></div>
        <div style="font-size:14px;color:var(--text);font-weight:500">Press PrintScreen or click Capture</div>
        <div style="font-size:12px">Region · Window · Full screen · Delayed · Pin</div>
        <div class="row" style="margin-top:6px;gap:6px"><span class="kind">Ctrl+N</span><span class="lab">region</span><span class="kind" style="margin-left:8px">Ctrl+Shift+N</span><span class="lab">full screen</span><span class="kind" style="margin-left:8px">Ctrl+V</span><span class="lab">paste</span></div>
      </div>'''
empty_right = f'''{panel_switch("Layers")}
      <div style="margin:4px 0 10px;height:80px;border:1px dashed var(--border);border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:12px;color:var(--muted)">No layers yet</div>
      {colour_card}<div style="flex:1"></div>
      {navigator}'''
toast = '<div class="toast">Copied <b>LinShot_23.png</b> to clipboard<span class="kind" style="margin-left:4px">Undo</span></div>'
build("Empty", stage(empty, "—", toast), empty_right, ["Delayed 3 s"], "No capture", "Delayed · 3 s · region · ~/Pictures", "Capturing in 2 s", " attention")

# =========================== 4. Preferences dialog ============================
folder = icon("folder-open"); caret = icon("caret-down")
dialog = f'''<div style="position:absolute;inset:0;background:rgba(0,0,0,.55)"></div>
  <div class="dlg">
    <div class="row" style="height:52px;padding:0 16px;border-bottom:1px solid var(--border)"><span style="font-size:14px;font-weight:500">Preferences</span><div style="flex:1"></div><div class="seg"><span class="on">Capture</span><span>System</span><span>Shortcuts</span></div><button class="btn" aria-label="Close" style="margin-left:8px">{icon("x")}</button></div>
    <div style="padding:4px 16px 16px;display:flex;flex-direction:column">
      <div class="ptitle">Saving</div>
      <div class="pgroup">
        <div class="prow"><div class="t">Save folder<span class="s">Every capture is written here immediately</span></div><span class="val">~/Pictures/Screenshots</span><button class="btn" aria-label="Choose folder">{folder}</button></div>
        <div class="prow"><div class="t">File name prefix</div><div class="dd" style="flex:none;width:150px">LinShot_ {caret}</div></div>
        <div class="prow"><div class="t">Numbering</div><div class="seg"><span class="on">Sequence</span><span>Timestamp</span></div></div>
        <div class="prow"><div class="t">Format</div><div class="seg"><span class="on">PNG</span><span>JPEG 92</span><span>WebP</span></div></div>
      </div>
      <div class="ptitle">Capture</div>
      <div class="pgroup">
        <div class="prow"><div class="t">Copy to clipboard<span class="s">Also when the editor is closed</span></div><div class="sw on"></div></div>
        <div class="prow"><div class="t">Delayed capture</div><div class="spin"><button class="btn" aria-label="Less">{icon("minus")}</button><span class="val">3 s</span><button class="btn" aria-label="More">{icon("plus")}</button></div></div>
        <div class="prow"><div class="t">Include pointer</div><div class="sw"></div></div>
        <div class="prow"><div class="t">Pin to screen opacity</div><div class="scale" style="max-width:160px"><div class="fill" style="width:90%"></div><div class="knob" style="left:90%"></div></div><span class="val" style="width:36px;text-align:right">90%</span></div>
        <div class="prow"><div class="t">Backend<span class="s">Auto picks the portal on Wayland and X11 on X11</span></div><div class="dd" style="flex:none;width:150px">Auto {caret}</div></div>
      </div>
      <div class="ptitle">Window</div>
      <div class="pgroup">
        <div class="prow"><div class="t">Start with rails collapsed</div><div class="sw"></div></div>
        <div class="prow"><div class="t">Reopen last capture on launch</div><div class="sw on"></div></div>
      </div>
    </div>
  </div>
'''
build("Preferences", stage(fake_window(), "100%"), right_orig.split("\n  </div>\n</div>")[0].replace("<!-- RIGHT RAIL -->\n    ",""), ["Arrow"], "LinShot_24.png", "Edit · 1440×900 · PNG · 2 layers · saved", "Ready", overlay=dialog)

# =========================== 5. Capture overlay (region picker) ===============
kb = icon("keyboard"); sel_x, sel_y, sel_w, sel_h = 300, 180, 760, 470
overlay_doc = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Capture overlay — region picker</title>
<script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
<link href="https://fonts.googleapis.com/css2?family=Ubuntu:wght@400;500;700&family=Ubuntu+Mono&display=swap" rel="stylesheet">
<style>
:root{{--bg:#1c1f23;--surface:#262a30;--hover:#2f343b;--rail:#17191d;--border:#3a4048;--border2:#7d8590;--text:#eceff3;--muted:#aab2bd;--accent:#4c9dff;--accenth:#6aaeff;--onacc:#0b1320;--soft:#1f3350;--ok:#5fd38d;--attn:#ffbf4d;--err:#ff8a80;}}
*{{box-sizing:border-box}}
body{{margin:0;font-family:Ubuntu,system-ui,sans-serif;color:var(--text);-webkit-font-smoothing:antialiased}}
svg.i{{width:18px;height:18px;display:block;flex:none}}
button{{font-family:inherit}}
.btn{{width:30px;height:30px;display:inline-flex;align-items:center;justify-content:center;border:none;background:transparent;color:var(--muted);border-radius:6px;cursor:pointer;padding:0}}
.btn.active{{background:var(--soft);color:var(--accent)}}
.chip{{display:inline-flex;align-items:center;gap:8px;height:30px;padding:0 12px;border-radius:6px;background:rgba(38,42,48,.94);border:1px solid var(--border);font-size:12px;color:var(--text);box-shadow:0 8px 24px rgba(0,0,0,.4)}}
.kind{{font-size:9px;letter-spacing:.06em;color:var(--muted);border:1px solid var(--border);border-radius:4px;padding:1px 5px}}
.mono{{font-family:"Ubuntu Mono",monospace}}
.h{{position:absolute;width:9px;height:9px;background:#fff;border:1.5px solid var(--accent);border-radius:2px}}
.win{{position:absolute;border-radius:8px;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,.45)}}
</style>
</helmet>

<div style="width:1360px;height:840px;position:relative;overflow:hidden;background:radial-gradient(1200px 700px at 30% 20%,#2e4a6b 0%,#1a2538 45%,#0d131c 100%)">
  <!-- desktop wallpaper + two app windows -->
  <div class="win" style="left:120px;top:90px;width:900px;height:560px;background:#eef1f4">
    <div style="height:34px;background:#dfe4ea;display:flex;align-items:center;gap:7px;padding:0 12px"><span style="width:11px;height:11px;border-radius:50%;background:#ff5f57"></span><span style="width:11px;height:11px;border-radius:50%;background:#febc2e"></span><span style="width:11px;height:11px;border-radius:50%;background:#28c840"></span><span style="margin-left:10px;font-size:12px;color:#5b6572">example.com — Sign in</span></div>
    <div style="display:flex;height:526px"><div style="width:180px;background:#f4f6f9;border-right:1px solid #e2e7ee;padding:16px 12px;display:flex;flex-direction:column;gap:10px"><div style="height:9px;width:70%;background:#cdd5e0;border-radius:3px"></div><div style="height:9px;width:90%;background:#dde3ec;border-radius:3px"></div><div style="height:9px;width:60%;background:#dde3ec;border-radius:3px"></div></div>
    <div style="flex:1;padding:28px 32px"><div style="height:18px;width:50%;background:#c6cedb;border-radius:4px;margin-bottom:18px"></div><div style="height:9px;width:92%;background:#e2e7ee;border-radius:3px;margin-bottom:9px"></div><div style="height:9px;width:80%;background:#e2e7ee;border-radius:3px;margin-bottom:28px"></div><div style="display:flex;flex-direction:column;gap:10px;width:60%"><div style="height:32px;border:1px solid #d7dfea;border-radius:6px;background:#fff"></div><div style="height:32px;border:1px solid #d7dfea;border-radius:6px;background:#fff"></div><div style="height:32px;width:130px;border-radius:6px;background:#0091ff"></div></div></div></div>
  </div>
  <div class="win" style="left:760px;top:420px;width:520px;height:330px;background:#15181c;border:1px solid #2a2f36">
    <div style="height:30px;background:#20242a;display:flex;align-items:center;padding:0 12px;font-size:12px;color:#aab2bd">user@mint: ~/projects</div>
    <div class="mono" style="padding:12px;font-size:12px;color:#8fd5a0;line-height:1.6">$ linscreencapture --capture<br><span style="color:#aab2bd">overlay ready in 212 ms</span><br>$ _</div>
  </div>

  <!-- veil everywhere except the selection -->
  <div style="position:absolute;left:{sel_x}px;top:{sel_y}px;width:{sel_w}px;height:{sel_h}px;box-shadow:0 0 0 4000px rgba(0,0,0,.45);border:1px solid var(--accent)"></div>
  <!-- crosshair through the pointer (bottom-right corner) -->
  <div style="position:absolute;left:0;top:{sel_y+sel_h}px;width:1360px;height:1px;background:rgba(76,157,255,.55)"></div>
  <div style="position:absolute;top:0;left:{sel_x+sel_w}px;width:1px;height:840px;background:rgba(76,157,255,.55)"></div>
  <!-- handles -->
  <div class="h" style="left:{sel_x-5}px;top:{sel_y-5}px"></div><div class="h" style="left:{sel_x+sel_w-5}px;top:{sel_y-5}px"></div><div class="h" style="left:{sel_x-5}px;top:{sel_y+sel_h-5}px"></div><div class="h" style="left:{sel_x+sel_w-5}px;top:{sel_y+sel_h-5}px"></div>
  <div class="h" style="left:{sel_x+sel_w//2-5}px;top:{sel_y-5}px"></div><div class="h" style="left:{sel_x+sel_w//2-5}px;top:{sel_y+sel_h-5}px"></div><div class="h" style="left:{sel_x-5}px;top:{sel_y+sel_h//2-5}px"></div><div class="h" style="left:{sel_x+sel_w-5}px;top:{sel_y+sel_h//2-5}px"></div>
  <!-- dimension chip -->
  <div class="chip mono" style="position:absolute;left:{sel_x+sel_w-96}px;top:{sel_y+sel_h+10}px;height:26px;padding:0 10px">{sel_w} × {sel_h}</div>
  <!-- pointer -->
  <svg width="20" height="24" viewBox="0 0 20 24" style="position:absolute;left:{sel_x+sel_w+2}px;top:{sel_y+sel_h+2}px"><path d="M2,2 L2,18 L6,14 L9,21 L12,20 L9,13 L15,13 Z" fill="#fff" stroke="#000" stroke-width="1.2"/></svg>

  <!-- top mode bar -->
  <div class="chip" style="position:absolute;left:50%;top:16px;transform:translateX(-50%);padding:0 6px 0 6px;gap:4px">
    <button class="btn active" aria-label="Region">{icon("selection")}</button><button class="btn" aria-label="Window">{icon("app-window")}</button><button class="btn" aria-label="Full screen">{icon("monitor")}</button><span style="width:1px;height:18px;background:var(--border);margin:0 4px"></span>
    <span class="kind">Enter</span><span style="color:var(--muted)">capture</span><span class="kind">Esc</span><span style="color:var(--muted)">cancel</span><span class="kind">Space</span><span style="color:var(--muted)">move</span><span class="kind">Shift</span><span style="color:var(--muted)">square</span>
  </div>
  <!-- bottom-left: pointer position -->
  <div class="chip mono" style="position:absolute;left:16px;bottom:16px;height:26px;padding:0 10px;gap:12px"><span style="color:var(--muted)">x</span>1060<span style="color:var(--muted)">y</span>650<span style="color:var(--muted)">·</span><span style="width:12px;height:12px;border-radius:3px;background:#0091ff;display:inline-block"></span>#0091FF</div>
  <div class="chip" style="position:absolute;right:16px;bottom:16px;height:26px;padding:0 10px;gap:8px">{kb}<span style="color:var(--muted)">Arrows nudge 1 px · Shift+Arrows 10 px</span></div>
</div>

</x-dc>
<script type="text/x-dc" data-dc-script data-props='{{"$preview":{{"width":1360,"height":840}}}}'>
class Component extends DCLogic {{ renderVals(){{ return {{}}; }} }}
</script>
</body>
</html>
'''
(OUT / "Overlay.dc.html").write_text(overlay_doc)

# ---- canvas.json ------------------------------------------------------------
cj = json.loads((SRC / "canvas.json").read_text())
new = {
 "Overlay.dc.html":     {"x":0,    "y":2300, "w":1360, "h":840, "title":"Capture overlay — region picker, mode bar, dimension chip", "radius":10},
 "Captures.dc.html":    {"x":1440, "y":2300, "w":1360, "h":840, "title":"Captures panel · step numbers, callout and text annotations", "radius":10},
 "Props.dc.html":       {"x":0,    "y":3260, "w":1360, "h":840, "title":"Props panel · pixelate redaction with per-tool settings", "radius":10},
 "Preferences.dc.html": {"x":1440, "y":3260, "w":1360, "h":840, "title":"Preferences dialog — Capture page", "radius":10},
 "Empty.dc.html":       {"x":0,    "y":4220, "w":1360, "h":840, "title":"Empty state · delayed countdown · toast", "radius":10},
}
for k,v in new.items():
    cj["boards"][k] = v
    if k not in cj["order"]: cj["order"].append(k)
cj["notes"]["t2"] = {"x":0,"y":2000,"text":"Feature mockups — capture overlay, panels, preferences, empty state","kind":"title1","maxW":2800}
(OUT / "canvas.json").write_text(json.dumps(cj, indent=2, ensure_ascii=False) + "\n")
print("wrote", sorted(p.name for p in OUT.iterdir()))
