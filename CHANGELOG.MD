# Changelog

## 0.1.0 - Initial Implementation

- **Backend (Flask & SQLite):**
  - Implemented SQLite schema (`user`, `user_relation`, `project`, `participation`, `eval`, `grades`, `documents`, `knowledge`).
  - Added Argon2 password hashing, session authentication, CSRF protection, and reverse proxy (`ProxyFix`) support.
  - Added company-scoped file and Markdown storage under `/data/documents/<company-slug>/` with path traversal protection.
  - Implemented REST endpoints `/api/auth`, `/api/user`, `/api/project`, `/api/implementation`, `/api/evaluation`, `/api/documents`, `/api/grades`, and `/api/knowledge`.
  - Added seed script (`backend/seed.py`) and API test suite (`backend/test_api.py`).
- **Frontend (Vue 3 & Vite, German UI):**
  - Created reusable CSS variables/base styles and Vue UI components (`AppLayout`, `StudentSelector`, `DocumentManager`, `MarkdownEditor`, `ModalDialog`).
  - Built views for `Projekte`, `Lerndokumentation` (`Noten & Prüfungen`, `Zeugnisse`, `Ausbildungsgespräche`, `Kursnachweise`, `Lernjournal`), `Wissen` (`Thema -> Seite`), `Personen` (`Vorgesetzte`, `Lernende / Admin / Vertrag / Bewerbung`), and `Account` (`Kontaktangaben`, `Passwort`, `Foto`).
