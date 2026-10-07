# Bulk Certificate Generator

A FastAPI service and React frontend that accept up to 1,000 recipients in one request, create a PDF certificate for each valid recipient, and show job progress and outcomes. A single predefined design is implemented in `certificate_generator/pdf.py`.

## Setup

Use Python 3.12 for the tested setup. From this directory:

```powershell
py -3.12 -m venv .venv312
.\.venv312\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

On this computer, `.venv312` has already been created and the dependencies installed. If PowerShell still shows `(.venv)`, run `deactivate` first, then activate `.venv312`. Check with `python --version`; it should report Python 3.12. Python 3.15 currently selects a Pydantic Core release without a matching Windows wheel and may fail while attempting a Rust source build.

For a runtime-only installation, use `requirements.txt` instead. The default SQLite database and PDFs are created in `data/`. Set `CERTIFICATE_DATA_DIR` to choose another directory.

## Run

```powershell
uvicorn certificate_generator.app:app --host 127.0.0.1 --port 8000
```

The interactive API documentation is at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

## Run the React frontend

Requires Node.js 20.19+ and npm. Keep the API running in one terminal, then open another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173). Enter the course and issue date, paste one recipient per line, or upload a CSV file. The expected columns are `name,email,recipient_id`; the last column is optional and a header row is accepted. Quoted CSV fields are supported. Submit the job to see progress and per-recipient downloads. The job ID stays in the page URL, so refreshing the page reloads its status.

Run `npm test` for the CSV parser tests or `npm run build` for a production frontend build inside `frontend/`. The development server proxies `/api` to the FastAPI server at `127.0.0.1:8000`; start the backend first.

## Submit a job

```powershell
$body = @{
  course = "Python Workshop"
  issue_date = "2026-10-07"
  recipients = @(
    @{ name = "Asha Rao"; email = "asha@example.org"; recipient_id = "P-001" }
    @{ name = "Dev Shah"; email = "dev@example.org" }
  )
} | ConvertTo-Json -Depth 4
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/jobs -ContentType application/json -Body $body
```

The response has HTTP 202, a `job_id`, and a `status_url`. Poll `GET /jobs/{job_id}`. Its `counts` show queued, completed, and failed recipients; `recipients` lists each input position, outcome, error, and download URL. Job status is `queued`, `running`, `completed`, or `completed_with_errors`.

```powershell
$job = Invoke-RestMethod http://127.0.0.1:8000/jobs/YOUR_JOB_ID
$job.counts
$url = $job.recipients[0].download_url
Invoke-WebRequest "http://127.0.0.1:8000$url" -OutFile certificate.pdf
```

`GET /jobs/{job_id}/certificates/{recipient_id}` returns a completed PDF. It returns 409 for a pending or failed recipient and 404 for an unknown ID or missing file.

## Tests

```powershell
python -m pytest -q
```

Tests use temporary storage and cover request validation, per-recipient validation, PDF contents, progress, isolated generation failures, and downloads.

## Design decisions

- SQLite stores the job and each recipient outcome. PDF files live on disk, with paths tracked in SQLite. Recipient UUIDs are used as filenames to avoid unsafe user-supplied paths.
- Top-level input errors return 422. An invalid recipient becomes a failed item while valid recipients continue. Each item retains its input `position`, including malformed objects.
- FastAPI background tasks run after the 202 response. This keeps the API simple and gives clients a progress endpoint. Work is sequential within a job, so memory use stays low and one PDF failure is isolated. The 1,000-recipient cap bounds one request.
- Background tasks run in the web process. If that process exits during a job, queued/running work does not automatically resume. For production durability or multiple workers, move `process_job` to a separate queue worker and add job recovery on startup. The service has no authentication; add it before exposing recipient data to untrusted clients.
- The bundled Vera font supports common Latin text. For names in other scripts, add an appropriate Unicode font and choose it in `pdf.py`.
- The React app uses a Vite development proxy and polls the status endpoint every 1.5 seconds while a job is active. It shows backend validation and per-recipient generation errors without hiding successful downloads.
