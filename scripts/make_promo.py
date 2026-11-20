#!/usr/bin/env python3
"""スキル紹介動画（縦型 1080x1920 / 30fps / 約30秒）を spec.json から作る。

使い方:
  python3 make_promo.py spec.json --out 出力フォルダ                 # 動画を作る
  python3 make_promo.py spec.json --out 出力フォルダ --preview 0:2.5 3:4  # 指定コマだけPNGで描く（シーン番号:秒）
  python3 make_promo.py spec.json --out 出力フォルダ --sheet          # 各シーンの見せ場を並べた一覧画像 sheet.png

必要なもの: Python3 + Pillow, ffmpeg, 日本語フォント（Noto Sans CJK JP など。spec.json の fonts で場所を変えられる）
spec.json の書き方は references/spec-guide.md。
"""
import argparse, json, math, os, random, subprocess, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1080, 1920, 30
FADE = 0.3  # シーンの頭で前のシーンから切り替える秒数

# ---------------- 設定の読み込み ----------------
DEFAULT_FONTS = {
    "Regular": ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"],
    "Medium": ["/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc", "/System/Library/Fonts/ヒラギノ角ゴシック W5.ttc"],
    "Bold": ["/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"],
    "Black": ["/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc", "/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc"],
}
DEFAULT_PALETTE = {
    "bg": "#F4F1EA", "ink": "#1F2328", "sub": "#60666E", "accent": "#2271B1",
    "alert": "#D63638", "dark": "#1D2327", "surface": "#FFFFFF", "line": "#DCDCDE",
}

SPEC = {}
P = {}
FONT_PATHS = {}
_fc = {}

def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

def col(name_or_hex):
    """'accent' のようなパレット名か '#RRGGBB' を色にする"""
    if isinstance(name_or_hex, (list, tuple)):
        return tuple(name_or_hex)
    if name_or_hex in P:
        return P[name_or_hex]
    return hexrgb(name_or_hex)

def font(size, w="Bold"):
    k = (int(size), w)
    if k not in _fc:
        _fc[k] = ImageFont.truetype(FONT_PATHS[w], int(size), index=0)
    return _fc[k]

def load(spec_path):
    global SPEC, P, FONT_PATHS
    with open(spec_path, encoding="utf-8") as f:
        SPEC = json.load(f)
    pal = dict(DEFAULT_PALETTE)
    pal.update(SPEC.get("palette", {}))
    P = {k: hexrgb(v) for k, v in pal.items()}
    fonts = SPEC.get("fonts", {})
    for w, cands in DEFAULT_FONTS.items():
        cands = ([fonts[w]] if w in fonts else []) + cands
        path = next((c for c in cands if os.path.exists(c)), None)
        if not path:
            sys.exit(f"フォントが見つかりません（{w}）。spec.json の fonts.{w} にファイルの場所を書いてください")
        FONT_PATHS[w] = path

# ---------------- 小さな道具 ----------------
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))

