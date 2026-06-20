# GitHub Upload Checklist

Use this checklist before pushing DrugScreen360 to GitHub.

## 1. Confirm Local Checks

```powershell
cd "D:\DRUG CONJUGATE\drugscreen360"
.\scripts\run_tests.ps1
```

Expected:

- Backend tests pass.
- Frontend tests pass.
- Frontend build passes.

## 2. Check Git Status

```powershell
git status
```

Review all changed and untracked files before committing.

## 3. Confirm Ignored Files

These files/folders should not be committed:

- `frontend/node_modules/`
- `frontend/dist/`
- `backend/.venv/`
- `backend/.venv312/`
- `.env`
- `backend/.env`
- `frontend/.env`
- `*.db`
- `*.sqlite`
- `*.sqlite3`
- `backups/`
- `backend/uploads/`
- `backend/reports/`
- `backend/app/uploads/`
- `__pycache__/`
- `*.pyc`

Optional check:

```powershell
git status --ignored
```

## 4. Confirm No Secrets

Check that only example placeholders exist for provider keys.

```powershell
rg -n --hidden --glob '!frontend/node_modules/**' --glob '!frontend/dist/**' --glob '!backend/.venv312/**' --glob '!backups/**' --glob '!.git/**' "API_KEY|password|token|secret|Bearer" .
```

Do not commit real `.env` files or real API keys.

## 5. Commit

```powershell
git add .
git commit -m "Prepare v0.1.0 local MVP release"
```

## 6. Tag

```powershell
git tag v0.1.0-local-mvp
```

## 7. Push

If the remote is already configured:

```powershell
git push origin main
git push origin v0.1.0-local-mvp
```

If your branch is named `master`, use:

```powershell
git push origin master
git push origin v0.1.0-local-mvp
```

## 8. Verify Online Repository

After pushing:

- Confirm `README.md` renders correctly.
- Confirm `RELEASE_NOTES.md` is visible.
- Confirm `LICENSE` is visible.
- Confirm `.env` files and SQLite databases are not present.
- Confirm GitHub shows tag `v0.1.0-local-mvp`.
- Confirm the repository visibility is what you intend, especially if this project is private.
