# SMT Model Package Placeholder

Put your Moses SMT runtime files here.

Minimum required file:

- `moses.ini`

You can bootstrap quickly by copying:

- `moses.ini.example` -> `moses.ini`

Common additional files referenced by `moses.ini`:

- `phrase-table.gz`
- `reordering-table*.gz`
- `lm.binary` (KenLM)

This folder is used by `SMT_MODEL_DIR` in `backend/.env`.

After putting files in place, run:

```powershell
cd backend
.venv312\Scripts\python.exe scripts/check_model_ready.py
```

The checker validates `moses.ini` and referenced resource paths.
