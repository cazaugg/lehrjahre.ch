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

Requires [uv](https://docs.astral.sh/uv/), Node.js >= 26 with npm, and Python >= 3.14. `uv` installs the version pinned in `.python-version`.

### 1. Development

From the repository root:

```bash
npm run dev
```

Starts Flask and Vite together, installs missing dependencies, and prints both URLs. Ports 5000/5173 are used when free; otherwise the next free port is picked and wired into both processes.

Seed demo data once (skipped if the database already has users):

```bash
uv run python -m backend.seed
```

**Demo Accounts (Password: `Lehrjahre2026!`):**
- **Berufsbildner:** `thomas.keller@vektorwerk.ch`
- **HR / Rekrutierung:** `sandra.meier@vektorwerk.ch`
- **Lernender (Polymechaniker EFZ):** `lukas.frei@vektorwerk.ch`

### 2. Manual Backend & Frontend

```bash
uv sync
uv run python -m backend.seed
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

## API Endpoints

- `/api/health` (Service status)
- `/api/auth` (`POST /login`, `POST /logout`, `GET /me`)
- `/api/user` (Users & `user_relation` management)
- `/api/project` (Hierarchical projects, topics, internships & learning goals)
- `/api/implementation` (Backed by `participation` – student task reports)
- `/api/evaluation` (Backed by `eval` – goal planning & trainer assessments)
- `/api/documents` (Metadata, Markdown editor content & authenticated file download `/api/documents/<id>/file`)
- `/api/grades` (Exam grades & subject averages)
- `/api/knowledge` (Hierarchical knowledge base linked to `documents`)
