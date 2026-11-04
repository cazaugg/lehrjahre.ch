# Changelog

## Unreleased

- **Backend:** Added a `company` table and moved users from the free-text `company` column to a mandatory `company_id` foreign key. Company membership cannot be changed through the API.
- **Backend:** Enforced that a user's `company_email` matches the company's `email_domain`. New users inherit the company address when none is supplied.
- **Tooling:** Added `backend.companies` CLI (`add`, `list`) for provisioning companies and a startup migration for existing SQLite databases.
- **Frontend:** Added a domain hint to the create-user form.
- **Security:** Enforced company isolation for projects, including hiding authorless projects and reassigning projects before user deletion. Evaluations and implementation reports no longer accept foreign-company supervisor or participation references, and profile pictures must be documents owned by the target user.
- **Security:** Project tree context no longer grants edit/delete rights: supervisors can manage only their own projects and projects of their learners. Learners can submit reports only for projects they directly participate in. Supervisors can now also edit/delete their own certificates.
- **Frontend:** Added a read-only Word (`.docx`) preview in document views using lazy-loaded `docx-preview`; other binary files keep the existing open/download fallback.
- **Frontend:** Added a read-only PDF preview using the browser's native PDF viewer, plus a generated 2-page PDF example in the seed data.
- **Tooling:** Upgraded to Node.js 26 LTS and Python 3.14; refreshed frontend dependencies (Vite 8, Vue Router 5, Pinia 4) and backend dependencies (Flask 3.1, Werkzeug 3.1, argon2-cffi 25, pytest 9).
- **Tooling:** Switched backend environment and dependency management to uv (`pyproject.toml` + `uv.lock`); removed `backend/requirements.txt`.
- **Tooling:** Added root `npm run dev` to start Flask and Vite together, with free-port detection and automatic dependency bootstrap.
- **Frontend:** Added an "Alpha" badge to the login and sidebar branding to mark the build as an early prototype.
- **Seed data:** Expanded the knowledge base to 4 subjects with 20 pages (Fertigung & Automatisierung, Arbeitssicherheit, Werkstoffkunde, Zeichnen/Messtechnik).
- **Frontend:** Wissen view now groups pages under their subject instead of listing all entries flat; removed the redundant topic overview block (header already shows title and description).
- **Frontend:** Replaced the Markdown textarea with `md-editor-v3` (lazy-loaded, German toolbar labels, no external CDN assets). Read-only rendering still uses the existing markdown-it/KaTeX pipeline.
- **Frontend:** Added a shared `DocumentViewer` for consistent inline document previews and downloads across documents, project submissions and knowledge pages. The document header stays on top and the preview opens below it.
- **Frontend:** Project participation is now document-based. Students can either write a Markdown document in a full-page editor or upload a file; replaced/removed documents are deleted after saving.
- **Backend:** Project documents (`type=projekt`) can be created and deleted by their owners and supervising trainers. Documents linked to a released participation are locked until the release is undone.
- **Lernjournal:** Feedback now records and displays the supervising author. The duplicate “Erstellt von …” line is hidden when it matches the document owner.
- **Projekte:** Trainer view now lists all assigned learners with a combined submission/evaluation status badge. Expanding a learner shows sections 2 (Durchführung & Abgabe) and 3 (Auswertung & Bewertung) for that learner.
- **Projekte:** The evaluation view now uses the same expandable learner list. Per-learner evaluation, release and saving happen inside the expanded row; global text and project completion are separate actions.
- **Lerndokumentation:** Noten & Prüfungen now shows the average per learner between the filter bar and the grade list, respecting the active subject, semester and search filters.

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
