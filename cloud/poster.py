# -*- coding: utf-8 -*-
"""
每日早安海报生成器
输入：当天日期 → 输出：poster_YYYY-MM-DD.jpg (1080x1620)
布局：顶部 日期/农历/节气候 → 中部金句 → 右下「涛哥的小舟」徽标
"""
import json
import math
import random
import re
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

BASE = Path(__file__).parent
W, H = 1080, 1620

# ---------- 二十四节气 · 七十二候 ----------
HOU = {
    "立春": ["东风解冻", "蛰虫始振", "鱼陟负冰"],
    "雨水": ["獭祭鱼", "鸿雁来", "草木萌动"],
    "惊蛰": ["桃始华", "仓庚鸣", "鹰化为鸠"],
    "春分": ["玄鸟至", "雷乃发声", "始电"],
    "清明": ["桐始华", "田鼠化为鴽", "虹始见"],
    "谷雨": ["萍始生", "鸣鸠拂其羽", "戴胜降于桑"],
    "立夏": ["蝼蝈鸣", "蚯蚓出", "王瓜生"],
    "小满": ["苦菜秀", "靡草死", "麦秋至"],
    "芒种": ["螳螂生", "鵙始鸣", "反舌无声"],
    "夏至": ["鹿角解", "蜩始鸣", "半夏生"],
    "小暑": ["温风至", "蟋蟀居宇", "鹰始挚"],
    "大暑": ["腐草为萤", "土润溽暑", "大雨时行"],
    "立秋": ["凉风至", "白露生", "寒蝉鸣"],
    "处暑": ["鹰乃祭鸟", "天地始肃", "禾乃登"],
    "白露": ["鸿雁来", "玄鸟归", "群鸟养羞"],
    "秋分": ["雷始收声", "蛰虫培户", "水始涸"],
    "寒露": ["鸿雁来宾", "雀入大水为蛤", "菊有黄华"],
    "霜降": ["豺乃祭兽", "草木黄落", "蛰虫咸俯"],
    "立冬": ["水始冰", "地始冻", "雉入大水为蜃"],
    "小雪": ["虹藏不见", "天气上升地气下降", "闭塞而成冬"],
    "大雪": ["鹖鴠不鸣", "虎始交", "荔挺出"],
    "冬至": ["蚯蚓结", "麋角解", "水泉动"],
    "小寒": ["雁北乡", "鹊始巢", "雉始雊"],
    "大寒": ["鸡始乳", "征鸟厉疾", "水泽腹坚"],
}
HOU_ORD = ["初候", "二候", "三候"]
WEEK = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
NUM_CN = "一二三四五六七八九十"


def n2cn(n):
    """1-30 → 中文（廿X 格式）"""
    if n <= 10:
        return NUM_CN[n-1]
    if n == 20:
        return "二十"
    if n == 30:
        return "三十"
    if n < 20:
        return "十" + NUM_CN[n-11]
    return "廿" + NUM_CN[n-21]


def lunar_day_cn(n):
    """农历日：初一~初十、十一~十九、二十、廿一~廿九、三十"""
    if n <= 10:
        return "初" + NUM_CN[n-1]
    if n == 20:
        return "二十"
    if n == 30:
        return "三十"
    return n2cn(n)


