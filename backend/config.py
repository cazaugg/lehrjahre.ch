import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")
# Global control database: company registry + user->company routing index.
CONTROL_DB_PATH = os.path.join(DATA_DIR, "control.db")
# Each company owns its own folder: <company root>/<company-slug>/ with a
# dedicated app.db (tenant database) and a documents/ directory.
_DEFAULT_COMPANY_ROOT = os.environ.get("LEHRJAHRE_COMPANY_ROOT", DATA_DIR)


INSECURE_DEFAULT_SECRET = "dev-secret-key-change-in-production"


class Config:
    LEHRJAHRE_ENV = os.environ.get("LEHRJAHRE_ENV", "production").lower()
    IS_DEV = LEHRJAHRE_ENV == "development"
    DEBUG = os.environ.get("LEHRJAHRE_DEBUG", "0").lower() in {
        "1",
        "true",
        "yes",
    }
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{CONTROL_DB_PATH}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    COMPANY_ROOT = os.environ.get("LEHRJAHRE_COMPANY_ROOT", _DEFAULT_COMPANY_ROOT)
    # Built frontend (Vite output) served by Flask behind the reverse proxy.
    FRONTEND_DIST = os.environ.get(
        "LEHRJAHRE_FRONTEND_DIST",
        os.path.join(BASE_DIR, "frontend", "dist"),
    )
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024  # 20 MB max upload size

    # Cookie & Session security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "true").lower() == "true"
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    # Constants for MEM professions and trainer functions
    MEM_PROFESSIONS = [
        "Anlagen- und Apparatebauerin / Anlagen- und Apparatebauer EFZ",
        "Konstrukteurin / Konstrukteur EFZ",
        "Mechanikpraktikerin / Mechanikpraktiker EBA",
        "Produktionsmechanikerin / Produktionsmechaniker EFZ",
        "Polymechanikerin / Polymechaniker EFZ",
        "Automatikmonteurin / Automatikmonteur EFZ",
        "Automatikerin / Automatiker EFZ",
        "Elektronikerin / Elektroniker EFZ",
    ]

    TRAINER_FUNCTIONS = [
        "Administrator",
        "Berufsbildner",
        "Fachvorgesetzter",
        "Kursleiter",
        "Lehrer",
        "HR / Rekrutierung",
    ]
