# SMT Quickstart（完整可用版）

本项目的 `smt` 现在支持 5 种模式：

- `auto`（推荐）：优先 `local` -> `docker`，都不可用时自动回退 `lite`
- `local`：调用本机 Moses 可执行文件 + `moses.ini`
- `niutrans`：调用 `NiuTrans.Decoder` + NiuTrans 配置文件
- `docker`：调用 Docker 中的 Moses + `moses.ini`
- `lite`：纯本地轻量统计短语表（无需 `moses.ini`，开箱可用）

---

## 1) 最快可用（推荐）

把后端 `.env` 设为：

```env
SMT_ENABLED=true
SMT_MODE=auto
SMT_LITE_MODEL_PATH=./smt_model/lite_phrase_table.json
SMT_LITE_SEED_PATH=./data/smt_lite_seed.tsv
SMT_LITE_MAX_CEDICT_ENTRIES=120000
```

然后执行检查：

```powershell
cd backend
.venv312\Scripts\python.exe scripts/check_model_ready.py
```

当 `local/niutrans/docker` 缺资源时，`auto` 会自动走 `lite`，`smt` 仍然可用。

---

## 1.1) 使用 NiuTrans.SMT（你刚下载的）

你已下载到：

- `tools/NiuTrans.SMT`

仓库默认没有 `NiuTrans.Decoder`，可先在 Docker 里编译（推荐）：

```powershell
cd scripts
.\build_niutrans_decoder_in_docker.ps1
```

编译成功后，再这样配置：

```env
SMT_MODE=niutrans
SMT_NIUTRANS_ROOT=../tools/NiuTrans.SMT
SMT_NIUTRANS_BIN=
SMT_NIUTRANS_CONFIG=../tools/NiuTrans.SMT/config/NiuTrans.phrase.config
```

说明：
- 若 `SMT_NIUTRANS_BIN` 为空，会自动尝试 `${SMT_NIUTRANS_ROOT}/bin/NiuTrans.Decoder(.exe)`。
- 若 Docker 报 daemon 未启动，请先启动 Docker Desktop 再执行编译脚本。

---

## 2) 构建/训练 lite 统计模型（可选）

你可以把种子语料 + CEDICT 构建成持久化短语表：

```powershell
cd backend
.venv312\Scripts\python.exe scripts/prepare_smt_lite_model.py `
  --seed data/smt_lite_seed.tsv `
  --cedict C:/Users/23396/Downloads/cedict_1_0_ts_utf-8_mdbg/cedict_ts.u8 `
  --max-cedict 120000 `
  --output smt_model/lite_phrase_table.json
```

生成后，`SMT_MODE=lite` 或 `SMT_MODE=auto` 都会优先使用该短语表。

---

## 3) 切回真实 Moses（local/docker）

如果你后续准备了完整 Moses 产物：

- `backend/smt_model/moses.ini`
- `moses.ini` 引用的文件（如 `phrase-table.gz`、`lm.binary` 等）
- 本地 Moses 可执行文件（`local`）或 Docker 镜像（`docker`）

即可把模式改为：

```env
SMT_MODE=local
```

或

```env
SMT_MODE=docker
```

---

## 4) 一键写入 SMT 配置

```powershell
cd scripts
.\configure_smt_env.ps1 -Mode auto
```

也支持：

```powershell
.\configure_smt_env.ps1 -Mode local
.\configure_smt_env.ps1 -Mode niutrans
.\configure_smt_env.ps1 -Mode docker
.\configure_smt_env.ps1 -Mode lite
```

---

## 5) 验收标准

- `GET /api/v1/engines` 中 `smt.ready=true`
- 前端选择 `smt` 时可返回翻译结果（不再是 `not ready`）
