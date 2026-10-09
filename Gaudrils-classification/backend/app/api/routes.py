import os
import uuid
import pandas as pd
import time
import threading
from typing import Any
from fastapi import APIRouter, BackgroundTasks, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool
from app.services.openrouter_service import (
    get_available_models,
    get_recommended_models,
    classify_with_llm
)
from app.services.jev_service import (
    classify_guardrail,
    classify_guardrails_batch,
    get_jev_settings,
)
from app.services.excel_service import (
    inspect_excel,
    get_guardrails,
    save_jev_results,
    save_comparison_results
)
from app.services.comparison_service import compare_classifications
from app.services.copy_creation_service import (
    MAX_EXTRACTED_CHARACTERS,
    MAX_FILE_BYTES,
    MAX_FILE_COUNT,
    detect_copy_metadata,
    extract_document_text,
)
from app.models.schemas import (
    ClassificationRequest,
    FullClassificationRequest,
    PreviewClassificationRequest,
    SingleLLMClassificationRequest,
    LLMFullClassificationRequest,
    LLMPreviewClassificationRequest,
    CompareRequest
)

router = APIRouter(
    prefix="/api",
    tags=["Excel"]
)


UPLOAD_DIR = "uploads"
OUTPUT_DIR = "output"
_jev_jobs: dict[str, dict[str, Any]] = {}
_jev_jobs_lock = threading.Lock()
_llm_jobs: dict[str, dict[str, Any]] = {}
_llm_jobs_lock = threading.Lock()

os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/copy-creation/detect")
async def detect_copy_creation_metadata(
    project_description: str = Form(""),
    actual_material_description: str = Form(""),
    reference_description: str = Form(""),
    project_files: list[UploadFile] = File(default=[]),
    actual_material_files: list[UploadFile] = File(default=[]),
    reference_files: list[UploadFile] = File(default=[]),
):
    uploads = [
        ("Project Brief", project_description, project_files),
        ("Actual Material", actual_material_description, actual_material_files),
        ("Reference Material", reference_description, reference_files),
    ]
    file_count = sum(len(files) for _, _, files in uploads)
    if file_count > MAX_FILE_COUNT:
        raise HTTPException(
            status_code=413,
            detail=f"Upload no more than {MAX_FILE_COUNT} documents in total.",
        )

    sources: list[dict[str, str]] = []
    for section, description, files in uploads:
        if description.strip():
            sources.append({
                "label": f"{section} description",
                "text": description.strip(),
            })
        for uploaded_file in files:
            filename = uploaded_file.filename or "unnamed file"
            extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            if extension not in {"pdf", "docx", "xlsx"}:
                raise HTTPException(
                    status_code=400,
                    detail=f"{filename}: only PDF, DOCX, and XLSX are supported.",
                )
            if extension == "xlsx":
                file_size = uploaded_file.size
                if file_size is None:
                    contents = await uploaded_file.read(MAX_FILE_BYTES + 1)
                    file_size = len(contents)
                if file_size > MAX_FILE_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"{filename} exceeds the 10 MB per-file limit.",
                    )
                sources.append({
                    "label": f"{section} / {filename}",
                    "text": f"Spreadsheet filename: {filename}",
                })
                continue

            contents = await uploaded_file.read(MAX_FILE_BYTES + 1)
            if len(contents) > MAX_FILE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"{filename} exceeds the 10 MB per-file limit.",
                )
            try:
                text = await run_in_threadpool(
                    extract_document_text,
                    filename,
                    contents,
                )
                if not text:
                    raise ValueError(
                        "No readable text was found. Scanned image-only PDFs "
                        "are not supported."
                    )
            except Exception as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"Could not read {filename}: {exc}",
                ) from exc
            if text:
                sources.append({
                    "label": f"{section} / {filename}",
                    "text": text,
                })

    for section, description, files in uploads[:2]:
        if not description.strip() and not files:
            raise HTTPException(
                status_code=400,
                detail=f"Add a description or at least one document for {section}.",
            )

    extracted_size = sum(len(source["text"]) for source in sources)
    if extracted_size > MAX_EXTRACTED_CHARACTERS:
        raise HTTPException(
            status_code=413,
            detail=(
                "The combined extracted content exceeds 40,000 characters. "
                "Remove documents or shorten descriptions before analyzing."
            ),
        )

    if not sources:
        raise HTTPException(
            status_code=400,
            detail="Add project brief and actual material content before analyzing.",
        )

    try:
        return await run_in_threadpool(detect_copy_metadata, sources)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _update_jev_job(job_id: str, **updates: Any) -> None:
    with _jev_jobs_lock:
        _jev_jobs[job_id].update(updates)


