import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")


def _load_dotenv(path: str) -> None:
    """Load KEY=VALUE lines from `path` into the process environment.

    Runs once at import so development runs (``npm run dev``, CLI helpers)
    pick up the deployment-style ``.env`` file. Variables that are already
    set in the environment (shell, Docker, tests) always win and are never
    overridden. Values keep their raw content (inline comments etc. are
    treated as part of the value to not break passwords).
    """
    if not path or not os.path.isfile(path):
        return
    try:
        with open(path, encoding="utf-8") as env_file:
            for line in env_file:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.lower().startswith("export "):
                    line = line[len("export "):]
                key, sep, value = line.partition("=")
                if not sep:
                    continue
                key = key.strip()
                value = value.strip()
                if (
                    len(value) >= 2
                    and value[0] == value[-1]
                    and value[0] in {'"', "'"}
                ):
                    value = value[1:-1]
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        pass


# Local deployment-style configuration file; compose.yaml reads it in
# production, everything else (dev server, CLI helpers) reads it here.
_load_dotenv(os.path.join(BASE_DIR, ".env"))


def _read_version_file() -> str:
    """Read the app version from the VERSION file (matches CHANGELOG.MD)."""
    try:
        with open(os.path.join(BASE_DIR, "VERSION"), encoding="utf-8") as fh:
            value = fh.read().strip()
        return value
    except OSError:
        return ""


APP_VERSION = _read_version_file()
# Optional build stamp injected via Docker build args (see compose.yaml).
GIT_SHA = os.environ.get("LEHRJAHRE_GIT_SHA", "")

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
    # Absolute public base URL used to build links in outgoing mails.
    LEHRJAHRE_PUBLIC_URL = os.environ.get(
        "LEHRJAHRE_PUBLIC_URL", "https://lehrjahre.ch"
    ).rstrip("/")
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024  # 20 MB max upload size

    # Outgoing mail (verification mails) via SMTP; MAIL_FROM is the
    # address the recipients answer to / see as sender.
    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USER = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_TIMEOUT = int(os.environ.get("SMTP_TIMEOUT", "20"))
    MAIL_FROM = os.environ.get("MAIL_FROM", "kontakt@lehrjahre.ch")
    MAIL_FROM_NAME = os.environ.get("MAIL_FROM_NAME", "lehrjahre.ch")
    # Development fallback: without SMTP_HOST, outgoing mail is written to
    # this file instead of being sent (development environments and tests).
    MAIL_DEV_OUTBOX = os.environ.get("MAIL_DEV_OUTBOX", os.path.join(DATA_DIR, "outgoing_mail.log"))
    SIGNUP_ENABLED = os.environ.get("SIGNUP_ENABLED", "1").lower() not in {
        "0",
        "false",
        "no",
    }
    # How long a verification link stays valid.
    SIGNUP_TOKEN_TTL_HOURS = int(os.environ.get("SIGNUP_TOKEN_TTL_HOURS", "24"))
    # How long a first-login invitation link stays valid (7 days).
    USER_INVITE_TTL_HOURS = int(os.environ.get("USER_INVITE_TTL_HOURS", "168"))

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
