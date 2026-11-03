import argparse
import sys

from backend.app import create_app
from backend.models import Company, db, normalize_email_domain
from backend.storage import slugify_company


def _company_by_name(name: str) -> Company | None:
    return Company.query.filter(
        db.func.lower(Company.name) == name.lower()
    ).first()


def add_company(name: str, domain: str, address: str = "") -> Company:
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
                f"Firmenname '{name}' kollidiert mit dem Dokumentordner von "
                f"'{existing.name}'."
            )

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
                print(
                    f"Firma angelegt: {company.name} (@{company.email_domain})"
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
