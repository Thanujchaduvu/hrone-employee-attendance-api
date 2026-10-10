# Employee Attendance & Analytics API

A REST API built with **Python, FastAPI, and MongoDB** for managing employee records, attendance punch-in/punch-out operations, attendance corrections, and employee and department analytics.

## Tech Stack

- **Language:** Python
- **API Framework:** FastAPI
- **Database:** MongoDB 6.0+
- **API Server:** Uvicorn
- **API Documentation:** OpenAPI / Swagger UI

## Prerequisites

Before running the application, make sure you have:

- Python installed
- MongoDB 6.0 or newer, locally or through MongoDB Atlas
- Git installed

## Project Structure

```text
.
├── app/
│   └── main.py
├── sample_data/
├── sample_seed.py
├── requirements.txt
├── openapi.yaml
├── DATA_MODEL.md
├── REVIEW.md
├── DECISIONS.md
├── .env.example
└── README.md
```

## Setup and Installation

### 1. Clone the repository

```bash
git clone https://github.com/Thanujchaduvu/hrone-employee-attendance-api.git
cd hrone-employee-attendance-api
```

### 2. Create and activate a virtual environment

**Windows PowerShell:**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**Linux / macOS:**

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy the example environment file:

**Windows PowerShell:**

```powershell
Copy-Item .env.example .env
```

**Linux / macOS:**

```bash
cp .env.example .env
```

Configure the MongoDB connection settings in `.env`:

```env
MONGO_URI=mongodb://localhost:27017
MONGO_DB=attendance_db
```

Use the database name and variable names expected by your application. If you use MongoDB Atlas, configure `MONGO_URI` with your Atlas connection string. Keep `.env` private and never commit database credentials or secrets.

### 5. Load sample data

Make sure MongoDB is running, then execute:

```bash
python sample_seed.py
```

The seed script loads the sample documents into MongoDB.

### 6. Start the API server

```bash
uvicorn app.main:app --port 8000 --reload
```

The API will be available at:

- **Base URL:** `http://localhost:8000`
- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Check API health |
| POST | `/employees` | Create an employee |
| GET | `/employees` | Retrieve employee records |
| POST | `/attendance/punch-in` | Record employee punch-in |
| POST | `/attendance/punch-out` | Record employee punch-out |
| GET | `/attendance` | Retrieve attendance records |
| PATCH | `/attendance/{emp_code}/{date_str}` | Correct an attendance record |
| GET | `/analytics/employees/{emp_code}/monthly` | Retrieve monthly employee analytics |
| GET | `/analytics/departments/summary` | Retrieve department summaries |
| GET | `/analytics/leaderboard/late` | Retrieve late-arrival leaderboard |
| GET | `/analytics/departments/{department}/trend` | Retrieve department attendance trends |
| GET | `/admin/explain/{endpoint}` | Inspect query execution information |

Refer to the actual API implementation and `openapi.yaml` for request schemas, query parameters, response formats, and business rules.

## Testing

1. Start the API server.
2. Open `http://localhost:8000/docs`.
3. Test the endpoints using the interactive Swagger UI.
4. Check the responses, validation errors, and HTTP status codes.
5. Verify the business rules documented in `openapi.yaml` (R1–R10).

The candidate kit includes nine sample documents. The evaluation dataset may contain additional records and edge cases, so testing should not be limited to the supplied examples.

## Assignment Documentation

- **`openapi.yaml`** — API contract and business rules.
- **`DATA_MODEL.md`** — MongoDB data model and sample-document information.
- **`REVIEW.md`** — Implementation review.
- **`DECISIONS.md`** — Design decisions and their rationale.

## Notes

- MongoDB 6.0 or newer is required.
- The application must run using `uvicorn app.main:app --port 8000`.
- Keep all application code in `app/main.py`, as required by the assignment.
- Do not commit `.env`, database credentials, or other secrets.
- Do not include `PROBLEM_STATEMENT.docx` in the public repository.

## Author

**Thanuj Chaduvu**

GitHub: https://github.com/Thanujchaduvu