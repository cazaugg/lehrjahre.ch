# lehrjahre.ch

Digital learning documentation (Lerndokumentation) for Swiss MEM apprenticeships — see the public instance at **[lehrjahre.ch](https://lehrjahre.ch)**.

Covered occupations (official German job titles as used in the app):

- Anlagen- und Apparatebauerin / Anlagen- und Apparatebauer mit eidgenössischem Fähigkeitszeugnis (EFZ)
- Konstrukteurin / Konstrukteur mit eidgenössischem Fähigkeitszeugnis (EFZ)
- Mechanikpraktikerin / Mechanikpraktiker mit eidgenössischem Berufsattest (EBA)
- Produktionsmechanikerin / Produktionsmechaniker mit eidgenössischem Fähigkeitszeugnis (EFZ)
- Polymechanikerin / Polymechaniker mit eidgenössischem Fähigkeitszeugnis (EFZ)
- Automatikmonteurin / Automatikmonteur mit eidgenössischem Fähigkeitszeugnis (EFZ)
- Automatikerin / Automatiker mit eidgenössischem Fähigkeitszeugnis (EFZ)
- Elektronikerin / Elektroniker mit eidgenössischem Fähigkeitszeugnis (EFZ)

## Quickstart

Requires [uv](https://docs.astral.sh/uv/), Node.js >= 26 with npm, and Python >= 3.14. `uv` installs the version pinned in `.python-version`.

### 1. Production Deployment

Flask serves both the API and the built frontend. The Docker stack (Traefik edge proxy, Gunicorn application container) routes `Host(domain)` to the API container; non-`/api` paths fall back to `index.html` for client-side routes (see `serve_frontend` in `backend/app.py`). Cloudflare fronts the origin as the public edge (DNS, WAF, TLS) — see [Cloudflare](#1a-cloudflare-waf--dns--tls).

```bash
# Get the repo
git clone https://github.com/cazaugg/lehrjahre.ch.git
cd lehrjahre.ch

# Persistent data lives on the host (control.db, tenant databases, documents):
# Create required folders
sudo install -d -m 0755 /data/lehrjahre.ch
sudo install -d -o 10001 -g 10001 -m 0750 /data/lehrjahre.ch/app   # API user (10001) owns its data
# TLS material is system config, not application data (see "1a. Cloudflare"):
#   /etc/ssl/lehrjahre.pem + /etc/ssl/lehrjahre.key (key chmod 600, root only).

# Configuration (see .env.example):
#   DOMAIN, SECRET_KEY via openssl rand -hex 32, and the
#   outgoing-mail settings (mails are sent from MAIL_FROM, by default
#   kontakt@lehrjahre.ch, via an SMTP account):
#     SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASSWORD
cp .env.example .env && chmod 600 .env
$EDITOR .env

# Build & start. The build stamps the image with the semver from the
# VERSION file and the current git commit (shown in the UI and exposed
# via /api/health):
GIT_SHA=$(git rev-parse --short HEAD) docker compose up -d --build
```

Companies can register themselves via `/registrierung` (public form with e-mail verification; the signup e-mail's domain becomes the company's `email_domain`). Companies that should *not* have a public signup path are created with the CLI instead, which replaces the folder/`app.db` provisioning of the form flow:

```bash
docker compose exec api python -m backend.companies add "Firma AG" "firma.ch" --address "Musterstrasse 1, 8000 Zürich"
```

**Production checklist**

- Set `LEHRJAHRE_ENV=production` (the default) and a strong, random `SECRET_KEY` of at least 32 characters. The app refuses to start without a secret outside development.
- Set `LEHRJAHRE_DEBUG=0` (the default) and run the API with a production WSGI server, not `python -m backend.app`. Debug mode is rejected outside development.
- Keep `COOKIE_SECURE=true` when the site is served over HTTPS. Set it to `false` only for local HTTP development (`npm run dev` does this automatically).
- The reverse proxy must not trust client-supplied `X-Forwarded-*` headers: Traefik accepts them only from Cloudflare's ranges and sets them itself, and `ProxyFix` trusts one proxy hop (the visitor IP Cloudflare passes through).
- Do not run `backend.seed` in production; demo accounts and the shared demo password are development-only.
- Keep the company data root (`data/` — containing `control.db` and each company folder with `app.db` + `documents/`) readable only by the API process user (the app creates the folders with `0750` and the databases/files with `0640`, but verify after deployment).
- Collect the API process logs. Security-relevant audit entries are written at `INFO` level.
- Configure outgoing mail (`SMTP_HOST`, `SMTP_PORT` default 587 with STARTTLS-required, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM` — see `.env.example`) before enabling public signups; a missing `SMTP_HOST` logs a startup warning and signup/invite requests fail until mail is set up. `SIGNUP_ENABLED=0` is the kill switch for public company registrations.
- Egress to the SMTP submission port (default `mail.infomaniak.com:587`) must be allowed if the host firewall restricts container traffic.
- For mail deliverability, add DNS records for the sending domain (`lehrjahre.ch`): an SPF record authorising the SMTP provider (e.g. `v=spf1 include:spf.infomaniak.ch -all`, adjusted to the actual provider) and preferably a DMARC policy. Without them verification/invite mails may be classified as spam.
- `SMTP_PASSWORD` is passed as an environment variable: readable by root via `docker inspect` on the API container only. Keep the server access limited (SSH keys, `.env` chmod 600) as documented.

### 1a. Cloudflare (WAF / DNS / TLS)

Cloudflare is the public edge: it terminates visitor TLS, applies the WAF, and re-encrypts to the origin with a **Cloudflare Origin Certificate**. The origin therefore runs no ACME client and needs no inbound Let's Encrypt challenge.

**DNS** — zone `lehrjahre.ch`, all records **proxied** (🟠):

| Type | Name | Content |
| --- | --- | --- |
| A | `@` | public IPv4 of the server |
| AAAA | `@` | public IPv6 of the server |

Add `www` as a redirect (Redirect Rule) or an extra router; the stack routes `Host(DOMAIN)` only.

**TLS** — SSL/TLS → Overview: **Full (strict)**. Then SSL/TLS → Origin Server → *Create Certificate* (`lehrjahre.ch, *.lehrjahre.ch`, 15 years) and install it as host system config (the private key is shown once; keep it out of application-data backups):

```bash
sudo -e /etc/ssl/lehrjahre.pem   # paste the certificate
sudo -e /etc/ssl/lehrjahre.key   # paste the private key
sudo chmod 644 /etc/ssl/lehrjahre.pem && sudo chmod 600 /etc/ssl/lehrjahre.key
```

`compose.yaml` bind-mounts those two files read-only into the container, and `traefik/dynamic.yml` uses them as the default certificate. Traefik trusts `X-Forwarded-*` only from Cloudflare's ranges and does not append the Cloudflare edge address (`notAppendXForwardedFor`), so `ProxyFix`'s single hop resolves to the visitor IP. Refresh the ranges in `compose.yaml` occasionally from `https://www.cloudflare.com/ips-v4` and `ips-v6`. Rotation requires a Traefik restart (file bind-mounts resolve at container start).

**Origin firewall** — published Docker ports bypass the host `INPUT` chain, and the WAF is only meaningful if the origin is unreachable directly. Restrict forwarded traffic instead (`/etc/nftables.conf`, Cloudflare ranges in `/etc/cf-ips-v4` + `/etc/cf-ips-v6`):

```nft
table inet filter {
  chain forward {
    type filter hook forward priority -150; policy accept;
    ct state invalid drop
    ct state established,related accept
    # Docker-published 80/443: Cloudflare (or a local bridge) only.
    ip saddr != $cf4 ip saddr != { 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16 } tcp dport { 80, 443 } ct state new drop
    ip6 saddr != $cf6 ip6 saddr != { fc00::/7, fe80::/10 } tcp dport { 80, 443 } ct state new drop
  }
}
```

A forward chain at priority `-150` runs before Docker's own rules, so it covers container ports regardless of Docker's `DOCKER` chains. `cf4`/`cf6` are set variables built from `/etc/cf-ips-v4` and `/etc/cf-ips-v6` (the `input` chain uses the same sets). Keep SSH (port 22) open in the `input` chain.

Verify:

```bash
curl -I https://lehrjahre.ch     # expect `server: cloudflare`
curl -m 5 http://<origin-ip>     # must time out (direct access blocked)
```

### 2. Development

To test the app locally, run from the repository root:

```bash
npm run setup   # first time only
npm run dev
```

Starts Flask and Vite together, installs missing dependencies, and prints both URLs. Ports 5000/5173 are used when free; otherwise the next free port is picked and wired into both processes.

Seed demo data once (skipped if the database already has users):

```bash
npm run seed
```

Reseed without existing data — this deletes the demo company's data folder (`app.db`, `documents/`) and its registry entries, then seeds everything fresh:

```bash
npm run seed -- --force
```

(`npm run seed` runs `backend.seed` with the development environment and a local secret; `--force` is equivalent to `python -m backend.seed --force`.)

Create another company (tenant) — this also creates its data folder with an empty `app.db` and `documents/` — before adding its users:

```bash
LEHRJAHRE_ENV=development uv run python -m backend.companies add "Muster AG" "muster.ch" --address "Musterstrasse 1, 8000 Zürich"
LEHRJAHRE_ENV=development uv run python -m backend.companies list
```

**Development-only demo accounts (Password: `Lehrjahre2026!`):**
- **Trainer (Berufsbildner):** `thomas.keller@vektorwerk.ch`
- **Administrator (user management):** `sandra.meier@vektorwerk.ch`
- **Students (Konstrukteur/in EFZ, 1st–3rd year of apprenticeship):** `lea.buchmann@vektorwerk.ch`, `sven.hug@vektorwerk.ch`, `livia.kaelin@vektorwerk.ch`

These demo accounts are for local development only. Do not seed them in production.

### 3. Manual Backend & Frontend

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

### 4. Run Tests

```bash
uv run pytest backend/test_api.py
```

## API Endpoints

- `/api/health` (Service status, incl. `mail_configured`, `version`, `git_sha`)
- `/api/auth` (`POST /login`, `POST /logout`, `POST /logout-all`, `GET /me`)
- `/api/company-signup` (public self-service company registration: `POST` submit, `POST /resend`, `POST /verify` one-time mail token, `GET /domain-check`)
- `/api/user` (Users & `user_relation` management; first-login invitations: `POST /invite/accept` with the mailed token, `POST /<id>/invite/resend` for admins)
- `/api/project` (Hierarchical projects, topics, internships & learning goals)
- `/api/implementation` (Backed by `participation` – student task reports)
- `/api/evaluation` (Backed by `eval` – goal planning & trainer assessments)
- `/api/documents` (Metadata, Markdown editor content & authenticated file download `/api/documents/<id>/file`)
- `/api/grades` (Exam grades & subject averages)
- `/api/knowledge` (Hierarchical knowledge base linked to `documents`)

## Architecture & Design Choices

- **Authentication & Security:** Signed Flask sessions with `HttpOnly`, `SameSite=Lax`, and `Secure` cookies by default, Argon2id password hashing (`argon2-cffi`), per-user session versioning for password-change/logout-all revocation, and `X-CSRF-Token` validation on all state-changing API calls. Configured with `ProxyFix` for deployment behind a reverse proxy and WAF.
- **Per-Company Databases (one SQLite file per tenant):** Each company owns its own database and data folder. The global *control database* (`data/control.db`) holds only the routing layer:
  - `company` is the tenant registry (name, email domain, default address) used to resolve a login to the correct company database.
  - `user_routing` maps a login email address to a user *inside* a company database — no credentials, no profile data.
  - A company's folder `<company root>/<company-slug>/` contains `app.db` (its full database) and `documents/`. `app.db` holds every operational table (`user`, `user_relation`, `project`, `participation`, `eval`, `grades`, `documents`, `knowledge`) including complete user records (password hash, contacts, session version) — nothing about other companies exists in it.
  - The SQLAlchemy session routes each statement to the control engine or the active tenant engine (`backend/tenants.py`); the tenant is resolved per request from the signed session cookie.
  - **Company signup & first-login invitations:** public self-service registrations create a *pending* signup in the control database and mail a one-time verification link (256-bit token, only its SHA-256 hash is stored) from `kontakt@lehrjahre.ch`; the tenant (database folder + `app.db`) and the admin account are provisioned only when the link is confirmed. New users created by an admin likewise receive an e-mail invitation to set their own password (invitations always go to company e-mail addresses).
- **Users & Companies:** Every `user` belongs to exactly one `company` (assignment is fixed once created — the company cannot be changed through the API). A user's `company_email` must match the company's `email_domain`. New users inherit `company.address` when no company address is supplied, and the login email must stay globally unique (`user_routing`).
  - `user.role` distinguishes `'ausbildner'` (supervisor), `'admin'`, and `'lernender'` (student). Supervisors and admins share the same visibility rules (own data + subordinate students). People and relationship management is exclusively the admin role: creating/deleting users, editing contacts/master data of anyone in the company, managing supervisor assignments, performing role changes, and viewing everyone's private contacts. Supervisors keep editing their own and their subordinate students' master data/contacts and their own contacts. `user.job_title` stores the trainer function (`Administrator`, `Berufsbildner`, `Fachvorgesetzter`, `Kursleiter`, `Lehrer`, `HR / Rekrutierung`), the MEM profession, or `Administrator` for admins.
  - `knowledge` models the `Thema -> Seite` hierarchy (`parent_id`) and links via `document_id` to `documents`.
- **Company-Scoped File Storage (`<company root>/<company-slug>/documents/`):** Uploaded files (PDFs, images, certificates) and Markdown/text documents (`lernjournal`, `wissen`, `ausbildungsgespraech`, `vertrag`) are stored on disk per company next to its `app.db` and served through `/api/documents/<id>/file` with strict path-traversal protection.
- **Deployment design:**
  - **Two containers only (`traefik`, `api`)** — Traefik is the single reverse proxy and routes everything to the Flask/Gunicorn container; `ProxyFix` therefore sees exactly one trusted hop. Cloudflare sits in front of Traefik and passes the visitor IP in `X-Forwarded-For`.
  - **Persistent data** is bind-mounted read-write only for the API and lives under `/data/lehrjahre.ch/` (`app/control.db`, `app/<company-slug>/app.db` + `documents/`). The static lehrplan JSON is baked into the image instead. TLS keys are host system config (`/etc/ssl`), never part of this backup tree.
  - **TLS** is a long-lived Cloudflare Origin Certificate (no ACME); the origin is only reachable through Cloudflare's WAF (host firewall + forwarding rules, see [Cloudflare](#1a-cloudflare-waf--dns--tls)).
  - **Least privilege** — the API container runs as user 10001 with a read-only root filesystem (`tmpfs` for temp uploads); only Traefik publishes 80/443.
  - **Client-side routes without an asset extension** resolve to `index.html`; unknown `/api/*` paths keep returning a JSON 404.