def _usage_count(usage: dict[str, Any], key: str) -> int:
    return int(usage.get(key, 0) or 0)


def _guardrail_text(row: dict[str, Any]) -> str:
    value = row.get("ShortRule", "")
    if pd.isna(value):
        return ""
    return str(value).strip()


def _run_full_jev_job(
    job_id: str,
    file_path: str,
    categories: dict[str, str],
    context: str,
    mode: str,
    batch_size: int,
    row_limit: int,
) -> None:
    started_at = time.time()
    try:
        df = pd.read_excel(file_path, sheet_name="Guardrails")
        dataset_rows = len(df)
        rows = df.to_dict(orient="records")
        if row_limit:
            rows = rows[:row_limit]
        total_rows = len(rows)
        _update_jev_job(job_id, total_rows=total_rows, status="running")
        results: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        completed = 0

        if mode == "normal":
            for row in rows:
                guardrail_text = _guardrail_text(row)
                if not guardrail_text:
                    completed += 1
                    _update_jev_job(job_id, completed=completed)
                    continue

                try:
                    classify_text = (
                        f"{context}\n\n{guardrail_text}" if context else guardrail_text
                    )
                    result = classify_guardrail(classify_text, categories)
                    results.append({
                        "GuardrailId": row.get("GuardrailId"),
                        "ShortRule": guardrail_text,
                        "JEV_Category": result["category"],
                        "JEV_Confidence": result["confidence"],
                        "JEV_Probabilities": result["probabilities"],
                        "JEV_Usage": result["usage"],
                    })
                except Exception as exc:
                    failures.append({
                        "GuardrailId": row.get("GuardrailId"),
                        "ShortRule": guardrail_text,
                        "error": str(exc),
                    })
                completed += 1
                _update_jev_job(
                    job_id,
                    completed=completed,
                    processed=len(results),
                    failed=len(failures),
                )
        else:
            nonempty_rows = [
                row for row in rows
                if _guardrail_text(row)
            ]
            empty_rows = total_rows - len(nonempty_rows)
            completed = empty_rows
            _update_jev_job(job_id, completed=completed)

            for start in range(0, len(nonempty_rows), batch_size):
                batch_rows = nonempty_rows[start:start + batch_size]
                questions = [
                    {
                        "question_id": f"guardrail_{start + offset}",
                        "guardrail_id": str(row.get("GuardrailId", "")),
                        "text": _guardrail_text(row),
                        "row": row,
                    }
                    for offset, row in enumerate(batch_rows)
                ]
                try:
                    batch_result = classify_guardrails_batch(
                        [
                            {
                                "question_id": item["question_id"],
                                "guardrail_id": item["guardrail_id"],
                                "text": item["text"],
                            }
                            for item in questions
                        ],
                        categories,
                        context,
                    )
                except Exception as exc:
                    failures.extend(
                        {
                            "GuardrailId": item["row"].get("GuardrailId"),
                            "ShortRule": item["text"],
                            "error": str(exc),
                        }
                        for item in questions
                    )
                    completed += len(questions)
                    _update_jev_job(
                        job_id,
                        completed=completed,
                        processed=len(results),
                        failed=len(failures),
                    )
                    continue

                answers = batch_result["answers"] or {}
                usage = batch_result["usage"] or {}
                successful_items = [
                    (item, answers.get(item["question_id"]))
                    for item in questions
                ]
                valid_answers = [
                    (item, answer)
                    for item, answer in successful_items
                    if isinstance(answer, dict)
                ]
                if valid_answers:
                    input_tokens = _usage_count(usage, "input_tokens")
                    output_tokens = _usage_count(usage, "output_tokens")
                    try:
                        total_cost = float(usage.get("cost", 0) or 0)
                    except (TypeError, ValueError):
                        total_cost = 0.0
                    input_share, input_remainder = divmod(
                        input_tokens, len(valid_answers)
                    )
                    output_share, output_remainder = divmod(
                        output_tokens, len(valid_answers)
                    )
                    cost_share = total_cost / len(valid_answers)

                    for index, (item, answer) in enumerate(valid_answers):
                        category_answer = answer
                        results.append({
                            "GuardrailId": item["row"].get("GuardrailId"),
                            "ShortRule": item["text"],
                            "JEV_Category": category_answer.get("choice"),
                            "JEV_Confidence": category_answer.get("confidence"),
                            "JEV_Probabilities": category_answer.get("probabilities"),
                            "JEV_Usage": {
                                "input_tokens": input_share + (index < input_remainder),
                                "output_tokens": output_share + (index < output_remainder),
                                "cost": cost_share,
                                "allocation": "evenly allocated batch usage",
                            },
                        })

                for item, answer in successful_items:
                    if not isinstance(answer, dict):
                        failures.append({
                            "GuardrailId": item["row"].get("GuardrailId"),
                            "ShortRule": item["text"],
                            "error": (
                                "The JEV batch response did not include an answer "
                                f"for {item['question_id']}."
                            ),
                        })

                completed += len(questions)
                _update_jev_job(
                    job_id,
                    completed=completed,
                    processed=len(results),
                    failed=len(failures),
                )

        usage_totals = {
            "input_tokens": sum(
                _usage_count(item.get("JEV_Usage", {}), "input_tokens")
                for item in results
            ),
            "output_tokens": sum(
                _usage_count(item.get("JEV_Usage", {}), "output_tokens")
                for item in results
            ),
            "cost": sum(
                float(item.get("JEV_Usage", {}).get("cost", 0) or 0)
                for item in results
            ),
        }
        output_path = save_jev_results(file_path=file_path, results=results)
        _update_jev_job(
            job_id,
            status="done",
            total_rows=total_rows,
            dataset_rows=dataset_rows,
            completed=completed,
            processed=len(results),
            failed=len(failures),
            failures=failures,
            results=results,
            usage=usage_totals,
            processing_time_seconds=round(time.time() - started_at, 2),
            output_file=output_path,
            usage_note=(
                "Batch usage is reported as an even per-row allocation; "
                "the provider returns usage for the whole batch, not each question."
                if mode == "batch"
                else None
            ),
        )
    except Exception as exc:
        _update_jev_job(
            job_id,
            status="error",
            error=f"Full classification failed: {exc}",
            processing_time_seconds=round(time.time() - started_at, 2),
        )


