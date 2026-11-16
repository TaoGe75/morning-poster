# -*- coding: utf-8 -*-
r"""
云端微信推送（GitHub Actions 里跑，仅标准库，不依赖本机）

链路：企业微信「消息推送」Webhook -> 微信插件 -> 个人微信。
只发纯文本：markdown 在个人微信里会显示成「暂不支持此消息类型」。
凭证只从环境变量读取，绝不写进代码、仓库或日志：
  WECOM_WEBHOOK        企业微信消息推送 Webhook
  IMPORTANT_DATES_JSON 重要日期库（含姓名/生日，隐私数据，仅存 Actions Secret）

模式（自动判断，无需参数）：
  1) PUSH_SCHEDULE_ID 有值      -> 发 push_schedule.json 里指定 id 的条目
  2) PUSH_TITLE / PUSH_BODY 有值 -> 发这条自定义内容（GitHub 网页手动触发）
  3) 都没有                     -> 定时模式，按北京时间匹配该发的条目

清单条目可带 "dynamic": "important_dates"，标题与正文按当天日期动态生成，
数据来自 IMPORTANT_DATES_JSON，云端不读 xlsx、不装第三方包。

本机自测：
  python cloud/wecom_push.py --list
  python cloud/wecom_push.py --dry-run
  IMPORTANT_DATES_FILE=... python cloud/wecom_push.py --render-dates 2026-11-16
"""
import json
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).parent
SCHEDULE = BASE / "push_schedule.json"
STATE = BASE / "_push_state.json"
BEIJING = timezone(timedelta(hours=8))
# workflow 每小时 05/35/50 分触发；GitHub 定时常延迟，窗口放宽到 55 分钟，
# 配合 _push_state.json 保证「不漏发、不重复发」。
WINDOW_MINUTES = 55
WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
DAY_LABELS = {0: "今天", 1: "明天", 2: "后天"}


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def items():
    return load_json(SCHEDULE, {"items": []}).get("items", [])


