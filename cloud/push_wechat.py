# -*- coding: utf-8 -*-
"""生成海报后推送到微信（Server酱）。在 GitHub Actions 里跑。

图片托管：公开仓库 + jsDelivr CDN（国内可直连）。
jsDelivr 对新提交有缓存延迟，所以推送前先轮询预热，任一链路可用即用。
"""
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = Path(__file__).parent
REPO = os.environ.get("GITHUB_REPOSITORY", "")  # owner/name

# jsDelivr 主站 / Fastly 备用 / GitHub 原链（国内可能不通，作最后兜底）
CDN_TEMPLATES = [
    "https://cdn.jsdelivr.net/gh/{repo}@main/posters/poster_{d}.jpg",
    "https://fastly.jsdelivr.net/gh/{repo}@main/posters/poster_{d}.jpg",
    "https://raw.githubusercontent.com/{repo}/main/posters/poster_{d}.jpg",
]


def _probe(url, timeout=8):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status == 200 and len(r.read(1024)) > 0
    except Exception:
        return False


def resolve_image_url(d):
    """轮询预热，返回第一个真正可访问的图片地址"""
    if not REPO:
        return ""
    urls = [t.format(repo=REPO, d=d) for t in CDN_TEMPLATES]
    for attempt in range(8):          # 最多 8 轮 × 8 秒 ≈ 1 分钟
        for u in urls:
            if _probe(u):
                print("IMG OK:", u)
                return u
        time.sleep(8)
    print("IMG: 所有 CDN 均未就绪，本次仅推文字")
    return ""


def push_serverchan(title, desp, key):
    url = f"https://sctapi.ftqq.com/{key}.send"
    data = urllib.parse.urlencode({"title": title[:32], "desp": desp}).encode()
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=20) as r:
        resp = json.loads(r.read().decode("utf-8", "ignore"))
    if resp.get("code") == 0:
        print("PUSH: OK Server酱")
    else:
        print("PUSH: Server酱返回错误", str(resp)[:300])


def main():
    info = json.loads((BASE / "_info.json").read_text(encoding="utf-8"))
    d = info["date"]
    key = os.environ.get("SERVERCHAN_KEY", "").strip()
    if not key:
        print("PUSH: 未配置 SERVERCHAN_KEY，跳过推送")
        return

    jieqi = info.get("jieqi_line", "").replace(" · ", " ")
    month, day = int(d[5:7]), int(d[8:10])
    title = f"早安 · {month}月{day}日 {jieqi}".strip()

    desp = []
    img = resolve_image_url(d)
    if img:
        desp.append(f"![]({img})")
    q = info["quote"]
    desp.append(f"**{q['text']}**")
    desp.append(f"{q['author']}《{q['work']}》")
    desp.append(f"{info['date_line']}　{info['lunar_line']}")
    if info.get("jieqi_line"):
        desp.append(info["jieqi_line"])
    src = info.get("photo_source", "")
    if src.startswith("commons:"):
        artist = src.split(":", 1)[1].strip()
        desp.append(f"📷 图：{artist or 'Wikimedia'}（Wikimedia Commons）")
    desp = "\n\n".join(desp)

    push_serverchan(title, desp, key)


if __name__ == "__main__":
    main()
