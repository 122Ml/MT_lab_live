# MT-Lab Live

<p align="center">
  机器翻译课程汇报 Demo（本地可运行 · 多方法并排对比 · 自动评测）
</p>

<p align="center">
  <a href="https://github.com/122Ml/MT_lab_live/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0-blue.svg" /></a>
  <img src="https://img.shields.io/badge/python-3.12+-3776AB?logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/backend-FastAPI-009688?logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/frontend-Vue3%20%7C%20React-4FC08D" />
  <img src="https://img.shields.io/badge/modelscope-supported-6f42c1" />
</p>

<p align="center">
  <a href="#-项目定位">项目定位</a> ·
  <a href="#-功能矩阵">功能矩阵</a> ·
  <a href="#-快速开始3分钟">快速开始</a> ·
  <a href="#-环境变量与模型配置">环境变量</a> ·
  <a href="#-常见问题">常见问题</a>
</p>

---

## 🎯 项目定位

`MT-Lab Live` 将 **RBMT / SMT / NMT / Transformer / LLM API** 放到同一套系统中，解决课堂汇报时最核心的两个问题：

- 同一输入下，多方法结果并排可视化对比
- 同一协议下，自动计算 BLEU / chrF / 延迟指标

> [!TIP]
> 项目默认是“离线优先”策略：`HF_LOCAL_FILES_ONLY=true`。  
> 即：不会在运行时自动下载模型，需要你先手动准备模型文件。

---

## ✨ 功能矩阵

| 模块 | 当前能力 | 说明 |
|---|---|---|
| 翻译接口 | 单句/批量翻译 | FastAPI 统一接口调度多引擎 |
| 评测 | BLEU / chrF / latency | 统一结果结构，便于横向比较 |
| 前端展示 | Vue + React 双前端 | Vue 为主展示，React 为备选 |
| 多模态输入 | text / image / audio / video | 图像/音频/视频统一走 `llm_api` |
| 状态监控 | 引擎 ready/not ready/error | 可视化状态与配置面板 |
| SMT 兼容 | local / docker / lite / niutrans | `auto` 模式自动回退保障可用性 |

---

## 🧱 项目结构

```text
MT-Lab Live/
├─ backend/                # FastAPI 服务 + 多引擎实现
│  ├─ app/
│  ├─ scripts/
│  ├─ data/
│  ├─ smt_model/
│  ├─ .env.example
│  └─ requirements.txt
├─ frontend-vue/           # 主前端（推荐用于汇报）
├─ frontend-react/         # 备选前端
├─ scripts/                # 一键启动/验证/模型同步脚本
├─ docs/                   # 技术文档与下载清单
├─ models/                 # 本地模型目录（默认不提交）
└─ README.md
```

---

## 🚀 快速开始（3分钟）

### 1) 安装依赖

```powershell
# backend
Set-Location .\backend
python -m venv .venv312
.\.venv312\Scripts\Activate.ps1
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# modelscope（用于模型下载）
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple modelscope
```

### 2) 下载模型（示例）

```powershell
modelscope download --model Helsinki-NLP/opus-mt-zh-en
modelscope download --model Helsinki-NLP/opus-mt-en-zh
modelscope download --model facebook/nllb-200-distilled-600M
modelscope download --model facebook/m2m100_418M
```

> [!NOTE]
> 你的项目里实际路径由 `backend/.env` 中的 `NMT_MODEL_*` / `TRANSFORMER_MODEL` 决定。  
> 下载后请按该路径放置或同步模型目录。

### 3) 一键启动

```powershell
Set-Location .\scripts
.\start_dev.ps1
```

常用参数：

```powershell
# 指定后端首选端口
.\start_dev.ps1 -BackendPort 8010

# 启动 React 前端
.\start_dev.ps1 -UseReact
```

启动后访问：

- Vue 前端：`http://127.0.0.1:5173`
- React 前端：`http://127.0.0.1:5174`
- 后端 Swagger：`http://127.0.0.1:<port>/docs`

---

## ⚙️ 环境变量与模型配置

后端配置模板：`backend/.env.example`

### 通用

- `APP_HOST` / `APP_PORT`
- `HF_LOCAL_FILES_ONLY=true`
- `MODEL_CACHE_DIR`

### NMT / Transformer

- `NMT_ENABLED=true`
- `NMT_MODEL_ZH_EN`
- `NMT_MODEL_EN_ZH`
- `NMT_EN_ZH_RULES_PATH=./data/nmt_en_zh_rules.tsv`
- `TRANSFORMER_ENABLED=true|false`
- `TRANSFORMER_MODEL`

