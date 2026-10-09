from typing import Any, Dict, List

from pydantic import BaseModel


class ClassificationRequest(BaseModel):
    guardrail: str
    categories: Dict[str, str]


class PreviewClassificationRequest(BaseModel):
    categories: Dict[str, str]
    limit: int = 5
    context: str = ""


class FullClassificationRequest(BaseModel):
    categories: Dict[str, str]
    limit: int = 0
    context: str = ""


class SingleLLMClassificationRequest(BaseModel):
    guardrail: str
    categories: Dict[str, str]
    model: str
    prompt: str


class LLMPreviewClassificationRequest(BaseModel):
    categories: Dict[str, str]
    model: str
    prompt: str
    limit: int = 5
    context: str = ""


class LLMFullClassificationRequest(BaseModel):
    categories: Dict[str, str]
    model: str
    prompt: str
    limit: int = 0
    context: str = ""


class CompareRequest(BaseModel):
    jev_results: List[Dict[str, Any]]
    llm_results: List[Dict[str, Any]]
    model: str = ""
