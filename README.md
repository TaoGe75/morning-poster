# 每日早安海报

每天北京时间 7:00，GitHub Actions 自动：拉一张**阳光明快的**城市风光实拍照片 → 叠上
日期 / 农历 / 节气七十二候 / 唐诗宋词元曲励志金句 / 「涛哥的小舟」徽标 →
推送到你微信（Server酱）。全程云端运行，与本地电脑无关。

## 内容规则（2026-11-10 调整）

- **配图只收白天、光线充足、朝气的画面**。夜景、暮色、黄昏蓝调、阴沉灰调的
  8 张图已从 `cloud/pool/` 移除；`poster.py` 里加了亮度闸门（`is_bright`：
  平均亮度 ≥105、暗部占比 ≤30%、高光占比 ≥7%），以后新增照片或退回网图时
  会自动跳过偏暗的候选，不会再混进夜景。
- **金句回到励志主线**：`cloud/quotes.json` 共 111 条 = 95 条全年励志 +
  每季 4 条应景且明亮的点缀；剔除了上一版混入的写景、离愁、思乡、夜色句。
  每条带 `theme` 标签（志向 / 奋进 / 坚韧 / 勤学 / 实干 / 格局 / 担当 / 自新）。
- **防重复**：选句按主题交错打散，一季内每句只出现一次，相邻三天自动避开
  同作者、同主题（`_daily_sequence`）。想调金句只改 `quotes.json`，
  算法不用动。

## 当前版式（2026-11-04 定稿 v1）

- 画布 1080×1620，底部右下角圆形徽标（`assets/badge.png`）
- 字体：日期/农历/节气/落款用霞鹜文楷；金句用**马善政毛笔楷书**（MaShanZheng，笔画端正有笔锋，不加粗）
- 字号统一由 `cloud/poster.py` 里的 `TEXT_SCALE = 1.25` 控制，换算后：日期 80 / 农历·节气 50 / 金句 80 / 落款 40；行距同步按系数放大
- 所有文字整体下移量由 `TEXT_OFFSET_Y = 30` 控制（画布像素），只挪位置不动字号；2026-11-05 应涛哥要求微调
- 调度：`0 23 * * *`（北京 7:00）主跑 + `30 23 * * *`（北京 7:30）兜底重试，当天已推过自动跳过，不会重复推送
- 推送配图链接带 commit 号（`@<sha>`），避免 jsdelivr 缓存住旧图

改版式时只改 `TEXT_SCALE`（整体字号）或对应字体文件，其余布局参数都跟着系数走。

## 上线步骤

1. GitHub 建一个仓库（如 `morning-poster`），把本目录全部内容推上去
   （注意 `.github/workflows/daily.yml` 必须在仓库根的 `.github/` 下）。
2. 仓库 Settings → Secrets and variables → Actions → New repository secret：
   - Name: `SERVERCHAN_KEY`
   - Value: 你的 Server酱 SendKey（sctapi.ftqq.com 里的 SCT 开头串）
3. 进 Actions 标签页，选中 daily-morning-poster → Run workflow 手动跑一次验证。
4. 之后每天 07:00（北京）自动推送。

## 可选增强

- **图源顺序（2026-11-10 调整）**：本地明亮照片池（`cloud/pool/`，现有 7 张，
  含涛哥实拍 3 张）优先，7 天一轮；池子为空才退回
  Pexels（有 key）→ Wikimedia Commons，两条网图链路同样过亮度闸门。
  想把网图调回第一优先，改 `cloud/poster.py` 里 `fetch_photo` 的层序即可。
- **Pexels 图源**：注册 pexels.com/api 拿免费 key，加 Secret `PEXELS_KEY`，
  即可用作备用图源；不配也能跑（还有 Commons 兜底）。

## 文件说明

- `cloud/poster.py` — 生成海报（农历/节气七十二候/金句轮换/合成）
- `cloud/push_wechat.py` — Server酱 推送
- `cloud/quotes.json` — 励志金句库（111 条，带 `season` / `theme` 标签，按日期自动轮换）
- `cloud/pool/` — 内置明亮城市风光照片池（涛哥实拍 3 张 + 储备图，第一优先图源）
- `posters/` — 每日产出（推送到微信的图走 jsdelivr CDN 引用此目录）
