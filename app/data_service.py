"""
Data loading, validation and merging.

Startup pipeline (see DataService.load):
  1. Read each CSV as TEXT (so we can detect invalid values ourselves).
  2. Validate: required columns, duplicate IDs, numeric ranges, categories.
       - Structural problems (missing file/column, duplicate IDs) -> DataValidationError
         and the API reports "unavailable" instead of serving wrong numbers.
       - Bad VALUES (out of range, not a number) -> turned into "missing" + a warning.
  3. Merge the one-row-per-student files on `student_id` (left join on students).
     interventions.csv stays separate (a student can have many records).
     The synthetic outcome labels are validated but NOT merged or used.
  4. Compute scores, risk levels and segments.
"""
from __future__ import annotations

import logging
import os
import tempfile
import threading
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from .config import (DATASET_FILES, DATASET_SCHEMAS, FEATURE_DATASETS, INTERVENTION_STATUSES,
                     INTERVENTION_TYPES, LABEL_DATASETS, NA_VALUES, OPEN_INTERVENTION_STATUSES,
                     SCORE_CONFIG, get_data_dir)
from .risk_service import assess_student, assign_segment
from .scoring import compute_scores
from .utils import is_missing

logger = logging.getLogger("smart_campus")


class DataValidationError(Exception):
    """Raised when the datasets are structurally unusable."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


class PersistenceError(Exception):
    """Raised when an intervention change could not be written to disk."""


class NotFoundError(Exception):
    pass


def _strip(value):
    return value.strip() if isinstance(value, str) else value


def _sample(ids: pd.Series, n: int = 3) -> str:
    sample = ", ".join(map(str, ids.head(n)))
    return f"{sample}{', ...' if len(ids) > n else ''}"


class DataService:
    def __init__(self, data_dir: str | Path | None = None):
        self.data_dir = get_data_dir(data_dir)
        self._write_lock = threading.RLock()
        self.warnings: list[str] = []
        self.dataset_info: dict[str, dict] = {}
        self.student_skills = pd.DataFrame()  # Multiple skill records per student
        self.student_skills = pd.DataFrame()       # merged, one row per student (index = student_id)
        self.interventions = pd.DataFrame()
        self.risk_details: dict[str, dict] = {}
        self.loaded_at: str | None = None
        self.feature_columns: list[str] = []

    # ------------------------------------------------------------------ loading
    def _read_dataset(self, name: str, errors: list[str]) -> pd.DataFrame | None:
        schema = DATASET_SCHEMAS[name]
        path = self.data_dir / DATASET_FILES[name]
        if not path.exists():
            errors.append(f"{name}: file '{path.name}' not found in {self.data_dir}")
            return None
        try:
            df = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=NA_VALUES)
        except Exception as exc:  # unreadable / malformed CSV
            errors.append(f"{name}: could not read '{path.name}' ({exc.__class__.__name__}: {exc})")
            return None

        df.columns = [str(c).strip() for c in df.columns]
        missing_cols = [c for c in schema["required"] if c not in df.columns]
        if missing_cols:
            errors.append(f"{name}: '{path.name}' is missing required column(s): {', '.join(missing_cols)}")
            return None

        extra = [c for c in df.columns if c not in schema["required"]]
        if extra:
            self.warnings.append(f"{name}: ignoring unexpected column(s): {', '.join(extra)}")
        df = df[schema["required"]].copy()
        for col in df.columns:
            df[col] = df[col].map(_strip)

        # student_id: normalise, drop blank
        df["student_id"] = df["student_id"].map(lambda v: v.upper() if isinstance(v, str) else v)
        blank = df["student_id"].isna()
        if blank.any():
            self.warnings.append(f"{name}: dropped {int(blank.sum())} row(s) with a blank student_id")
            df = df[~blank].copy()

        self._check_values(name, df, schema)
        self.dataset_info[name] = {
            "file": path.name, "rows": int(len(df)), "columns": list(df.columns),
            "role": ("synthetic labels (not used for scoring)" if name in LABEL_DATASETS
                     else "separate history table" if name == "interventions" else "student features"),
        }
        return df

    def _check_values(self, name: str, df: pd.DataFrame, schema: dict) -> None:
        """Coerce numeric/categorical columns in place; bad values become missing + a warning."""
        for col, (lo, hi) in schema["ranges"].items():
            raw = df[col]
            num = pd.to_numeric(raw, errors="coerce")
            not_numeric = raw.notna() & num.isna()
            out_of_range = num.notna() & ((num < lo) | (num > hi))
            if not_numeric.any():
                self.warnings.append(
                    f"{name}.{col}: {int(not_numeric.sum())} non-numeric value(s) treated as missing "
                    f"(e.g. {_sample(df.loc[not_numeric, 'student_id'])})")
            if out_of_range.any():
                self.warnings.append(
                    f"{name}.{col}: {int(out_of_range.sum())} value(s) outside {lo}-{hi} treated as missing "
                    f"(e.g. {_sample(df.loc[out_of_range, 'student_id'])})")
            num[out_of_range] = float("nan")
            df[col] = num

        for col, allowed in schema["categories"].items():
            lookup = {a.lower(): a for a in allowed}
            mapped = df[col].map(lambda v: lookup.get(v.lower()) if isinstance(v, str) else None)
            unknown = df[col].notna() & mapped.isna()
            if unknown.any():
                self.warnings.append(
                    f"{name}.{col}: {int(unknown.sum())} unrecognised value(s) treated as missing "
                    f"(e.g. {_sample(df.loc[unknown, col])})")
            df[col] = mapped

    def load(self) -> "DataService":
        self.warnings, self.dataset_info = [], {}
        errors: list[str] = []
        raw = {name: self._read_dataset(name, errors) for name in DATASET_FILES}
        
        # Load detailed skills data separately (multiple rows per student)
        skills_path = self.data_dir / "source_sheets" / "student_skills.csv"
        try:
            self.student_skills = pd.read_csv(
                skills_path,
                dtype=str,
                keep_default_na=False,
            )
        except FileNotFoundError:
            self.student_skills = pd.DataFrame()
            self.warnings.append(
                f"Student skills dataset not found: {skills_path}"
            )
        except Exception as exc:
            self.student_skills = pd.DataFrame()
            self.warnings.append(
                f"Could not load student skills dataset: {exc}"
            )


        # Duplicate IDs
        for name, df in raw.items():
            if df is None:
                continue
            if name == "interventions":
                dup = df["intervention_id"][df["intervention_id"].duplicated()]
                if len(dup):
                    errors.append(f"interventions: duplicate intervention_id value(s): {_sample(dup)}")
            else:
                dup = df["student_id"][df["student_id"].duplicated()]
                if len(dup):
                    errors.append(f"{name}: duplicate student_id value(s): {_sample(dup)} "
                                  f"({int(df['student_id'].duplicated().sum())} extra row(s))")
        if errors:
            raise DataValidationError(errors)

        # Merge one-row-per-student datasets onto the students table
        master = raw["students"].copy()
        base_ids = set(master["student_id"])
        for name in FEATURE_DATASETS:
            df = raw[name]
            ids = set(df["student_id"])
            orphans = ids - base_ids
            absent = base_ids - ids
            if orphans:
                self.warnings.append(f"{name}: {len(orphans)} student_id(s) not in students file were ignored")
            if absent:
                self.warnings.append(f"{name}: {len(absent)} student(s) have no record (their fields stay empty)")
            master = master.merge(df, on="student_id", how="left", validate="one_to_one")

        self.feature_columns = [c for c in master.columns
                                if c not in DATASET_SCHEMAS["students"]["required"]]

        # Scores, risk, segments
        scores = compute_scores(master, SCORE_CONFIG)
        master = pd.concat([master, scores], axis=1)

        records = master.to_dict("records")
        risk_details, academic_levels, placement_levels = {}, [], []
        academic_points, placement_points, segments = [], [], []
        for rec in records:
            assessment = assess_student(rec)
            risk_details[rec["student_id"]] = assessment
            a, p = assessment["academic"], assessment["placement"]
            academic_levels.append(a["level"]); placement_levels.append(p["level"])
            academic_points.append(a["points"]); placement_points.append(p["points"])
            segments.append(assign_segment(rec["success_score"], a["level"], p["level"]))
        master["academic_risk_level"] = academic_levels
        master["academic_risk_points"] = academic_points
        master["placement_risk_level"] = placement_levels
        master["placement_risk_points"] = placement_points
        master["segment"] = segments

        # Data completeness per student (share of feature columns that have data)
        master["data_completeness_pct"] = (
            master[self.feature_columns].notna().mean(axis=1) * 100).round(1)

        master.index = master["student_id"].values
        master.index.name = None
        self.students = master
        self.risk_details = risk_details

        # interventions: separate table
        iv = raw["interventions"].copy()
        parsed = pd.to_datetime(iv["assigned_date"], errors="coerce", format="%Y-%m-%d")
        bad_dates = iv["assigned_date"].notna() & parsed.isna()
        if bad_dates.any():
            self.warnings.append(f"interventions.assigned_date: {int(bad_dates.sum())} invalid date(s) treated as missing")
        iv["assigned_date"] = parsed.dt.strftime("%Y-%m-%d")
        iv_orphans = set(iv["student_id"]) - base_ids
        if iv_orphans:
            self.warnings.append(f"interventions: {len(iv_orphans)} student_id(s) not found in students file")
        for col, allowed in (("intervention_type", INTERVENTION_TYPES), ("status", INTERVENTION_STATUSES)):
            unknown = iv[col].notna() & ~iv[col].isin(allowed)
            if unknown.any():
                self.warnings.append(f"interventions.{col}: {int(unknown.sum())} value(s) not in the known list")
        self.interventions = iv.reset_index(drop=True)

        self.loaded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        logger.info("Loaded %d students, %d interventions, %d warning(s)",
                    len(self.students), len(self.interventions), len(self.warnings))
        return self

    # ------------------------------------------------------------------ lookups
    def has_student(self, student_id: str) -> bool:
        return student_id.strip().upper() in self.students.index

    def student_row(self, student_id: str) -> dict:
        sid = student_id.strip().upper()
        if sid not in self.students.index:
            raise NotFoundError(f"Student '{student_id}' was not found.")
        return self.students.loc[sid].to_dict()

    def departments(self) -> list[str]:
        return sorted(self.students["department"].dropna().unique().tolist())

    def match_department(self, value: str | None) -> str | None:
        if not value:
            return None
        lookup = {d.lower(): d for d in self.departments()}
        return lookup.get(value.strip().lower())

    # ------------------------------------------------------------------ student CRUD (CSV-backed; no database required)
    def _persist_student_files(self, student_id: str, updates: dict, create: bool) -> None:
        """Stage all affected CSVs, then replace them. CSV files are the source of truth."""
        staged: list[tuple[str, str]] = []
        try:
            for name, filename in DATASET_FILES.items():
                if name == "interventions":
                    continue
                path = self.data_dir / filename
                columns = DATASET_SCHEMAS[name]["required"]
                if path.exists():
                    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
                else:
                    frame = pd.DataFrame(columns=columns)
                for col in columns:
                    if col not in frame.columns:
                        frame[col] = ""
                frame = frame[columns]
                if create:
                    row = {col: "" for col in columns}
                    row["student_id"] = student_id
                    for col, value in updates.items():
                        if col in row and value is not None:
                            row[col] = str(value)
                    frame = pd.concat([frame, pd.DataFrame([row], columns=columns)], ignore_index=True)
                else:
                    match = frame["student_id"].astype(str).str.upper() == student_id
                    if match.sum() != 1:
                        raise NotFoundError(f"Student '{student_id}' was not found in {filename}.")
                    for col, value in updates.items():
                        if col in columns and col != "student_id":
                            frame.loc[match, col] = "" if value is None else str(value)
                fd, tmp_name = tempfile.mkstemp(dir=str(self.data_dir), suffix=".tmp")
                with os.fdopen(fd, "w", newline="", encoding="utf-8") as handle:
                    frame.to_csv(handle, index=False)
                staged.append((tmp_name, str(path)))
            for tmp_name, final_path in staged:
                os.replace(tmp_name, final_path)
        except Exception as exc:
            for tmp_name, _ in staged:
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
            if isinstance(exc, (NotFoundError, ValueError)):
                raise
            logger.exception("Could not persist student CSV files")
            raise PersistenceError("The student record could not be saved to CSV files.") from exc

    def create_student(self, values: dict) -> dict:
        with self._write_lock:
            requested_id = str(values.get("student_id") or "").strip().upper()
            if requested_id:
                sid = requested_id
                if sid in self.students.index:
                    raise ValueError(f"Student ID '{sid}' already exists.")
            else:
                numeric_ids = [int(str(v)[3:]) for v in self.students.index
                               if str(v).startswith("STU") and str(v)[3:].isdigit()]
                next_num = max(numeric_ids, default=20260000) + 1
                sid = f"STU{next_num:08d}"
            record = {k: v for k, v in values.items() if k != "student_id"}
            self._persist_student_files(sid, {**record, "student_id": sid}, create=True)
            self.load()
            return self.student_row(sid)

    def update_student(self, student_id: str, values: dict) -> dict:
        sid = student_id.strip().upper()
        with self._write_lock:
            if sid not in self.students.index:
                raise NotFoundError(f"Student '{student_id}' was not found.")
            allowed = {col for name, schema in DATASET_SCHEMAS.items() if name != "interventions"
                       for col in schema["required"]} - {"student_id"}
            updates = {k: v for k, v in values.items() if k in allowed}
            if not updates:
                raise ValueError("Provide at least one editable student field.")
            self._persist_student_files(sid, updates, create=False)
            self.load()
            return self.student_row(sid)

    # ------------------------------------------------------------------ interventions (read)
    def student_interventions(self, student_id: str) -> list[dict]:
        sid = student_id.strip().upper()
        df = self.interventions[self.interventions["student_id"] == sid]
        return self._intervention_records(df)

    def _intervention_records(self, df: pd.DataFrame) -> list[dict]:
        df = df.sort_values(["assigned_date", "intervention_id"], ascending=[False, False],
                            na_position="last")
        names = self.students["student_name"].to_dict()
        depts = self.students["department"].to_dict()
        out = []
        for rec in df.to_dict("records"):
            rec["student_name"] = names.get(rec["student_id"])
            rec["department"] = depts.get(rec["student_id"])
            out.append(rec)
        return out

    def list_interventions(self, student_id=None, status=None, intervention_type=None,
                           date_from: date | None = None, date_to: date | None = None):
        df = self.interventions
        if student_id:
            df = df[df["student_id"] == student_id.strip().upper()]
        if status:
            df = df[df["status"] == status]
        if intervention_type:
            df = df[df["intervention_type"] == intervention_type]
        if date_from:
            df = df[df["assigned_date"] >= date_from.isoformat()]
        if date_to:
            df = df[df["assigned_date"] <= date_to.isoformat()]
        status_counts = df["status"].value_counts().to_dict()
        return self._intervention_records(df), status_counts

    # ------------------------------------------------------------------ interventions (write)
    def _persist_interventions(self, df: pd.DataFrame) -> None:
        """Atomic write: write a temp file, then replace the real file."""
        path = self.data_dir / DATASET_FILES["interventions"]
        columns = DATASET_SCHEMAS["interventions"]["required"]
        fd, tmp_name = tempfile.mkstemp(dir=str(self.data_dir), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", newline="", encoding="utf-8") as handle:
                df[columns].to_csv(handle, index=False)
            os.replace(tmp_name, path)
        except Exception as exc:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            logger.exception("Could not write interventions file")
            raise PersistenceError("The intervention could not be saved to disk.") from exc

    def add_intervention(self, student_id: str, intervention_type: str, assigned_date: date,
                         status: str, follow_up_notes: str) -> dict:
        sid = student_id.strip().upper()
        if sid not in self.students.index:
            raise NotFoundError(f"Student '{student_id}' was not found.")
        with self._write_lock:
            numbers = pd.to_numeric(self.interventions["intervention_id"].str.extract(r"(\d+)$")[0],
                                    errors="coerce")
            next_no = int(numbers.max()) + 1 if numbers.notna().any() else 1
            new = {
                "intervention_id": f"INT{next_no:04d}", "student_id": sid,
                "intervention_type": intervention_type, "assigned_date": assigned_date.isoformat(),
                "status": status, "follow_up_notes": follow_up_notes,
            }
            updated = pd.concat([self.interventions, pd.DataFrame([new])], ignore_index=True)
            self._persist_interventions(updated)   # only swap in-memory data if the write worked
            self.interventions = updated
        return self._intervention_records(updated[updated["intervention_id"] == new["intervention_id"]])[0]

    def update_intervention(self, intervention_id: str, status: str | None,
                            follow_up_notes: str | None) -> dict:
        iid = intervention_id.strip().upper()
        with self._write_lock:
            mask = self.interventions["intervention_id"] == iid
            if not mask.any():
                raise NotFoundError(f"Intervention '{intervention_id}' was not found.")
            updated = self.interventions.copy()
            if status is not None:
                updated.loc[mask, "status"] = status
            if follow_up_notes is not None:
                updated.loc[mask, "follow_up_notes"] = follow_up_notes
            self._persist_interventions(updated)
            self.interventions = updated
        return self._intervention_records(updated[updated["intervention_id"] == iid])[0]

    def open_interventions_for(self, student_id: str) -> list[dict]:
        sid = student_id.strip().upper()
        df = self.interventions[(self.interventions["student_id"] == sid) &
                                (self.interventions["status"].isin(OPEN_INTERVENTION_STATUSES))]
        return df.to_dict("records")

    # ------------------------------------------------------------------ health
    def health(self) -> dict:
        return {
            "datasets": {k: {"loaded": True, **v} for k, v in self.dataset_info.items()},
            "student_count": int(len(self.students)),
            "intervention_count": int(len(self.interventions)),
            "warning_count": len(self.warnings),
            "warnings": self.warnings,
            "loaded_at": self.loaded_at,
        }
