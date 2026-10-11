"""Shared test fixtures. Tests never touch the real data/ folder: they work on temporary copies."""
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import DATASET_SCHEMAS, DEFAULT_DATA_DIR
from app.main import create_app
from app.auth import get_current_user


@pytest.fixture(autouse=True)
def skip_auth_store_initialization(monkeypatch):
    """API tests use overridden identities and a temporary CSV directory."""
    monkeypatch.setattr("app.main.init_auth_store", lambda: None)


def working_student_count() -> int:
    """Number of students in the shipped working data (so tests keep passing as records are added)."""
    with open(DEFAULT_DATA_DIR / "students.csv", encoding="utf-8") as fh:
        return max(0, sum(1 for _ in fh) - 1)


def copy_data(dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    for f in DEFAULT_DATA_DIR.glob("*.csv"):
        if f.name == "interventions.csv":
            header = ",".join(DATASET_SCHEMAS["interventions"]["required"])
            (dest / f.name).write_text(f"{header}\n", encoding="utf-8")
        else:
            shutil.copy(f, dest / f.name)
    source_sheets = DEFAULT_DATA_DIR / "source_sheets"
    if source_sheets.exists():
        shutil.copytree(source_sheets, dest / "source_sheets")
    return dest


@pytest.fixture()
def client(tmp_path_factory):
    """Read-only client over a temp copy of the real CSV data."""
    data_dir = copy_data(tmp_path_factory.mktemp("data_readonly"))
    app = create_app(str(data_dir))
    app.dependency_overrides[get_current_user] = lambda: {"username": "test-admin", "role": "admin"}
    with TestClient(app) as c:
        c.data_dir = data_dir
        yield c


@pytest.fixture()
def data_dir(tmp_path):
    """A fresh, private copy of the real CSVs that a test may modify."""
    return copy_data(tmp_path / "data")


@pytest.fixture()
def writable_client(data_dir):
    app = create_app(str(data_dir))
    app.dependency_overrides[get_current_user] = lambda: {"username": "test-admin", "role": "admin"}
    with TestClient(app) as c:
        c.data_dir = data_dir
        yield c
