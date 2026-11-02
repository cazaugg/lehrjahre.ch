import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")
DOCUMENTS_DIR = os.path.join(DATA_DIR, "documents")
DB_PATH = os.path.join(DATA_DIR, "lehrjahre.db")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{DB_PATH}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DOCUMENTS_ROOT = os.environ.get("DOCUMENTS_ROOT", DOCUMENTS_DIR)
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024  # 20 MB max upload size

    # Cookie & Session security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"
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