def calendar_info(d):
    """返回 (日期行, 农历行, 节气行)"""
    from lunar_python import Solar
    solar = Solar.fromYmd(d.year, d.month, d.day)
    lunar = solar.getLunar()

    date_line = f"{d.year}.{d.month:02d}.{d.day:02d} {WEEK[d.weekday()]}"
    lunar_line = f"农历{n2cn(lunar.getMonth())}月{lunar_day_cn(lunar.getDay())}"

    # 当前节气：往前找最近一个已到的节气
    PINYIN = {
        "LI_CHUN": "立春", "YU_SHUI": "雨水", "JING_ZHE": "惊蛰", "CHUN_FEN": "春分",
        "QING_MING": "清明", "GU_YU": "谷雨", "LI_XIA": "立夏", "XIAO_MAN": "小满",
        "MANG_ZHONG": "芒种", "XIA_ZHI": "夏至", "XIAO_SHU": "小暑", "DA_SHU": "大暑",
        "LI_QIU": "立秋", "CHU_SHU": "处暑", "BAI_LU": "白露", "QIU_FEN": "秋分",
        "HAN_LU": "寒露", "SHUANG_JIANG": "霜降", "LI_DONG": "立冬", "XIAO_XUE": "小雪",
        "DA_XUE": "大雪", "DONG_ZHI": "冬至", "XIAO_HAN": "小寒", "DA_HAN": "大寒",
    }
    from datetime import date as _date
    table = lunar.getJieQiTable()  # 键名中英文混用：中文或拼音
    terms = sorted(
        [(PINYIN.get(name, name), _date.fromisoformat(s.toYmd()))
         for name, s in table.items() if name in PINYIN or name in HOU],
        key=lambda x: x[1],
    )
    prev = None
    for name, tdate in terms:
        if tdate <= d:
            prev = (name, tdate)
        else:
            break
    if prev:
        tname, tdate = prev
        idx = min((d - tdate).days // 5, 2)
        jieqi_line = f"{tname} · {HOU_ORD[idx]} {HOU[tname][idx]}"
    else:
        jieqi_line = ""
    return date_line, lunar_line, jieqi_line


def pick_quote(d):
    quotes = json.loads((BASE / "quotes.json").read_text(encoding="utf-8"))
    # 按日期确定性轮换
    idx = d.toordinal() % len(quotes)
    return quotes[idx]


# ---------- 图源 ----------
CITY_QUERIES = ["city skyline morning", "city sunrise", "urban skyline dawn",
                "city skyline golden hour", "cityscape morning light"]


def fetch_photo(d, out):
    """三层图源：Pexels(有key) → Wikimedia Commons(免key) → 本地照片池"""
    import os
    # 1) Pexels（官方 key，若后续开放申请）
    key = os.environ.get("PEXELS_KEY", "").strip()
    if key:
        try:
            q = random.choice(CITY_QUERIES)
            url = ("https://api.pexels.com/v1/search?query=" + urllib.parse.quote(q)
                   + "&orientation=portrait&per_page=20&page="
                   + str((d.toordinal() % 30) + 1))
            req = urllib.request.Request(url, headers={"Authorization": key})
            data = json.loads(urllib.request.urlopen(req, timeout=30).read())
            photos = data.get("photos", [])
            if photos:
                ph = photos[d.toordinal() % len(photos)]
                src = ph["src"]["large2x"]
                req2 = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})
                open(out, "wb").write(urllib.request.urlopen(req2, timeout=60).read())
                return "pexels"
        except Exception as e:
            print("Pexels 失败，转 Openverse:", e)

    # 2) Wikimedia Commons（永久免 key，真实摄影图）
    try:
        q = random.Random(d.toordinal()).choice(CITY_QUERIES)  # 按日期确定性选词
        params = urllib.parse.urlencode({
            "action": "query", "format": "json", "generator": "search",
            "gsrsearch": f"filetype:bitmap {q}", "gsrnamespace": "6",
            "gsrlimit": "50", "prop": "imageinfo",
            "iiprop": "url|size|extmetadata", "iiurlwidth": "1200",
        })
        req = urllib.request.Request(
            "https://commons.wikimedia.org/w/api.php?" + params,
            headers={"User-Agent": "morning-poster/1.0 (personal daily poster)"})
        data = json.loads(urllib.request.urlopen(req, timeout=30).read())
        pages = list(data.get("query", {}).get("pages", {}).values())
        cands = []
        for p in pages:
            try:
                ii = p["imageinfo"][0]
                if ii.get("width", 0) >= 900 and ii.get("height", 0) >= ii.get("width", 1):
                    cands.append(ii)
            except (KeyError, IndexError, TypeError):
                continue
        if cands:
            ii = cands[d.toordinal() % len(cands)]
            src = ii.get("thumburl") or ii["url"]
            req2 = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})
            raw = urllib.request.urlopen(req2, timeout=90).read()
            if len(raw) > 100000:
                open(out, "wb").write(raw)
                # 提取作者用于署名
                meta = ii.get("extmetadata", {}) or {}
                artist = re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", "")).strip()
                artist = re.sub(r"\s+", " ", artist)[:60]
                return f"commons:{artist}" if artist else "commons"
        print("Commons 无合适候选")
    except Exception as e:
        print("Commons 失败，退回照片池:", e)

    # 3) 内置照片池（保底，永不断供）
    pool = sorted((BASE / "pool").glob("*.jpg"))
    if not pool:
        raise RuntimeError("照片池为空")
    random.seed(d.toordinal())          # 每天确定性地选一张
    chosen = pool[d.toordinal() % len(pool)]
    open(out, "wb").write(chosen.read_bytes())
    return f"pool:{chosen.stem}"


