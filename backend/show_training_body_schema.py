import json
from app.main import app

spec = app.openapi()
schemas = spec["components"]["schemas"]

wanted = [
    "AdmetTrainingRequest",
    "ModelActivateRequest",
    "AdmetTrainingResponse",
    "DiscoveredModelSummary",
    "ActiveModelResponse"
]

for name in wanted:
    print("\n==============================")
    print(name)
    print("==============================")
    print(json.dumps(schemas.get(name, {}), indent=2))
