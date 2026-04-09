# MT-Lab Live

机器翻译课程汇报 Demo（前后端分离，本地 `localhost` 运行）。

本项目目标是：把“规则/统计/神经/Transformer/LLM API”多条翻译路线放到同一套可运行系统中，支持课堂汇报时的**并排对比展示**与**自动评测**。

---

## 1. 项目概览

- 主前端：`frontend-vue`（汇报主用）
- 备选前端：`frontend-react`（能力对齐，可切换）
- 后端：`backend`（FastAPI，多引擎调度 + 评测）
- 脚本入口：`scripts`
- 文档：`docs`

当前已实现：

- 单句翻译、批量翻译、BLEU/chrF 评测
- 多引擎状态检测（ready/not ready/error）
- Vue 与 React 两套前端展示
- “圆角哲学”视觉风格（渐变、玻璃态、状态徽标）
- Vue 前端支持多模态输入：`text / image / audio / video`（后三者走 `llm_api`）
- 支持 LLM 多模态设置面板（模型与 Prompt 可在线配置）
- React 前端已对齐上述多模态与设置能力

---

## 2. 技术栈

### 后端

- Python + FastAPI + Uvicorn
- Pydantic / pydantic-settings
- `transformers` + `torch`（NMT / Transformer）
- `openai` SDK（OpenAI 兼容格式 LLM API）
- `sacrebleu`（BLEU / chrF）

依赖文件：`backend/requirements.txt`

### 前端

- Vue 3 + Vite：`frontend-vue`
- React + Vite：`frontend-react`

---

## 3. 目录结构

```text
MT-Lab Live/
├─ backend/                # FastAPI 服务
│  ├─ app/
│  ├─ scripts/             # 后端检查/冒烟脚本
│  ├─ smt_model/           # SMT 运行产物目录（默认不提交）
│  ├─ .env.example
│  └─ requirements.txt
├─ frontend-vue/           # 主前端
├─ frontend-react/         # 备选前端
├─ scripts/                # 一键启动/验证/SMT配置/模型同步
├─ docs/                   # 项目文档
└─ README.md
```

---

## 4. 运行条件

建议环境（Windows 优先，其他系统可自行适配命令）：

- Python `3.12.x`（推荐）
- Node.js `>= 18` + npm
- PowerShell `5+` 或 `7+`
- （可选）Docker：用于 `SMT_MODE=docker`
- （可选）本地 `mosesdecoder`：用于 `SMT_MODE=local`
- （推荐）`SMT_MODE=auto`：优先 `local` / `docker`，自动回退 `lite`（无需 `moses.ini` 也可跑通）

> 默认策略是离线优先：`HF_LOCAL_FILES_ONLY=true`，不会自动下载模型。

---

## 5. 快速开始（推荐）

### 5.0 模型准备（ModelScope）

先安装 `modelscope`（建议清华源）：

```powershell
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple modelscope
```

使用 `modelscope` 命令下载模型（示例）：

```powershell
modelscope download --model Helsinki-NLP/opus-mt-zh-en
modelscope download --model Helsinki-NLP/opus-mt-en-zh
modelscope download --model facebook/nllb-200-distilled-600M
modelscope download --model facebook/m2m100_418M
```

### 5.1 一键启动开发环境

在项目根目录执行：

```powershell
Set-Location .\scripts
.\start_dev.ps1
```

说明：

- 会自动拉起后端（新 PowerShell 窗口）
- 默认拉起 Vue 前端（新窗口）
- 若 `8000` 被占用，会自动尝试 `8010/18000/28000`

常用参数：

```powershell
# 指定后端首选端口
.\start_dev.ps1 -BackendPort 8010

# 改为启动 React 备选前端
.\start_dev.ps1 -UseReact
```

### 5.2 访问地址

- 后端：启动日志显示的 `http://127.0.0.1:<port>`
- Vue 前端：`http://127.0.0.1:5173`
- React 前端：`http://127.0.0.1:5174`
- 接口文档（Swagger）：`http://127.0.0.1:<port>/docs`

---

## 6. 手动启动（可选）

如果你不使用脚本，也可手动分开启动。

### 6.1 后端

