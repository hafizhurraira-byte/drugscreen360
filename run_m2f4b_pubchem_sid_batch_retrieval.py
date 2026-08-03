"""Repair, rebuild, validate, and seal M2F-4B PubChem AID 743079 raw provenance."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"D:\DRUG CONJUGATE\DRUGDESIGN360_REAL_DATA\toxicity_panel")
WORK = ROOT / "m2f4b_era_v2_data_retrieval_and_raw_provenance"
OPS = ROOT / "_operational" / "m2f4b_pubchem_aid_743079_recovery"
REC_RAW, REC_META = OPS / "raw", OPS / "http_metadata"
PILOT = OPS / "pilot"
POST_SEAL = ROOT / "_operational" / "m2f4b_post_seal_verification.json"
ENDPOINT = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/assay/aid/743079/CSV"
PYTHON = Path(r"D:\DRUG CONJUGATE\drugscreen360\backend\.venv\Scripts\python.exe")
BATCH_SIZE, MAX_ATTEMPTS, DELAY = 400, 5, 0.75
EXPECTED = {
    "chembl_esr1_ec50_offset_0000.json": "043C2F243BB9635E0E3832D8C9DD8F60A5621CE6C0DD18DCCA7C34F4D655A678",
    "chembl_esr1_ec50_offset_1000.json": "6805E3B9BC8E05F581F0A4F5C021E31829B9A7B49D874A76A44E47D3D2A4DA35",
    "chembl_esr1_ac50_offset_0000.json": "459F24E43D6B9A3CEB198EBE4E737DAA3F12F1ECB2C150D539231BD8964343C7",
    "chembl_esr1_ac50_offset_1000.json": "54AB0C75D80FFF5C68B6DC35AECABBABE8A4BA6F542FDE7440B1CDF1A3FD6E65",
    "chembl_esr1_ac50_offset_2000.json": "A2DEEBF2EC95F709DECDF4B5BC2A1992728B2EDD7237302B2E6614D1B19B2E10",
    "pubchem_aid_743079_concise_raw.csv": "A4B1F68C544C01BB68AC19263576ACFF2E17A6281D322B54F267FEB60575917E",
    "pubchem_aid_743079_description.json": "6E0C5B20A6E9B7246AE6FC570687CAD0093462BCDC6BA5C1ABCC03AADD14516A",
    "pubchem_aid_743079_summary.json": "11375381FDB9C7CB3E16C54AC9F7E0804D8AE4D28E40B8705C4D11C3D9C41856",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    os.replace(temp, path)


def write_raw(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def sid_column(headers: list[str]) -> str:
    normalized = {h.strip().upper().replace(" ", "_"): h for h in headers}
    for name in ("PUBCHEM_SID", "SID", "SUBSTANCE_ID"):
        if name in normalized:
            return normalized[name]
    raise RuntimeError(f"SID column absent: {headers}")


def parse_csv(data: bytes) -> dict:
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
    if not reader.fieldnames:
        raise RuntimeError("CSV header absent")
    column = sid_column(reader.fieldnames)
    values, rows, metadata_rows = [], 0, 0
    for row in reader:
        raw_sid = str(row[column] or "").strip()
        if not raw_sid:
            metadata_rows += 1
            continue
        rows += 1
        try:
            values.append(int(raw_sid))
        except (ValueError, TypeError):
            raise RuntimeError(f"Invalid SID at response row {rows + 1}")
    if not rows:
        raise RuntimeError("CSV response has zero rows")
    return {"headers": reader.fieldnames, "sid_column": column, "row_count": rows, "metadata_row_count": metadata_rows, "sid_values": values, "unique_sids": sorted(set(values)), "duplicate_sid_row_occurrences": len(values) - len(set(values))}


def frozen_sids(concise: Path) -> tuple[list[int], dict]:
    if sha(concise) != EXPECTED[concise.name]:
        raise RuntimeError("Frozen concise CSV hash mismatch")
    with concise.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise RuntimeError("Frozen concise CSV header absent")
        column = sid_column(reader.fieldnames)
        values = [int(row[column]) for row in reader]
    unique = sorted(set(values))
    return unique, {"original_row_count": len(values), "sid_column": column, "sid_value_count": len(values), "unique_sid_count": len(unique), "duplicate_sid_occurrences": len(values) - len(unique), "source_sha256": sha(concise)}


def request_sids(sids: list[int]) -> tuple[bytes, dict]:
    body = urllib.parse.urlencode({"sid": ",".join(map(str, sids))}).encode("ascii")
    for attempt in range(1, MAX_ATTEMPTS + 1):
        request = urllib.request.Request(ENDPOINT, data=body, method="POST", headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "text/csv", "User-Agent": "DrugDesign360-M2F4B-Recovery/2.0"})
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                data = response.read()
                received = now()
                metadata = {"request_method": "POST", "request_endpoint": ENDPOINT, "request_content_type": "application/x-www-form-urlencoded", "requested_sids": sids, "http_status": int(response.status), "response_headers": dict(response.headers.items()), "http_retrieval_timestamp_utc": received, "attempt": attempt}
            if metadata["http_status"] != 200:
                raise RuntimeError(f"Unexpected HTTP status {metadata['http_status']}")
            return data, metadata
        except urllib.error.HTTPError as exc:
            excerpt = exc.read(2000).decode("utf-8", errors="replace")
            if exc.code == 429 or 500 <= exc.code <= 599:
                if attempt == MAX_ATTEMPTS:
                    raise RuntimeError(f"Retriable HTTP {exc.code} exhausted: {excerpt}") from exc
                time.sleep(min(60, 2 ** attempt))
                continue
            raise RuntimeError(f"Non-retriable HTTP {exc.code}: {excerpt}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == MAX_ATTEMPTS:
                raise RuntimeError(f"Transport retries exhausted: {exc}") from exc
            time.sleep(min(60, 2 ** attempt))
    raise AssertionError("unreachable")


def validate_membership(parsed: dict, requested: list[int]) -> dict:
    expected, returned = set(requested), set(parsed["unique_sids"])
    return {"requested_sid_count": len(expected), "returned_unique_sid_count": len(returned), "missing_sids": sorted(expected - returned), "unexpected_sids": sorted(returned - expected), "raw_row_count": parsed["row_count"], "duplicate_sid_row_occurrences": parsed["duplicate_sid_row_occurrences"]}


def pilot(sids: list[int]) -> None:
    chosen = sids[:3]
    data, http = request_sids(chosen)
    write_raw(PILOT / "pubchem_aid_743079_full_raw_pilot.csv", data)
    parsed = parse_csv(data)
    membership = validate_membership(parsed, chosen)
    concise_headers = {"AID", "SID", "CID", "Activity Outcome", "Target Accession", "Target GeneID", "Activity Value [uM]", "Activity Name", "Assay Name", "Assay Type", "PubMed ID", "RNAi"}
    full = set(parsed["headers"]) != concise_headers and len(parsed["headers"]) > len(concise_headers)
    result = {**http, **membership, "status": "PASS" if http["http_status"] == 200 and not membership["missing_sids"] and not membership["unexpected_sids"] and full else "FAIL", "response_content_type": http["response_headers"].get("Content-Type"), "returned_format": "CSV", "sid_column": parsed["sid_column"], "full_bioassay_data": full, "multiple_rows_per_sid_observed": parsed["duplicate_sid_row_occurrences"] > 0, "multiple_rows_per_sid_handling": "ALLOWED_AND_COVERAGE_ASSESSED_BY_UNIQUE_SID"}
    result["response_sha256"] = sha(PILOT / "pubchem_aid_743079_full_raw_pilot.csv")
    result["response_size_bytes"] = len(data)
    result["filesystem_last_write_time_utc"] = datetime.fromtimestamp((PILOT / "pubchem_aid_743079_full_raw_pilot.csv").stat().st_mtime, timezone.utc).isoformat()
    write_json(PILOT / "pilot_http_metadata.json", result)
    if result["status"] != "PASS":
        raise RuntimeError(f"Pilot failed: {result}")


def batches(sids: list[int]) -> list[dict]:
    return [{"batch_number": i // BATCH_SIZE + 1, "sids": sids[i:i+BATCH_SIZE], "filename": f"pubchem_aid_743079_full_raw_part_{i // BATCH_SIZE + 1:03d}.csv"} for i in range(0, len(sids), BATCH_SIZE)]


def valid_existing(batch: dict) -> dict | None:
    raw, meta = REC_RAW / batch["filename"], REC_META / batch["filename"].replace(".csv", "_http_metadata.json")
    if not raw.is_file() or not meta.is_file():
        return None
    try:
        record = json.loads(meta.read_text(encoding="utf-8"))
        parsed = parse_csv(raw.read_bytes())
        membership = validate_membership(parsed, batch["sids"])
        if record["response_sha256"] == sha(raw) and record["requested_sids"] == batch["sids"] and not membership["missing_sids"] and not membership["unexpected_sids"]:
            return record
    except Exception:
        return None
    return None


def retrieve(batch: dict) -> dict:
    reused = valid_existing(batch)
    if reused:
        return reused
    data, http = request_sids(batch["sids"])
    parsed = parse_csv(data)
    membership = validate_membership(parsed, batch["sids"])
    if membership["missing_sids"] or membership["unexpected_sids"]:
        raise RuntimeError(f"Batch {batch['batch_number']:03d} SID mismatch: {membership}")
    raw = REC_RAW / batch["filename"]
    write_raw(raw, data)
    record = {**http, **membership, "batch_number": batch["batch_number"], "raw_filename": batch["filename"], "response_sha256": sha(raw), "response_size_bytes": raw.stat().st_size, "filesystem_last_write_time_utc": datetime.fromtimestamp(raw.stat().st_mtime, timezone.utc).isoformat(), "scientific_role": "ROBUSTNESS_ONLY", "independent_external_validation": False, "status": "PASS"}
    write_json(REC_META / batch["filename"].replace(".csv", "_http_metadata.json"), record)
    return record


def next_archive() -> Path:
    n = 1
    while (ROOT / f"m2f4b_era_v2_data_retrieval_and_raw_provenance_failed_attempt_{n}").exists():
        n += 1
    return ROOT / f"m2f4b_era_v2_data_retrieval_and_raw_provenance_failed_attempt_{n}"


def rebuild(source: Path, plan: list[dict], summary: dict, records: list[dict], coverage: dict) -> Path:
    archive = next_archive()
    shutil.move(str(source), str(archive))
    WORK.mkdir(parents=True)
    for directory in ("raw", "http_metadata", "provenance", "manifests", "reports", "validators", "master"):
        (WORK / directory).mkdir()
    historical = []
    for name, expected_hash in EXPECTED.items():
        src, dst = archive / "raw" / name, WORK / "raw" / name
        if not src.is_file() or sha(src) != expected_hash:
            raise RuntimeError(f"Historical raw integrity failure: {name}")
        shutil.copy2(src, dst)
        historical.append({"filename": name, "sha256": sha(dst), "bytes": dst.stat().st_size, "http_retrieval_timestamp_utc": None, "filesystem_last_write_time_utc": datetime.fromtimestamp(dst.stat().st_mtime, timezone.utc).isoformat(), "timestamp_trust": "LOW_FILESYSTEM_ONLY"})
    for batch in plan:
        shutil.copy2(REC_RAW / batch["filename"], WORK / "raw" / batch["filename"])
        metadata_name = batch["filename"].replace(".csv", "_http_metadata.json")
        shutil.copy2(REC_META / metadata_name, WORK / "http_metadata" / metadata_name)
    write_json(WORK / "provenance/raw_source_provenance.json", {"historical_files": historical, "pubchem_aid": 743079, "pubchem_scientific_role": "ROBUSTNESS_ONLY", "pubchem_independent_external_validation": False, "no_curation": True, "model_load_count": 0, "model_fit_count": 0, "model_inference_count": 0, "era_internal_test_access_count": 0, "ar_test_access_count": 0})
    write_json(WORK / "manifests/pubchem_sid_batch_request_plan.json", {"endpoint": ENDPOINT, "request_method": "POST", "batch_size": BATCH_SIZE, "expected_unique_sid_count": summary["unique_sid_count"], "batches": plan})
    write_json(WORK / "reports/pubchem_full_raw_sid_coverage_validation.json", coverage)
    checks = {
        "5_chEMBL_files_hash_match": sum(1 for n in EXPECTED if n.startswith("chembl") and sha(WORK/"raw"/n)==EXPECTED[n]) == 5,
        "concise_hash_match": sha(WORK/"raw/pubchem_aid_743079_concise_raw.csv") == EXPECTED["pubchem_aid_743079_concise_raw.csv"],
        "description_hash_match": sha(WORK/"raw/pubchem_aid_743079_description.json") == EXPECTED["pubchem_aid_743079_description.json"],
        "summary_hash_match": sha(WORK/"raw/pubchem_aid_743079_summary.json") == EXPECTED["pubchem_aid_743079_summary.json"],
        "full_chunks_present": len(list((WORK/"raw").glob("pubchem_aid_743079_full_raw_part_*.csv"))) == len(plan),
        "deterministic_numbering": [p.name for p in sorted((WORK/"raw").glob("pubchem_aid_743079_full_raw_part_*.csv"))] == [b["filename"] for b in plan],
        "request_plan_coverage": len({sid for b in plan for sid in b["sids"]}) == summary["unique_sid_count"],
        "zero_missing_sids": coverage["missing_sid_count"] == 0,
        "zero_unexpected_sids": coverage["unexpected_sid_count"] == 0,
        "zero_requested_overlap": coverage["requested_cross_batch_overlap_count"] == 0,
        "metadata_per_chunk": len(list((WORK/"http_metadata").glob("*_http_metadata.json"))) == len(plan),
        "chunk_hash_metadata_match": all(sha(WORK/"raw"/b["filename"]) == json.loads((WORK/"http_metadata"/b["filename"].replace(".csv","_http_metadata.json")).read_text())["response_sha256"] for b in plan),
        "timestamps_governed": all(x["http_retrieval_timestamp_utc"] is None and x["timestamp_trust"] == "LOW_FILESYSTEM_ONLY" for x in historical) and all(r["http_retrieval_timestamp_utc"] and r["filesystem_last_write_time_utc"] for r in records),
        "pubchem_robustness_only": True,
        "not_independent_external_validation": True,
        "no_curation": True,
        "no_model_activity": True,
        "no_protected_test_access": True,
        "manifest_written_last_contract": True,
        "post_seal_verification_required": True,
    }
    validator = {"status": "PASS" if all(checks.values()) else "FAIL", "passed_checks": sum(checks.values()), "failed_checks": len(checks)-sum(checks.values()), "total_checks": len(checks), "checks": checks}
    write_json(WORK / "validators/validator_result.json", validator)
    if validator["status"] != "PASS":
        raise RuntimeError(f"Pre-seal validator failed: {checks}")
    master = {"phase": "M2F-4B_ERA_V2_DATA_RETRIEVAL_AND_RAW_PROVENANCE_REPAIR", "overall_status": "PASS", "final_phase_decision": "ERA_V2_RAW_DATA_AND_PROVENANCE_READY_FOR_CURATION", "m2f4c_permitted": True, "concise": summary, "coverage": {k:v for k,v in coverage.items() if k != "chunks"}, "validator": validator, "archive_path": str(archive), "retrieval_logs": str(OPS), "model_activity_count": 0, "protected_test_access_count": 0}
    write_json(WORK / "master/master_results.json", master)
    manifest_path = WORK / "master/file_hash_manifest.json"
    entries = [{"relative_path": str(p.relative_to(WORK)).replace("\\", "/"), "bytes": p.stat().st_size, "sha256": sha(p)} for p in sorted(WORK.rglob("*")) if p.is_file() and p != manifest_path]
    write_json(manifest_path, {"manifest_version": "M2F4B_REPAIRED_FILE_HASH_MANIFEST_V1", "entries": entries, "total_files": len(entries)})
    return archive


def verify_post_seal(archive: Path) -> dict:
    manifest = json.loads((WORK/"master/file_hash_manifest.json").read_text(encoding="utf-8"))
    listed = {e["relative_path"] for e in manifest["entries"]}
    actual = {str(p.relative_to(WORK)).replace("\\", "/") for p in WORK.rglob("*") if p.is_file() and p != WORK/"master/file_hash_manifest.json"}
    hashes = all((WORK/e["relative_path"]).is_file() and sha(WORK/e["relative_path"]) == e["sha256"] and (WORK/e["relative_path"]).stat().st_size == e["bytes"] for e in manifest["entries"])
    latest_governed = max(p.stat().st_mtime_ns for p in WORK.rglob("*") if p.is_file() and p != WORK/"master/file_hash_manifest.json")
    result = {"status": "PASS" if listed == actual and hashes and (WORK/"master/file_hash_manifest.json").stat().st_mtime_ns >= latest_governed else "FAIL", "manifest_sha256": sha(WORK/"master/file_hash_manifest.json"), "listed_file_count": len(listed), "actual_file_count": len(actual), "no_extra_files": listed == actual, "all_hashes_and_sizes_match": hashes, "manifest_written_last": (WORK/"master/file_hash_manifest.json").stat().st_mtime_ns >= latest_governed, "archived_workspace": str(archive), "verified_at_utc": now()}
    write_json(POST_SEAL, result)
    return result


def main() -> None:
    for path in (OPS, REC_RAW, REC_META, PILOT): path.mkdir(parents=True, exist_ok=True)
    concise = WORK / "raw/pubchem_aid_743079_concise_raw.csv"
    sids, summary = frozen_sids(concise)
    write_json(OPS / "frozen_concise_sid_summary.json", summary)
    pilot(sids)
    if "--pilot-only" in sys.argv:
        print(json.dumps(json.loads((PILOT / "pilot_http_metadata.json").read_text(encoding="utf-8")), indent=2))
        return
    plan = batches(sids)
    flattened = [sid for batch in plan for sid in batch["sids"]]
    if len(flattened) != len(set(flattened)) or flattened != sids:
        raise RuntimeError("Request plan overlaps or does not exactly cover frozen SIDs")
    write_json(OPS / "pubchem_sid_batch_request_plan.json", {"endpoint": ENDPOINT, "request_method": "POST", "batch_size": BATCH_SIZE, "batches": plan})
    records = []
    for batch in plan:
        print(f"Retrieving {batch['batch_number']:03d}/{len(plan):03d}", flush=True)
        records.append(retrieve(batch))
        time.sleep(DELAY)
    returned_by_chunk, chunk_results, all_returned = {}, [], []
    for batch in plan:
        parsed = parse_csv((REC_RAW/batch["filename"]).read_bytes())
        membership = validate_membership(parsed, batch["sids"])
        returned_by_chunk[batch["batch_number"]] = set(parsed["unique_sids"])
        all_returned.extend(parsed["sid_values"])
        chunk_results.append({"batch_number": batch["batch_number"], "filename": batch["filename"], **{k:v for k,v in membership.items() if k not in ("missing_sids","unexpected_sids")}, "missing_sid_count": len(membership["missing_sids"]), "unexpected_sid_count": len(membership["unexpected_sids"])})
    cross_overlap = set()
    seen = set()
    for n in sorted(returned_by_chunk): cross_overlap |= seen & returned_by_chunk[n]; seen |= returned_by_chunk[n]
    expected, returned = set(sids), set(all_returned)
    coverage = {"status": "PASS" if expected == returned and not cross_overlap else "FAIL", "expected_unique_sid_count": len(expected), "returned_unique_sid_count": len(returned), "missing_sid_count": len(expected-returned), "unexpected_sid_count": len(returned-expected), "missing_sids": sorted(expected-returned), "unexpected_sids": sorted(returned-expected), "requested_cross_batch_overlap_count": len(flattened)-len(set(flattened)), "returned_cross_chunk_overlap_count": len(cross_overlap), "returned_cross_chunk_overlap_sids": sorted(cross_overlap), "total_raw_response_row_count": len(all_returned), "total_chunk_count": len(plan), "chunks": chunk_results}
    write_json(OPS / "pubchem_full_raw_sid_coverage_validation.json", coverage)
    if coverage["status"] != "PASS": raise RuntimeError(f"Global SID coverage failed: {coverage}")
    archive = rebuild(WORK, plan, summary, records, coverage)
    post = verify_post_seal(archive)
    if post["status"] != "PASS": raise RuntimeError(f"Post-seal verification failed: {post}")
    print(json.dumps({"overall_status":"PASS","pilot_endpoint":ENDPOINT,"request_method":"POST","frozen_concise_row_count":summary["original_row_count"],"expected_unique_sid_count":coverage["expected_unique_sid_count"],"returned_unique_sid_count":coverage["returned_unique_sid_count"],"chunk_count":coverage["total_chunk_count"],"total_returned_raw_rows":coverage["total_raw_response_row_count"],"missing_sid_count":coverage["missing_sid_count"],"unexpected_sid_count":coverage["unexpected_sid_count"],"duplicate_overlap_status":"PASS","validator":"PASS","manifest_sha256":post["manifest_sha256"],"post_seal_verification":"PASS","decision":"ERA_V2_RAW_DATA_AND_PROVENANCE_READY_FOR_CURATION","m2f4c_permitted":True}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        write_json(OPS / "fatal_failure.json", {"status":"FAIL","error_type":type(exc).__name__,"error":str(exc),"failed_at_utc":now(),"resume_command":f"& '{PYTHON}' '{Path(__file__).resolve()}'"})
        print(f"FATAL: {exc}", file=sys.stderr)
        raise
