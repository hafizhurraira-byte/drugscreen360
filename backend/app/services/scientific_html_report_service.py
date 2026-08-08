import json
from datetime import datetime, timezone
from html import escape
from importlib.metadata import version
from typing import Any

from app.models.platform_models import ScientificHtmlReportRequest
from app.services.descriptors import render_structure_image_base64


def _table(value: Any) -> str:
    if not value:
        return "<p>Not supplied.</p>"
    rows = value if isinstance(value, list) else [value]
    if not all(isinstance(row, dict) for row in rows):
        return f"<pre>{escape(json.dumps(value, indent=2, default=str))}</pre>"
    keys = list(dict.fromkeys(key for row in rows for key in row))
    head = "".join(f"<th>{escape(str(key))}</th>" for key in keys)
    body = "".join("<tr>" + "".join(f"<td>{escape(str(row.get(key, '')))}</td>" for key in keys) + "</tr>" for row in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _bars(values: dict[str, Any]) -> str:
    bars = []
    for name, raw in values.items():
        if isinstance(raw, (int, float)):
            percent = max(0.0, min(100.0, float(raw) * 100 if abs(float(raw)) <= 1 else float(raw)))
            bars.append(f'<div class="bar"><span>{escape(str(name))}</span><i style="width:{percent:.2f}%"></i><b>{raw}</b></div>')
    return "".join(bars) or "<p>No numeric chart data supplied.</p>"


def create_scientific_html_report(request: ScientificHtmlReportRequest) -> str:
    smiles = request.compound.get("canonical_smiles") or request.compound.get("smiles")
    image = ""
    if isinstance(smiles, str) and smiles.strip():
        image = f'<img class="structure" alt="2D molecular structure" src="{render_structure_image_base64(smiles)}">'
    timestamp = datetime.now(timezone.utc).isoformat()
    metadata = {"generated_at": timestamp, "rdkit_version": version("rdkit"), **request.metadata}
    sections = [
        ("Compound information", _table(request.compound) + image),
        ("Predictions", _table(request.predictions)),
        ("ADMET", _table(request.admet)),
        ("Confidence", _table(request.confidence) + _bars(request.confidence)),
        ("Uncertainty", _table(request.uncertainty) + _bars(request.uncertainty)),
        ("Explainability", _table(request.explainability)),
        ("Ranking", _table(request.ranking) + _bars(request.ranking.get("contributions", {}) if isinstance(request.ranking, dict) else {})),
        ("Metadata and model versions", _table(metadata)),
    ]
    content = "".join(f"<section><h2>{escape(title)}</h2>{body}</section>" for title, body in sections)
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>{escape(request.title)}</title><style>body{{font:14px system-ui;max-width:1100px;margin:auto;padding:2rem;color:#172033}}h1,h2{{color:#123d5a}}section{{border-top:1px solid #ccd6df;padding:1rem 0}}table{{border-collapse:collapse;width:100%;overflow-wrap:anywhere}}th,td{{border:1px solid #d7e0e7;padding:.45rem;text-align:left;vertical-align:top}}th{{background:#edf4f7}}.structure{{max-width:520px;width:100%;height:auto}}.bar{{display:grid;grid-template-columns:10rem 1fr 5rem;gap:.5rem;align-items:center;margin:.4rem 0}}.bar i{{display:block;background:#287fa3;height:.8rem}}pre{{white-space:pre-wrap}}</style></head><body><h1>{escape(request.title)}</h1><p>Research-use computational evidence; not clinical or regulatory advice.</p>{content}</body></html>'''
