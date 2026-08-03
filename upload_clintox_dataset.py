import json
from pathlib import Path
import requests

url = "http://127.0.0.1:8010/api/admet-datasets/upload"
csv_path = Path(r"D:\DRUG CONJUGATE\drugscreen360\data\training\drugscreen360_clintox_full_cttox.csv")

data = {
    "dataset_name": "ClinTox toxicity concern full dataset",
    "task_name": "toxicity_concern",
    "smiles_column": "smiles",
    "label_column": "toxicity_concern",
    "compound_name_column": "",
    "notes": "Authentic ClinTox CT_TOX mapped to toxicity_concern for v0.16 trained local ADMET/toxicity model."
}

with csv_path.open("rb") as f:
    files = {"file": (csv_path.name, f, "text/csv")}
    response = requests.post(url, data=data, files=files)

print("STATUS:", response.status_code)
try:
    print(json.dumps(response.json(), indent=2))
except Exception:
    print(response.text)
