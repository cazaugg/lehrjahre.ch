# Changelog

## Unreleased

- **Frontend:** Added a read-only Word (`.docx`) preview in document views using lazy-loaded `docx-preview`; other binary files keep the existing open/download fallback.
- **Frontend:** Added a read-only PDF preview using the browser's native PDF viewer, plus a generated 2-page PDF example in the seed data.
- **Tooling:** Upgraded to Node.js 26 LTS and Python 3.14; refreshed frontend dependencies (Vite 8, Vue Router 5, Pinia 4) and backend dependencies (Flask 3.1, Werkzeug 3.1, argon2-cffi 25, pytest 9).
- **Tooling:** Switched backend environment and dependency management to uv (`pyproject.toml` + `uv.lock`); removed `backend/requirements.txt`.
- **Tooling:** Added root `npm run dev` to start Flask and Vite together, with free-port detection and automatic dependency bootstrap.
- **Frontend:** Added an "Alpha" badge to the login and sidebar branding to mark the build as an early prototype.
- **Seed data:** Expanded the knowledge base to 4 subjects with 20 pages (Fertigung & Automatisierung, Arbeitssicherheit, Werkstoffkunde, Zeichnen/Messtechnik).
- **Frontend:** Wissen view now groups pages under their subject instead of listing all entries flat; removed the redundant topic overview block (header already shows title and description).
- **Frontend:** Replaced the Markdown textarea with `md-editor-v3` (lazy-loaded, German toolbar labels, no external CDN assets). Read-only rendering still uses the existing markdown-it/KaTeX pipeline.

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
