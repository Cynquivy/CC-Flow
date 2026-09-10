"""M3 schema: programs, curriculum_versions, courses, course_slots,
requisite_edges, elective_slots.
M4 adds: course_offering_windows.
M5 adds: course_code_equivalencies, shiftee_credit_mappings.

`course_slots` holds only the flowchart's literal printed year/term
position; per the M2 exceptions log, that "year" value is not yet
trustworthy for 6 of the 11 programs (see
parser/output/exceptions_log.txt), so it's stored as-is (year_raw)
rather than normalized into a year_level int -- normalizing now would
mean guessing at exactly the records that are already known to be
mislabeled.
"""

from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Program(Base):
    __tablename__ = "programs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    curriculum_versions: Mapped[list["CurriculumVersion"]] = relationship(back_populates="program")


class CurriculumVersion(Base):
    __tablename__ = "curriculum_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id"), nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)

    program: Mapped[Program] = relationship(back_populates="curriculum_versions")
    courses: Mapped[list["Course"]] = relationship(back_populates="curriculum_version")


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    curriculum_version_id: Mapped[int] = mapped_column(
        ForeignKey("curriculum_versions.id"), nullable=False
    )
    code: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False, default="")
    units: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_zero_credit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # GE (LCC..NN) / program-elective (*ELEC*) placeholder rows, per elective_slots below --
    # these represent a category slot, not one fixed course title.
    is_elective_placeholder: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    curriculum_version: Mapped[CurriculumVersion] = relationship(back_populates="courses")
    slot: Mapped["CourseSlot"] = relationship(back_populates="course", uselist=False)
    elective_slot: Mapped["ElectiveSlot | None"] = relationship(back_populates="course", uselist=False)
    offering_window: Mapped["CourseOfferingWindow | None"] = relationship(
        back_populates="course", uselist=False
    )

    # Deliberately no UNIQUE(curriculum_version_id, code): MSCS.txt has a genuine
    # duplicate "THESIS" code for two different courses (flagged, not renamed, in
    # M2's exceptions log) -- enforcing uniqueness here would fail that seed row.


class CourseSlot(Base):
    __tablename__ = "course_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False, unique=True)
    year_raw: Mapped[str | None] = mapped_column(String, nullable=True)
    term: Mapped[int | None] = mapped_column(Integer, nullable=True)

    course: Mapped[Course] = relationship(back_populates="slot")


class RequisiteEdge(Base):
    __tablename__ = "requisite_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    requisite_code: Mapped[str] = mapped_column(String, nullable=False)
    # Null when requisite_code doesn't resolve to exactly one course in the same
    # curriculum_version (an external exam-waiver code like BASMATH, a typo like
    # PRCCC01/PRCC01 or LSLSONE/LCLSONE, or an ambiguous duplicate-code match) --
    # see the seed script's exceptions log rather than guessing which course it means.
    requisite_course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id"), nullable=True)

    course: Mapped[Course] = relationship(foreign_keys=[course_id])
    requisite_course: Mapped["Course | None"] = relationship(foreign_keys=[requisite_course_id])


class ElectiveSlot(Base):
    __tablename__ = "elective_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False, unique=True)
    category: Mapped[str] = mapped_column(String, nullable=False)

    course: Mapped[Course] = relationship(back_populates="elective_slot")


# The flowchart only ever shows a course's canonical on-time slot -- when a
# course can actually be *offered* (which terms it runs, and whether a
# delayed/retaking student can still fit it in) isn't in that data at all;
# it's domain knowledge the user provides directly. See
# backend/app/seed_offering_windows.py for the known-code overrides
# (currently just LCC..NN -> "every_term") -- everything else seeds as
# "unknown" rather than being inferred from the flowchart position.
OFFERING_WINDOWS = {
    "every_term",
    "t1_only",
    "t2_only",
    "t3_only",
    "shifted_earlier_delayed",
    "unknown",
}


class CourseOfferingWindow(Base):
    __tablename__ = "course_offering_windows"
    __table_args__ = (
        CheckConstraint(
            "offering_window in (" + ", ".join(f"'{v}'" for v in sorted(OFFERING_WINDOWS)) + ")",
            name="ck_course_offering_windows_offering_window",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False, unique=True)
    # named offering_window, not "window" -- that's a reserved word in Postgres
    offering_window: Mapped[str] = mapped_column(String, nullable=False, default="unknown")
    notes: Mapped[str | None] = mapped_column(String, nullable=True)

    course: Mapped[Course] = relationship(back_populates="offering_window")


# M5, part 1: does the same course *code* actually mean the same thing in
# every program that carries it? Purely derived from parsed data (courses +
# requisite_edges) -- one row per code that appears in 2+ programs, no
# per-program row here since that's just `courses` filtered by code. Fully
# recomputed on every seed run (see seed_equivalencies.py); nothing here is
# hand-editable, so nothing to preserve across reruns.
class CourseCodeEquivalency(Base):
    __tablename__ = "course_code_equivalencies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    program_count: Mapped[int] = mapped_column(Integer, nullable=False)
    units_consistent: Mapped[bool] = mapped_column(Boolean, nullable=False)
    name_consistent: Mapped[bool] = mapped_column(Boolean, nullable=False)
    requisites_consistent: Mapped[bool] = mapped_column(Boolean, nullable=False)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)


# M5, part 2: the "shiftee" case -- a student switching programs whose old
# program used a *different* code for what looks like the same course.
# Candidates are generated by exact-name-match across programs (see
# seed_equivalencies.py) and start life as "candidate", never asserted as
# fact -- same "flag for manual fix/confirmation, don't guess" posture as
# M2's exceptions log and M4's "unknown" default. A human confirms or
# rejects each row directly (no UI yet); reseeding only adds newly-found
# candidate pairs, it never touches a row someone has already reviewed.
SHIFTEE_MAPPING_STATUSES = {"candidate", "confirmed", "rejected"}


class ShifteeCreditMapping(Base):
    __tablename__ = "shiftee_credit_mappings"
    __table_args__ = (
        CheckConstraint(
            "status in (" + ", ".join(f"'{v}'" for v in sorted(SHIFTEE_MAPPING_STATUSES)) + ")",
            name="ck_shiftee_credit_mappings_status",
        ),
        UniqueConstraint("code_a", "code_b", name="uq_shiftee_credit_mappings_code_pair"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # code_a is always the lexicographically smaller of the pair (enforced at
    # seed time) so the same pair can't get inserted twice in swapped order.
    code_a: Mapped[str] = mapped_column(String, nullable=False)
    code_b: Mapped[str] = mapped_column(String, nullable=False)
    shared_name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="candidate")
    source: Mapped[str] = mapped_column(String, nullable=False, default="exact_name_match")
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
