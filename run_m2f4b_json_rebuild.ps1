$ErrorActionPreference = 'Stop'
$python = 'D:\DRUG CONJUGATE\drugscreen360\backend\.venv\Scripts\python.exe'
$script = 'D:\DRUG CONJUGATE\drugscreen360\run_m2f4b_pubchem_sid_batch_retrieval.py'
$log = 'D:\DRUG CONJUGATE\DRUGDESIGN360_REAL_DATA\toxicity_panel\_operational\m2f4b_pubchem_aid_743079_recovery\retrieval.log'
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $log) | Out-Null
& $python $script 2>&1 | Tee-Object -FilePath $log
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) { exit $exitCode }
