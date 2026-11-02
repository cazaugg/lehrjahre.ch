# lehrjahre.ch

Digitale Lerndokumentation für MEM Berufslehren in der Schweiz.

- Anlagen- und Apparatebauerin / Anlagen- und Apparatebauer mit eidgenössischem Fähigkeitszeugnis (EFZ)
- Konstrukteurin / Konstrukteur mit eidgenössischem Fähigkeitszeugnis (EFZ)
- Mechanikpraktikerin / Mechanikpraktiker mit eidgenössischem Berufsattest (EBA)
- Produktionsmechanikerin / Produktionsmechaniker mit eidgenössischem Fähigkeitszeugnis (EFZ)
- Polymechanikerin / Polymechaniker mit eidgenössischem Fähigkeitszeugnis (EFZ)
- Automatikmonteurin / Automatikmonteur mit eidgenössischem Fähigkeitszeugnis (EFZ)
- Automatikerin / Automatiker mit eidgenössischem Fähigkeitszeugnis (EFZ)
- Elektronikerin / Elektroniker mit eidgenössischem Fähigkeitszeugnis (EFZ)

## Architecture & Design Choices

- **Authentication & Security:** Server-side Flask sessions with `HttpOnly`, `SameSite=Lax` cookies, Argon2id password hashing (`argon2-cffi`), and `X-CSRF-Token` validation on all state-changing API calls. Configured with `ProxyFix` for deployment behind a reverse proxy and WAF.
- **Database (`data/lehrjahre.db`):** SQLite via SQLAlchemy using the 8 core tables (`user`, `user_relation`, `project`, `participation`, `eval`, `grades`, `documents`, `knowledge`).
  - `user.role` distinguishes `'ausbildner'` and `'lernender'`, while `user.job_title` stores either the trainer function (`Administrator`, `Berufsbildner`, `Fachvorgesetzter`, `Kursleiter`, `Lehrer`, `HR / Rekrutierung`) or the apprentice's MEM profession.
  - `knowledge` models the `Thema -> Seite` hierarchy (`parent_id`) and links via `document_id` to `documents`.
- **Company-Scoped File Storage (`data/documents/<company-slug>/`):** Uploaded files (PDFs, images, certificates) and Markdown/text documents (`lernjournal`, `wissen`, `ausbildungsgespraech`, `vertrag`) are stored on disk per company and served through `/api/documents/<id>/file` with strict path-traversal protection.

## Quickstart

### 1. Backend Setup & Seed

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
.venv/bin/python -m backend.seed
.venv/bin/python -m backend.app
```

**Demo Accounts (Password: `Lehrjahre2026!`):**
- **Berufsbildner:** `thomas.keller@swissmem-technik.ch`
- **HR / Rekrutierung:** `sandra.meier@swissmem-technik.ch`
- **Lernender (Polymechaniker EFZ):** `lukas.frei@swissmem-technik.ch`

### 2. Frontend Development & Production Build

```bash
cd frontend
npm install
npm run dev     # Vite dev server on http://127.0.0.1:5173 (proxies /api to :5000)
npm run build   # Builds static assets into frontend/dist (served directly by Flask)
```

### 3. Run Tests

```bash
.venv/bin/pytest backend/test_api.py
```

## API Endpoints

- `/api/auth` (`POST /login`, `POST /logout`, `GET /me`)
- `/api/user` (Users & `user_relation` management)
- `/api/project` (Hierarchical projects, topics, internships & learning goals)
- `/api/implementation` (Backed by `participation` – student task reports)
- `/api/evaluation` (Backed by `eval` – goal planning & trainer assessments)
- `/api/documents` (Metadata, Markdown editor content & authenticated file download `/api/documents/<id>/file`)
- `/api/grades` (Exam grades & subject averages)
- `/api/knowledge` (Hierarchical knowledge base linked to `documents`)
