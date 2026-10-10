
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional, Any
from zoneinfo import ZoneInfo
import os
import math

from bson import ObjectId
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, ConfigDict
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError, PyMongoError


# --------------------------------------------------
# APP CONFIGURATION
# --------------------------------------------------

app = FastAPI(
    title="Employee Attendance & Analytics API",
    description="Employee attendance tracking and analytics",
    version="1.0.0",
)

IST = ZoneInfo("Asia/Kolkata")
UTC = timezone.utc

MONGODB_URI = os.getenv(
    "MONGODB_URI",
    "mongodb://localhost:27017"
)
DATABASE_NAME = os.getenv(
    "DATABASE_NAME",
    "employee_attendance"
)

client = MongoClient(
    MONGODB_URI,
    serverSelectionTimeoutMS=5000,
)

db = client[DATABASE_NAME]
employees = db["employees"]
attendance = db["attendance"]


# --------------------------------------------------
# SERIALIZATION HELPERS
# Fixes: TypeError: 'ObjectId' object is not iterable
# --------------------------------------------------

def serialize_doc(value: Any) -> Any:
    """Convert MongoDB/Python values into JSON-safe values."""

    if isinstance(value, ObjectId):
        return str(value)

    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.isoformat()

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, dict):
        return {
            str(key): serialize_doc(item)
            for key, item in value.items()
            if key != "_id"
        } | (
            {"id": str(value["_id"])}
            if "_id" in value
            else {}
        )

    if isinstance(value, list):
        return [serialize_doc(item) for item in value]

    return value


