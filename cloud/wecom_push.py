# -*- coding: utf-8 -*-
r"""
云端微信推送（GitHub Actions 里跑，仅标准库，不依赖本机）

链路：企业微信「消息推送」Webhook -> 微信插件 -> 个人微信。
只发纯文本：markdown 在个人微信里会显示成「暂不支持此消息类型」。
凭证只从环境变量 WECOM_WEBHOOK 读取，绝不写进代码、仓库或日志。

模式（自动判断，无需参数）：
  1) PUSH_SCHEDULE_ID 有值      -> 发 push_schedule.json 里指定 id 的条目
  2) PUSH_TITLE / PUSH_BODY 有值 -> 发这条自定义内容（GitHub 网页手动触发）
  3) 都没有                     -> 定时模式，按北京时间匹配该发的条目

本机自测：
  python cloud/wecom_push.py --list
  python cloud/wecom_push.py --dry-run
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).parent
SCHEDULE = BASE / "push_schedule.json"
STATE = BASE / "_push_state.json"
BEIJING = timezone(timedelta(hours=8))
# workflow 每半小时触发一次；GitHub 定时常延迟，窗口放宽到 55 分钟，
# 配合 _push_state.json 保证「不漏发、不重复发」。
WINDOW_MINUTES = 55


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
    # 响应里不含凭证，只报错误码
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


def main():
    args = sys.argv[1:]
    dry = "--dry-run" in args

    if "--list" in args:
        for it in items():
            print("%-16s %s  enabled=%-5s  %s"
                  % (it.get("id"), it.get("time"), it.get("enabled"), it.get("title")))
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
        if dry:
            print("DRY-RUN:", it.get("id"), "|", t, "|", str(b)[:100])
            continue
        if send(t, b):
            ok_ids.append(it.get("id"))

    # 定时模式才记去重状态；手动触发不算，方便随时补发
    if timed and ok_ids and not dry:
        mark_sent(today, ok_ids)
    return 0 if (dry or ok_ids) else 1


if __name__ == "__main__":
    sys.exit(main())
