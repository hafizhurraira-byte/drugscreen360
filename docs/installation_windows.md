# Windows Installation Guide

This guide is for running DrugScreen360 locally on Windows with PowerShell.

## Requirements

- Windows 10 or later.
- Git.
- Python 3.12.
- Node.js LTS, preferably Node.js 22.
- PowerShell.

DrugScreen360 is a local research-use computational decision-support app. It is not a clinical, diagnostic, therapeutic, regulatory, or guaranteed drug-safety tool.

## Clone

```powershell
cd "D:\DRUG CONJUGATE"
git clone https://github.com/hafizhurraira-byte/drugscreen360.git
cd "D:\DRUG CONJUGATE\drugscreen360"
```

## Backend Setup

If the backend virtual environment is already present, the start scripts can use it directly. If it is missing:

```powershell
cd "D:\DRUG CONJUGATE\drugscreen360\backend"
py -3.12 -m venv .venv312
.\.venv312\Scripts\Activate.ps1
pip install -r requirements.txt
```

Backend URL:

```text
http://127.0.0.1:8010
```

## Frontend Setup

```powershell
cd "D:\DRUG CONJUGATE\drugscreen360\frontend"
npm install
```

Frontend URL:

```text
http://127.0.0.1:5173
```

## Start the App

```powershell
cd "D:\DRUG CONJUGATE\drugscreen360"
.\scripts\start_all.ps1
```

The script opens backend and frontend PowerShell windows and launches the browser.

## Run Tests

```powershell
cd "D:\DRUG CONJUGATE\drugscreen360"
.\scripts\run_tests.ps1
```

This runs backend tests, frontend tests, and the frontend production build.

## Manual Backend Start

```powershell
cd "D:\DRUG CONJUGATE\drugscreen360\backend"
.\.venv312\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

## Manual Frontend Start

```powershell
cd "D:\DRUG CONJUGATE\drugscreen360\frontend"
npm run dev -- --host 127.0.0.1 --port 5173
```

## Common Notes

- Keep paths with spaces inside quotes.
- Do not commit `.env` files.
- Generated reports, exports, databases, trained model folders, `node_modules`, and `frontend/dist` are local artifacts.
- If RDKit installation fails, recreate the backend environment and reinstall from `backend/requirements.txt`.