def to_utc(value: datetime) -> datetime:
    """Interpret timestamps without a timezone as IST."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=IST)
    return value.astimezone(UTC)


def to_ist(value: Optional[datetime]) -> Optional[datetime]:
    """MongoDB stores naive datetimes as UTC; return aware IST."""
    if value is None:
        return None

    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)

    return value.astimezone(IST)


def today_ist() -> date:
    return datetime.now(IST).date()


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid date. Use YYYY-MM-DD.",
        )


# --------------------------------------------------
# ATTENDANCE CALCULATION HELPERS
# --------------------------------------------------

SHIFT_START = time(9, 0)
SHIFT_END = time(18, 0)
LATE_GRACE_MINUTES = 10


def compute_late_minutes(
    punch_in: Optional[datetime],
    shift_start: time = SHIFT_START,
) -> int:
    if punch_in is None:
        return 0

    local_time = to_ist(punch_in)
    shift_start_dt = datetime.combine(
        local_time.date(), shift_start, tzinfo=IST
    )

    difference = (
        local_time - shift_start_dt
    ).total_seconds() / 60

    if difference <= LATE_GRACE_MINUTES:
        return 0

    return max(0, math.floor(difference))


def compute_work_hours(
    punch_in: Optional[datetime],
    punch_out: Optional[datetime],
) -> float:
    if punch_in is None or punch_out is None:
        return 0.0

    minutes = (
        to_utc(punch_out) - to_utc(punch_in)
    ).total_seconds() / 60

    return round(max(0, minutes) / 60, 2)


def compute_overtime(
    punch_out: Optional[datetime],
    shift_end: time = SHIFT_END,
) -> int:
    if punch_out is None:
        return 0

    local_time = to_ist(punch_out)
    end_dt = datetime.combine(
        local_time.date(), shift_end, tzinfo=IST
    )

    minutes = (
        local_time - end_dt
    ).total_seconds() / 60

    return max(0, math.floor(minutes))


def calculate_attendance_fields(record: dict) -> dict:
    punch_in = record.get("punch_in")
    punch_out = record.get("punch_out")

    record["late_minutes"] = compute_late_minutes(punch_in)
    record["work_hours"] = compute_work_hours(
        punch_in, punch_out
    )
    record["overtime_minutes"] = compute_overtime(punch_out)

    return record


# --------------------------------------------------
# REQUEST MODELS
# --------------------------------------------------

class EmployeeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    emp_code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=100)
    department: str = Field(min_length=1, max_length=100)
    email: Optional[str] = None
    shift_start: str = "09:00"
    shift_end: str = "18:00"


class PunchInIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    emp_code: str
    punch_in: Optional[datetime] = None


class PunchOutIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    emp_code: str
    punch_out: Optional[datetime] = None


class AttendanceCorrection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Optional[str] = None
    punch_in: Optional[datetime] = None
    punch_out: Optional[datetime] = None
    reason: str = Field(min_length=3, max_length=500)


# --------------------------------------------------
# DATABASE INDEXES
# --------------------------------------------------

@app.on_event("startup")
def create_indexes():
    try:
        employees.create_index(
            [("emp_code", ASCENDING)], unique=True
        )
        attendance.create_index(
            [("emp_code", ASCENDING), ("date", ASCENDING)],
            unique=True,
        )
        attendance.create_index(
            [("date", DESCENDING), ("status", ASCENDING)]
        )
        attendance.create_index(
            [("department", ASCENDING), ("date", ASCENDING)]
        )
    except PyMongoError:
        # The health endpoint will report connection issues.
        pass


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

@app.get("/")
def root():
    return {
        "message": "Employee Attendance & Analytics API",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    try:
        client.admin.command("ping")
        return {
            "status": "ok",
            "database": "connected",
        }
    except PyMongoError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"MongoDB unavailable: {str(exc)}",
        )


# --------------------------------------------------
# EMPLOYEE ENDPOINTS
# --------------------------------------------------

@app.post("/employees", status_code=201)
def create_employee(employee: EmployeeIn):
    emp_code = employee.emp_code.strip().upper()

    if not emp_code:
        raise HTTPException(400, "Employee code is required.")

    existing = employees.find_one({"emp_code": emp_code})
    if existing:
        raise HTTPException(
            status_code=409,
            detail="Employee code already exists.",
        )

    data = employee.model_dump()
    data["emp_code"] = emp_code
    data["name"] = data["name"].strip()
    data["department"] = data["department"].strip()
    data["created_at"] = datetime.now(UTC)

    try:
        result = employees.insert_one(data)
        saved = employees.find_one({"_id": result.inserted_id})
        return serialize_doc(saved)
    except DuplicateKeyError:
        raise HTTPException(
            status_code=409,
            detail="Employee code already exists.",
        )
    except PyMongoError as exc:
        raise HTTPException(500, str(exc))


@app.get("/employees")
def list_employees(
    department: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    query = {}
    if department:
        query["department"] = department

    total = employees.count_documents(query)
    offset = (page - 1) * page_size

    items = list(
        employees.find(query)
        .sort("emp_code", ASCENDING)
        .skip(offset)
        .limit(page_size)
    )

    return {
        "items": [serialize_doc(item) for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# --------------------------------------------------
# ATTENDANCE HELPERS
# --------------------------------------------------

def get_employee(emp_code: str) -> dict:
    employee = employees.find_one({
        "emp_code": emp_code.strip().upper()
    })

    if not employee:
        raise HTTPException(
            status_code=404,
            detail="Employee not found.",
        )

    return employee


def get_attendance_record(emp_code: str, day: date) -> dict:
    record = attendance.find_one({
        "emp_code": emp_code.strip().upper(),
        "date": day.isoformat(),
    })

    if not record:
        raise HTTPException(
            status_code=404,
            detail="Attendance record not found.",
        )

    return record


def department_for(emp_code: str) -> str:
    employee = get_employee(emp_code)
    return employee.get("department", "Unknown")


# --------------------------------------------------
# PUNCH IN
# --------------------------------------------------

@app.post("/attendance/punch-in")
def punch_in(data: PunchInIn):
    employee = get_employee(data.emp_code)
    emp_code = employee["emp_code"]

    punch_time = data.punch_in or datetime.now(IST)
    punch_utc = to_utc(punch_time)
    day = to_ist(punch_utc).date().isoformat()

    existing = attendance.find_one({
        "emp_code": emp_code,
        "date": day,
    })

    if existing and existing.get("punch_in"):
        raise HTTPException(
            status_code=409,
            detail="Employee has already punched in for this date.",
        )

    record = {
        "emp_code": emp_code,
        "name": employee["name"],
        "department": employee["department"],
        "date": day,
        "status": "PRESENT",
        "punch_in": punch_utc,
        "punch_out": None,
        "work_hours": 0.0,
        "late_minutes": compute_late_minutes(punch_utc),
        "overtime_minutes": 0,
        "history": [],
        "updated_at": datetime.now(UTC),
    }

    try:
        if existing:
            attendance.update_one(
                {"_id": existing["_id"]},
                {"$set": record},
            )
            saved = attendance.find_one(
                {"_id": existing["_id"]}
            )
        else:
            result = attendance.insert_one(record)
            saved = attendance.find_one(
                {"_id": result.inserted_id}
            )

        return serialize_doc(saved)

    except DuplicateKeyError:
        raise HTTPException(
            status_code=409,
            detail="Attendance already exists for this date.",
        )


# --------------------------------------------------
# PUNCH OUT
# --------------------------------------------------

@app.post("/attendance/punch-out")
def punch_out(data: PunchOutIn):
    employee = get_employee(data.emp_code)
    emp_code = employee["emp_code"]

    punch_time = data.punch_out or datetime.now(IST)
    punch_utc = to_utc(punch_time)
    day = to_ist(punch_utc).date().isoformat()

    record = attendance.find_one({
        "emp_code": emp_code,
        "date": day,
    })

    if not record or not record.get("punch_in"):
        raise HTTPException(
            status_code=404,
            detail="Punch-in record not found for this date.",
        )

    if record.get("punch_out"):
        raise HTTPException(
            status_code=409,
            detail="Employee has already punched out.",
        )

    if punch_utc < to_utc(record["punch_in"]):
        raise HTTPException(
            status_code=400,
            detail="Punch-out cannot be earlier than punch-in.",
        )

    update = {
        "punch_out": punch_utc,
        "work_hours": compute_work_hours(
            record["punch_in"], punch_utc
        ),
        "overtime_minutes": compute_overtime(punch_utc),
        "updated_at": datetime.now(UTC),
    }

    attendance.update_one(
        {"_id": record["_id"]},
        {"$set": update},
    )

    saved = attendance.find_one({"_id": record["_id"]})
    return serialize_doc(saved)


# --------------------------------------------------
# LIST ATTENDANCE
# --------------------------------------------------

@app.get("/attendance")
def list_attendance(
    emp_code: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    query = {}

    if emp_code:
        query["emp_code"] = emp_code.strip().upper()

    if date_from:
        start_day = parse_date(date_from).isoformat()
        query.setdefault("date", {})["$gte"] = start_day

    if date_to:
        end_day = parse_date(date_to).isoformat()
        query.setdefault("date", {})["$lte"] = end_day

    if date_from and date_to:
        if parse_date(date_from) > parse_date(date_to):
            raise HTTPException(
                status_code=400,
                detail="date_from cannot be after date_to.",
            )

    if status:
        query["status"] = status.strip().upper()

    total = attendance.count_documents(query)
    offset = (page - 1) * page_size

    records = list(
        attendance.find(query)
        .sort([("date", DESCENDING), ("emp_code", ASCENDING)])
        .skip(offset)
        .limit(page_size)
    )

    items = []
    for record in records:
        record = calculate_attendance_fields(record)
        items.append(serialize_doc(record))

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# --------------------------------------------------
# CORRECT ATTENDANCE
# PATCH /attendance/{emp_code}/{date_str}
# --------------------------------------------------

@app.patch("/attendance/{emp_code}/{date_str}")
def correct_attendance(
    emp_code: str,
    date_str: str,
    correction: AttendanceCorrection,
):
    day = parse_date(date_str)
    employee = get_employee(emp_code)

    record = attendance.find_one({
        "emp_code": employee["emp_code"],
        "date": day.isoformat(),
    })

    if not record:
        raise HTTPException(
            status_code=404,
            detail="Attendance record not found.",
        )

    changes = correction.model_dump(exclude_unset=True)
    reason = changes.pop("reason")

    if "status" in changes and changes["status"] is not None:
        allowed = {"PRESENT", "ABSENT", "HALF_DAY", "LEAVE"}
        changes["status"] = changes["status"].upper()

        if changes["status"] not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"Status must be one of: {sorted(allowed)}",
            )

    for field in ("punch_in", "punch_out"):
        if field in changes and changes[field] is not None:
            changes[field] = to_utc(changes[field])

    new_punch_in = changes.get(
        "punch_in", record.get("punch_in")
    )
    new_punch_out = changes.get(
        "punch_out", record.get("punch_out")
    )

    if new_punch_in and new_punch_out:
        if to_utc(new_punch_out) < to_utc(new_punch_in):
            raise HTTPException(
                status_code=400,
                detail="Punch-out cannot be earlier than punch-in.",
            )

    history_entry = {
        "reason": reason,
        "changed_at": datetime.now(UTC),
        "changes": serialize_doc(changes),
    }

    history = record.get("history", [])
    history.append(history_entry)

    record_after = {
        **record,
        **changes,
    }

    changes["late_minutes"] = compute_late_minutes(
        record_after.get("punch_in")
    )
    changes["work_hours"] = compute_work_hours(
        record_after.get("punch_in"),
        record_after.get("punch_out"),
    )
    changes["overtime_minutes"] = compute_overtime(
        record_after.get("punch_out")
    )
    changes["history"] = history
    changes["updated_at"] = datetime.now(UTC)

    attendance.update_one(
        {"_id": record["_id"]},
        {"$set": changes},
    )

    saved = attendance.find_one({"_id": record["_id"]})
    return serialize_doc(saved)


# --------------------------------------------------
# MONTHLY EMPLOYEE ANALYTICS
# --------------------------------------------------

@app.get("/analytics/employees/{emp_code}/monthly")
def employee_monthly_analytics(
    emp_code: str,
    year: int = Query(default_factory=lambda: today_ist().year),
    month: int = Query(default_factory=lambda: today_ist().month, ge=1, le=12),
):
    employee = get_employee(emp_code)

    if month < 1 or month > 12:
        raise HTTPException(400, "Month must be between 1 and 12.")

    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)

    records = list(attendance.find({
        "emp_code": employee["emp_code"],
        "date": {
            "$gte": start.isoformat(),
            "$lt": end.isoformat(),
        },
    }))

    present = sum(
        1 for r in records if r.get("status") == "PRESENT"
    )
    absent = sum(
        1 for r in records if r.get("status") == "ABSENT"
    )
    leave = sum(
        1 for r in records if r.get("status") == "LEAVE"
    )

    total_hours = 0.0
    late_days = 0
    total_late_minutes = 0
    total_overtime_minutes = 0

    for record in records:
        calculated = calculate_attendance_fields(record)
        total_hours += calculated["work_hours"]
        total_late_minutes += calculated["late_minutes"]
        total_overtime_minutes += calculated["overtime_minutes"]

        if calculated["late_minutes"] > 0:
            late_days += 1

    return {
        "emp_code": employee["emp_code"],
        "name": employee["name"],
        "department": employee["department"],
        "year": year,
        "month": month,
        "total_records": len(records),
        "present_days": present,
        "absent_days": absent,
        "leave_days": leave,
        "late_days": late_days,
        "total_late_minutes": total_late_minutes,
        "total_work_hours": round(total_hours, 2),
        "total_overtime_minutes": total_overtime_minutes,
    }


# --------------------------------------------------
# DEPARTMENT SUMMARY ANALYTICS
# --------------------------------------------------

@app.get("/analytics/departments/summary")
def department_summary(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    query = {}

    if date_from:
        query.setdefault("date", {})["$gte"] = (
            parse_date(date_from).isoformat()
        )

    if date_to:
        query.setdefault("date", {})["$lte"] = (
            parse_date(date_to).isoformat()
        )

    records = list(attendance.find(query))

    departments = {}

    for record in records:
        department = record.get("department", "Unknown")
        group = departments.setdefault(
            department,
            {
                "department": department,
                "total_records": 0,
                "present_days": 0,
                "absent_days": 0,
                "late_days": 0,
                "total_late_minutes": 0,
                "total_work_hours": 0.0,
                "total_overtime_minutes": 0,
            },
        )

        calculated = calculate_attendance_fields(record)
        group["total_records"] += 1

        if record.get("status") == "PRESENT":
            group["present_days"] += 1
        elif record.get("status") == "ABSENT":
            group["absent_days"] += 1

        if calculated["late_minutes"] > 0:
            group["late_days"] += 1

        group["total_late_minutes"] += calculated["late_minutes"]
        group["total_work_hours"] += calculated["work_hours"]
        group["total_overtime_minutes"] += calculated["overtime_minutes"]

    result = []
    for group in departments.values():
        group["total_work_hours"] = round(
            group["total_work_hours"], 2
        )
        result.append(group)

    result.sort(key=lambda item: item["department"].lower())

    return {"items": result, "total_departments": len(result)}


# --------------------------------------------------
# LATE ARRIVAL LEADERBOARD
# --------------------------------------------------

@app.get("/analytics/leaderboard/late")
def late_arrival_leaderboard(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = Query(10, ge=1, le=100),
):
    query = {}

    if date_from:
        query.setdefault("date", {})["$gte"] = (
            parse_date(date_from).isoformat()
        )

    if date_to:
        query.setdefault("date", {})["$lte"] = (
            parse_date(date_to).isoformat()
        )

    records = list(attendance.find(query))
    leaderboard = {}

    for record in records:
        if not record.get("punch_in"):
            continue

        emp_code = record["emp_code"]
        calculated = calculate_attendance_fields(record)

        item = leaderboard.setdefault(
            emp_code,
            {
                "emp_code": emp_code,
                "name": record.get("name", ""),
                "department": record.get("department", "Unknown"),
                "late_days": 0,
                "total_late_minutes": 0,
            },
        )

        if calculated["late_minutes"] > 0:
            item["late_days"] += 1
            item["total_late_minutes"] += calculated["late_minutes"]

    items = sorted(
        leaderboard.values(),
        key=lambda item: (
            -item["total_late_minutes"],
            -item["late_days"],
            item["emp_code"],
        ),
    )[:limit]

    return {"items": items, "total": len(items)}


# --------------------------------------------------
# DEPARTMENT ATTENDANCE TREND
# --------------------------------------------------

@app.get("/analytics/departments/{department}/trend")
def department_trend(
    department: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    query = {"department": department}

    if date_from:
        query.setdefault("date", {})["$gte"] = (
            parse_date(date_from).isoformat()
        )

    if date_to:
        query.setdefault("date", {})["$lte"] = (
            parse_date(date_to).isoformat()
        )

    records = list(
        attendance.find(query).sort("date", ASCENDING)
    )

    trend = {}

    for record in records:
        day = record["date"]
        item = trend.setdefault(
            day,
            {
                "date": day,
                "total_records": 0,
                "present": 0,
                "absent": 0,
                "late": 0,
            },
        )

        item["total_records"] += 1

        if record.get("status") == "PRESENT":
            item["present"] += 1
        elif record.get("status") == "ABSENT":
            item["absent"] += 1

        if compute_late_minutes(record.get("punch_in")) > 0:
            item["late"] += 1

    return {
        "department": department,
        "items": sorted(
            trend.values(), key=lambda item: item["date"]
        ),
    }


# --------------------------------------------------
# QUERY EXPLAIN
# --------------------------------------------------

@app.get("/admin/explain/{endpoint}")
def explain_endpoint(endpoint: str):
    allowed = {
        "attendance": attendance,
        "employees": employees,
    }

    if endpoint not in allowed:
        raise HTTPException(
            status_code=400,
            detail="Supported values are 'attendance' and 'employees'.",
        )

    collection = allowed[endpoint]

    try:
        explanation = db.command({
            "explain": {
                "find": collection.name,
                "filter": {},
            },
            "verbosity": "executionStats",
        })

        return serialize_doc(explanation)

    except PyMongoError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not explain query: {str(exc)}",
        )
