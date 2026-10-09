# Running this project on a new machine

This folder was exported without `backend/venv/` and `frontend/node_modules/`
(both are regenerated from the files below) to keep the transfer small. Follow
these steps on the new device.

## Prerequisites

- **Python 3.12+** — https://python.org
- **Node.js 20+** (ships with npm) — https://nodejs.org
- A **TypeSafe JEV API key** (`JEV_API_KEY`) for JEV guardrail classification
  and Copy Creation metadata detection
- An **OpenRouter API key** (`OPENROUTER_API_KEY`) for the General LLM model
  catalog and chat completions
- Network access to `api.typesafe.ai` and `openrouter.ai`. If you're on a
  corporate network with TLS inspection (Zscaler, Netskope, etc.) and see
  `SSLCertVerificationError: unable to get local issuer certificate`, see
  **Troubleshooting** below — this is a network/cert issue, not a bug in the app.

## 1. Environment file

Create a `.env` file at the **repo root** (same folder as this file):

```text
JEV_API_KEY=your-typesafe-jev-api-key
OPENROUTER_API_KEY=your-openrouter-api-key
```

JEV calls TypeSafe directly at `https://api.typesafe.ai/v1/systemone` using
the `jev-1.13.0` model and bearer authentication. OpenRouter is used only by
the separate General LLM panel and model catalog. See the
[TypeSafe JEV API reference](https://typesafe-jev.com/en/guides/api/).

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
4. JEV always classifies guardrails in batches. Set **Guardrails to classify**
   and click **Run custom** to classify that many rows, or click **Run all
   guardrails** in either engine panel. Both engines report background progress.
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
among unresolved candidates using one batched TypeSafe JEV API request. JEV
returns typed choices rather than generating arbitrary text. If there are no
candidates for Brand, “No brand found” is returned. Brand candidates may also
come from the leading product name in an XLSX filename; spreadsheet cells
remain unread. When no market or asset type can be detected, the defaults are
“Canada” and “Email.” Extracted PDF/DOCX text is also carried into both engines
as shared classification context, while the Guardrails workbook remains a
separate upload on the next page.

Metadata detection uses the direct TypeSafe JEV API and `JEV_API_KEY`. It does
not make OpenRouter chat-completion requests.

The General LLM selector loads all text-output models in the OpenRouter
catalog, including free and paid models. Catalog presence does not guarantee
that a model or its provider is available to the configured account; OpenRouter
may reject requests because of access, credits, or rate limits.

### JEV batch size

JEV custom runs and full-dataset runs always use batch requests.
`batch_size` in the repository-root `settings.txt` controls guardrails per
request (1-64; the default is 64). For example:

```text
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

This project can run on one Ubuntu EC2 instance using Docker Compose. Nginx
serves the production frontend and proxies API requests to FastAPI. Caddy
obtains and renews HTTPS certificates automatically. The API port is not
published to the internet.

### 1. Create the EC2 instance

In the AWS Console, launch an **Ubuntu Server 24.04 LTS, 64-bit x86** EC2
instance. A **t3.medium** instance with at least **30 GB** of storage is a
recommended starting point because the frontend and backend Docker images are
built on the instance.

Configure the instance's security group to allow:

| Type | Protocol/port | Source |
| --- | --- | --- |
| SSH | TCP 22 | Your public IP only |
| HTTP | TCP 80 | Anywhere |
| HTTPS | TCP 443 | Anywhere |

Do **not** open port 8000. Assign an Elastic IP so the public IP stays stable.

### 2. Point a domain at the instance

Create a DNS `A` record for a domain or subdomain you control, pointing to the
instance's Elastic IP. DNS must resolve to the instance before starting Caddy,
so it can obtain an HTTPS certificate.

### 3. Connect and install Docker

Connect to the instance over SSH using its public IP or DNS name and the EC2
key pair selected when creating it. Install Docker Engine and the Compose
plugin from Docker's official Ubuntu repository:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin
```

### 4. Clone the GitHub repository

For a public repository:

```bash
git clone https://github.com/Akshat001003/COPY_PLATFORM.git
cd COPY_PLATFORM/Gaudrils-classification
```

If the repository is private, configure GitHub access for this instance first,
for example with a read-only deploy key. Do not put a personal access token in
the clone URL or shell history.

### 5. Configure the API key and domain

Create a private server-side environment file from the example:

```bash
cp .env.example .env
chmod 600 .env
nano .env
```

Set both values in `.env`:

```text
JEV_API_KEY=your-real-typesafe-jev-api-key
OPENROUTER_API_KEY=your-real-openrouter-api-key
APP_DOMAIN=your-domain.example.com
```

Replace the example values with your real TypeSafe JEV key, OpenRouter key,
and DNS hostname, then save and exit. **Never commit `.env` or put either API
key in frontend variables, source code, or GitHub.**

### 6. Build and start the application

From the `Gaudrils-classification` directory:

```bash
sudo docker compose up --build -d
sudo docker compose ps
```

Caddy obtains and renews the HTTPS certificate automatically. Open
`https://your-domain.example.com` and verify the health endpoint at
`https://your-domain.example.com/health`.

If the application does not start, inspect the recent container logs:

```bash
sudo docker compose logs --tail=100
```

### 7. Deploy future GitHub updates

From the project directory on EC2:

```bash
git pull --ff-only
sudo docker compose up --build -d
```

Uploaded workbooks and generated output are stored in Docker volumes across
container restarts. They are local to the EC2 host, so back up the host's
storage before replacing or terminating the instance. Classification jobs
are held in backend memory and will not survive a backend restart. The
example workbook under `data/` is excluded from Git by default; upload the
workbook you intend to classify through the application.
