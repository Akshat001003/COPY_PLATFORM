# Running this project on a new machine

This folder was exported without `backend/venv/` and `frontend/node_modules/`
(both are regenerated from the files below) to keep the transfer small. Follow
these steps on the new device.

## Prerequisites

- **Python 3.12+** — https://python.org
- **Node.js 20+** (ships with npm) — https://nodejs.org
- An **OpenRouter API key** for the Decisions API (`typesafe/jev-1.13`),
  chat completions, and the General LLM model list
- Network access to `openrouter.ai`. If you're on a corporate network with TLS
  inspection (Zscaler, Netskope, etc.) and see
  `SSLCertVerificationError: unable to get local issuer certificate`, see
  **Troubleshooting** below — this is a network/cert issue, not a bug in the app.

## 1. Environment file

Create a `.env` file at the **repo root** (same folder as this file):

```
OPENROUTER_API_KEY=sk-or-v1-...
```

## 2. Backend setup

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Verify: open http://127.0.0.1:8000/health — should return `{"status":"healthy"}`.
Swagger UI is at http://127.0.0.1:8000/docs.

Leave this terminal running.

## 3. Frontend setup

In a **second terminal**:

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 in a browser. The frontend expects the backend at
`http://localhost:8000/api` — this is set in `frontend/.env.local`
(`VITE_API_BASE_URL`); edit it if the backend runs elsewhere.

## 4. Using the app

1. Upload an Excel workbook (must have a `Guardrails` sheet; see
   `data/Jardiance_Guardrails_Relevance.xlsx` for the expected columns) from
   either engine panel — both panels share the same uploaded file.
2. Define one or more categories (name + description) in the JEV panel — both
   engines use the same categories, per the project's Fair Comparison
   Principle (see `CLAUDE.md`).
3. Pick a model and enter a prompt in the "General LLM" panel.
4. For JEV, choose **Normal** (one request per guardrail) or **Batch** (one
   request for a group of guardrails). Set **Guardrails to classify** and click
   **Run custom** to classify that many rows, or click **Run all guardrails** in
   either engine panel. Both engines report background progress.
5. Each finished engine displays its category distribution, response time,
   token usage, and cost. Once both finish, the comparison section calculates
   agreement and enables the combined comparison Excel download.

Each General LLM request caps generated output at 512 tokens, which is enough
for the requested category and short reason while avoiding unnecessarily large
provider token reservations.

### Copy Creation intake

The app opens on **Copy Creation**. Add a description, documents, or both for
Project Brief and Actual Material; Reference Material is optional. PDF, DOCX,
and XLSX files are supported (up to six documents total and 10 MB per file).
Descriptions and extracted PDF/DOCX text are limited to 40,000 combined
characters. Scanned/image-only PDFs are not supported. XLSX files are accepted
by filename only: workbook contents are not opened, analyzed, or added to the
classification context. Choose **Analyse** to identify Brand, Market, and
Asset Type, then review the values and source labels before continuing. Clearly
labeled values (for example, `brand: ...`, `market: ...`, and `asset: ...`) are
read directly without waiting for a model request. For any remaining field,
the app builds candidate values from recognized markets, asset types, and
proper-name phrases in descriptions and readable PDF/DOCX material; JEV chooses
among unresolved candidates using one batched Decisions API request. JEV
returns typed choices rather than generating arbitrary text. If there are no
candidates for Brand, “No brand found” is returned. Brand candidates may also
come from the leading product name in an XLSX filename; spreadsheet cells
remain unread. When no market or asset type can be detected, the defaults are
“Canada” and “Email.” Extracted PDF/DOCX text is also carried into both engines
as shared classification context, while the Guardrails workbook remains a
separate upload on the next page.

Metadata detection uses the JEV model through OpenRouter's Decisions API with
`OPENROUTER_API_KEY`. It does not make chat-completion requests or use the
configurable JEV normal/batch setting used by the later guardrail-classification
page.

