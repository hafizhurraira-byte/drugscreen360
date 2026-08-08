# Dependency and licence audit

Audit date: 2026-08-06. Scope: declared direct dependencies plus installed frontend audit. “Commercial” means compatible with the prompt's MIT/BSD/BSD-3/Apache-2/PostgreSQL allowlist; dataset and model-weight terms remain separate.

| Package | Declared version | Licence | Commercial | Purpose | Replace? | Homepage / source / citation |
|---|---:|---|---|---|---|---|
| FastAPI | 0.115.6 | MIT | Yes | API | No | https://github.com/fastapi/fastapi |
| Uvicorn | 0.34.0 | BSD-3-Clause | Yes | ASGI server | No | https://www.uvicorn.org/ |
| Requests | 2.32.3 | Apache-2.0 | Yes | HTTP client | No | https://github.com/psf/requests |
| Pydantic | 2.10.4 | MIT | Yes | Validation | No | https://github.com/pydantic/pydantic |
| RDKit | 2026.3.3 | BSD-3-Clause | Yes | Cheminformatics | No | https://github.com/rdkit/rdkit ; https://www.rdkit.org/docs/Cookbook.html#citing-the-rdkit |
| ReportLab | 4.2.5 | BSD | Yes | PDF export | No | https://www.reportlab.com/opensource/ |
| python-docx | 1.1.2 | MIT | Yes | DOCX export | No | https://github.com/python-openxml/python-docx |
| pytest | 8.3.4 | MIT | Yes | Tests | No | https://github.com/pytest-dev/pytest |
| httpx | 0.28.1 | BSD-3-Clause | Yes | API tests/client | No | https://github.com/encode/httpx |
| python-multipart | 0.0.20 | Apache-2.0 | Yes | Multipart uploads | No | https://github.com/Kludex/python-multipart |
| scikit-learn | 1.5.2 | BSD-3-Clause | Yes | ML | No | https://github.com/scikit-learn/scikit-learn ; https://scikit-learn.org/stable/about.html#citing-scikit-learn |
| React / React DOM | 18.3.1 | MIT | Yes | UI | No | https://github.com/facebook/react |
| Vite | ^6.0.5 | MIT | Yes | Frontend build | No | https://github.com/vitejs/vite |
| @vitejs/plugin-react | ^4.3.4 | MIT | Yes | React build plugin | No | https://github.com/vitejs/vite-plugin-react |
| react-icons | 5.5.0 | MIT | Yes | UI icons | No | https://github.com/react-icons/react-icons |
| Autoprefixer | ^10.4.20 | MIT | Yes | CSS build | No | https://github.com/postcss/autoprefixer |
| PostCSS | ^8.5.24 | MIT | Yes | CSS processing | No | https://github.com/postcss/postcss |
| Tailwind CSS | ^3.4.17 | MIT | Yes | CSS utilities | No | https://github.com/tailwindlabs/tailwindcss |

Removed: unused `chardet` (LGPL-2.1) and `lucide-react` (ISC, commercially permissive but outside the explicit allowlist). `react-icons` is the MIT replacement. PostCSS was raised to 8.5.24 to resolve GHSA-r28c-9q8g-f849 and GHSA-fxqj-rqcc-2cmp; `npm audit` then reported zero vulnerabilities.

The current machine's globally installed Python versions differ from several pins, so it is evidence for tests, not a reproducible production environment. Build production from `backend/requirements.txt`. Optional approved tools (SHAP, XGBoost, DeepChem, Chemprop, Vina, py3Dmol/NGL) are not declared merely because they are approved: their code, weights, runtime, and scientific scope require separate validation before activation.