```powershell
Set-Location 'F:\Spark_Incubator\新建文件夹\MT-Lab Live\backend'
python -m venv .venv312
.\.venv312\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env -ErrorAction SilentlyContinue
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 6.2 Vue 前端

```powershell
Set-Location 'F:\Spark_Incubator\新建文件夹\MT-Lab Live\frontend-vue'
npm install
Copy-Item .env.example .env -ErrorAction SilentlyContinue
npm run dev
```

### 6.3 React 前端

```powershell
Set-Location 'F:\Spark_Incubator\新建文件夹\MT-Lab Live\frontend-react'
npm install
Copy-Item .env.example .env -ErrorAction SilentlyContinue
npm run dev
```

---

## 7. 环境变量说明

后端模板：`backend/.env.example`

关键配置（按优先级）

### 通用

- `APP_HOST` / `APP_PORT`：服务监听地址和端口
- `HF_LOCAL_FILES_ONLY=true`：仅本地模型，不自动联网下载
- `MODEL_CACHE_DIR`：本地模型缓存目录（可选）

### NMT / Transformer

- `NMT_ENABLED=true`
- `NMT_MODEL_ZH_EN`
- `NMT_MODEL_EN_ZH`
- `NMT_EN_ZH_RULES_PATH=./data/nmt_en_zh_rules.tsv`
- `TRANSFORMER_ENABLED=false`（默认关闭）
- `TRANSFORMER_MODEL`

### SMT（Moses + KenLM）

- `SMT_ENABLED=true`
- `SMT_MODE=auto`（推荐）/ `local` / `niutrans` / `docker` / `lite`
- `SMT_MOSES_ROOT` / `SMT_MOSES_BIN`
- `SMT_NIUTRANS_ROOT` / `SMT_NIUTRANS_BIN` / `SMT_NIUTRANS_CONFIG`
- `SMT_MODEL_DIR=./smt_model`
- `SMT_DOCKER_IMAGE=moses-smt:latest`
- `SMT_LITE_MODEL_PATH=./smt_model/lite_phrase_table.json`
- `SMT_LITE_SEED_PATH=./data/smt_lite_seed.tsv`
- `SMT_LITE_MAX_CEDICT_ENTRIES=120000`

### LLM API（OpenAI 兼容格式）

- `OPENAI_BASE_URL`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `OPENAI_IMAGE_MODEL`
- `OPENAI_AUDIO_MODEL`
- `OPENAI_VIDEO_MODEL`
- `OPENAI_TEXT_PROMPT`
- `OPENAI_IMAGE_PROMPT`
- `OPENAI_AUDIO_PROMPT`
- `OPENAI_VIDEO_PROMPT`
- `OPENAI_MEDIA_MAX_BASE64_CHARS`

前端模板：

- `frontend-vue/.env.example`
- `frontend-react/.env.example`

通用配置：

- `VITE_API_BASE_URL=http://127.0.0.1:8000`

---

## 8. 模型与 SMT 准备

本项目约定：**下载相关由人工处理**，代码只做检查与接线。

请参考：

- 模型手动下载清单：`docs/manual_download_todo.md`
- SMT 快速接入：`docs/smt_quickstart.md`
- 当前进展：`docs/skeleton_progress.md`
- 技术栈总览：`docs/mt_demo_tech_stack.md`

---

## 9. 常用脚本

目录：`scripts`

- `start_dev.ps1`：一键拉起前后端（自动处理端口）
- `verify_project.ps1`：项目检查（编译、模型就绪、冒烟、前端构建）
- `configure_smt_env.ps1`：快速写入 SMT 相关 `.env`
  - 支持 `-Mode auto|local|niutrans|docker|lite`
- `build_niutrans_decoder_in_docker.ps1`：在 Docker 内编译 `NiuTrans.Decoder`
- `sync_modelscope_cache.ps1`：从 ModelScope 本地缓存同步模型

目录：`backend/scripts`

- `check_model_ready.py`：检查模型/SMT 资源是否就绪
- `prepare_smt_lite_model.py`：从种子 TSV + CEDICT 构建 `lite_phrase_table.json`
- `smoke_test_api.py`：API 冒烟测试
- `acceptance_full_chain.py`：全链路验收（每种方法出结果 + text/image/audio/video）
- `warmup_models.py`：模型预热（可选）

---

## 10. API 一览

后端前缀：`/api/v1`

- `GET /health`
- `GET /api/v1/engines`
- `GET /api/v1/test_cases`
- `GET /api/v1/settings/llm`
- `POST /api/v1/translate`
- `POST /api/v1/batch_translate`
- `POST /api/v1/evaluate`
- `PUT /api/v1/settings/llm`
- `POST /api/v1/llm/process`

示例：

```powershell
Invoke-WebRequest http://127.0.0.1:8000/health
```

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/translate' -Method Post -ContentType 'application/json' -Body (@{
  text = '机器翻译正在快速发展'
  src_lang = 'zh'
  tgt_lang = 'en'
  engines = @('rbmt','nmt','transformer','llm_api')
} | ConvertTo-Json)
```

---

## 11. 常见问题（FAQ）

### Q1: 前端报 `NetworkError`

通常是后端没启动成功或端口不一致：

- 用 `start_dev.ps1` 输出的实际后端地址
- 检查前端 `.env` 的 `VITE_API_BASE_URL`
- 先访问 `GET /health` 再开前端

### Q2: 后端报 `WinError 10013`（端口权限/占用）

- 换端口启动：`start_dev.ps1 -BackendPort 8010`
- 或检查占用进程后释放端口

### Q3: `transformer not ready (disabled by config)`

- 打开 `backend/.env`，把 `TRANSFORMER_ENABLED=false` 改为 `true`
- 确保 `TRANSFORMER_MODEL` 指向已就绪模型目录

### Q4: `smt not ready`

- 核心原因通常是 `moses.ini` 或其引用文件缺失
- 参考 `docs/smt_quickstart.md` 补齐 `phrase-table.gz`、`lm.binary` 等

---

## 12. GitHub 上传建议（组内协作）

### 12.1 不要提交的内容

- 本地虚拟环境：`.venv*`
- Node 依赖：`node_modules`
- 本地模型：`models/`
- SMT 产物：`backend/smt_model/*`（除说明文件）
- 私密配置：`backend/.env`

以上已在 `.gitignore` 中处理。

### 12.2 建议保留

- `backend/.env.example`
- `frontend-vue/.env.example`
- `frontend-react/.env.example`
- `docs/manual_download_todo.md`（下载与落盘指南）

### 12.3 组员上手顺序

1. 克隆仓库
2. 执行 `scripts/start_dev.ps1`
3. 执行 `scripts/verify_project.ps1`
4. 按 `docs/manual_download_todo.md` 补齐模型与 SMT

---

## 13. 备注

- 本项目面向课程汇报，优先保证可演示性与可复现性。
- 若需要生产级能力（鉴权、限流、日志平台、部署编排），可在此基础上继续扩展。