def send(title, body):
    hook = os.environ.get("WECOM_WEBHOOK", "").strip()
    if not hook:
        print("PUSH: SKIP 未配置 WECOM_WEBHOOK（检查仓库 Actions Secret）")
        return False
    content = (str(title) + "\n\n" + str(body)).strip()[:2000]
    data = json.dumps({"msgtype": "text", "text": {"content": content}},
                      ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(hook, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        resp = json.loads(r.read().decode("utf-8", "ignore") or "{}")
    if resp.get("errcode") == 0:
        print("PUSH: OK 企业微信消息推送 -> 个人微信")
        return True
    # 响应里不含凭证，只报错误码；绝不打印正文（含隐私）
    print("PUSH: FAILED errcode=%s errmsg=%s"
          % (resp.get("errcode"), resp.get("errmsg", "")))
    return False


def mark_sent(today, sent_ids):
    """记录当天已发条目，只保留最近 14 天，避免文件无限增长。"""
    state = load_json(STATE, {})
    state[today] = sorted(set(state.get(today, [])) | set(sent_ids))
    keep = sorted(state.keys())[-14:]
    STATE.write_text(json.dumps({k: state[k] for k in keep},
                                ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")


def due_items():
    now = datetime.now(BEIJING)
    today = now.strftime("%Y-%m-%d")
    done = set(load_json(STATE, {}).get(today, []))
    out = []
    for it in items():
        if not it.get("enabled") or it.get("id") in done:
            continue
        try:
            h, m = (int(x) for x in str(it["time"]).split(":"))
            target = now.replace(hour=h, minute=m, second=0, microsecond=0)
        except Exception:
            continue
        delta = (now - target).total_seconds() / 60.0
        if 0 <= delta < WINDOW_MINUTES:
            out.append(it)
    return out, today


def important_dates_data():
    """日期库只从 Actions Secret 读；本机自测可用 IMPORTANT_DATES_FILE 指路径。"""
    raw = os.environ.get("IMPORTANT_DATES_JSON", "").strip()
    if raw:
        return json.loads(raw)
    f = os.environ.get("IMPORTANT_DATES_FILE", "").strip()
    if f and Path(f).exists():
        return json.loads(Path(f).read_text(encoding="utf-8"))
    raise RuntimeError("缺少 IMPORTANT_DATES_JSON（GitHub Actions Secret）")


def _age_text(row, occ_year):
    y = row.get("year")
    if not y:
        return ""
    n = occ_year - y
    if row.get("cat") == "纪念日":
        return "%d 周年" % n if n > 0 else "当年"
    return "满 %d 周岁" % n if n > 0 else "未满 1 周岁"


def _occurrences(row, start, end, data, missing):
    """复刻本机 daily_reminder.py 的口径：阳历直接匹配，农历查预生成对照表。"""
    out = []
    for y in sorted({start.year, end.year}):
        if row["kind"] == "阳历":
            try:
                d = date(y, row["m"], row["d"])
            except ValueError:
                if row["m"] == 2 and row["d"] == 29:
                    d = date(y, 2, 28)
                else:
                    continue
        else:
            table = data.get("lunar_map", {}).get(str(y))
            mmdd = (table or {}).get("%d-%d" % (row["m"], row["d"]))
            if not mmdd:
                missing.add(y)
                continue
            mm, dd = (int(x) for x in mmdd.split("-"))
            d = date(y, mm, dd)
        if start <= d <= end:
            out.append(d)
    return sorted(set(out))


def render_important_dates(now):
    """按当天日期动态生成「未来三天」提醒，纯文本，不发任何请求。"""
    data = important_dates_data()
    today = now.date()
    end = today + timedelta(days=2)
    missing = set()
    buckets = {i: [] for i in range(3)}
    for row in data.get("rows", []):
        for occ in _occurrences(row, today, end, data, missing):
            delta = (occ - today).days
            if 0 <= delta <= 2:
                buckets[delta].append((occ, row))

    total = sum(len(v) for v in buckets.values())
    title = "重要日期提醒 | %s %s | %s" % (
        today.strftime("%m-%d"), WEEKDAYS[today.weekday()],
        "%d 项" % total if total else "无事项")

    lines = []
    for i in range(3):
        d = today + timedelta(days=i)
        its = sorted(buckets[i], key=lambda x: (x[1]["kind"] != "阳历", x[1]["name"]))
        if not its:
            continue
        lines.append("▍%s %s（%s）" % (
            DAY_LABELS.get(i, "%d 天后" % i), d.strftime("%m-%d"),
            WEEKDAYS[d.weekday()]))
        for occ, row in its:
            seg = "%s · %s" % (row["name"], row["cat"] or "生日")
            age = _age_text(row, occ.year)
            if age:
                seg += " · " + age
            lines.append(seg)

    if not lines:
        lines.append("未来三天（%s 至 %s）无重要日期"
                     % (today.strftime("%m-%d"), end.strftime("%m-%d")))
        nxt = []
        for row in data.get("rows", []):
            for occ in _occurrences(row, today, today + timedelta(days=90),
                                    data, missing):
                if occ > end:
                    nxt.append((occ, row))
        if nxt:
            occ, row = min(nxt, key=lambda x: x[0])
            seg = "下一项 %s：%s %s" % (
                occ.strftime("%m-%d"), row["name"], row["cat"] or "生日")
            age = _age_text(row, occ.year)
            if age:
                seg += " · " + age
            lines.append(seg)

    if missing:
        lines.append("（农历对照表缺 %s 年，请联系小舟更新）"
                     % "、".join(str(y) for y in sorted(missing)))
    return title, "\n".join(lines)


def main():
    args = sys.argv[1:]
    dry = "--dry-run" in args

    if "--list" in args:
        for it in items():
            print("%-16s %s  enabled=%-5s  %s"
                  % (it.get("id"), it.get("time"), it.get("enabled"), it.get("title")))
        return 0

    if "--render-dates" in args:
        i = args.index("--render-dates")
        day = args[i + 1] if i + 1 < len(args) else datetime.now(BEIJING).strftime("%Y-%m-%d")
        dt = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=BEIJING)
        t, b = render_important_dates(dt)
        print("#TITLE#", t)
        print("#BODY#")
        print(b)
        return 0

    sid = os.environ.get("PUSH_SCHEDULE_ID", "").strip()
    title = os.environ.get("PUSH_TITLE", "").strip()
    body = os.environ.get("PUSH_BODY", "").strip()
    timed = False

    if sid:
        found = [it for it in items() if it.get("id") == sid]
        if not found:
            print("PUSH: 定时清单里没有 id =", sid)
            return 1
        todo = found
        today = datetime.now(BEIJING).strftime("%Y-%m-%d")
    elif title or body:
        todo = [{"id": "manual", "title": title or "小舟通知", "body": body}]
        today = datetime.now(BEIJING).strftime("%Y-%m-%d")
    else:
        todo, today = due_items()
        timed = True
        if not todo:
            print("PUSH: 当前无到期条目，跳过（北京时间 %s）"
                  % datetime.now(BEIJING).strftime("%Y-%m-%d %H:%M"))
            return 0

    ok_ids = []
    for it in todo:
        t, b = it.get("title", "小舟通知"), it.get("body", "")
        if it.get("dynamic") == "important_dates":
            try:
                t, b = render_important_dates(datetime.now(BEIJING))
            except Exception as e:
                print("PUSH: 动态内容渲染失败，跳过该条:",
                      type(e).__name__, str(e)[:150])
                continue
        if dry:
            preview = str(b).replace("\n", " / ")[:160]
            print("DRY-RUN:", it.get("id"), "|", t, "|", preview)
            continue
        if send(t, b):
            ok_ids.append(it.get("id"))

    # 定时模式才记去重状态；手动触发不算，方便随时补发
    if timed and ok_ids and not dry:
        mark_sent(today, ok_ids)
    return 0 if (dry or ok_ids) else 1


if __name__ == "__main__":
    sys.exit(main())
