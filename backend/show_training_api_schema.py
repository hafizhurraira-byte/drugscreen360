import json
from app.main import app

spec = app.openapi()

for path, methods in spec["paths"].items():
    if path in [
        "/api/admet-training/train",
        "/api/admet-training/models/{model_id}/activate",
        "/api/admet-training/active-model",
        "/api/admet-training/models"
    ]:
        print("\n==============================")
        print(path)
        print("==============================")
        print(json.dumps(methods, indent=2))
