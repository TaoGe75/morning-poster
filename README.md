# 每日早安海报

每天北京时间 8:45，GitHub Actions 自动：拉一张城市风光实拍照片 → 叠上
日期 / 农历 / 节气七十二候 / 唐诗宋词元曲励志金句 / 「涛哥的小舟」徽标 →
推送到你微信（Server酱）。全程云端运行，与本地电脑无关。

## 上线步骤

1. GitHub 建一个仓库（如 `morning-poster`），把本目录全部内容推上去
   （注意 `.github/workflows/daily.yml` 必须在仓库根的 `.github/` 下）。
2. 仓库 Settings → Secrets and variables → Actions → New repository secret：
   - Name: `SERVERCHAN_KEY`
   - Value: 你的 Server酱 SendKey（sctapi.ftqq.com 里的 SCT 开头串）
3. 进 Actions 标签页，选中 daily-morning-poster → Run workflow 手动跑一次验证。
4. 之后每天 08:45（北京）自动推送。

## 可选增强

- **Pexels 图源**：注册 pexels.com/api 拿免费 key，加 Secret `PEXELS_KEY`，
  即可每天搜索全新的城市晨光照片；不配则用内置照片池轮换（6 张，每 6 天一轮）。

## 文件说明

- `cloud/poster.py` — 生成海报（农历/节气七十二候/金句轮换/合成）
- `cloud/push_wechat.py` — Server酱 推送
- `cloud/quotes.json` — 金句库（可自行增删，按日期自动轮换）
- `cloud/pool/` — 内置城市风光照片池
- `posters/` — 每日产出（推送到微信的图走 jsdelivr CDN 引用此目录）
