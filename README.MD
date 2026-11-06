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

- **Authentication & Security:** Signed Flask sessions with `HttpOnly`, `SameSite=Lax`, and `Secure` cookies by default, Argon2id password hashing (`argon2-cffi`), per-user session versioning for password-change/logout-all revocation, and `X-CSRF-Token` validation on all state-changing API calls. Configured with `ProxyFix` for deployment behind a reverse proxy and WAF.
- **Per-Company Databases (one SQLite file per tenant):** Each company owns its own database and data folder. The global *control database* (`data/control.db`) holds only the routing layer:
  - `company` is the tenant registry (name, email domain, default address) used to resolve a login to the correct company database.
  - `user_routing` maps a login email address to a user *inside* a company database — no credentials, no profile data.
  - A company's folder `<company root>/<company-slug>/` contains `app.db` (its full database) and `documents/`. `app.db` holds every operational table (`user`, `user_relation`, `project`, `participation`, `eval`, `grades`, `documents`, `knowledge`) including complete user records (password hash, contacts, session version) — nothing about other companies exists in it.
  - The SQLAlchemy session routes each statement to the control engine or the active tenant engine (`backend/tenants.py`); the tenant is resolved per request from the signed session cookie.
- **Users & Companies:** Every `user` belongs to exactly one `company` (assignment is fixed once created — the company cannot be changed through the API). A user's `company_email` must match the company's `email_domain`. New users inherit `company.address` when no company address is supplied, and the login email must stay globally unique (`user_routing`).
  - `user.role` distinguishes `'ausbildner'`, `'admin'`, and `'lernender'`. Supervisors (`ausbildner`) and admins share the same visibility rules (own data + subordinate students). People and relationship management is exclusively the admin role: creating/deleting users, editing contacts/master data of anyone in the company, managing supervisor assignments, performing role changes, and viewing everyone's private contacts. Supervisors keep editing their own and their subordinate students' master data/contacts and their own contacts. `user.job_title` stores the trainer function (`Administrator`, `Berufsbildner`, `Fachvorgesetzter`, `Kursleiter`, `Lehrer`, `HR / Rekrutierung`), the MEM profession, or `Administrator` for admins.
  - `knowledge` models the `Thema -> Seite` hierarchy (`parent_id`) and links via `document_id` to `documents`.
- **Company-Scoped File Storage (`<company root>/<company-slug>/documents/`):** Uploaded files (PDFs, images, certificates) and Markdown/text documents (`lernjournal`, `wissen`, `ausbildungsgespraech`, `vertrag`) are stored on disk per company next to its `app.db` and served through `/api/documents/<id>/file` with strict path-traversal protection.

## Quickstart

Requires [uv](https://docs.astral.sh/uv/), Node.js >= 26 with npm, and Python >= 3.14. `uv` installs the version pinned in `.python-version`.

### 1. Development

From the repository root:

```bash
npm run dev
```

Starts Flask and Vite together, installs missing dependencies, and prints both URLs. Ports 5000/5173 are used when free; otherwise the next free port is picked and wired into both processes.

Seed demo data once (skipped if the database already has users):

```bash
npm run seed
```

(`npm run seed` runs `backend.seed` with the development environment and a local secret.)

Create another company (tenant) — this also creates its data folder with an empty `app.db` and `documents/` — before adding its users:

```bash
LEHRJAHRE_ENV=development uv run python -m backend.companies add "Muster AG" "muster.ch" --address "Musterstrasse 1, 8000 Zürich"
LEHRJAHRE_ENV=development uv run python -m backend.companies list
```

**Development-only demo accounts (Password: `Lehrjahre2026!`):**
- **Berufsbildner:** `thomas.keller@vektorwerk.ch`
- **HR / Rekrutierung:** `sandra.meier@vektorwerk.ch`
- **Lernende (Konstrukteur/in EFZ, 1.–3. Lehrjahr):** `lea.buchmann@vektorwerk.ch`, `sven.hug@vektorwerk.ch`, `livia.kaelin@vektorwerk.ch`

These demo accounts are for local development only. Do not seed them in production.

### 2. Manual Backend & Frontend

```bash
uv sync
npm run seed
LEHRJAHRE_ENV=development LEHRJAHRE_DEBUG=1 COOKIE_SECURE=false \
  uv run python -m backend.app    # API on http://127.0.0.1:5000
```

```bash
cd frontend
npm ci
npm run dev                     # Vite on http://127.0.0.1:5173, proxies /api to :5000
```

### 3. Production Build

```bash
cd frontend
npm run build                   # Builds static assets into frontend/dist
```

### 4. Run Tests

```bash
uv run pytest backend/test_api.py
```

### 5. Production Deployment

Flask only serves the API under `/api`. The reverse proxy serves the built frontend and falls back to `index.html` for client-side routes:

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:5000;
}

location / {
    root /path/to/frontend/dist;
    try_files $uri $uri/ /index.html;
}
```

**Production checklist**
- Set `LEHRJAHRE_ENV=production` (the default) and a strong, random `SECRET_KEY` of at least 32 characters. The app refuses to start without a secret outside development.
- Set `LEHRJAHRE_DEBUG=0` (the default) and run the API with a production WSGI server, not `python -m backend.app`. Debug mode is rejected outside development.
- Keep `COOKIE_SECURE=true` when the site is served over HTTPS. Set it to `false` only for local HTTP development (`npm run dev` does this automatically).
- The reverse proxy must strip incoming `X-Forwarded-For`, `X-Forwarded-Proto`, `X-Forwarded-Host`, and `X-Forwarded-Prefix` headers and set them itself. `ProxyFix` trusts one proxy hop.
- Do not run `backend.seed` in production; demo accounts and the shared demo password are development-only.
- Keep the company data root (`data/` — containing `control.db` and each company folder with `app.db` + `documents/`) readable only by the API process user (the app creates the folders with `0750` and the databases/files with `0640`, but verify after deployment).
- Collect the API process logs. Security-relevant audit entries are written at `INFO` level.

## API Endpoints

- `/api/health` (Service status)
- `/api/auth` (`POST /login`, `POST /logout`, `POST /logout-all`, `GET /me`)
- `/api/user` (Users & `user_relation` management)
- `/api/project` (Hierarchical projects, topics, internships & learning goals)
- `/api/implementation` (Backed by `participation` – student task reports)
- `/api/evaluation` (Backed by `eval` – goal planning & trainer assessments)
- `/api/documents` (Metadata, Markdown editor content & authenticated file download `/api/documents/<id>/file`)
- `/api/grades` (Exam grades & subject averages)
- `/api/knowledge` (Hierarchical knowledge base linked to `documents`)
