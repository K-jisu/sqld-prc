import importlib

import pytest


def test_postgres_urls_use_installed_psycopg_driver():
    db = importlib.import_module("backend.database")
    url = db.database_url("postgresql://tester:local@localhost/test_db")
    assert url.drivername == "postgresql+psycopg"
    assert url.database == "test_db"


def test_missing_database_url_has_actionable_error(monkeypatch):
    db = importlib.import_module("backend.database")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValueError, match="DATABASE_URL"):
        db.database_url()


@pytest.mark.parametrize("url", ["invalid-secret-url", "mysql://user:private-value@host/db"])
def test_invalid_database_url_does_not_disclose_value(url):
    db = importlib.import_module("backend.database")
    with pytest.raises(ValueError) as error:
        db.database_url(url)
    assert url not in str(error.value)
    assert "private-value" not in str(error.value)


def test_neon_connection_requires_tls():
    db = importlib.import_module("backend.database")
    with pytest.raises(ValueError, match="sslmode"):
        db.database_url("postgresql://user:local@ep-example.aws.neon.tech/db")
    assert db.database_url("postgresql://user:local@ep-example.aws.neon.tech/db?sslmode=require").query["sslmode"] == "require"