def _update_llm_job(job_id: str, **updates: Any) -> None:
    with _llm_jobs_lock:
        _llm_jobs[job_id].update(updates)


def _run_full_llm_job(
    job_id: str,
    file_path: str,
    categories: dict[str, str],
    model: str,
    prompt: str,
    context: str,
    row_limit: int,
) -> None:
    started_at = time.time()
    try:
        df = pd.read_excel(file_path, sheet_name="Guardrails")
        rows = df.to_dict(orient="records")
        if row_limit:
            rows = rows[:row_limit]
        total_rows = len(rows)
        dataset_rows = len(df)
        _update_llm_job(
            job_id,
            status="running",
            total_rows=total_rows,
            dataset_rows=dataset_rows,
        )

        results: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        for completed, row in enumerate(rows, start=1):
            guardrail_text = _guardrail_text(row)
            if guardrail_text:
                classify_text = (
                    f"{context}\n\n{guardrail_text}" if context else guardrail_text
                )
                try:
                    result = classify_with_llm(
                        guardrail=classify_text,
                        categories=categories,
                        model=model,
                        prompt=prompt,
                    )
                    results.append({
                        "GuardrailId": row.get("GuardrailId"),
                        "ShortRule": guardrail_text,
                        "LLM_Category": result["category"],
                        "LLM_Answer": result.get("answer", result["category"]),
                        "LLM_Usage": result["usage"],
                    })
                except Exception as exc:
                    failures.append({
                        "GuardrailId": row.get("GuardrailId"),
                        "ShortRule": guardrail_text,
                        "error": str(exc)[:1000],
                    })

            _update_llm_job(
                job_id,
                completed=completed,
                processed=len(results),
                failed=len(failures),
            )

        usage = {
            "input_tokens": sum(
                int(item.get("LLM_Usage", {}).get("prompt_tokens", 0) or 0)
                for item in results
            ),
            "output_tokens": sum(
                int(item.get("LLM_Usage", {}).get("completion_tokens", 0) or 0)
                for item in results
            ),
            "cost": sum(
                float(item.get("LLM_Usage", {}).get("cost", 0) or 0)
                for item in results
            ),
        }
        _update_llm_job(
            job_id,
            status="done",
            total_rows=total_rows,
            dataset_rows=dataset_rows,
            completed=total_rows,
            processed=len(results),
            failed=len(failures),
            failures=failures,
            results=results,
            usage=usage,
            processing_time_seconds=round(time.time() - started_at, 2),
        )
    except Exception as exc:
        _update_llm_job(
            job_id,
            status="error",
            error=f"LLM classification failed: {exc}",
            processing_time_seconds=round(time.time() - started_at, 2),
        )

