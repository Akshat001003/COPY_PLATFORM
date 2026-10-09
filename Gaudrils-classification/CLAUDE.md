# CLAUDE.md — Guardrails Classification / JEV vs Other LLM

## Project Purpose
Build a Guardrails Classification application where a user can:
1. Upload an arbitrary Excel workbook.
2. Dynamically define the number of categories.
3. Provide category names and descriptions.
4. Classify guardrails with JEV AI.
5. Classify the same guardrails with another selectable LLM.
6. Compare JEV vs the selected LLM.
7. Capture agreement, confidence, tokens, cost, and timing.
8. Eventually export results to Excel.
9. Provide a UI matching the team's requested workflow.

The current 513-row workbook is ONLY example/test data. Never hardcode 513.

## Intended UI
Two side-by-side engines:

LEFT — JEV:
- XLSX upload
- Number of categories
- Category heading/description inputs

RIGHT — Other LLM:
- Model dropdown
- Prompt textbox

BOTTOM:
- Comparison section

Models should eventually include OpenAI, Anthropic/Claude, Google/Gemini, and other models available through OpenRouter.

## Stack
- Python
- FastAPI
- Pydantic
- Requests
- Pandas
- OpenPyXL
- python-dotenv
- Uvicorn
- OpenRouter

Project:
```text
Gaudrils-classification/
├── .env
├── CLAUDE.md
├── RUNBOOK.md            # setup/run instructions for a fresh machine
├── backend/
│   ├── requirements.txt
│   ├── venv/             # not exported; recreate via requirements.txt
│   ├── uploads/          # uploaded workbooks, gitignored
│   ├── output/           # generated result/comparison Excel files, gitignored
│   └── app/
│       ├── __init__.py
│       ├── main.py
│       ├── api/
│       │   ├── __init__.py
│       │   └── routes.py
│       ├── services/
│       │   ├── __init__.py
│       │   ├── jev_service.py
│       │   ├── excel_service.py
│       │   ├── comparison_service.py
│       │   └── openrouter_service.py
│       └── models/
│           ├── __init__.py
│           └── schemas.py
├── frontend/             # React + Vite + TypeScript; node_modules not exported
│   └── src/
│       ├── App.tsx
│       ├── types.ts
│       ├── api/client.ts
│       └── components/
└── data/
```

Run backend from `backend` (see `RUNBOOK.md` for full first-time setup):
```powershell
cd backend
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

Run frontend from `frontend`:
```powershell
cd frontend
npm run dev
```

Swagger:
`http://127.0.0.1:8000/docs`

Frontend dev server:
`http://localhost:5173`

## Environment
`.env` contains:
```text
OPENROUTER_API_KEY=...
```
Never expose or request the secret.

## Excel
Example workbook:
`Jardiance_Guardrails_Relevance_1.xlsx`

Sheet:
`Guardrails`

Example columns:
```text
GuardrailId
ShortRule
FullMachineRule
GuardrailReason
category
subcategory
applicability
severity
useCases
topGuardrail
confidence
audience
channel
RELEVANCE
Staus
Comment
```

The example has 513 rows. This is not a product constraint.

Existing example categories included:
- Brand & Creative
- Promotional Messaging
- Clinical Evidence
- Product Information
- Safety & Risk

These are sample/reference categories only. User-supplied categories must be used dynamically.

## Current Excel functionality
`excel_service.py` provides:
- `inspect_excel()` — workbook/sheet/row/column inspection
- `get_guardrails()` — preview rows from `Guardrails`
- `save_jev_results()` — writes JEV classification fields to Excel

JEV Excel fields currently include:
```text
JEV_Category
JEV_Confidence
JEV_Probabilities
JEV_Input_Tokens
JEV_Output_Tokens
JEV_Cost
```

## Upload
`POST /api/upload`
- accepts XLSX
- saves file
- inspects workbook
- returns file ID
- returns dynamic total guardrail count

Current test file ID:
`e3b698a2-6b37-4f07-b57f-8ee4a3aea301`

Do not hardcode this ID.

## Guardrail Preview
`GET /api/guardrails/{file_id}`

Returns a small preview.

## Dynamic Categories
Categories are NOT hardcoded.

Example:
```json
{
  "promotional_compliance": "Promotional claims, approved claims, comparative claims, and promotional requirements.",
  "product_information": "Indications, dosage, administration, contraindications, label information, and product information.",
  "safety_risk": "Warnings, precautions, adverse events, safety information, and risk communication."
}
```

## JEV
File:
`backend/app/services/jev_service.py`

OpenRouter Decisions API:
`https://openrouter.ai/api/alpha/decisions`

Model:
`typesafe/jev-1.13`

