"""M8/M9: request/response schemas for the scheduling and catalog API.

All JSON over the wire is camelCase; internally everything stays
snake_case, matching the rest of this codebase.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ScheduleRequest(CamelModel):
    target_program: str
    completed_courses: list[str] = Field(default_factory=list)
    max_units_per_term: float = Field(gt=0)
    solver: Literal["greedy", "optimal"] = "greedy"


class ScheduledCourseOut(CamelModel):
    code: str
    name: str
    units: float


class TermPlanOut(CamelModel):
    term_number: int
    calendar_term: int
    courses: list[ScheduledCourseOut]
    total_units: float


class ScheduleResponse(CamelModel):
    program: str
    solver: str
    term_count: int
    terms: list[TermPlanOut]


class CourseRequisiteOut(CamelModel):
    type: Literal["hard", "soft", "coreq", "exemption"]
    code: str


class CatalogCourseOut(CamelModel):
    code: str
    name: str
    units: float
    is_zero_credit: bool
    year_raw: str | None
    year_number: int | None
    term: int | None
    requisites: list[CourseRequisiteOut]


class ProgramCatalogResponse(CamelModel):
    program: str
    year_data_reliable: bool
    courses: list[CatalogCourseOut]