@router.post("/upload")
async def upload_excel(file: UploadFile = File(...)):

    # Validate file type
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=400,
            detail="Only Excel files (.xlsx, .xls) are supported."
        )

    # Create unique filename
    file_id = str(uuid.uuid4())
    extension = os.path.splitext(file.filename)[1]

    saved_filename = f"{file_id}{extension}"
    file_path = os.path.join(
        UPLOAD_DIR,
        saved_filename
    )

    # Save uploaded file
    contents = await file.read()

    with open(file_path, "wb") as f:
        f.write(contents)

    # Inspect workbook
    try:
        result = inspect_excel(file_path)

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Could not read Excel file: {str(e)}"
        )

    return {
    "success": True,
    "file_id": file_id,
    "original_filename": file.filename,
    "file_path": file_path,
    "workbook": result,
    "total_guardrails": result["sheets"]["Guardrails"]["rows"]
}


@router.get("/guardrails/{file_id}")
async def read_guardrails(file_id: str):
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}.xlsx")

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found.")

    try:
        guardrails = get_guardrails(file_path, limit=5)

        return {
            "success": True,
            "file_id": file_id,
            "count": len(guardrails),
            "guardrails": guardrails
        }

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Could not read guardrails: {str(e)}"
        )


@router.post("/classify/test")
async def test_classification():
    categories = {
        "brand_visual_identity": (
            "Logo usage, typography, colors, visual identity, "
            "or other brand identity requirements."
        ),
        "creative_layout": (
            "Imagery, layout, composition, spacing, visual hierarchy, "
            "or creative design requirements."
        ),
        "content_messaging": (
            "Tone, voice, wording, language, copy, messaging, "
            "or communication style."
        ),
        "promotional_compliance": (
            "Promotional claims, approved claims, comparative claims, "
            "benefit claims, or promotional requirements."
        ),
        "clinical_scientific": (
            "Clinical evidence, efficacy, endpoints, studies, "
            "statistics, or scientific claims."
        ),
        "product_information": (
            "Indications, dosage, administration, contraindications, "
            "label information, or product information."
        ),
        "safety_risk": (
            "Warnings, precautions, adverse events, safety information, "
            "risk communication, or patient safety."
        ),
        "regulatory_compliance": (
            "Regulatory, legal, MLR, approval, or market-specific "
            "compliance requirements."
        ),
        "data_security": (
            "Confidential information, privacy, data protection, "
            "information security, or access restrictions."
        ),
        "ai_content_governance": (
            "AI hallucination prevention, source accuracy, unsupported "
            "claims, human review, or AI output validation."
        ),
        "other": (
            "Does not clearly belong to any of the categories above."
        )
    }

    test_guardrail = (
        "Do not disclose personally identifiable patient information."
    )

    result = classify_guardrail(test_guardrail, categories)

    return {
        "guardrail": test_guardrail,
        "result": result
    }


@router.post("/classify")
async def classify(request: ClassificationRequest):
    try:
        result = classify_guardrail(
            guardrail=request.guardrail,
            categories=request.categories
        )

        return {
            "success": True,
            "guardrail": request.guardrail,
            "result": result
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"JEV classification failed: {str(e)}"
        )


