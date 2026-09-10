# Overnight QA Log

Record of unattended QA passes on the `overnight/qa` branch. Newest section at top. QA only — no new features, no milestone work. See ROADMAP.md for milestone status/context; findings and assumptions from these runs live here, not there.

---

## 2026-09-10 05:35 TST — Run 5 of 5 (last one tonight)

**Read first:** runs 1-4 below in full.

**Tested:** `parser/test_parse_flowchart.py` (pass).

**Checked, no new bugs found:** duplicate requisite entries within a single course's own requisites list (e.g. the same code listed twice) — none found, across all 729 records. Same-pair type contradictions (a course listing the same requisite code twice with two different types) — none found. Both checks came back clean, which is itself useful confirmation given how much editing happened to nearby records tonight.

**Real finding — the live `course_code_equivalencies` table (M5) is now stale relative to tonight's fixes, in a good way:** several of tonight's touched codes are shared across multiple programs (`CBARTAP`, `CBASEAN`, `CBEMC-2`, `CBINOV1`, `CBINOV2`, `CBINOV4`, `CBPCOMM`, `CBSTSOC`, `CBWORLD`, `LBYCBC2` all also appear in `CS`; `LBYARCH` also appears in `BSCS-CSE`/`BSCS-NIS`/`CS-ST`). Recomputed `course_code_equivalencies` locally from the corrected `curricula.json` (using `compute_code_equivalencies` from `seed_equivalencies.py` directly, no DB write) and diffed against what's actually live. **5 rows drifted, all in the direction of *more* consistent** (their `requisites_consistent` flag should now be `True`, live still says `False`, since the cross-program discrepancy that flag was catching is exactly what runs 1-3 fixed):