The General LLM selector loads all text-output models in the OpenRouter
catalog, including free and paid models. Catalog presence does not guarantee
that a model or its provider is available to the configured account; OpenRouter
may reject requests because of access, credits, or rate limits.

### JEV full-dataset mode

The JEV mode is selected in the JEV panel before each run. In batch mode,
`batch_size` in the repository-root `settings.txt` controls guardrails per
request (1-64; the default is 20). The file's `mode` setting remains the
fallback for API clients that do not send a mode. For example:

```text
mode=batch
batch_size=20
```

Full runs are submitted as background jobs, and the dashboard shows progress.
Batch usage is returned by the provider for the whole request and is evenly
allocated across that batch's successful rows for row-level reporting; the
dashboard identifies this allocation.

## Troubleshooting

**`SSLCertVerificationError` / `unable to get local issuer certificate`**
Your network's TLS-inspecting proxy (common on corporate laptops) isn't
trusted by Python's bundled certificate bundle. `pip-system-certs` (already
in `requirements.txt`) patches Python to trust your OS certificate store
instead — reinstall requirements and restart the backend. If it's Node/npm
hitting the same issue (e.g. during `npm install`), export your corporate
root CA to a `.pem` file and set `NODE_EXTRA_CA_CERTS` to its path before
running `npm install`.

**`403 Forbidden` from `openrouter.ai` with an HTML body mentioning your
network vendor (e.g. Zscaler)** — your network is blocking the domain
outright, not an API-key problem. Ask IT to allowlist `openrouter.ai`, or run
from a different network/VPN.

**Backend starts but frontend requests fail with a CORS error** — confirm
the backend's `CORSMiddleware` origin list in `backend/app/main.py` includes
the frontend's actual URL (defaults to `http://localhost:5173`).

**`ModuleNotFoundError` after `pip install -r requirements.txt`** — confirm
the venv is activated (`.\venv\Scripts\Activate.ps1`) before installing/
running; `pip`/`uvicorn` must come from inside `backend/venv/`, not a global
Python install.

## AWS EC2 deployment (Docker Compose)

The repository includes a Docker Compose deployment for one Ubuntu EC2
instance. Nginx serves the production frontend and proxies API requests to
FastAPI. Caddy provides HTTPS automatically after a DNS name points to the
instance. The API port is not published to the internet.

1. Launch an Ubuntu 24.04 EC2 instance. Configure its security group to allow
   inbound TCP ports **80** and **443**. Allow SSH (TCP 22) only from your own
   IP address. Do not open port 8000.
2. Install Git, Docker Engine, and the Docker Compose plugin using their
   official Ubuntu installation instructions.
3. Add an `A` record for a domain you control pointing to the instance's
   public IP. Keep that IP stable (for example, assign an Elastic IP).
4. Clone the GitHub repository onto the instance. In this checkout, the app
   is in the `Gaudrils-classification` subfolder, so change into that directory
   before continuing:

   ```sh
   cd <repository>/Gaudrils-classification
   cp .env.example .env
   chmod 600 .env
   ```

5. Edit `.env` and set `OPENROUTER_API_KEY` and `APP_DOMAIN` to the real API
   key and DNS hostname. Never commit `.env` or put the API key in frontend
   variables, source code, or GitHub.
6. Start the application:

   ```sh
   docker compose up --build -d
   docker compose ps
   ```

   Caddy obtains and renews the HTTPS certificate automatically. Visit
   `https://<your-domain>` and verify `https://<your-domain>/health`.
7. To deploy a later GitHub update:

   ```sh
   git pull --ff-only
   docker compose up --build -d
   ```

Uploaded workbooks and generated output are stored in Docker volumes across
container restarts. They are local to the EC2 host, so back up the host's
storage before replacing or terminating the instance. Classification jobs
are held in backend memory and will not survive a backend restart. The
example workbook under `data/` is excluded from Git by default; upload the
workbook you intend to classify through the application.
