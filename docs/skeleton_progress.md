# Skeleton Progress

## 已完成
- `backend`：FastAPI 主服务、核心 API、多引擎并发调度。
- `frontend-vue`：主演示前端，支持单句翻译、批量测试、BLEU/chrF 展示。
- `frontend-react`：已补齐批量测试与 CSV 导出，和 Vue 主前端能力对齐。
- UI 视觉：已升级为“圆角哲学”风格（柔和渐变、玻璃态面板、胶囊按钮、状态徽标）。
- `llm_api`：已接入 OpenAI 兼容接口，支持重试与指数退避。
- `smt`：已接入运行时（`local` / `docker`），并提供就绪状态检测。
- 本地模型策略：默认 `HF_LOCAL_FILES_ONLY=true`，不自动下载。
- 检查脚本：`backend/scripts/check_model_ready.py`（仅检查，不下载）。
- 冒烟脚本：`backend/scripts/smoke_test_api.py`。
- 一键验证脚本：`scripts/verify_project.ps1`。
- SMT 配置脚本：`scripts/configure_smt_env.ps1`。
- SMT 模板：`backend/smt_model/moses.ini.example`。

## 当前阻塞
- SMT 仍需手动准备：
  - Moses 可执行文件（本地编译或 Docker 镜像）。
  - `backend/smt_model/moses.ini` 及其依赖文件（`phrase-table.gz`、`reordering-table*.gz`、`lm.binary` 等）。

## 你手动处理 / 我继续处理
- 你手动：模型下载与落盘、Moses/KenLM 训练产物准备。
- 我继续：代码结构、接口、前后端功能、脚本与文档完善。

## 下一阶段
- 完成 SMT 产物接入后，打通 `smt` 引擎真实翻译链路。
- 增加前端对比可视化（图表）和导出模板。
- 提供演示模式配置（按引擎开关预设）。

## API 状态
- `GET /health`：可用。
- `GET /api/v1/engines`：可用。
- `GET /api/v1/test_cases`：可用。
- `POST /api/v1/translate`：可用。
- `POST /api/v1/batch_translate`：可用。
- `POST /api/v1/evaluate`：可用。