@router.post("/classify/{file_id}/preview")
async def classify_preview(
    file_id: str,
    request: PreviewClassificationRequest
):
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}.xlsx")

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found.")

    if not request.categories:
        raise HTTPException(
            status_code=400,
            detail="At least one category is required."
        )

    if request.limit < 1 or request.limit > 50:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 50."
        )

    try:
        guardrails = get_guardrails(
            file_path,
            limit=request.limit
        )

        results = []

        for row in guardrails:
            guardrail_text = row.get("ShortRule", "")
            classify_text = (
                f"{request.context}\n\n{guardrail_text}"
                if request.context
                else guardrail_text
            )

            result = classify_guardrail(
                guardrail=classify_text,
                categories=request.categories
            )

            results.append({
                "GuardrailId": row.get("GuardrailId"),
                "ShortRule": guardrail_text,
                "JEV_Category": result["category"],
                "JEV_Confidence": result["confidence"],
                "JEV_Probabilities": result["probabilities"],
                "JEV_Usage": result["usage"]
            })

        return {
            "success": True,
            "file_id": file_id,
            "processed": len(results),
            "categories": request.categories,
            "results": results
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Classification failed: {str(e)}"
        )        

@router.post("/classify/{file_id}/run")
async def classify_all(
    file_id: str,
    request: FullClassificationRequest,
    background_tasks: BackgroundTasks,
):
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}.xlsx")

    if not os.path.isfile(file_path):
        raise HTTPException(
            status_code=404,
            detail="File not found."
        )

    if not request.categories:
        raise HTTPException(
            status_code=400,
            detail="At least one category is required."
        )

    if request.limit < 0:
        raise HTTPException(
            status_code=400,
            detail="Limit must be zero (all rows) or a positive row count.",
        )

    try:
        settings = get_jev_settings()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Invalid JEV settings: {exc}",
        ) from exc

    mode = request.mode or settings["mode"]
    job_id = str(uuid.uuid4())
    job = {
        "success": True,
        "job_id": job_id,
        "file_id": file_id,
        "status": "queued",
        "mode": mode,
        "batch_size": settings["batch_size"],
        "total_rows": None,
        "completed": 0,
        "processed": 0,
        "failed": 0,
    }
    with _jev_jobs_lock:
        for existing_id, existing_job in list(_jev_jobs.items()):
            if (
                existing_job.get("file_id") == file_id
                and existing_job.get("status") in {"queued", "running"}
            ):
                raise HTTPException(
                    status_code=409,
                    detail="A full JEV run is already active for this workbook.",
                )
            if (
                existing_job.get("file_id") == file_id
                and existing_job.get("status") in {"done", "error"}
            ):
                del _jev_jobs[existing_id]
        _jev_jobs[job_id] = job

    background_tasks.add_task(
        _run_full_jev_job,
        job_id,
        file_path,
        request.categories,
        request.context,
        mode,
        settings["batch_size"],
        request.limit,
    )
    return job


@router.get("/classify/{file_id}/run/{job_id}")
async def get_jev_run_status(file_id: str, job_id: str):
    with _jev_jobs_lock:
        job = _jev_jobs.get(job_id)
        if job is None or job.get("file_id") != file_id:
            raise HTTPException(status_code=404, detail="JEV run not found.")
        response = dict(job)

    if response.get("status") == "error":
        response["success"] = False
    return response


@router.get("/models")
async def available_models():
    try:
        models = get_available_models()

        return {
            "success": True,
            "count": len(models),
            "models": models
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Could not retrieve OpenRouter models: {str(e)}"
        )


@router.get("/models/recommended")
async def recommended_models():
    try:
        models = get_recommended_models()

        return {
            "success": True,
            "count": len(models),
            "models": models
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Could not retrieve recommended models: {str(e)}"
        )


@router.post("/classify/llm")
async def classify_llm(request: SingleLLMClassificationRequest):
    try:
        result = classify_with_llm(
            guardrail=request.guardrail,
            categories=request.categories,
            model=request.model,
            prompt=request.prompt
        )

        return {
            "success": True,
            "guardrail": request.guardrail,
            "model": request.model,
            "result": result
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"LLM classification failed: {str(e)}"
        )


