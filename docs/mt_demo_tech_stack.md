# 机器翻译 Demo 完全体技术栈结论（④部分）

## 1. 结论（先给答案）

- 前端采用：`Vue 3 + Vite`（主方案）
- 后端采用：`FastAPI`（统一推理与评测服务）
- 前端可替换：`React + Vite`（接口不变，便于队友按熟悉栈开发）
- 部署方式：全本地 `localhost`，支持离线演示

> 说明：本项目将前后端分离，保证“多模型并行翻译 + 实时对比展示”在课堂场景下稳定运行。

---

## 2. 目标范围（按当前要求）

### 2.1 保留目标

- 输入文本
- 多引擎本地翻译（规则/统计/神经/Transformer/LLM）
- 结果并排对比（译文 + 耗时 + 自动指标）

### 2.2 暂不纳入

- 错误解释模块
- 自动结论输出模块

---

## 3. 总体架构

```text
Browser (Vue/React @ localhost:5173)
        |
        | HTTP/JSON
        v
FastAPI Service (@ localhost:8000)
        |
        |-- RBMT Engine (词典+规则)
        |-- SMT Engine (Moses/预训练短语表)
        |-- NMT Engine (Marian/Opus-MT)
        |-- Transformer Engine (NLLB/M2M100)
        |-- LLM Engine (OpenAI-compatible API)
        |
        |-- Evaluation (BLEU/chrF + latency)
        |-- Result Store (SQLite, 可选)
```

---

## 4. 技术栈清单（固化版）

## 4.1 前端（展示层）

- 核心：`Vue 3`、`Vite`、`TypeScript`
- UI：`Element Plus`（或 `Naive UI`）
- 状态管理：`Pinia`
- 请求：`Axios`
- 可视化：`ECharts`（耗时、指标雷达图/柱状图）
- 当前实现补充：`Vue` 与 `React` 均支持单句翻译、批量测试、指标展示；`React` 已支持批量结果 CSV 导出。
- 视觉体系补充：圆角卡片、胶囊按钮、渐变背景、玻璃态面板、状态徽标（参考 Vben/Tailwind 风格）。

## 4.2 后端（服务层）

- 框架：`FastAPI`
- 运行：`Uvicorn`
- 校验：`Pydantic`
- 并发：`asyncio`（多引擎并发调用）

## 4.3 翻译引擎（本地优先 + API扩展）

- 规则方法（RBMT）：
  - 自定义词典 + 规则模板（Python实现）
- 统计机器翻译（SMT）：
  - `Moses`（已接入运行时，支持 `local` / `docker` 模式）
  - `KenLM`（语言模型）
- 神经机器翻译（NMT）：
  - `transformers` + `torch`
  - 基线模型：`Helsinki-NLP/opus-mt-zh-en`、`Helsinki-NLP/opus-mt-en-zh`
- Transformer 强化：
  - `facebook/nllb-200-distilled-600M`（推荐）
- LLM API 翻译（OpenAI 兼容格式）：
  - `openai` Python SDK（指向兼容端点）
  - 协议：`/v1/chat/completions`
  - 兼容配置：`BASE_URL`、`API_KEY`、`MODEL`

## 4.5 模型加载策略（当前实现）

- 默认启用 `HF_LOCAL_FILES_ONLY=true`，后端不会自动下载模型。
- 本地模型未就绪时，引擎返回明确提示，由人工补齐模型文件。
- 可配置 `MODEL_CACHE_DIR` 指向离线模型目录。
- 推荐将 `NMT_MODEL_ZH_EN` / `NMT_MODEL_EN_ZH` / `TRANSFORMER_MODEL` 设置为本地目录路径。
- 提供脚本：`backend/scripts/check_model_ready.py`（仅检查，不下载）。
- 提供脚本：`scripts/sync_modelscope_cache.ps1`（从 ModelScope 缓存同步模型到项目）。
- 提供脚本：`scripts/configure_smt_env.ps1`（一键写入 SMT 相关 `.env` 配置）。
- 提供模板：`backend/smt_model/moses.ini.example`（可复制为 `moses.ini` 再替换真实产物路径）。

## 4.4 评测与记录

- 自动指标：`sacrebleu`（BLEU、chrF）
- 性能指标：响应耗时（ms）、吞吐量（可选）
- 记录（可选）：`SQLite`

---

## 5. 标准 API 设计（前后端契约）

### 5.1 `GET /api/v1/engines`

- 作用：返回可用引擎状态（ready/downloading/error）

### 5.2 `POST /api/v1/translate`

- 入参：`text`, `src_lang`, `tgt_lang`, `engines[]`
- 出参：每个引擎的 `translation`, `latency_ms`, `metrics`

### 5.3 `POST /api/v1/batch_translate`

- 作用：一次对多句进行并行翻译

### 5.4 `POST /api/v1/evaluate`

- 入参：`candidate`, `reference`
- 出参：`bleu`, `chrf`

---

## 6. 项目目录建议

```text
mt-demo/
  frontend-vue/
    src/
      views/CompareView.vue
      components/EngineTable.vue
      services/api.ts
  frontend-react/               # 可选：若队友用 React
    src/
  backend/
    app/
      main.py
      api/routes.py
      schemas/translation.py
      services/
        engine_manager.py
        rbmt_engine.py
        smt_engine.py
        nmt_engine.py
        transformer_engine.py
        llm_api_engine.py
        test_case_service.py
        evaluator.py
      data/
        test_cases.json
        glossary.json
    requirements.txt
  docs/
    mt_demo_tech_stack.md
```

---

## 7. 本地运行路线（最简）

### 7.0 推荐先做项目自检

```bash
cd scripts
.\verify_project.ps1
```

## 7.1 后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## 7.2 前端（Vue）

```bash
cd frontend-vue
npm install
copy .env.example .env
npm run dev
```

访问：`http://localhost:5173`

---

## 8. 里程碑（7天可交付）

- Day 1：完成 FastAPI 骨架 + `translate` 单接口
- Day 2：接入 RBMT + NMT（Marian）
- Day 3：接入 SMT 与 NLLB
- Day 4：接入 LLM API（OpenAI 兼容）
- Day 5：完成 Vue 对比页面（并排结果+耗时）
- Day 6：接入 BLEU/chrF 与预置测试句
- Day 7：离线彩排 + 录屏兜底

---

## 9. 演示稳定性策略（防翻车）

- 模型全部提前下载，设置离线缓存目录
- 默认只启用本地引擎，在线 API 不作为主路径
- 提供“轻量模型模式”（低配置机器可跑）
- 准备 30 秒录屏兜底（网络/显卡异常时切换）

---

## 10. React 的定位（与 Vue 并存策略）

- 当前主交付：`Vue + FastAPI`
- 如队友偏 React，可复用同一后端 API，无需改模型层
- 建议只保留一个正式前端用于答辩，另一个作为备选实现

> 最终建议：本组答辩版本统一采用 `Vue + FastAPI`，React 仅作协作兼容方案。
