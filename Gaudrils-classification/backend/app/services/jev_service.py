import os
import requests
from pathlib import Path
from dotenv import load_dotenv
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[3]
SETTINGS_FILE = BASE_DIR / "settings.txt"
load_dotenv(BASE_DIR / ".env")

JEV_API_URL = "https://api.typesafe.ai/v1/systemone"
JEV_MODEL = "jev-1.13.0"
MAX_JEV_BATCH_SIZE = 64


def get_jev_settings() -> dict[str, int]:
    if not SETTINGS_FILE.is_file():
        raise FileNotFoundError(
            f"JEV settings file not found: {SETTINGS_FILE}"
        )

    settings: dict[str, str] = {}
    for line_number, line in enumerate(
        SETTINGS_FILE.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            raise ValueError(
                f"Invalid JEV setting on line {line_number}; expected key=value."
            )
        key, value = (part.strip() for part in stripped.split("=", 1))
        settings[key.lower()] = value

    try:
        batch_size = int(settings.get("batch_size", ""))
    except ValueError as exc:
        raise ValueError(
            "JEV batch_size in settings.txt must be an integer from 1 to "
            f"{MAX_JEV_BATCH_SIZE}."
        ) from exc

    if not 1 <= batch_size <= MAX_JEV_BATCH_SIZE:
        raise ValueError(
            "JEV batch_size in settings.txt must be from 1 to "
            f"{MAX_JEV_BATCH_SIZE}."
        )

    return {"batch_size": batch_size}


def _authorization_headers() -> dict[str, str]:
    api_key = os.getenv("JEV_API_KEY")
    if not api_key:
        raise ValueError("JEV_API_KEY is not configured for the TypeSafe JEV API.")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def classify_guardrail(guardrail: str, categories: dict) -> dict:
    payload = {
        "model": JEV_MODEL,
        "state": guardrail,
        "questions": {
            "category": {
                "type": "choice",
                "instructions": (
                    "Which category best describes this guardrail? "
                    "Choose exactly one category based on the guardrail's meaning."
                ),
                "criteria": categories
            }
        }
    }

    response = requests.post(
        JEV_API_URL,
        headers=_authorization_headers(),
        json=payload,
        timeout=60
    )

    response.raise_for_status()

    data = response.json()

    answer = data["answers"]["category"]

    return {
        "category": answer.get("choice"),
        "confidence": answer.get("confidence"),
        "probabilities": answer.get("probabilities"),
        "usage": data.get("usage", {})
    }


def classify_guardrails_batch(
    guardrails: list[dict[str, str]],
    categories: dict[str, str],
    context: str,
) -> dict[str, Any]:
    if not guardrails:
        raise ValueError("A JEV batch must contain at least one guardrail.")

    questions = {
        item["question_id"]: {
            "type": "choice",
            "instructions": (
                "Which category best describes the guardrail in the state "
                f"whose question_id is {item['question_id']}? Choose exactly "
                "one category based on the guardrail's meaning."
            ),
            "criteria": categories,
        }
        for item in guardrails
    }
    payload = {
        "model": JEV_MODEL,
        "state": {
            "context": context,
            "guardrails": [
                {
                    "question_id": item["question_id"],
                    "guardrail_id": item["guardrail_id"],
                    "text": item["text"],
                }
                for item in guardrails
            ],
        },
        "questions": questions,
    }

    response = requests.post(
        JEV_API_URL,
        headers=_authorization_headers(),
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()

    return {
        "answers": data.get("answers", {}),
        "usage": data.get("usage", {}),
    }


def detect_metadata_batch(
    sources: list[dict[str, str]],
    options_by_field: dict[str, dict[str, str]],
) -> dict[str, Any]:
    if not sources:
        raise ValueError("JEV metadata detection requires at least one source.")

    field_instructions = {
        "brand": (
            "Choose the brand or product name explicitly supported by the "
            "provided material. Do not select an agency, person, or "
            "organization unless it is clearly the brand. If none is clear, "
            "choose 'No brand found'."
        ),
        "market": (
            "Choose the country or market explicitly supported by the "
            "provided material. If none is clear, choose 'No market found'."
        ),
        "asset_type": (
            "Choose the type of content or asset explicitly supported by the "
            "provided material. If none is clear, choose 'No asset type found'."
        ),
    }
    questions: dict[str, dict[str, Any]] = {}
    for field, options in options_by_field.items():
        if field not in field_instructions:
            raise ValueError(f"Unsupported JEV metadata field: {field}.")
        instructions = field_instructions[field]
        fallback = {
            "brand": "No brand found",
            "market": "No market found",
            "asset_type": "No asset type found",
        }[field]
        criteria = dict(options)
        criteria.setdefault(fallback, "No clear evidence for this field.")
        questions[field] = {
            "type": "choice",
            "instructions": instructions,
            "criteria": criteria,
        }

    if not questions:
        raise ValueError("JEV metadata batch requires at least one field.")
    payload = {
        "model": JEV_MODEL,
        "state": {"sources": sources},
        "questions": questions,
    }
    try:
        response = requests.post(
            JEV_API_URL,
            headers=_authorization_headers(),
            json=payload,
            timeout=(8, 25),
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        raise ValueError(f"JEV metadata batch request failed: {exc}") from exc
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError(f"JEV metadata batch response was invalid: {exc}") from exc

    answers = data.get("answers")
    if not isinstance(answers, dict):
        raise ValueError("JEV metadata batch response did not contain answers.")
    return {"answers": answers, "usage": data.get("usage", {})}