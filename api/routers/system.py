from __future__ import annotations

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import Response

from api import __version__
from api.errors import ApiError
from api.schemas import AnalysisStatus, DatasetInfo, Health, RunRequest
from api.state import SESSION, require_data
from api.util import clean, paginate
from core.detection.rules import RULE_DESCRIPTIONS
from core.detection.pipeline import SCORE_DISCLAIMER

router = APIRouter(prefix="/api")


@router.get("/health", response_model=Health, tags=["system"])
def health():
    return {"status": "ok", "version": __version__, "dataset_loaded": SESSION.result is not None,
            "analysis_status": SESSION.status}


@router.get("/dataset", response_model=DatasetInfo, tags=["dataset"])
def dataset():
    m, r = SESSION.meta, SESSION.result
    if m is None or r is None:
        return {"loaded": False}
    return {"loaded": True, **m.__dict__, "analysis_completed_at": SESSION.finished_at,
            "model_ran": r.model_ran, "notes": r.notes}


@router.get("/analysis/status", response_model=AnalysisStatus, tags=["analysis"])
def analysis_status():
    return {"status": SESSION.status, "stage": SESSION.stage, "error": SESSION.error, "started_at": SESSION.started_at,
            "finished_at": SESSION.finished_at, "dataset_loaded": SESSION.result is not None}


@router.post("/analysis/run", response_model=AnalysisStatus, status_code=202, tags=["analysis"])
def analysis_run(req: RunRequest | None = None):
    req = req or RunRequest()
    SESSION.start_synthetic(req.seed, req.num_accounts, req.num_normal_transactions)
    return analysis_status()


@router.post("/analysis/upload", status_code=202, tags=["analysis"])
async def analysis_upload(file: UploadFile = File(...)):
    # Read at most limit+1 bytes: never buffers an unbounded body; file is never written to disk.
    from api.state import MAX_UPLOAD_BYTES
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    out = SESSION.ingest_csv(file.filename or "upload.csv", data)
    return {**out, "status": analysis_status()}


@router.get("/analysis/ingest", tags=["analysis"])
def last_ingest():
    i = SESSION.last_ingest
    if i is None:
        return {"available": False}
    return {"available": True, "name": i.name, "source": i.source, "accepted": i.accepted, "rejected": i.rejected,
            "ignored_columns": i.ignored_columns, "at": i.at,
            "reason_counts": clean(i.rejects["reasons"].explode().value_counts().to_dict()) if len(i.rejects) else {}}


@router.get("/analysis/rejects", tags=["analysis"])
def rejects(page: int = 1, page_size: int = 50):
    from fastapi import Query  # noqa: F401
    if page < 1 or not (1 <= page_size <= 200):
        raise ApiError(422, "VALIDATION_ERROR", "page must be >= 1 and page_size within 1..200.")
    i = SESSION.last_ingest
    if i is None:
        return {"items": [], "meta": {"page": 1, "page_size": page_size, "total": 0, "total_pages": 1}}
    part, meta = paginate(i.rejects, page, page_size)
    return {"items": clean(part.to_dict("records")), "meta": meta}


@router.get("/analysis/rejects.csv", tags=["analysis"])
def rejects_csv():
    i = SESSION.last_ingest
    if i is None:
        raise ApiError(404, "NO_REJECTS_REPORT", "No ingestion has been run yet.")
    df = i.rejects.copy()
    for c in ("reasons", "details"):
        df[c] = df[c].apply(lambda xs: " | ".join(xs) if isinstance(xs, list) else xs)
    return Response(df.to_csv(index=False), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="rejects_report.csv"'})


@router.get("/analysis/evaluation", tags=["analysis"])
def evaluation():
    require_data()
    if SESSION.evaluation is None:
        return {"available": False, "reason": "Evaluation needs synthetic scenario labels; uploaded data has none."}
    return {"available": True, **clean(SESSION.evaluation)}


@router.get("/analysis/config", tags=["analysis"])
def detection_config():
    d = SESSION.det
    return {"rules": [{"code": k, "description": v, "weight": d.rule_weights[k]} for k, v in RULE_DESCRIPTIONS.items()],
            "thresholds": {k: v for k, v in d.__dict__.items() if k != "rule_weights"},
            "score_disclaimer": SCORE_DISCLAIMER,
            "score_formula": "risk_score = rule_share x rule_score + (1 - rule_share) x model_score; "
                             "rule_score = 100 x (1 - prod(1 - w)) over matched rule codes; "
                             "model_score = Isolation Forest percentile within this dataset."}