def ease(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3

def prog(t, start, dur):
    return ease((t - start) / dur)

def mix(c1, c2, k):
    return tuple(int(a + (b - a) * k) for a, b in zip(c1, c2))

def text_c(d, cx, y, s, f, fill):
    w = d.textlength(s, font=f)
    d.text((cx - w / 2, y), s, font=f, fill=fill)

def fit(d, s, size, weight, maxw):
    """幅に収まるまで文字を小さくする"""
    while size > 20 and d.textlength(s, font=font(size, weight)) > maxw:
        size -= 2
    return size

def headline(img, t, lines, y=250, size=104, start=0.0):
    d = ImageDraw.Draw(img)
    size = min(fit(d, s, size, "Black", W - 120) for s, _ in lines)
    for i, (s, c) in enumerate(lines):
        p = prog(t, start + i * 0.18, 0.5)
        if p <= 0:
            continue
        layer = Image.new("RGBA", (W, size + 40), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        text_c(ld, W / 2, 0, s, font(size, "Black"), col(c) + (int(255 * p),))
        img.alpha_composite(layer, (0, int(y + i * (size + 30) + (1 - p) * 40)))

def caption(img, t, s, y=1640, start=0.8):
    if not s:
        return
    p = prog(t, start, 0.5)
    if p <= 0:
        return
    d = ImageDraw.Draw(img)
    size = fit(d, s, 42, "Medium", W - 120)
    text_c(d, W / 2, y, s, font(size, "Medium"), mix(P["bg"], P["sub"], p))

def step_tag(d, n, total):
    f = font(34, "Bold")
    s = f"STEP {n}/{total}"
    w = d.textlength(s, font=f) + 60
    d.rounded_rectangle((80, 110, 80 + w, 174), radius=32, outline=P["ink"], width=3)
    text_c(d, 80 + w / 2, 118, s, f, P["ink"])

def shadow_paste(img, im, x, y, r=16, blur=24, alpha=60):
    sh = Image.new("RGBA", (im.width + blur * 4, im.height + blur * 4), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((blur * 2, blur * 2, blur * 2 + im.width, blur * 2 + im.height), radius=r, fill=(0, 0, 0, alpha))
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    img.alpha_composite(sh, (int(x - blur * 2), int(y - blur * 2 + 12)))
    m = Image.new("L", im.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, im.width, im.height), radius=r, fill=255)
    if im.mode == "RGBA":
        m = Image.composite(m, Image.new("L", im.size, 0), im.getchannel("A"))
    img.paste(im.convert("RGB"), (int(x), int(y)), m)

def cursor(d, x, y, s=1.3):
    pts = [(0, 0), (0, 46), (12, 35), (21, 56), (30, 52), (21, 32), (37, 32)]
    pts = [(x + px * s, y + py * s) for px, py in pts]
    d.polygon(pts, fill=P["ink"])
    d.line(pts + [pts[0]], fill=(255, 255, 255), width=3)

def badge(d, cx, cy, n, r=30, k=1.0):
    r = r * k
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=P["alert"])
    if k > 0.4:
        text_c(d, cx, cy - r * 0.78, str(n), font(int(r * 1.3), "Black"), (255, 255, 255))

def window_chrome(d, w, dark):
    d.rectangle((0, 0, w, 44), fill=dark)
    for i in range(3):
        d.ellipse((18 + i * 30, 14, 34 + i * 30, 30), fill=mix(dark, (255, 255, 255), 0.3))

# ---------------- 画面のイメージ（screen.style ごと） ----------------
# どれも (画像, 部品の矩形リスト) を返す。矩形の番号は spec.json の targets で使う。

def screen_app(w, h, s):
    """左メニュー付きの業務アプリ・管理画面。部品 = 入力欄… → ボタン"""
    dark = col(s.get("chrome", "dark"))
    im = Image.new("RGBA", (w, h), P["surface"])
    d = ImageDraw.Draw(im)
    window_chrome(d, w, dark)
    sb = int(w * 0.24)
    d.rectangle((0, 44, sb, h), fill=dark)
    fm = font(24, "Medium")
    for i, m in enumerate(s.get("menu", ["ホーム", "一覧", "新規作成", "設定"])):
        yy = 80 + i * 62
        on = m == s.get("active")
        if on:
            d.rectangle((0, yy - 14, sb, yy + 44), fill=P["accent"])
        size = fit(d, m, 24, "Medium", sb - 30)
        d.text((24, yy), m, font=font(size, "Medium"), fill=(240, 240, 241) if on else (195, 196, 199))
    x0 = sb + 40
    d.rectangle((sb, 44, w, h), fill=mix(P["surface"], P["line"], 0.4))
    d.text((x0, 76), s.get("title", ""), font=font(40, "Bold"), fill=P["ink"])
    fy, rects = 160, []
    for f in s.get("fields", []):
        d.text((x0, fy), f, font=font(26, "Medium"), fill=P["sub"])
        box = (x0, fy + 42, w - 40, fy + 108)
        d.rounded_rectangle(box, radius=6, fill=P["surface"], outline=mix(P["sub"], P["surface"], 0.3), width=2)
        rects.append(box)
        fy += 150
    if s.get("button"):
        bw = max(200, d.textlength(s["button"], font=font(30, "Bold")) + 60)
        bt = (x0, fy + 10, x0 + bw, fy + 80)
        d.rounded_rectangle(bt, radius=6, fill=P["accent"])
        text_c(d, (bt[0] + bt[2]) / 2, bt[1] + 14, s["button"], font(30, "Bold"), (255, 255, 255))
        rects.append(bt)
    return im, rects

def screen_sheet(w, h, s):
    """表計算。部品 = 各データ行 → ボタン"""
    im = Image.new("RGBA", (w, h), P["surface"])
    d = ImageDraw.Draw(im)
    window_chrome(d, w, col(s.get("chrome", "dark")))
    d.text((30, 64), s.get("title", ""), font=font(36, "Bold"), fill=P["ink"])
    cols = s.get("columns", ["A", "B", "C"])
    rows = s.get("rows", [])
    gx, gy, rh = 30, 140, 74
    cw = (w - 60) / len(cols)
    d.rectangle((gx, gy, w - 30, gy + rh), fill=mix(P["surface"], P["accent"], 0.12))
    for j, c in enumerate(cols):
        sz = fit(d, c, 26, "Bold", cw - 24)
        d.text((gx + j * cw + 14, gy + 20), c, font=font(sz, "Bold"), fill=P["ink"])
    rects = []
    for i, r in enumerate(rows):
        y = gy + rh * (i + 1)
        for j, v in enumerate(r[:len(cols)]):
            sz = fit(d, str(v), 26, "Regular", cw - 24)
            d.text((gx + j * cw + 14, y + 20), str(v), font=font(sz, "Regular"), fill=P["ink"])
        rects.append((gx, y, w - 30, y + rh))
    nrows = len(rows) + 1
    for i in range(nrows + 1):
        d.line((gx, gy + i * rh, w - 30, gy + i * rh), fill=P["line"], width=2)
    for j in range(len(cols) + 1):
        d.line((gx + j * cw, gy, gx + j * cw, gy + nrows * rh), fill=P["line"], width=2)
    if s.get("button"):
        y = gy + nrows * rh + 40
        bw = max(200, d.textlength(s["button"], font=font(30, "Bold")) + 60)
        bt = (gx, y, gx + bw, y + 70)
        d.rounded_rectangle(bt, radius=6, fill=P["accent"])
        text_c(d, (bt[0] + bt[2]) / 2, bt[1] + 14, s["button"], font(30, "Bold"), (255, 255, 255))
        rects.append(bt)
    return im, rects

def wrap(d, s, f, maxw):
    lines, cur = [], ""
    for ch in s:
        if d.textlength(cur + ch, font=f) > maxw and cur:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines

def screen_chat(w, h, s):
    """チャット。部品 = 各吹き出し → 入力欄"""
    im = Image.new("RGBA", (w, h), mix(P["surface"], P["line"], 0.3))
    d = ImageDraw.Draw(im)
    window_chrome(d, w, col(s.get("chrome", "dark")))
    d.text((30, 64), s.get("title", ""), font=font(34, "Bold"), fill=P["ink"])
    f = font(28, "Medium")
    y, rects = 140, []
    for m in s.get("messages", []):
        me = m.get("from") == "user"
        lines = wrap(d, m.get("text", ""), f, w * 0.6)
        bw = max(d.textlength(l, font=f) for l in lines) + 48
        bh = len(lines) * 42 + 30
        x = w - 30 - bw if me else 30
        fill = P["accent"] if me else P["surface"]
        d.rounded_rectangle((x, y, x + bw, y + bh), radius=22, fill=fill, outline=None if me else P["line"], width=2)
        for i, l in enumerate(lines):
            d.text((x + 24, y + 12 + i * 42), l, font=f, fill=(255, 255, 255) if me else P["ink"])
        rects.append((x, y, x + bw, y + bh))
        y += bh + 26
    ib = (30, h - 100, w - 30, h - 30)
    d.rounded_rectangle(ib, radius=34, fill=P["surface"], outline=P["line"], width=2)
    d.text((60, h - 86), s.get("placeholder", "メッセージを入力"), font=font(26, "Regular"), fill=P["sub"])
    rects.append(ib)
    return im, rects

def screen_terminal(w, h, s):
    """ターミナル・コード。部品 = 各行"""
    bg = col(s.get("chrome", "dark"))
    im = Image.new("RGBA", (w, h), bg)
    d = ImageDraw.Draw(im)
    window_chrome(d, w, mix(bg, (0, 0, 0), 0.3))
    d.text((30, 64), s.get("title", ""), font=font(28, "Bold"), fill=(240, 184, 73))
    f = font(32, "Regular")
    rects = []
    for i, l in enumerate(s.get("lines", [])):
        y = 140 + i * 84
        c = (140, 220, 160) if l.startswith("✓") else (220, 222, 225)
        d.text((30, y), l, font=f, fill=c)
        rects.append((22, y - 4, min(w - 22, 30 + d.textlength(l, font=f) + 12), y + 50))
    return im, rects

SCREENS = {"app": screen_app, "sheet": screen_sheet, "chat": screen_chat, "terminal": screen_terminal}

def screen(w, h, s):
    return SCREENS[s.get("style", "app")](w, h, s)

# ---------------- 出力アイコン・文書カード ----------------
def doc_card(w, h, card, accent, dark):
    """できあがる資料のイメージ（見出し帯＋小さな画面＋説明）"""
    im = Image.new("RGBA", (w, h), P["surface"])
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, w, int(h * 0.16)), fill=dark)
    t = card.get("title", "")
    d.text((28, int(h * 0.04)), t, font=font(fit(d, t, int(h * 0.07), "Bold", w - 56), "Bold"), fill=(255, 255, 255))
    sx, sy, sw, sh = 28, int(h * 0.22), int(w * 0.58), int(h * 0.68)
    d.rectangle((sx, sy, sx + sw, sy + sh), fill=mix(P["surface"], P["line"], 0.4), outline=P["line"], width=2)
    d.rectangle((sx, sy, sx + int(sw * 0.22), sy + sh), fill=P["dark"])
    for i in range(3):
        yy = sy + 40 + i * int(sh * 0.22)
        d.rounded_rectangle((sx + int(sw * 0.3), yy, sx + sw - 20, yy + int(sh * 0.11)), radius=4, fill=P["surface"], outline=mix(P["sub"], P["surface"], 0.4))
    bx = (sx + int(sw * 0.3) - 8, sy + 32, sx + sw - 12, sy + 40 + int(sh * 0.11) + 8)
    d.rectangle(bx, outline=P["alert"], width=max(2, int(h / 130)))
    badge(d, bx[0], bx[1], 1, r=max(8, h / 32))
    tx = sx + sw + 28
    for i, s in enumerate(card.get("lines", [])[:2]):
        d.text((tx, sy + 10 + i * int(h * 0.075)), s, font=font(fit(d, s, int(h * 0.055), "Bold", w - tx - 20), "Bold"), fill=P["ink"])
    for i in range(3):
        yy = sy + int(h * 0.24) + i * int(h * 0.07)
        d.rounded_rectangle((tx, yy, w - 28 - (i * 40), yy + max(4, h // 52)), radius=5, fill=P["line"])
    note = card.get("note")
    if note:
        d.rounded_rectangle((tx, sy + sh - int(h * 0.12), w - 28, sy + sh), radius=10, fill=mix(P["surface"], accent, 0.12))
        d.text((tx + 14, sy + sh - int(h * 0.1)), note, font=font(fit(d, note, int(h * 0.04), "Medium", w - tx - 56), "Medium"), fill=accent)
    return im

def output_tile(bw, bh, o):
    c = col(o.get("color", "accent"))
    tile = Image.new("RGBA", (bw, bh), P["surface"])
    td = ImageDraw.Draw(tile)
    td.rectangle((0, 0, bw, 14), fill=c)
    icon = o.get("icon", "doc")
    if icon == "video":
        td.rounded_rectangle((30, 60, bw - 30, 250), radius=10, fill=mix(P["surface"], P["line"], 0.5))
        td.polygon([(bw / 2 - 30, 115), (bw / 2 - 30, 195), (bw / 2 + 40, 155)], fill=c)
        if o.get("sub"):
            td.rounded_rectangle((30, 270, bw - 30, 300), radius=8, fill=P["ink"])
            td.text((42, 271), o["sub"], font=font(fit(td, o["sub"], 19, "Medium", bw - 84), "Medium"), fill=(255, 255, 255))
    elif icon == "sheet":
        for i in range(5):
            for j in range(3):
                x = 30 + j * (bw - 60) / 3
                y = 60 + i * 44
                td.rectangle((x, y, x + (bw - 60) / 3, y + 44), outline=P["line"], width=2, fill=mix(P["surface"], c, 0.15) if i == 0 else None)
    elif icon == "image":
        td.rounded_rectangle((30, 60, bw - 30, 290), radius=10, fill=mix(P["surface"], c, 0.15))
        td.ellipse((bw - 110, 90, bw - 60, 140), fill=c)
        td.polygon([(40, 280), (130, 160), (200, 240), (240, 200), (bw - 40, 280)], fill=c)
    elif icon == "code":
        td.rounded_rectangle((30, 60, bw - 30, 290), radius=10, fill=P["dark"])
        for i in range(5):
            td.rounded_rectangle((50 + (i % 2) * 30, 85 + i * 40, bw - 60 - (i * 17 % 60), 97 + i * 40), radius=6, fill=(140, 220, 160) if i == 2 else (180, 184, 190))
    elif icon == "chat":
        td.rounded_rectangle((30, 70, bw - 90, 150), radius=20, fill=mix(P["surface"], P["line"], 0.6))
        td.rounded_rectangle((90, 175, bw - 30, 255), radius=20, fill=c)
    else:  # doc / slides
        sm = doc_card(460, 260, {"title": o.get("name", ""), "lines": ["", ""]}, P["accent"], P["dark"]).resize((bw - 60, int((bw - 60) * 260 / 460)), Image.LANCZOS)
        for k in range(2):
            tile.alpha_composite(sm, (30 + k * 10, 60 + k * 95))
    name = o.get("name", "")
    text_c(td, bw / 2, bh - 90, name, font(fit(td, name, 40, "Black", bw - 24), "Black"), P["ink"])
    return tile

# ---------------- シーン ----------------
SCR_X, SCR_Y, SCR_W, SCR_H = 90, 640, 900, 860

def sc_hook(sc, t):
    img = Image.new("RGBA", (W, H), P["bg"])
    v = sc.get("visual", {})
    base = v.get("screen", {})
    titles = v.get("titles", [base.get("title", "")] * 6)
    rnd = random.Random(3)
    for i, ttl in enumerate(titles[:6]):
        p = prog(t, 0.05 * i, 0.5)
        s2 = dict(base, title=ttl)
        sh, _ = screen(620, 460, s2)
        ang = rnd.uniform(-14, 14)
        sh = sh.rotate(ang, expand=True, resample=Image.BICUBIC)
        x = W / 2 + rnd.uniform(-150, 150) - sh.width / 2
        y = 1100 + rnd.uniform(-110, 150) - sh.height / 2 + (1 - p) * 300
        if p > 0:
            sh.putalpha(sh.getchannel("A").point(lambda a: int(a * p)))
            img.alpha_composite(sh, (int(x), int(y)))
    headline(img, t, sc["title"], y=260, size=110, start=0.15)
    caption(img, t, sc.get("caption"), y=1660, start=0.9)
    return img

def step_header(img, sc, t):
    d = ImageDraw.Draw(img)
    if sc.get("step"):
        step_tag(d, sc["step"], sc.get("total", 3))
    headline(img, t, sc["title"], y=240, size=104)

def sc_cursor(sc, t, dur):
    """画面に入力していき、撮影（シャッター）する"""
    img = Image.new("RGBA", (W, H), P["bg"])
    step_header(img, sc, t)
    v = sc["visual"]
    adm, rects = screen(SCR_W, SCR_H, v["screen"])
    p = prog(t, 0.1, 0.6)
    x, y = SCR_X, SCR_Y + (1 - p) * 80
    shadow_paste(img, adm, x, y)
    d = ImageDraw.Draw(img)
    tg = v.get("targets") or list(range(min(2, len(rects) - 1))) + [len(rects) - 1]
    pts = [(700, 1700)] + [((rects[i][0] + rects[i][2]) / 2 + x, (rects[i][1] + rects[i][3]) / 2 + y - 10) for i in tg]
    move = max(1.5, dur - 2.2)
    tt = clamp((t - 0.7) / move) * (len(pts) - 1)
    i = min(int(tt), len(pts) - 2)
    k = ease(tt - i)
    cursor(d, pts[i][0] + (pts[i + 1][0] - pts[i][0]) * k, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * k)
    shots = [0.7 + move * (j + 1) / (len(pts) - 1) - 0.05 for j in range(len(pts) - 1)]
    for ts in shots:
        f = t - ts
        if 0 <= f < 0.35:
            img.alpha_composite(Image.new("RGBA", adm.size, (255, 255, 255, int(170 * (1 - f / 0.35)))), (int(x), int(y)))
    counter = v.get("counter")
    n = sum(1 for ts in shots if t >= ts)
    if counter and n:
        d = ImageDraw.Draw(img)
        s = counter.replace("{n}", str(n))
        f = font(40, "Bold")
        tw = d.textlength(s, font=f)
        d.rounded_rectangle((W - 90 - tw - 50, 110, W - 90, 174), radius=32, fill=P["ink"])
        d.text((W - 90 - tw - 25, 116), s, font=f, fill=(255, 255, 255))
    caption(img, t, sc.get("caption"), y=1640, start=0.8)
    return img

def sc_highlight(sc, t, dur):
    """画面の部品に赤枠と番号を順に付ける"""
    img = Image.new("RGBA", (W, H), P["bg"])
    step_header(img, sc, t)
    v = sc["visual"]
    adm, rects = screen(SCR_W, SCR_H, v["screen"])
    x, y = SCR_X, SCR_Y
    shadow_paste(img, adm, x, y)
    d = ImageDraw.Draw(img)
    tg = v.get("targets") or [0, len(rects) - 1]
    gap = min(1.1, (dur - 1.5) / max(1, len(tg)))
    for j, ri in enumerate(tg):
        r = rects[ri]
        st = 0.5 + j * gap
        p = prog(t, st, 0.5)
        if p <= 0:
            continue
        x1, y1, x2, y2 = r[0] + x - 10, r[1] + y - 10, r[2] + x + 10, r[3] + y + 10
        L = 2 * ((x2 - x1) + (y2 - y1)) * p
        for a, b in [((x1, y1), (x2, y1)), ((x2, y1), (x2, y2)), ((x2, y2), (x1, y2)), ((x1, y2), (x1, y1))]:
            sl = math.dist(a, b)
            if L <= 0:
                break
            q = min(1, L / sl)
            d.line((a, (a[0] + (b[0] - a[0]) * q, a[1] + (b[1] - a[1]) * q)), fill=P["alert"], width=7)
            L -= sl
        bk = prog(t, st + 0.35, 0.3)
        if bk > 0 and v.get("numbers", True):
            badge(d, x1, y1, j + 1, r=34, k=bk)
    caption(img, t, sc.get("caption"), y=1640, start=1.2)
    return img

def sc_fanout(sc, t, dur):
    """1つの入力から複数の成果物ができる"""
    img = Image.new("RGBA", (W, H), P["bg"])
    step_header(img, sc, t)
    v = sc["visual"]
    d = ImageDraw.Draw(img)
    inp = v.get("input", {})
    p = prog(t, 0.3, 0.5)
    cw, ch = 560, 300
    cx, cy = (W - cw) / 2, 640 + (1 - p) * 60
    if p > 0:
        card = Image.new("RGBA", (cw, ch), P["dark"])
        cd = ImageDraw.Draw(card)
        cd.text((30, 26), inp.get("title", ""), font=font(34, "Bold"), fill=(240, 184, 73))
        for i, s in enumerate(inp.get("lines", [])[:3]):
            cd.text((30, 96 + i * 52), s, font=font(fit(cd, s, 30, "Regular", cw - 60), "Regular"), fill=(220, 222, 225))
        shadow_paste(img, card, cx, cy, r=18)
    d = ImageDraw.Draw(img)
    outs = v.get("outputs", [])[:3]
    n = max(1, len(outs))
    gap = 30
    bw = min(290, (W - 80 - gap * (n - 1)) / n)
    bh = 420
    total = bw * n + gap * (n - 1)
    for i, o in enumerate(outs):
        q = prog(t, 1.3 + i * 0.35, 0.5)
        if q <= 0:
            continue
        d.line(((W / 2, cy + ch), (W / 2, cy + ch + 40 * q)), fill=P["ink"], width=4)
        shadow_paste(img, output_tile(int(bw), bh, o), (W - total) / 2 + i * (bw + gap), 1080 + (1 - q) * 80, r=14, alpha=40)
        d = ImageDraw.Draw(img)
    caption(img, t, sc.get("caption"), y=1640, start=2.6)
    return img

def sc_variants(sc, t, dur):
    """同じ成果物の色・見た目が切り替わる"""
    img = Image.new("RGBA", (W, H), P["bg"])
    step_header(img, sc, t)
    v = sc["visual"]
    pals = [(hexrgb(a), hexrgb(b)) for a, b in v.get("palettes", [[DEFAULT_PALETTE["accent"], DEFAULT_PALETTE["dark"]]] * 2)]
    seg = clamp((t - 0.8) / (dur - 1.4)) * (len(pals) - 1)
    i = min(int(seg), len(pals) - 2) if len(pals) > 1 else 0
    k = ease((seg - i) * 1.6) if len(pals) > 1 else 0
    nxt = pals[min(i + 1, len(pals) - 1)]
    acc, dk = mix(pals[i][0], nxt[0], k), mix(pals[i][1], nxt[1], k)
    p = prog(t, 0.2, 0.6)
    shadow_paste(img, doc_card(920, 520, v.get("card", {}), acc, dk), 80, 720 + (1 - p) * 60, r=14)
    d = ImageDraw.Draw(img)
    for j, (a, _) in enumerate(pals):
        cx = W / 2 + (j - (len(pals) - 1) / 2) * 130
        on = abs(seg - j) < 0.5
        r = 44 if on else 34
        d.ellipse((cx - r, 1400 - r, cx + r, 1400 + r), fill=a, outline=P["ink"] if on else None, width=5)
    caption(img, t, sc.get("caption"), y=1560, start=0.9)
    return img

def sc_end(sc, t, dur):
    img = Image.new("RGBA", (W, H), P["dark"])
    d = ImageDraw.Draw(img)
    light = (195, 196, 199)
    p = prog(t, 0.1, 0.6)
    for i, s in enumerate(SPEC.get("tagline", [])[:2]):
        text_c(d, W / 2, 560 + i * 90 + (1 - p) * 30, s, font(fit(d, s, 60, "Medium", W - 120), "Medium"), mix(P["dark"], light, p))
    q = prog(t, 0.5, 0.6)
    s = SPEC["name"]
    size = fit(d, s, 108, "Black", W - 100)
    f2 = font(size, "Black")
    tw = d.textlength(s, font=f2)
    d.text((W / 2 - tw / 2, 820 + (1 - q) * 40), s, font=f2, fill=mix(P["dark"], (255, 255, 255), q))
    u = prog(t, 0.9, 0.6)
    uy = 820 + size * 1.38
    d.rectangle((W / 2 - tw / 2, uy, W / 2 - tw / 2 + tw * u, uy + 12), fill=P["alert"])
    tags = SPEC.get("tags", [])
    if tags:
        r = prog(t, 1.4, 0.6)
        f3 = font(40, "Bold")
        widths = [d.textlength(x, font=f3) + 70 for x in tags]
        xx = W / 2 - (sum(widths) + 30 * (len(tags) - 1)) / 2
        c = mix(P["dark"], light, r)
        for x, wd in zip(tags, widths):
            d.rounded_rectangle((xx, 1060, xx + wd, 1130), radius=35, outline=c, width=3)
            d.text((xx + 35, 1068), x, font=f3, fill=c)
            xx += wd + 30
    g = prog(t, 2.0, 0.6)
    if SPEC.get("url"):
        text_c(d, W / 2, 1400, SPEC.get("url_label", "GitHub"), font(34, "Bold"), mix(P["dark"], (140, 143, 148), g))
        text_c(d, W / 2, 1452, SPEC["url"], font(fit(d, SPEC["url"], 38, "Medium", W - 100), "Medium"), mix(P["dark"], (255, 255, 255), g))
    return img

KINDS = {"cursor": sc_cursor, "highlight": sc_highlight, "fanout": sc_fanout, "variants": sc_variants}

def draw_scene(si, t):
    sc = SPEC["scenes"][si]
    dur = sc["duration"]
    typ = sc.get("type")
    if typ == "hook":
        return sc_hook(sc, t)
    if typ == "end":
        return sc_end(sc, t, dur)
    return KINDS[sc["visual"]["kind"]](sc, t, dur)

def frame(si, t):
    im = draw_scene(si, t)
    if si > 0 and t < FADE:
        pv = draw_scene(si - 1, SPEC["scenes"][si - 1]["duration"] + t)
        im = Image.blend(pv, im, ease(t / FADE))
    return im.convert("RGB")

# ---------------- 書き出し ----------------
def render(args):
    spec_path, out, si = args
    load(spec_path)
    n = int(round(SPEC["scenes"][si]["duration"] * FPS))
    tmp, dst = os.path.join(out, f"scene{si}.tmp.mp4"), os.path.join(out, f"scene{si}.mp4")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", str(FPS), tmp]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for k in range(n):
        pr.stdin.write(frame(si, k / FPS).tobytes())
    pr.stdin.close()
    if pr.wait() != 0:
        raise RuntimeError(f"scene{si} の書き出しに失敗")
    os.replace(tmp, dst)
    return dst

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--out", default=".")
    ap.add_argument("--preview", nargs="*")
    ap.add_argument("--sheet", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    load(a.spec)
    if a.preview is not None:
        for x in a.preview:
            si, t = x.split(":")
            frame(int(si), float(t)).save(os.path.join(a.out, f"pv_{si}_{t}.png"))
        return
    if a.sheet:
        # 各シーンの終わり近く（いちばん要素が多いコマ）を並べる
        ims = [frame(i, max(0, sc["duration"] - 0.4)).resize((360, 640)) for i, sc in enumerate(SPEC["scenes"])]
        cols = 3
        rows = math.ceil(len(ims) / cols)
        sheet = Image.new("RGB", (360 * cols, 640 * rows), (128, 128, 128))
        for i, im in enumerate(ims):
            sheet.paste(im, ((i % cols) * 360, (i // cols) * 640))
        sheet.save(os.path.join(a.out, "sheet.png"))
        print(os.path.join(a.out, "sheet.png"))
        return
    import concurrent.futures as cf
    with cf.ProcessPoolExecutor() as ex:
        files = list(ex.map(render, [(a.spec, a.out, i) for i in range(len(SPEC["scenes"]))]))
    lst = os.path.join(a.out, "list.txt")
    with open(lst, "w") as f:
        for p in files:
            f.write(f"file '{os.path.abspath(p)}'\n")
    final = os.path.join(a.out, SPEC.get("output", f"{SPEC['name']}_promo.mp4"))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", final], check=True)
    for p in files:
        os.remove(p)
    os.remove(lst)
    print(final)

if __name__ == "__main__":
    main()