### SMT（Moses + KenLM / NiuTrans / Lite）

- `SMT_ENABLED=true`
- `SMT_MODE=auto|local|niutrans|docker|lite`
- `SMT_MOSES_ROOT` / `SMT_MOSES_BIN`
- `SMT_NIUTRANS_ROOT` / `SMT_NIUTRANS_BIN` / `SMT_NIUTRANS_CONFIG`
- `SMT_LITE_MODEL_PATH` / `SMT_LITE_SEED_PATH`

### LLM API（OpenAI兼容）

- `OPENAI_BASE_URL`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `OPENAI_IMAGE_MODEL` / `OPENAI_AUDIO_MODEL` / `OPENAI_VIDEO_MODEL`
- `OPENAI_TEXT_PROMPT` / `OPENAI_IMAGE_PROMPT` / `OPENAI_AUDIO_PROMPT` / `OPENAI_VIDEO_PROMPT`

> [!WARNING]
> 不要提交 `backend/.env`（包含 API Key）。  
> 仅提交 `backend/.env.example`。

---

## 🔌 API 一览

后端前缀：`/api/v1`

| Method | Path | 用途 |
|---|---|---|
| GET | `/health` | 服务健康检查 |
| GET | `/api/v1/engines` | 引擎就绪状态 |
| GET | `/api/v1/test_cases` | 示例数据 |
| POST | `/api/v1/translate` | 单条翻译 |
| POST | `/api/v1/batch_translate` | 批量翻译 |
| POST | `/api/v1/evaluate` | BLEU/chrF 评测 |
| GET/PUT | `/api/v1/settings/llm` | LLM 设置查询/更新 |
| POST | `/api/v1/llm/process` | 多模态 LLM 处理 |

---

## 🛠 常用脚本

### `scripts/`

- `start_dev.ps1`：一键拉起前后端（自动处理端口）
- `verify_project.ps1`：项目完整检查（编译/模型就绪/冒烟/前端构建）
- `configure_smt_env.ps1`：快速写入 SMT 配置
- `build_niutrans_decoder_in_docker.ps1`：Docker 编译 `NiuTrans.Decoder`
- `sync_modelscope_cache.ps1`：从 ModelScope 缓存同步模型

### `backend/scripts/`

- `check_model_ready.py`：检查模型/SMT 资源
- `prepare_smt_lite_model.py`：构建 `lite_phrase_table.json`
- `smoke_test_api.py`：API 冒烟
- `acceptance_full_chain.py`：全链路验收
- `warmup_models.py`：模型预热

---

## 🧪 手动启动（可选）

如果不使用脚本，可分开启动：

```powershell
# backend
Set-Location .\backend
.\.venv312\Scripts\Activate.ps1
Copy-Item .env.example .env -ErrorAction SilentlyContinue
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

```powershell
# vue
Set-Location .\frontend-vue
npm install
Copy-Item .env.example .env -ErrorAction SilentlyContinue
npm run dev
```

```powershell
# react
Set-Location .\frontend-react
npm install
Copy-Item .env.example .env -ErrorAction SilentlyContinue
npm run dev
```

---

## ❓ 常见问题

### Q1: 前端 `NetworkError`

- 后端未启动或端口不一致
- 前端 `.env` 的 `VITE_API_BASE_URL` 指向错误
- 先检查 `GET /health` 再打开前端

### Q2: 后端 `WinError 10013`

- 端口被占用/权限冲突
- 换端口：`.\start_dev.ps1 -BackendPort 8010`

### Q3: `transformer not ready`

- `TRANSFORMER_ENABLED=false`
- 或 `TRANSFORMER_MODEL` 路径未就绪

### Q4: `smt not ready`

- 缺失 `moses.ini` 或相关资源（`phrase-table.gz`, `lm.binary`）
- 可先用 `SMT_MODE=auto`，由系统回退到 `lite`

---

## 📚 文档索引

- 技术路线：`docs/mt_demo_tech_stack.md`
- 手动下载清单：`docs/manual_download_todo.md`
- SMT 快速接入：`docs/smt_quickstart.md`
- 骨架进展记录：`docs/skeleton_progress.md`

---

## 🤝 协作建议

推荐组员 onboarding 流程：

1. 克隆仓库
2. 执行 `scripts/start_dev.ps1`
3. 执行 `scripts/verify_project.ps1`
4. 按 `docs/manual_download_todo.md` 补齐模型与 SMT 资源

---

## 📄 License

本项目采用 `GNU AGPL-3.0` 许可证，见 `LICENSE`。

