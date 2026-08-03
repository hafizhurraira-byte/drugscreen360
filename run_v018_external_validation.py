import json
from pathlib import Path
import requests

url = "http://127.0.0.1:8010/api/admet-validation/external/run"
csv_path = Path(r"D:\DRUG CONJUGATE\drugscreen360\v018_smoke_external_validation_12.csv")

data = {
    "validation_dataset_name": "v0.18 smoke external validation 12 records",
    "model_id": "trained_admet_dataset_1479_run_692",
    "smiles_column": "smiles",
    "label_column": "toxicity_concern",
    "compound_name_column": "compound_name",
    "positive_label": "1",
    "negative_label": "0",
    "decision_threshold": "0.5",
    "notes": "Smoke-test external validation for active v0.18 model with at least 10 valid records."
}

with csv_path.open("rb") as f:
    files = {"file": (csv_path.name, f, "text/csv")}
    response = requests.post(url, data=data, files=files)

print("STATUS:", response.status_code)
try:
    print(json.dumps(response.json(), indent=2))
except Exception:
    print(response.text)
