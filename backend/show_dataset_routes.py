import json
from app.main import app

spec = app.openapi()

for path, methods in spec["paths"].items():
    if any(k in path.lower() for k in ["dataset", "datasets", "curation", "import", "upload"]):
        print("\n==============================")
        print(path)
        print("==============================")
        print(json.dumps(methods, indent=2)[:4000])
