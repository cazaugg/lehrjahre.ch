"""Per-company (tenant) database routing.

The global *control database* (configured via ``SQLALCHEMY_DATABASE_URI``)
holds only the routing layer: the ``company`` registry and the
``user_routing`` index that maps a login e-mail address to a user inside a
company database. Every company owns its own SQLite file
(``<company folder>/app.db``) which contains ALL company data, including the
full user records (credentials, contacts, session state) and every
operational table (``user``, ``user_relation``, ``project``, ``participation``,
``eval``, ``grades``, ``documents``, ``knowledge``).

The SQLAlchemy session (see ``backend.models.RoutingSession``) resolves the
tenant engine per statement through :func:`engine_for_tables`; the active
company is a per-request context (see :func:`set_tenant_company`).
"""

from __future__ import annotations

import contextvars
import os
from contextlib import contextmanager

from flask import current_app

from backend.storage import slugify_company

TENANT_TABLES = frozenset(
    {
        "user",
        "user_relation",
        "project",
        "participation",
        "eval",
        "grades",
        "documents",
        "knowledge",
    }
)
CONTROL_TABLES = frozenset({"company", "user_routing"})

_APP_EXT_KEY = "lehrjahre_tenants"

# Active tenant company per request/context. Set by auth.get_current_user
# (and explicitly by the CLI/tests/seed); cleared before every request.
_tenant_company: contextvars.ContextVar = contextvars.ContextVar(
    "lehrjahre_tenant_company", default=None
)


def set_tenant_company(company) -> None:
    """Activate the tenant database of `company` for the current context."""
    _tenant_company.set(company)


def clear_tenant_company() -> None:
    _tenant_company.set(None)


def has_tenant_context() -> bool:
    return _tenant_company.get() is not None


def current_company():
    """Return the active company object (control DB row)."""
    company = _tenant_company.get()
    if company is None:
        raise RuntimeError(
            "No company tenant context is active; cannot resolve company "
            "database."
        )
    return company


def current_company_optional():
    return _tenant_company.get()


def company_slug(company) -> str:
    return slugify_company(company.name)


def company_base_dir(company) -> str:
    """Absolute path of the company's own data folder."""
    root = os.path.realpath(current_app.config["COMPANY_ROOT"])
    base = os.path.realpath(os.path.join(root, company_slug(company)))
    if not base.startswith(root + os.sep):
        raise ValueError("Invalid company directory path")
    return base


def tenant_db_path(company) -> str:
    """Absolute path of the company's SQLite database file."""
    return os.path.join(company_base_dir(company), "app.db")


def tenant_documents_dir(company) -> str:
    """Absolute path of the company's documents directory."""
    return os.path.join(company_base_dir(company), "documents")


def _chmod_path(path: str, mode: int) -> None:
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def ensure_company_folder(company) -> str:
    """Create the company folder and its documents directory."""
    from backend.storage import get_company_root

    root = get_company_root()
    base = company_base_dir(company)
    documents_dir = os.path.join(base, "documents")
    for path in (root, base, documents_dir):
        os.makedirs(path, mode=0o750, exist_ok=True)
        _chmod_path(path, 0o750)
    return base


def _state():
    app = current_app._get_current_object()
    return app.extensions.setdefault(_APP_EXT_KEY, {"engines": {}})


def reset_engine_cache() -> None:
    """Drop cached tenant engines (e.g. after deleting a company folder)."""
    _state()["engines"].clear()


def tenant_engine(company):
    """Return (creating if needed) the SQLAlchemy engine for this company's DB.

    The first access creates the company folder, the ``app.db`` schema and
    writes restrictive file permissions. Schema columns are ensured
    idempotently on every engine creation.
    """
    state = _state()
    key = company_slug(company)
    engine = state["engines"].get(key)
    if engine is not None:
        return engine

    from sqlalchemy import create_engine

    from backend.models import db, ensure_tenant_columns, tenant_tables

    ensure_company_folder(company)
    db_path = tenant_db_path(company)
    engine = create_engine(f"sqlite:///{db_path}")
    if not os.path.exists(db_path):
        db.metadata.create_all(bind=engine, tables=tenant_tables())
    ensure_tenant_columns(engine)
    _chmod_path(db_path, 0o640)

    state["engines"][key] = engine
    return engine


def create_company_schema(company):
    """Create the company folder, ``app.db`` schema and documents directory."""
    return tenant_engine(company)


@contextmanager
def tenant_context(company):
    """Explicitly activate a tenant DB (CLI, tests, seeding)."""
    token = _tenant_company.set(company)
    try:
        yield company
    finally:
        _tenant_company.reset(token)


def engine_for_tables(table_names):
    """Resolve the engine a statement targeting `table_names` must use.

    Returns ``None`` for control tables (the default control engine is used,
    as configured via ``SQLALCHEMY_DATABASE_URI``). Tenant tables route to
    the active company's engine. A statement touching both control and
    tenant tables is a programming error.
    """
    tables = {
        item if isinstance(item, str) else (getattr(item, "name", None) or "")
        for item in table_names
    }
    if any(table in TENANT_TABLES for table in tables):
        if any(table in CONTROL_TABLES for table in tables):
            raise RuntimeError(
                "A query mixes control tables (company/user_routing) with "
                f"tenant tables: {sorted(tables)}"
            )
        return tenant_engine(current_company())
    if any(table in CONTROL_TABLES for table in tables):
        return None
    # Unknown table names (e.g. aliases) fall back to the control engine.
    return None
