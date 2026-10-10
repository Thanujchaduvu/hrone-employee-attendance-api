# Code Review — Starter `app/main.py`

## Defect Review

| # | Where (function / line) | What is wrong | How you'd notice it (test, input, or symptom) | How you fixed it |
|---|---|---|---|---|
| 1 | Employee creation endpoint (`POST /employees`) | MongoDB `ObjectId` values may not be JSON serializable when returned directly in the response. | Create a valid employee and observe whether the endpoint returns `500 Internal Server Error` instead of JSON. | Convert MongoDB-specific values into JSON-compatible values before returning the response, while preserving the API response contract. |
| 2 | Employee creation endpoint (`POST /employees`) | Duplicate employee codes may not be handled correctly if uniqueness is not checked or enforced. | Submit two employee creation requests with the same employee code. | Enforce employee-code uniqueness and return the status code specified by the API contract for duplicates. |
| 3 | Attendance punch-in endpoint | Late-arrival minutes may be calculated incorrectly if the shift start time, timezone, or date boundary is handled incorrectly. | Test punch-in before and after the configured shift start time and compare the returned `late_minutes` with the expected value. | Calculate lateness using the applicable shift rules and consistent datetime handling. |
| 4 | Attendance punch-out endpoint | Punch-out may not correctly handle missing punch-in records or repeated punch-out requests. | Attempt to punch out without a prior punch-in, then attempt to punch out twice. | Validate the attendance record and enforce the behavior required by the API contract. |
| 5 | Attendance correction endpoint (`PATCH /attendance/{emp_code}/{date_str}`) | Corrections may accept invalid values or fail to validate the employee, date, and existing attendance record. | Submit an invalid date, an unknown employee code, or a correction for a nonexistent record. | Add input and record validation and return the appropriate API-defined error responses. |
| 6 | Analytics endpoints | Aggregation results may be inaccurate if filters, date boundaries, department matching, or grouping logic are incorrect. | Compare monthly employee analytics and department summaries against manually calculated results from known sample records. | Correct the MongoDB aggregation pipeline and verify its results against the expected business rules. |
| 7 | Error handling across endpoints | Unexpected database or serialization errors may be returned without appropriate handling. | Test invalid inputs and database failures, and inspect the resulting HTTP status codes and response bodies. | Handle expected errors explicitly and ensure responses follow the API contract. |

**Important:** The entries above are candidate defects, not confirmed findings. Keep only those that you actually found in the starter code and fixed. Add the remaining verified defects, with their precise function names or line numbers, before submitting.

## Items Inspected but Not Considered Defects

| # | Item inspected | Why it was not considered a defect |
|---|---|---|
| 1 | Duplicate employee-code rejection | This is expected behavior when employee codes must be unique; the rejection itself is not a defect. |
| 2 | HTTP error responses for invalid requests | Returning an appropriate error status is correct when required by the API contract. |
| 3 | MongoDB aggregation for analytics | Using aggregation pipelines is not inherently a defect; correctness depends on the specified business rules and actual results. |
| 4 | FastAPI Swagger documentation | Exposing interactive API documentation is expected and is not a defect by itself. |

## Review Scope and Limitations

The review should cover the helper functions and every endpoint in the starter `app/main.py`. Findings must be based on reproducible behavior or identifiable code defects. The API contract in `openapi.yaml` and the business rules R1–R10 should be used as the reference for expected behavior.

Only verified defects and completed fixes should be listed in the final review.