# SMT Quickstart（Moses 主 + KenLM 辅）

本项目中，`smt` 引擎已经接到后端运行时；要进入“可用”状态，你只需要补齐运行产物。

## 1) 必备内容
- Moses 可执行文件（本地或 Docker）。
- `backend/smt_model/moses.ini`。
- `moses.ini` 引用的文件（通常包括 `phrase-table.gz`、`reordering-table*.gz`、`lm.binary`）。

## 2) `.env` 关键项

```env
SMT_ENABLED=true
SMT_MODE=local
SMT_MOSES_ROOT=../../mosesdecoder-master
SMT_MOSES_BIN=
SMT_MODEL_DIR=./smt_model
SMT_DOCKER_IMAGE=moses-smt:latest
```

也可以用脚本直接写入 `.env`：

```powershell
cd scripts
.\configure_smt_env.ps1 -Mode local -MosesRoot ../../mosesdecoder-master -ModelDir ./smt_model
```

如果你走 Docker 模式：
- `SMT_MODE=docker`
- 确保本地 `docker images` 中已有 `moses-smt:latest`

## 3) 最小 `moses.ini` 参考

> 仅示意，具体特征与权重以你的训练产物为准。

```ini
[input-factors]
0

[mapping]
0 T 0

[feature]
UnknownWordPenalty
WordPenalty
PhrasePenalty
Distortion
KENLM name=LM0 factor=0 path=lm.binary order=5
PhraseDictionaryMemory name=TranslationModel0 num-features=4 path=phrase-table.gz input-factor=0 output-factor=0
LexicalReordering name=LexicalReordering0 num-features=6 path=reordering-table.wbe-msd-bidirectional-fe.gz input-factor=0 output-factor=0

[weight]
UnknownWordPenalty0= 1
WordPenalty0= -1
PhrasePenalty0= 0.2
Distortion0= 0.3
LM0= 0.8
TranslationModel0= 0.2 0.2 0.2 0.2
LexicalReordering0= 0.3 0.3 0.3 0.3 0.3 0.3
```

## 4) 验证

先复制模板（如果你还没有 `moses.ini`）：

```powershell
cd backend\smt_model
Copy-Item moses.ini.example moses.ini
```

```powershell
cd backend
.venv312\Scripts\python.exe scripts/check_model_ready.py
```

现在脚本会额外检查：
- `moses.ini` 是否存在。
- `moses.ini` 中引用的文件路径是否真实存在。
- Moses 可执行文件是否可定位。

## 5) 调通后预期
- `GET /api/v1/engines` 中 `smt.ready=true`。
- 前端选择 `smt` 后可返回真实翻译结果。
