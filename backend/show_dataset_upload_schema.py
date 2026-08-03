import json
from app.main import app

spec = app.openapi()
schemas = spec["components"]["schemas"]

wanted = [
    "Body_upload_dataset_api_admet_datasets_upload_post",
    "DatasetUploadResponse",
    "DatasetValidationSummary",
    "DatasetRecord"
]

for name in wanted:
    print("\n==============================")
    print(name)
    print("==============================")
    print(json.dumps(schemas.get(name, {}), indent=2))