import urllib.parse  # noqa: E402  (fetch_photo 里用到)


# ---------- 合成 ----------
def _font(*candidates, size):
    """按顺序找第一个可用的字体文件"""
    for p in candidates:
        if p and Path(p).exists() and Path(p).stat().st_size > 100000:
            return str(p)
    return "C:/Windows/Fonts/simkai.ttf"


def load_fonts():
    fdir = BASE / "fonts"
    wenkai_reg = fdir / "LXGWWenKai-Regular.ttf"
    wenkai_med = fdir / "LXGWWenKai-Medium.ttf"
    win_kai = "C:/Windows/Fonts/simkai.ttf"
    win_hei = "C:/Windows/Fonts/simhei.ttf"
    bold = _font(wenkai_med, wenkai_reg, win_hei, win_kai, size=64)
    reg = _font(wenkai_reg, win_kai, size=30)
    # 金句：毛笔楷书（本机用华文行楷，云端用免费可商用的马善政），不加粗
    xingkai_win = "C:/Windows/Fonts/STXINGKA.TTF"
    mashan = fdir / "MaShanZheng-Regular.ttf"
    quote = _font(xingkai_win, mashan, wenkai_med, wenkai_reg, win_kai, size=64)
    return {
        "date": ImageFont.truetype(bold, 64),
        "sub": ImageFont.truetype(bold, 40),
        "quote": ImageFont.truetype(quote, 64),
        "attr": ImageFont.truetype(reg, 32),
    }


def text_with_shadow(draw, xy, text, font, anchor="mm",
                     fill=(255, 255, 255, 255), shadow=(0, 0, 0, 160),
                     stroke=0):
    x, y = xy
    draw.text((x + 3, y + 3), text, font=font, fill=shadow, anchor=anchor,
              stroke_width=stroke, stroke_fill=shadow)
    draw.text((x, y), text, font=font, fill=fill, anchor=anchor,
              stroke_width=stroke, stroke_fill=fill)


