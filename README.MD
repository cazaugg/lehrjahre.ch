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
- **Database (`data/lehrjahre.db`):** SQLite via SQLAlchemy using the 9 core tables (`company`, `user`, `user_relation`, `project`, `participation`, `eval`, `grades`, `documents`, `knowledge`).
  - `company` stores the tenant name, its email domain, and the default company address.
  - Every `user` belongs to exactly one `company` via `company_id`; the company cannot be changed through the API. A user's `company_email` must match the company's `email_domain`. New users inherit `company.address` when no company address is supplied.
  - `user.role` distinguishes `'ausbildner'` and `'lernender'`, while `user.job_title` stores either the trainer function (`Administrator`, `Berufsbildner`, `Fachvorgesetzter`, `Kursleiter`, `Lehrer`, `HR / Rekrutierung`) or the apprentice's MEM profession.
  - `knowledge` models the `Thema -> Seite` hierarchy (`parent_id`) and links via `document_id` to `documents`.
- **Company-Scoped File Storage (`data/documents/<company-slug>/`):** Uploaded files (PDFs, images, certificates) and Markdown/text documents (`lernjournal`, `wissen`, `ausbildungsgespraech`, `vertrag`) are stored on disk per company and served through `/api/documents/<id>/file` with strict path-traversal protection.

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

Create another company (tenant) before adding its users:

```bash
LEHRJAHRE_ENV=development uv run python -m backend.companies add "Muster AG" "muster.ch" --address "Musterstrasse 1, 8000 Zürich"
LEHRJAHRE_ENV=development uv run python -m backend.companies list
```

**Development-only demo accounts (Password: `Lehrjahre2026!`):**
- **Berufsbildner:** `thomas.keller@vektorwerk.ch`
- **HR / Rekrutierung:** `sandra.meier@vektorwerk.ch`
- **Lernender (Polymechaniker EFZ):** `lukas.frei@vektorwerk.ch`

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
- Keep `data/` and `data/documents/` readable only by the API process user (the app creates them with `0750`/`0640`, but verify after deployment).
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