@router.post("/classify/{file_id}/llm-preview")
async def classify_llm_preview(
    file_id: str,
    request: LLMPreviewClassificationRequest
):
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}.xlsx")

    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=404,
            detail="File not found."
        )

    if not request.categories:
        raise HTTPException(
            status_code=400,
            detail="At least one category is required."
        )

    if request.limit < 1 or request.limit > 50:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 50."
        )

    try:
        guardrails = get_guardrails(
            file_path,
            limit=request.limit
        )
        results = []

        for row in guardrails:
            guardrail_text = str(
                row.get("ShortRule", "")
            ).strip()

            if not guardrail_text:
                continue

            classify_text = (
                f"{request.context}\n\n{guardrail_text}"
                if request.context
                else guardrail_text
            )

            result = classify_with_llm(
                guardrail=classify_text,
                categories=request.categories,
                model=request.model,
                prompt=request.prompt
            )
            results.append({
                "GuardrailId": row.get("GuardrailId"),
                "ShortRule": guardrail_text,
                "LLM_Category": result["category"],
                "LLM_Answer": result.get("answer", result["category"]),
                "LLM_Usage": result["usage"]
            })

        return {
            "success": True,
            "file_id": file_id,
            "model": request.model,
            "processed": len(results),
            "results": results
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"LLM classification failed: {str(e)}"
        )


@router.post("/classify/{file_id}/llm-run")
async def classify_llm_all(
    file_id: str,
    request: LLMFullClassificationRequest,
    background_tasks: BackgroundTasks,
):
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}.xlsx")
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found.")
    if not request.categories:
        raise HTTPException(
            status_code=400,
            detail="At least one category is required.",
        )
    if not request.model.strip():
        raise HTTPException(status_code=400, detail="A model is required.")
    if request.limit < 0:
        raise HTTPException(
            status_code=400,
            detail="Limit must be zero (all rows) or a positive row count.",
        )

    job_id = str(uuid.uuid4())
    with _llm_jobs_lock:
        for existing_id, existing_job in list(_llm_jobs.items()):
            if (
                existing_job.get("file_id") == file_id
                and existing_job.get("status") in {"queued", "running"}
            ):
                raise HTTPException(
                    status_code=409,
                    detail="An LLM run is already active for this workbook.",
                )
            if (
                existing_job.get("file_id") == file_id
                and existing_job.get("status") in {"done", "error"}
            ):
                del _llm_jobs[existing_id]

        _llm_jobs[job_id] = {
            "success": True,
            "job_id": job_id,
            "file_id": file_id,
            "status": "queued",
            "total_rows": None,
            "completed": 0,
            "processed": 0,
            "failed": 0,
        }

    background_tasks.add_task(
        _run_full_llm_job,
        job_id,
        file_path,
        request.categories,
        request.model,
        request.prompt,
        request.context,
        request.limit,
    )
    return dict(_llm_jobs[job_id])


@router.get("/classify/{file_id}/llm-run/{job_id}")
async def get_llm_run_status(file_id: str, job_id: str):
    with _llm_jobs_lock:
        job = _llm_jobs.get(job_id)
        if job is None or job.get("file_id") != file_id:
            raise HTTPException(status_code=404, detail="LLM run not found.")
        response = dict(job)

    if response.get("status") == "error":
        response["success"] = False
    return response


@router.post("/compare/{file_id}")
async def compare(file_id: str, request: CompareRequest):
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}.xlsx")

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found.")

    try:
        comparison = compare_classifications(
            jev_results=request.jev_results,
            llm_results=request.llm_results
        )

        output_path = save_comparison_results(
            file_path=file_path,
            comparison_result=comparison,
            model=request.model,
            output_dir=OUTPUT_DIR,
            file_id=file_id
        )

        return {
            "success": True,
            "file_id": file_id,
            **comparison,
            "output_file": output_path
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Comparison failed: {str(e)}"
        )


@router.get("/export/{file_id}")
async def export_comparison(file_id: str):
    output_path = os.path.join(OUTPUT_DIR, f"{file_id}_comparison.xlsx")

    if not os.path.exists(output_path):
        raise HTTPException(
            status_code=404,
            detail="No comparison export found for this file. Run /api/compare first."
        )

    return FileResponse(
        output_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"{file_id}_comparison.xlsx"
    )