def draw_logo(img, font_path):
    """右下「涛哥的小舟」徽标"""
    LW, LH = 236, 78
    logo = Image.new("RGBA", (LW, LH), (0, 0, 0, 0))
    d = ImageDraw.Draw(logo)
    d.rounded_rectangle([0, 0, LW-1, LH-1], radius=18,
                        fill=(24, 22, 20, 228), outline=(214, 178, 110, 235), width=2)
    gold = (222, 186, 118, 255)
    cx, cy = 42, LH // 2 + 2
    d.pieslice([cx-22, cy-8, cx+22, cy+18], 15, 165, fill=gold)
    d.rectangle([cx-22, cy+3, cx+22, cy+7], fill=(24, 22, 20, 255))
    d.polygon([(cx+1, cy-27), (cx+1, cy-1), (cx+17, cy-1)], fill=gold)
    d.polygon([(cx-3, cy-19), (cx-3, cy-1), (cx-15, cy-1)], fill=gold)
    d.line([(cx, cy-28), (cx, cy-3)], fill=gold, width=2)
    d.arc([cx-30, cy+8, cx-8, cy+21], 200, 340, fill=gold, width=2)
    d.arc([cx+8, cy+8, cx+30, cy+21], 200, 340, fill=gold, width=2)
    font = ImageFont.truetype(
        _font(BASE / "fonts" / "LXGWWenKai-Regular.ttf",
              "C:/Windows/Fonts/simkai.ttf", size=32), 32)
    d.text((76, LH // 2), "涛哥的小舟", font=font,
           fill=(245, 238, 226, 255), anchor="lm")
    img.alpha_composite(logo, (W - LW - 24, H - LH - 24))


def compose(photo_path, out_path, d):
    date_line, lunar_line, jieqi_line = calendar_info(d)
    q = pick_quote(d)

    img = Image.open(photo_path).convert("RGB")
    # 中心裁切为海报比例
    tr = W / H
    w, h = img.size
    if w / h > tr:
        nw = int(h * tr)
        img = img.crop(((w - nw) // 2, 0, (w + nw) // 2, h))
    else:
        nh = int(w / tr)
        top = max(0, int((h - nh) * 0.35))   # 偏上取景
        img = img.crop((0, top, w, top + nh))
    img = img.resize((W, H)).convert("RGBA")

    # 顶部压暗渐变，保证日期可读
    grad = Image.new("L", (1, H), 0)
    for y in range(H):
        v = max(0, 200 - int(y / H * 700)) if y < H * 0.30 else 0
        grad.putpixel((0, y), v)
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    shade.putalpha(grad.resize((W, H)))
    img = Image.alpha_composite(img, shade)

    draw = ImageDraw.Draw(img, "RGBA")
    f = load_fonts()

    # 顶部三行
    y0 = 96
    text_with_shadow(draw, (W // 2, y0), date_line, f["date"])
    text_with_shadow(draw, (W // 2, y0 + 92), lunar_line, f["sub"])
    if jieqi_line:
        text_with_shadow(draw, (W // 2, y0 + 160), jieqi_line, f["sub"])

    # 金句（约 42% 高度处）
    qy = int(H * 0.42)
    lines = q["text"].split("，")
    if len(lines) < 2:
        lines = [q["text"][:len(q["text"])//2], q["text"][len(q["text"])//2:]]
    step = 96
    start = qy - (len(lines) - 1) * step // 2 - 24
    for i, ln in enumerate(lines):
        text_with_shadow(draw, (W // 2, start + i * step), ln, f["quote"])
    text_with_shadow(draw, (W // 2, start + len(lines) * step + 10),
                     f"——{q['author']}《{q['work']}》", f["attr"])

    draw_logo(img, BASE / "fonts" / "LXGWWenKai-Regular.ttf")
    img.convert("RGB").save(out_path, quality=90)
    return q


def main():
    from datetime import datetime, timezone, timedelta as td
    d = datetime.now(timezone(td(hours=8))).date()  # 北京日期
    out_dir = BASE.parent / "posters"
    out_dir.mkdir(exist_ok=True)
    tmp = BASE / "_photo.jpg"
    src = fetch_photo(d, tmp)
    q = compose(tmp, out_dir / f"poster_{d.isoformat()}.jpg", d)
    tmp.unlink(missing_ok=True)
    date_line, lunar_line, jieqi_line = calendar_info(d)
    info = {
        "date": d.isoformat(),
        "photo_source": src,
        "quote": q,
        "date_line": date_line,
        "lunar_line": lunar_line,
        "jieqi_line": jieqi_line,
    }
    (BASE / "_info.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print("DONE", json.dumps(info, ensure_ascii=False))


if __name__ == "__main__":
    main()