JEV receives:
- guardrail text
- category names
- category descriptions

It returns:
- selected category
- confidence
- probabilities
- usage/cost where available

### JEV preview
`POST /api/classify/{file_id}/preview`

Preview limit must stay 1–50. This is only a test/preview limit, NOT a workbook-size limit.

### JEV full run
`POST /api/classify/{file_id}/run`

Reads all rows dynamically, classifies with JEV, tracks:
- processed
- failed
- batch size
- processing time
- input/output/total tokens
- cost
- results
- failures

Current implementation is sequential and can be slow for hundreds of rows. Do not redesign the product because of this; optimize later if requested.

## JEV test result
JEV was successfully tested on 5 rows:
```text
GR-002 → promotional_compliance → 0.70
GR-003 → promotional_compliance → 0.94
GR-012 → product_information → 0.36
GR-014 → product_information → 0.89
GR-015 → promotional_compliance → 0.69
```

## Other LLM
Use OpenRouter for other LLMs too.

Model discovery:
`GET /api/models`

Recommended models:
`GET /api/models/recommended`

The tested model was:
`openai/gpt-6-luna`
Display name:
`OpenAI: GPT-6 Luna`

Do not hardcode only this model.

Other LLM API:
`https://openrouter.ai/api/v1/chat/completions`

Classification uses:
- same guardrail
- same category choices/descriptions
- user-provided prompt
- selected model
- temperature 0

## Important Pydantic model separation
Implemented in `backend/app/models/schemas.py`. Use TWO request models:

```python
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
```

Do not require `guardrail` for preview because preview reads guardrails from Excel.

## Other LLM Preview
`POST /api/classify/{file_id}/llm-preview`

Successfully tested with:
- model: `openai/gpt-6-luna`
- 5 rows

Results:
```text
GR-002 → promotional_compliance
GR-003 → promotional_compliance
GR-012 → product_information
GR-014 → product_information
GR-015 → promotional_compliance
```

OpenRouter returns:
- prompt_tokens
- completion_tokens
- total_tokens
- cost
- reasoning tokens

Example test costs ranged roughly from 0.0000462 to 0.0000696 per row. These are test values only.

## Current Comparison — IMPLEMENTED
File:
`backend/app/services/comparison_service.py`

Function:
`compare_classifications(jev_results, llm_results)`

It matches by `GuardrailId` and compares:
- JEV category
- LLM category
- agreement
- JEV confidence
- JEV tokens/cost
- LLM tokens/cost

JEV usage keys (`input_tokens`/`output_tokens`/`cost`) and raw OpenRouter LLM
usage keys (`prompt_tokens`/`completion_tokens`/`cost`) are normalized inside
this function so callers never see inconsistent field names.

Overall metrics:
```text
total_compared
agreements
disagreements
agreement_percentage
comparisons
```

Endpoint:
`POST /api/compare/{file_id}`

Request body `CompareRequest(jev_results, llm_results, model)` — stateless;
the client submits the two result arrays it already holds (from the preview
calls) rather than the backend persisting per-session state. Also writes a
combined Excel export via `save_comparison_results()` in `excel_service.py`
and returns its path. Download via:
`GET /api/export/{file_id}`

Verified with synthetic data (live OpenRouter calls are blocked on the
original dev network by a corporate TLS-inspecting proxy — see `RUNBOOK.md`
Troubleshooting section): 2/3 agreement computed correctly, token/cost fields
normalized correctly across both engines' usage shapes.

IMPORTANT: agreement is NOT model accuracy. Agreement between two models is not automatically ground truth.

## Excel Output — BASIC VERSION IMPLEMENTED
`save_comparison_results()` in `excel_service.py` writes, per uploaded file,
`backend/output/{file_id}_comparison.xlsx` (sheet `Comparison Results`) with:
```text
JEV_Category
JEV_Confidence
LLM_Model
LLM_Category
Agreement
```

Future Excel Output (not yet implemented, still future work — do not build
unless asked):
```text
JEV_Subcategory
JEV_Subcategory_Confidence
JEV_Category_Probabilities
JEV_Subcategory_Probabilities
JEV_Review_Required
JEV_Input_Tokens
JEV_Output_Tokens
JEV_Total_Tokens
JEV_Cost

LLM_Subcategory
LLM_Input_Tokens
LLM_Output_Tokens
LLM_Total_Tokens
LLM_Cost

Category_Match
Subcategory_Match
```

Implement incrementally.

