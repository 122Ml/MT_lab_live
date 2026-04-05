# 手动下载待办（由你执行）

> 按你的要求：涉及下载的步骤由你手动处理，我这边只继续推进代码和脚本。

## 已支持的便捷操作
- 若模型已在 ModelScope 缓存，可执行：

```powershell
cd scripts
.\sync_modelscope_cache.ps1
```

- 默认同步目标：`MT-Lab Live/models/`。

## 需要准备的模型
1. `Helsinki-NLP/opus-mt-zh-en`
2. `Helsinki-NLP/opus-mt-en-zh`
3. （可选）`facebook/nllb-200-distilled-600M`

## 最小必需文件

### `opus-mt-zh-en` / `opus-mt-en-zh`
- `pytorch_model.bin`
- `config.json`
- `tokenizer_config.json`
- `vocab.json`
- `source.spm`
- `target.spm`

### `nllb-200-distilled-600M`（可选）
- `pytorch_model.bin`
- `config.json`
- `tokenizer.json`
- `tokenizer_config.json`
- `sentencepiece.bpe.model`
- `special_tokens_map.json`

## SMT 额外准备
- `backend/smt_model/moses.ini`（必需）
- 常见依赖：`phrase-table.gz`、`reordering-table*.gz`、`lm.binary`
- Moses 运行时：
  - 本地模式：准备 `moses` 可执行文件（`SMT_MOSES_BIN` 或 `SMT_MOSES_ROOT`）
  - Docker 模式：准备可用镜像（默认 `moses-smt:latest`）

## 下载后你需要做
1. 在 `backend/.env` 配置本地路径：
   - `NMT_MODEL_ZH_EN`
   - `NMT_MODEL_EN_ZH`
   - `TRANSFORMER_MODEL`（若启用）
2. 配置 SMT：
   - `SMT_MODE=local` 或 `docker`
   - `SMT_MOSES_ROOT` / `SMT_MOSES_BIN`
   - `SMT_MODEL_DIR=./smt_model`
   - 或直接用脚本写入：

```powershell
cd scripts
.\configure_smt_env.ps1 -Mode local -MosesRoot ../../mosesdecoder-master -ModelDir ./smt_model
```

3. 执行本地检查：

```powershell
cd backend
.venv312\Scripts\python.exe scripts/check_model_ready.py
```

4. 执行项目自检（不下载）：

```powershell
cd ..
cd scripts
.\verify_project.ps1
```
