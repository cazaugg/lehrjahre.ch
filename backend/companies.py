import argparse
import os
import sys

from backend.app import create_app
from backend.models import Company, db, normalize_email_domain
from backend.storage import slugify_company
from backend import tenants


def _company_by_name(name: str) -> Company | None:
    return Company.query.filter(
        db.func.lower(Company.name) == name.lower()
    ).first()


def add_company(name: str, domain: str, address: str = "") -> Company:
    """Create the control-DB company registry row (no tenant file yet)."""
    name = (name or "").strip()
    if not name:
        raise ValueError("Firmenname ist erforderlich.")

    domain = normalize_email_domain(domain)
    address = (address or "").strip()

    if _company_by_name(name):
        raise ValueError(f"Firma '{name}' existiert bereits.")
    if Company.query.filter_by(email_domain=domain).first():
        raise ValueError(f"Domain '{domain}' ist bereits einer Firma zugeordnet.")

    slug = slugify_company(name)
    for existing in Company.query.all():
        if slugify_company(existing.name) == slug:
            raise ValueError(
                f"Firmenname '{name}' kollidiert mit dem Ordner von "
                f"'{existing.name}'."
            )
    from flask import current_app

    collision_path = os.path.join(
        current_app.config["COMPANY_ROOT"], slug
    )
    if os.path.exists(collision_path):
        raise ValueError(f"Das Firmenverzeichnis '{slug}' existiert bereits.")

    company = Company(name=name, email_domain=domain, address=address)
    db.session.add(company)
    db.session.commit()
    return company


def list_companies() -> list[Company]:
    return Company.query.order_by(Company.name.asc()).all()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m backend.companies",
        description="Verwaltet Firmen (Mandanten) für lehrjahre.ch.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Firma anlegen")
    add_parser.add_argument("name")
    add_parser.add_argument("domain", help="E-Mail-Domain, z.B. firma.ch")
    add_parser.add_argument("--address", default="")

    subparsers.add_parser("list", help="Firmen auflisten")

    args = parser.parse_args(argv)
    app = create_app()

    with app.app_context():
        try:
            if args.command == "add":
                company = add_company(args.name, args.domain, args.address)
                try:
                    # Provision the company folder: app.db + documents/.
                    db_path = tenants.tenant_db_path(company)
                    tenants.create_company_schema(company)
                except Exception:
                    # Keep registry and filesystem consistent: drop the row
                    # if the tenant database could not be provisioned.
                    db.session.delete(company)
                    db.session.commit()
                    raise
                print(
                    f"Firma angelegt: {company.name} (@{company.email_domain})\n"
                    f"  Firmen-Datenordner: {os.path.dirname(db_path)}\n"
                    f"  Firmen-Datenbank:   {db_path}"
                )
            elif args.command == "list":
                companies = list_companies()
                if not companies:
                    print("Keine Firmen vorhanden.")
                for company in companies:
                    print(
                        f"{company.id}\t{company.name}\t"
                        f"@{company.email_domain}\t{company.address or ''}"
                    )
        except ValueError as exc:
            print(f"Fehler: {exc}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