## Future Taxonomy
A proposed healthcare/pharma taxonomy discussed was:
1. Brand & Visual Identity
2. Creative & Layout
3. Content & Messaging
4. Promotional Compliance
5. Clinical & Scientific Evidence
6. Product Information
7. Safety & Risk
8. Regulatory & MLR Compliance
9. Data, Confidentiality & Security
10. AI & Content Governance
11. Other / Requires Review

This is a proposed future structure only. Do not replace user-defined categories automatically.

Potential future subcategories include logo usage, typography, imagery, tone/voice, promotional claims, clinical evidence, indications, dosage, warnings, regulatory/MLR requirements, data protection, hallucination prevention, source accuracy, human review, etc.

Recommended future approach:
1. JEV selects top-level category.
2. A second JEV decision selects a subcategory within that category.
3. Give the second decision only relevant subcategories plus the original guardrail and selected category.

## Fair Comparison Principle
Both engines must receive:
- the same guardrail
- the same category choices
- the same category descriptions

Only the decision engine should differ.

The Other LLM additionally receives the user's prompt.

An optional `context` string (UI field: "Context / state", JEV panel only) is
supported on `PreviewClassificationRequest`, the full-run request, and
`LLMPreviewClassificationRequest`. When set, it's prepended to each
guardrail's text before classification for **both** engines, preserving this
principle rather than giving JEV extra information the Other LLM doesn't get.

## Existing Excel Classification
The source Excel may contain `category` and `subcategory`.

Future comparison may be:
`Existing vs JEV vs Other LLM`

Do not automatically treat existing classifications as perfect ground truth.

## Development Rules
1. Work one step at a time.
2. Do not redesign scope without being asked.
3. Never hardcode 513, Jardiance, or specific Guardrail IDs.
4. Preserve working endpoints when changing models/schemas.
5. Use OpenRouter for Other LLM unless specifically requested otherwise.
6. Never expose API secrets.
7. Keep classification deterministic where possible.
8. Preview limits are not dataset limits.
9. Do not claim model accuracy from model-to-model agreement alone.
10. Prefer simple, modular implementation over unnecessary complexity.
11. Test each backend step before moving to the frontend.
12. When the user asks for the next step, provide only the next step unless they explicitly ask for the full implementation.

## Status

Completed:
- FastAPI/backend setup
- Virtual environment + `backend/requirements.txt` (pinned, for reproducible setup on a new machine)
- environment configuration
- Excel upload
- dynamic workbook inspection
- dynamic row count
- guardrail preview
- dynamic categories
- optional shared "Context / state" field (prepended to both engines' input)
- JEV via OpenRouter
- JEV preview
- JEV full-run endpoint
- JEV Excel saving
- OpenRouter model discovery
- recommended model discovery (with an offline fallback model list in the UI if the live fetch fails)
- Other LLM classification
- Other LLM preview
- OpenAI model test through OpenRouter
- Pydantic model separation (`SingleLLMClassificationRequest` / `LLMPreviewClassificationRequest`) moved into `backend/app/models/schemas.py`; fixed a bug where `/api/classify/llm` referenced a `guardrail` field its request model didn't declare
- comparison service implemented (`compare_classifications`)
- `POST /api/compare/{file_id}` endpoint
- basic comparison Excel output + `GET /api/export/{file_id}` download endpoint
- CORS enabled for the Vite dev origin
- frontend (React + Vite + TypeScript): shared upload, dynamic category UI ("Choice values" grid of name+description cells), JEV panel, Other LLM panel with model dropdown + prompt, comparison dashboard with response-time/token/cost meters, Excel download link
- UI restyled to match the team-provided mockup (layout, colors, field labels, monospace input styling)
- `RUNBOOK.md` — setup/run instructions for a fresh machine (this folder is exported without `venv/`/`node_modules/`)

Known environment limitation (not a code bug):
- The original dev network blocks `openrouter.ai` via a corporate TLS-inspecting proxy (confirmed via the proxy's own HTML block page, not an OpenRouter error). Compare/export logic was verified with synthetic data shaped like real preview responses instead. Confirm `openrouter.ai` is reachable on whatever network actually runs this before relying on live JEV/LLM classification.

In progress / not yet started:
- live end-to-end verification of JEV + Other LLM classification through the UI (blocked on this network only — see above)
- subcategory taxonomy (second-pass JEV decision)
- richer Excel export columns (see "Future Excel Output")
- `Existing vs JEV vs Other LLM` three-way comparison

## Engineering Intent
This is an internal POC being developed toward a usable application.

Priorities:
1. Correctness
2. Clear separation of JEV and Other LLM
3. Dynamic inputs
4. Reproducible classification
5. Transparent cost/token metrics
6. Simple comparison
7. UI matching the requested design
8. Extensibility for subcategories and additional dimensions later

Keep the implementation focused on the requested workflow.
