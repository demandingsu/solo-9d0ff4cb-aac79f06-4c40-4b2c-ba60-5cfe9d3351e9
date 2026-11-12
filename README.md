# 截标时间核对工具

面向采购专员的网页工具：从公开招标公告站抓取公告，按项目串起公告链，
自动应用更正与撤销，给出每个项目的**最终截标时间 / 停办状态**及**依据链接**。

仓库包含两个服务：

| 服务 | 目录 | 说明 |
| --- | --- | --- |
| 核对工具 | `app/` | FastAPI 网页：输入列表网址 → 抓取同源分页与详情 → 分析展示，SQLite 保存采集轮次 |
| 示例公告站 | `sample_site/` | FastAPI 模拟公告站：3 页列表分页 + 11 条公告详情（含更正、撤销），支持故障注入 |

## 快速开始（Docker Compose）

```bash
docker compose up --build
```

- 核对工具：http://localhost:8000/ （打开后点击 **开始抓取**，默认已填入示例站列表网址）
- 示例公告站：http://localhost:8080/list.html?page=1

## 功能说明

1. **抓取**：输入与示例站同结构的列表网址，点击抓取。工具只跟随与起始网址
   **同源**的分页链接（`nav.pagination`）与详情链接（`ul.notice-list`），
   逐个读取详情页的：项目编号、公告编号、公告类型、发布时间、截标时间、
   更正/撤销所指公告编号。
2. **分析**：同一项目编号的公告按发布时间串链——
   - 招标公告确立截标时间；
   - 更正公告更新截标时间（链上记录 `旧值 → 新值`）；
   - 撤销公告将项目标记为 **停办**。
   页面展示每个项目的最终状态、当前截标时间，以及每条公告的来源链接（依据）。
3. **轮次持久化（SQLite）**：每次抓取是一个轮次，公告快照挂在轮次下，
   保存于 SQLite（容器卷 `app-data`，`/data/app.db`）。
   - **任一页面失败**：轮次标记失败并记录出错网址与原因，页面红色横幅提示，
     项目结果仍展示上一轮成功数据；
   - **重抓不叠加**：公告只在整轮全部成功后于单事务内写入，失败轮次不留
     半截数据；页面始终只展示最近一次成功轮次的结果。

## 演示失败处理

```bash
# 开启故障注入：详情页 NT-2026-0004 返回 500
curl "http://localhost:8080/admin/fail?on=1"
# 在 http://localhost:8000/ 点击“开始抓取” → 第 N 轮失败，报出该网址，结果仍是上一轮
# 关闭故障后重抓 → 新一轮成功，数据整体替换，不叠加
curl "http://localhost:8080/admin/fail?on=0"
```

## 页面结构约定（解析契约）

输入网址须与示例站同结构：

- 列表页 `list.html?page=N`：公告链接在 `ul.notice-list a`，分页链接在 `nav.pagination a`；
- 详情页 `detail/<公告编号>.html`：容器 `div.notice[data-notice-type]`
  （`tender`/`correction`/`cancellation`），字段元素
  `#project-no`、`#notice-no`、`#publish-time`、`#deadline`（如有）、
  `#target-notice`（更正/撤销必填）。

## 配置（环境变量）

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DB_PATH` | `/data/app.db`（容器） | SQLite 文件路径 |
| `DEFAULT_START_URL` | `http://sample-site:8000/list.html?page=1` | 抓取表单预填的列表网址 |
| `URL_REWRITE_FROM` / `URL_REWRITE_TO` | 见 compose | 把结果页中的内部网址改写为浏览器可访问地址 |

## 本地开发与测试

```bash
pip install -r app/requirements.txt -r sample_site/requirements.txt pytest
python -m pytest tests/            # 单元测试：公告链分析 + 详情页解析
# 手动联调：
cd sample_site && uvicorn main:app --port 8080 &
cd app && DB_PATH=/tmp/app.db DEFAULT_START_URL=http://localhost:8080/list.html?page=1 \
  uvicorn main:app --port 8000
```
