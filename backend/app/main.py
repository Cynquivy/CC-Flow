from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from .catalog import CatalogError, load_program_catalog
from .config import get_settings
from .db import SessionLocal, check_db_connection
from .models import Program
from .scheduler import SchedulingError, SchedulingTimeoutError, generate_schedule, load_program_courses
from .scheduler_cpsat import generate_schedule_optimal
from .schemas import (
    CatalogCourseOut,
    CourseRequisiteOut,
    ProgramCatalogResponse,
    ScheduledCourseOut,
    ScheduleRequest,
    ScheduleResponse,
    TermPlanOut,
)

settings = get_settings()

app = FastAPI(title="CC-Flow API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Everything lives under /api -- the Vercel deployment routes /api/* to this
# service and everything else to the static frontend build (see vercel.json).
# Locally, the frontend still talks to this same prefix, just against
# http://localhost:8000 instead of a relative path (see frontend/src/api.ts).
router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "db": check_db_connection()}


def get_db():
    if SessionLocal is None:
        raise HTTPException(status_code=503, detail="database not configured")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/programs")
def list_programs(db: Session = Depends(get_db)) -> list[str]:
    return list(db.scalars(select(Program.code).order_by(Program.code)))


@router.get("/programs/{code}/courses", response_model=ProgramCatalogResponse)
def program_courses(code: str, db: Session = Depends(get_db)) -> ProgramCatalogResponse:
    try:
        catalog = load_program_catalog(db, code)
    except CatalogError:
        raise HTTPException(status_code=404, detail=f"unknown program: {code!r}")

    return ProgramCatalogResponse(
        program=catalog.program,
        year_data_reliable=catalog.year_data_reliable,
        courses=[
            CatalogCourseOut(
                code=c.code,
                name=c.name,
                units=c.units,
                is_zero_credit=c.is_zero_credit,
                year_raw=c.year_raw,
                year_number=c.year_number,
                term=c.term,
                requisites=[CourseRequisiteOut(type=r.type, code=r.code) for r in c.requisites],
            )
            for c in catalog.courses
        ],
    )


@router.post("/schedule", response_model=ScheduleResponse)
def schedule(request: ScheduleRequest, db: Session = Depends(get_db)) -> ScheduleResponse:
    try:
        courses = load_program_courses(db, request.target_program)
    except SchedulingError:
        raise HTTPException(status_code=404, detail=f"unknown program: {request.target_program!r}")

    known_codes = {c.code for c in courses}
    unknown_codes = sorted(set(request.completed_courses) - known_codes)
    if unknown_codes:
        raise HTTPException(
            status_code=400,
            detail=f"unknown completed course code(s) for {request.target_program!r}: {', '.join(unknown_codes)}",
        )

    completed = set(request.completed_courses)

    try:
        if request.solver == "optimal":
            plans = generate_schedule_optimal(courses, completed, request.max_units_per_term)
        else:
            plans = generate_schedule(courses, completed, request.max_units_per_term)
    except SchedulingTimeoutError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"optimal solver timed out before resolving a schedule ({exc}) -- try solver=greedy",
        )
    except SchedulingError as exc:
        raise HTTPException(status_code=422, detail=f"no feasible schedule found: {exc}")

    return ScheduleResponse(
        program=request.target_program,
        solver=request.solver,
        term_count=len(plans),
        terms=[
            TermPlanOut(
                term_number=p.term_number,
                calendar_term=p.calendar_term,
                courses=[
                    ScheduledCourseOut(code=c.code, name=c.name, units=c.units) for c in p.courses
                ],
                total_units=p.total_units,
            )
            for p in plans
        ],
    )


app.include_router(router)