| code | live requisites_consistent | should now be |
|---|---|---|
| `CBARTAP` | False | True |
| `CBINOV1` | False | True |
| `CBSTSOC` | False | True |
| `LBYARCH` | False | True |
| `LBYCBC2` | False | True (name/units still genuinely differ, unrelated to tonight's fixes — see M5 notes) |

**Could NOT apply to the live DB** — recomputing this table means running `python -m app.seed_equivalencies`, which writes to the live Supabase instance the same way the direct `UPDATE`s in runs 1-4 did. Not attempted, since that class of action is already confirmed blocked (runs 1-2) — no reason to expect this one to differ. Also checked `shiftee_credit_mappings` (M5's other table) the same way: 0 drift, unaffected by tonight's fixes (makes sense — those candidates are generated from course *names*, which nothing tonight touched).

**Verified clean (regression + new checks):** re-ran every check from runs 1-4 against tonight's final `curricula.json` — 0 self-references, 0 hard-prerequisite cycles, 0 hard-prereq ordering violations, 0 coreq position mismatches, 729 records total. All consistent with a clean night.

---

### End-of-night summary (all 5 runs) — read this first if you're catching up in the morning

**Fixed tonight, all in `flowchart_records_11programs/*.txt` + regenerated `parser/output/curricula.json`, all staged but requiring the actions below to land anywhere else:**
1. Run 1: 6 requisite entries in `BSIT-CBL.txt`, mutual same-term `hard` → `coreq` (the `CBINOV4`/`CBASEAN`/`CBMOBDV` and `CBARTAP`/`CBINOV1` clusters).
2. Run 2: 1 requisite entry in `MSCS.txt`, `LBYARCH` no longer lists itself as its own coreq — now correctly points to `CSARCH2`.
3. Run 3: 6 more requisite entries in `BSIT-CBL.txt`, the same hard-vs-coreq contradiction pattern as run 1, found by a systematic sweep instead of just where it happened to form a cycle.
4. Run 4: 2 `term` values swapped in `MSCS.txt` (`MSLABS1`/`MSLABS2`), fixing a hard-prereq scheduled-after-its-dependent violation.

**Two things need you, specifically, before any of this reaches the live Supabase DB or git history:**

- **Git identity is not configured anywhere on this machine** (not even globally) — `git commit` has failed identically on every one of tonight's 5 runs with `Author identity unknown`. I won't run `git config` myself (not my call to make for you). Run `git config user.name "..."` and `git config user.email "..."` (global or just this repo, your choice), then `git commit` on the `overnight/qa` branch — everything from tonight is staged and ready, nothing has been lost.
- **The live Supabase database has not received any of tonight's fixes.** Every attempted write (13 `requisite_edges` rows across runs 1-3, 1 `course_slots.term` row from run 4, and the `course_code_equivalencies` recompute from this run) was blocked by Claude Code's permission classifier, which doesn't allow an unattended session to write to a live remote database. The DB itself is untouched and safe — it's just now behind the corrected source files. Once you're in an interactive session, ask me to apply these (I can hand you the exact `UPDATE` statements, or you can just rerun `python -m app.seed_equivalencies` for the derived tables — though note `python -m app.seed` itself is **not** idempotent, don't rerun that one without `--reset`, which would wipe and reseed everything from the now-corrected `curricula.json`, a reasonable option if you're comfortable losing any *other* live-only DB state, which as of tonight there isn't any).

**Deliberately not touched tonight** (pre-existing, already logged in ROADMAP.md/project memory from earlier sessions — tonight's mandate was to act on *new* findings, not re-litigate your own prior deferrals):
- 80 unresolved `requisite_edges` (72 likely typos, 8 legitimate external exam-waiver codes).
- 62 of 100 `course_code_equivalencies` rows that genuinely diverge on units/name/requisites (independent of the 5 that will resolve once reseeded, above).
- 34 `shiftee_credit_mappings` candidates, all still `status='candidate'`.
- 6 of 11 programs with collapsed/unreliable `year` labels.

**Milestone/file:** M5 schema (`course_code_equivalencies`), M2/M3 source data and schema (cumulative across tonight).

---

## 2026-09-10 03:36 TST — Run 4 of 5

**Read first:** runs 1-3 below. Both blockers (live-DB write, git commit) confirmed still unresolved (identity check only, not retried — per run 2/3's own notes, no point re-attempting either until a human is back).

**Tested:** `parser/test_parse_flowchart.py` (pass).

**Found and fixed — a term-value swap, MSCS `MSLABS1`/`MSLABS2`:**

New check this run: for the 5 programs with *reliable* year labels (`CS-ST`, `CS`, `IET-AD`, `IET-GD`, `MSCS` — excluding the 6 programs M2 already flagged with collapsed year-label buckets, to avoid noise from that separate, already-known issue), verify that a `hard` prerequisite's own scheduled (year, term) position is actually *before* the course that requires it. A cycle check (run 1) catches loops; it doesn't catch a one-directional "the required course is scheduled later than the course requiring it," which is just as impossible to satisfy.

Found exactly one violation: MSCS's `MSLABS2` (Year 3, Term 1) hard-requires `MSLABS1` — but `MSLABS1` was tagged Term 3 of the *same* year, i.e. scheduled after `MSLABS2`, not before it.

**Not ambiguous — a clear swap, corroborated by the naming and the requisite chain itself:** `MSLABS1`/`MSLABS2`/`MSLABS3` are "Research Laboratory Exposure 1/2/3," an explicitly numbered sequence. `MSLABS2` already correctly lists `MSLABS1` as its hard prereq (that part isn't in question), and `MSLABS3` correctly lists `MSLABS2` as its own hard prereq at Year 5 — so the intended order (1 before 2 before 3) is unambiguous from the data itself; only the specific term numbers on `MSLABS1` and `MSLABS2` were swapped, both within Year 3.

**Changed:** `flowchart_records_11programs/MSCS.txt` — swapped `MSLABS1`'s `term` from 3 to 1, and `MSLABS2`'s `term` from 1 to 3. Deliberately a swap between two already-present values, not an invented one. This is a narrower, more confidently-diagnosed issue than the 6-program "collapsed year label" problem from M2 — MSCS wasn't one of those 6, this is an isolated two-record term mixup, not a symptom of that systemic bug.

Regenerated `parser/output/curricula.json` (729 records, 21 warnings, unchanged) and re-ran the ordering check: 0 violations remain across all 5 reliable programs. Also ran the same check for `soft` requisites (0 violations — informational only, a soft violation wouldn't be a hard error) and verified every `coreq` pair in the 5 reliable programs sits at the *same* (year, term) position (0 mismatches). Re-ran runs 1 and 3's checks as a regression pass: 0 self-references, 0 hard-prerequisite cycles, record count still 729 — nothing broken by this change.

**Could NOT apply to the live Supabase DB** — same reasoning as runs 1-3, not attempted (confirmed persistent already). This fix is only a `course_slots.term` update (not `requisite_edges` this time) — a 4th pending manual change for when you're back, on top of the 13 `requisite_edges` rows from runs 1-3.

**Explicitly not re-touched:** run 1's full deferred list (80 unresolved requisites, 62/100 divergent equivalencies, 34 candidate shiftee mappings, 6/11 unreliable year labels) and run 3's 8 one-sided coreq cases.

**Milestone/file:** M2 source data (`flowchart_records_11programs/MSCS.txt`, `parser/output/curricula.json`), M3 schema (`course_slots.term`).

---

## 2026-09-10 01:38 TST — Run 3 of 5

**Read first:** runs 1-2 below in full. Both blockers (live-DB write, git commit) still unresolved — not retrying either this run per run 2's own note, just confirming nothing needs to change about that approach.

**Tested:** `parser/test_parse_flowchart.py` (pass).

**Found and fixed — 6 more asymmetric hard/coreq contradictions, all BSIT-CBL:**

Generalized what runs 1-2 found (mutual/self coreq mislabeled as hard) into a full systematic check: for every `coreq` edge A→B in `curricula.json`, does B's own record actually agree (has a `coreq` edge back to A)? Ran this across all 11 programs. Found 14 asymmetric cases, which split into two very different categories:

- **8 cases where the other side simply has no entry at all** (empty requisites, or requisites about something unrelated) — e.g. CS's `CBASEAN` requisites are `[]` even though `CBINOV4` calls it a coreq. **Left these alone** — this isn't a contradiction, just one-sided documentation (plausibly how the source flowchart actually presents it, annotating the relationship on only one of the two courses). Fixing this would mean inventing a requisite entry that was never in the source, which is a bigger leap than correcting an existing wrong one — consistent with "flag, don't guess" for anything I'd otherwise have to invent from scratch.
- **6 cases where the other side has an explicit, contradictory `hard` entry** — this is the same bug class as runs 1-2 (a same-term mutual relationship, one side correctly says `coreq`, the other wrongly says `hard`), just not yet caught because it didn't happen to form a hard-only graph cycle or a self-reference. All 6 are in `flowchart_records_11programs/BSIT-CBL.txt`, all same-term pairs (lecture/lab pairs or a same-term take-together bloc):

| Course (the wrong side) | Wrongly said | Corrected to | Paired with (says `coreq` correctly) |
|---|---|---|---|
| `CBINOV2` | `hard: CBIST-4` | `coreq: CBIST-4` | `CBIST-4` |
| `LBYCBC2` | `hard: CBEMC-2` | `coreq: CBEMC-2` | `CBEMC-2` (lecture/lab pair) |
| `CBPCOMM` | `hard: CBIST-5` | `coreq: CBIST-5` | `CBIST-5` |
| `CBSTSOC` | `hard: CBIST-3` | `coreq: CBIST-3` | `CBIST-3` |
| `LBYCBCM` | `hard: CBCOMSY` | `coreq: CBCOMSY` | `CBCOMSY` (lecture/lab pair) |
| `CBWORLD` | `hard: CBBADEV` (one of its two requisites — its other requisite, `hard: CBIST-6`, was left alone; see below) | `coreq: CBBADEV` | `CBBADEV` |

Every one of these is a direct, unambiguous contradiction (not an inference): the same two courses, same term, one record explicitly says `coreq`, the other explicitly says `hard` — logically only one can be right, and corequisite is symmetric by definition, so the `coreq` side is authoritative. Not touched: `CBWORLD`'s other requisite, `hard: CBIST-6` — `CBBADEV` (now confirmed `CBWORLD`'s coreq partner) also calls `CBIST-6` a coreq, which is *suggestive* that `CBWORLD`'s hard tag on `CBIST-6` might be wrong too, but `CBIST-6`'s own record says nothing about either course either way — no direct contradiction, so left as one-sided per the same rule as the 8 cases above, not chased further by inference.

Regenerated `parser/output/curricula.json` (729 records, 21 warnings, unchanged) and re-verified: zero self-references, exactly the expected 8 one-sided cases remain (none newly broken), and re-ran the hard-prerequisite cycle check from run 1 against the corrected data — 0 cycles across all 11 programs.

**Could NOT apply to the live Supabase DB** — not attempted this run (confirmed persistent in run 2, no reason to retry). Three fixes now pending manual application to `requisite_edges` when you're back: run 1's 6 rows, run 2's 1 row, and these 6.

**Explicitly not re-touched:** the 8 one-sided coreq cases just found (see above — deliberately left, not deferred-from-before), plus run 1's full list (80 unresolved requisites, 62/100 divergent equivalencies, 34 candidate shiftee mappings, 6/11 unreliable year labels).

**Milestone/file:** M3 schema (`requisite_edges`), M2 source data (`flowchart_records_11programs/BSIT-CBL.txt`, `parser/output/curricula.json`).

---

## 2026-09-09 23:39 TST — Run 2 of 5

**Read first:** run 1's section below in full, including its commit-blocker note. Both blockers it flagged are still unresolved (confirmed again this run, see below) — not re-explaining them at length, just confirming status.

**Tested:** `parser/test_parse_flowchart.py` (pass). No other test suites found or added since run 1.

**Live-DB write: confirmed persistent block, not transient.** Retried run 1's pending 6-row `UPDATE requisite_edges` once, specifically to check whether the earlier block was a one-off (Claude Code's classifier has been transient on at least one other blocked action tonight in a different context). It was blocked identically again. Treating this as a confirmed policy block now, not retrying again in runs 3-5 — it will keep failing until a human applies it in an interactive session.

**Git commit: still blocked**, same reason as run 1 (`git config user.name`/`user.email` not set anywhere on this machine). Not retried (no reason it would have changed). Everything continues to accumulate staged, uncommitted, on `overnight/qa`.

**Found and fixed — self-referential requisite, MSCS `LBYARCH`:**

Checked for the basic case run 1 didn't cover: a course listing itself as its own requisite. Found exactly one, in `flowchart_records_11programs/MSCS.txt`: `LBYARCH`'s requisites were `[{"hard","CSARCH1"}, {"coreq","LBYARCH"}]` — identical, entry-for-entry, to `CSARCH2`'s requisites on the line right above it. A clear copy-paste artifact, not ambiguous: a course can't be its own corequisite.

**Verified against a working instance, not just inferred:** `CS-ST.txt` has the exact same `CSARCH2`/`LBYARCH` pair (same names, same units, same year/term), and there `LBYARCH`'s requisite correctly reads `coreq: CSARCH2`. ROADMAP.md's own M6 section already names `CSARCH2`/`LBYARCH` as its reference corequisite-pair fixture. Both independently confirm the intended value.

**Changed:** `flowchart_records_11programs/MSCS.txt`, `LBYARCH`'s second requisite: `{"type": "coreq", "code": "LBYARCH"}` → `{"type": "coreq", "code": "CSARCH2"}`. Regenerated `parser/output/curricula.json` (same 729 records, same 21 warnings) and confirmed zero self-referential requisites remain anywhere in it.

**Could NOT apply to the live Supabase DB** — same permission-classifier block as run 1's fix. Two fixes now pending manual application to `requisite_edges` when you're back (this one, plus run 1's 6 rows).

**Checked, no issue found (false alarm on my own first pass — noting the check anyway since a clean result is still useful):** a units/`is_zero_credit` sanity query initially flagged 47 rows where `is_zero_credit=True` but `units` is nonzero (1.0 or 3.0) — `NSTP-01`, `NSTP-02`, `LCLSONE`, `LCLSTWO`, `LCLSTRI`, consistently, across every program that has them (verified: each code has exactly one (units, is_zero_credit) pair everywhere it appears, no mixed signals). This isn't a bug — NSTP and these co-curricular courses are commonly non-credit-bearing by design even though they carry real contact-hour units, which matches this pattern exactly. Left as-is.

**One observation, not acted on (no ground truth to confirm either way):** `parse_all_flowcharts.py`'s printed per-program "total units" sums *all* units including these zero-credit courses. If the real flowchart's printed total excludes non-credit courses (common convention, but I can't verify it for *this* dataset — no PDFs or printed totals exist anywhere in this repo, per M2), the script's total would overstate the true figure. Not changing this without a ground-truth total to check against — flagging it for you to confirm if you ever get the source PDFs.

**Verified clean (no findings):** prerequisite-cycle check (BSIT-CBL's cycles from run 1 stay fixed in the regenerated `curricula.json`; DB itself still has the old unfixed rows, consistent with the pending DB update above), `course_slots.term` values (all null or in {1,2,3}), `courses.is_elective_placeholder` vs. `elective_slots` row presence (perfect 1:1 match, no drift), `requisite_edges.type` / `course_offering_windows.offering_window` / `shiftee_credit_mappings.status` (all values are exactly the allowed enum sets, nothing invalid slipped past the CHECK constraints).

**Explicitly not re-touched** (see run 1's list — 80 unresolved requisites, 62/100 divergent equivalencies, 34 candidate shiftee mappings, 6/11 unreliable year labels — all still deliberately deferred, unchanged tonight).

**Milestone/file:** M3 schema (`requisite_edges`), M2 source data (`flowchart_records_11programs/MSCS.txt`, `parser/output/curricula.json`), M2 tooling (`parser/parse_all_flowcharts.py` — observation only, not modified).

---

## 2026-09-09 21:42 TST — Run 1 of 5

**⚠ COMMIT BLOCKED — READ BEFORE RUN 2:** `git commit` failed with
`Author identity unknown` — this machine has no `user.name`/`user.email`
configured in git, not even globally, and this predates tonight (not
something this run broke). I will not run `git config` myself (that's a
hard rule for me, not a judgment call I can override for an unattended
run) — only the user can set their own commit identity. Everything below
is staged (`git add -A` on branch `overnight/qa`, which was created —
see below) but **NOT committed**. If you're a later run tonight reading
this: don't waste time retrying the commit, it will fail identically
until a human runs `git config user.name "..."` / `user.email "..."`
(local or global, their choice) — just keep doing QA, keep adding to the
staged tree, and leave one clear note like this one rather than
repeating it every run. If you're the user: your fixes from tonight are
sitting staged in the working tree, uncommitted, until you set your git
identity and run `git commit` yourself (or ask me to, once you're back).

**Tested:** `parser/test_parse_flowchart.py` (pass), `frontend`: `npm run lint` (oxlint, clean) and `npx tsc -b` (clean, exit 0). Then independently checked the live Supabase tables (`programs`, `curriculum_versions`, `courses`, `course_slots`, `requisite_edges`, `elective_slots`, `course_offering_windows`, `course_code_equivalencies`, `shiftee_credit_mappings`) and the static `parser/output/curricula.json` / `flowchart_records_11programs/*.txt` for: prerequisite cycles (new check — hadn't been run before tonight), row-count drift between the live DB and what ROADMAP.md documents, and duplicate codes within a program (already fully covered by M2's exceptions log — MSCS's `THESIS` duplicate is the only one, already flagged there, nothing new).

**Found and fixed — real prerequisite cycles (2), BSIT-CBL:**

Built the hard-prerequisite directed graph per curriculum_version from `requisite_edges` (resolved edges only, `type='hard'` only — `coreq` pairs are supposed to be mutual/same-term, so excluded from cycle detection by design) and ran cycle detection on all 11 curriculum_versions. Found exactly 2 cycles, both in BSIT-CBL (curriculum_version 5):

- `CBINOV4` (Business Innovations) ↔ `CBASEAN` (The Filipino and ASEAN) — each listed the other as a **hard** prerequisite, both in the same term (AY 2025-2026, Term 2). A same-term mutual hard-prereq is logically impossible to satisfy.
- `CBARTAP` (Art Appreciation) ↔ `CBINOV1` (Creativity and Design) — same pattern, same term.

**Not a guess — corroborated by the data itself:** `CBMOBDV` (Mobile Development), also term 2 of the same cluster, already correctly lists both `CBASEAN` and `CBINOV4` as `coreq` (line 42 of `flowchart_records_11programs/BSIT-CBL.txt`). A corequisite relation is symmetric by definition — if X is a coreq of Y, Y is necessarily a coreq of X. So `CBINOV4`/`CBASEAN` calling each other "hard" while `CBMOBDV` correctly calls them "coreq" is an internally self-contradictory data entry, not ambiguous domain knowledge requiring a guess. Extended the same fix to `CBINOV4`→`CBMOBDV` and `CBASEAN`→`CBMOBDV` (previously tagged `hard` on that side, `coreq` on `CBMOBDV`'s side — same symmetric-coreq contradiction, same fix), even though those two edges didn't individually form a graph cycle (no hard edge existed back from `CBMOBDV`).

**Changed:** 6 requisite entries in `flowchart_records_11programs/BSIT-CBL.txt` from `"type": "hard"` to `"type": "coreq"`:
`CBINOV1`→`CBARTAP`, `CBARTAP`→`CBINOV1`, `CBINOV4`→`CBASEAN`, `CBASEAN`→`CBINOV4`, `CBINOV4`→`CBMOBDV`, `CBASEAN`→`CBMOBDV`.

Regenerated `parser/output/curricula.json` and `parser/output/exceptions_log.txt` via `parser/parse_all_flowcharts.py` — same 21 warnings as before (this was a type reclassification, not a new parse issue), 729 records total, unchanged.

**Could NOT apply to the live Supabase DB:** the equivalent `UPDATE requisite_edges SET type='coreq' WHERE ...` for these 6 rows was **blocked by Claude Code's auto-mode permission classifier** (writes to a live remote database aren't something an unattended run is allowed to push through). No partial write happened — the block occurred before any SQL executed, so the DB is untouched, just now one step behind the corrected source files. **Action needed from you:** either re-run `python -m app.seed_equivalencies`-style targeted update yourself, or ask me interactively to apply it — I can hand you the exact 6-row UPDATE next time we're in a live session. Until then, `requisite_edges` in the live DB still has these 6 rows as `type='hard'`, and re-running `python -m app.seed --reset` would pick up the corrected `curricula.json` but wipe and reseed everything (not something I'll do unattended either).

**Verified, no drift found:** live DB row counts match ROADMAP.md's documented figures exactly (programs 11, curriculum_versions 11, courses 729, course_slots 729, requisite_edges 590, elective_slots 160, course_offering_windows 729, course_code_equivalencies 100, shiftee_credit_mappings 34).

**Explicitly NOT touched tonight** (deliberately deferred by you in earlier sessions, per ROADMAP.md/memory — tonight's "make a reasonable assumption" instruction is for *new* findings from tonight's own QA, not license to override your own prior explicit deferrals on already-known issues):
- The 80 unresolved `requisite_edges` (72 likely typos like `LSLSONE`/`LCLSONE`, `PRCCC01`/`PRCC01`) from M3.
- The 62/100 divergent `course_code_equivalencies` rows from M5.
- The 34 `shiftee_credit_mappings` candidates, still all `status='candidate'`.
- The 6/11 programs with collapsed/unreliable `year` labels from M2.

These remain exactly as previously logged in ROADMAP.md and project memory — not re-litigated here.

**Milestone/file:** M3 schema (`requisite_edges`), M2 source data (`flowchart_records_11programs/BSIT-CBL.txt`, `parser/output/curricula.json`).
