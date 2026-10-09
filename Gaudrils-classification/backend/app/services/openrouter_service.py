import json
import os
import re
import requests
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[3]
load_dotenv(BASE_DIR / ".env")

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
LLM_MAX_OUTPUT_TOKENS = 512
VERIFIED_FREE_LLM_MODEL_IDS = {
    "nvidia/nemotron-3.5-lightning:free",
}


def get_available_models() -> list:
    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is not configured.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }

    response = requests.get(
        OPENROUTER_MODELS_URL,
        headers=headers,
        params={
            "output_modalities": "text",
            "sort": "most-popular"
        },
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    models = []

    for model in data.get("data", []):
        models.append({
            "id": model.get("id"),
            "name": model.get("name"),
            "context_length": model.get("context_length"),
            "pricing": model.get("pricing"),
            "architecture": model.get("architecture"),
            "supported_parameters": model.get(
                "supported_parameters", []
            )
        })

    return models

def get_recommended_models() -> list:
    models = get_available_models()

    recommended = []

    for model in models:
        model_id = model.get("id", "").lower()
        model_name = model.get("name", "").lower()

        provider = None

        if "openai" in model_id or "openai" in model_name:
            provider = "OpenAI"

        elif "anthropic" in model_id or "claude" in model_name:
            provider = "Anthropic"

        elif "google" in model_id or "gemini" in model_name:
            provider = "Google"

        if provider:
            recommended.append({
                "id": model.get("id"),
                "name": model.get("name"),
                "provider": provider,
                "context_length": model.get("context_length"),
                "pricing": model.get("pricing")
            })

    return recommended

def classify_with_llm(
    guardrail: str,
    categories: dict,
    model: str,
    prompt: str
) -> dict:

    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is not configured.")

    categories_text = "\n".join(
        f"- {name}: {description}"
        for name, description in categories.items()
    )

    final_prompt = f"""
{prompt}

Guardrail:
{guardrail}

Available categories:
{categories_text}

"""
    if model in VERIFIED_FREE_LLM_MODEL_IDS:
        final_prompt += (
            "Return a JSON object with string fields category and reason. "
            "The category field must contain exactly one category name, "
            "not its description. Keep the reason to one concise sentence."
        )
    else:
        final_prompt += (
            "Return the best matching category and a concise reason in this format:\n"
            "Category: <exact category name>\n"
            "Reason: <one sentence explaining the classification>"
        )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": final_prompt
            }
        ],
        "temperature": 0,
        "max_tokens": LLM_MAX_OUTPUT_TOKENS,
    }
    if model in VERIFIED_FREE_LLM_MODEL_IDS:
        payload["response_format"] = {"type": "json_object"}
        payload["reasoning"] = {"effort": "none"}

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=60
    )

    if (
        response.status_code == 400
        and "temperature" in response.text.lower()
        and any(
            phrase in response.text.lower()
            for phrase in ("unsupported", "not supported", "does not support")
        )
    ):
        retry_payload = {
            key: value for key, value in payload.items() if key != "temperature"
        }
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=retry_payload,
            timeout=60
        )

    if not response.ok:
        raise ValueError(
            f"OpenRouter error {response.status_code}: "
            f"{response.text}"
        )

    data = response.json()

    answer = (
        data["choices"][0]["message"]["content"]
        .strip()
    )
    category = answer
    candidate = None
    reason = None

    if model in VERIFIED_FREE_LLM_MODEL_IDS:
        try:
            structured_answer = json.loads(answer)
        except json.JSONDecodeError:
            structured_answer = None
        if isinstance(structured_answer, dict):
            candidate = structured_answer.get("category")
            reason = structured_answer.get("reason")
    else:
        category_match = re.search(
            r"^\s*Category\s*:\s*(.+?)\s*$",
            answer,
            flags=re.IGNORECASE | re.MULTILINE,
        )
        if category_match:
            candidate = category_match.group(1).strip()
            reason_match = re.search(
                r"^\s*Reason\s*:\s*(.+?)\s*$",
                answer[category_match.end():],
                flags=re.IGNORECASE | re.MULTILINE,
            )
            if reason_match:
                reason = reason_match.group(1).strip()

    matching_category = None
    if isinstance(candidate, str):
        matching_category = next(
            (
                name for name in categories
                if name.casefold() == candidate.strip().casefold()
            ),
            None,
        )
        if matching_category is None:
            matching_category = next(
                (
                    name
                    for name in sorted(categories, key=len, reverse=True)
                    if candidate.strip().casefold().startswith(
                        f"{name}:".casefold()
                    )
                ),
                None,
            )

    if matching_category:
        category = matching_category
        answer = f"Category: {matching_category}"
        if isinstance(reason, str) and reason.strip():
            answer += f"\nReason: {reason.strip()}"

    usage = data.get("usage", {})

    return {
        "category": category,
        "answer": answer,
        "usage": usage
    }