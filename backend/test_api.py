import os
import tempfile
import pytest
from backend.app import create_app
from backend.models import db, User, UserRelation
from backend.auth import hash_password
from backend.storage import resolve_safe_path


@pytest.fixture
def client():
    tmp_dir = tempfile.mkdtemp(prefix="lehrjahre_test_")
    db_file = os.path.join(tmp_dir, "test.db")
    docs_dir = os.path.join(tmp_dir, "documents")

    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_file}",
            "DOCUMENTS_ROOT": docs_dir,
            "SECRET_KEY": "test-secret",
        }
    )

    with app.app_context():
        db.create_all()
        trainer = User(
            role="ausbildner",
            name="Thomas",
            surname="Keller",
            company="SwissMEM Technik AG",
            password_hash=hash_password("Passwort123!"),
            company_email="trainer@swissmem.ch",
            job_title="Berufsbildner",
        )
        student = User(
            role="lernender",
            name="Lukas",
            surname="Frei",
            company="SwissMEM Technik AG",
            password_hash=hash_password("Passwort123!"),
            company_email="student@swissmem.ch",
            job_title="Polymechanikerin / Polymechaniker EFZ",
        )
        db.session.add_all([trainer, student])
        db.session.flush()
        db.session.add(UserRelation(supervisor=trainer.id, student=student.id))
        db.session.commit()

    with app.test_client() as test_client:
        yield test_client


def login(client, email, password="Passwort123!"):
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    data = res.get_json()["data"]
    return data["csrf_token"], data["user"]


def test_auth_and_csrf_protection(client):
    csrf, user = login(client, "trainer@swissmem.ch")
    assert user["role"] == "ausbildner"

    # Mutating request without CSRF header fails
    res_no_csrf = client.post("/api/project", json={"title": "Testprojekt"})
    assert res_no_csrf.status_code == 403

    # With CSRF header succeeds
    res_ok = client.post(
        "/api/project",
        json={"title": "CNC Grundkurs", "goals": ["Ziel 1", "Ziel 2"]},
        headers={"X-CSRF-Token": csrf},
    )
    assert res_ok.status_code == 201
    proj = res_ok.get_json()["data"]
    assert proj["title"] == "CNC Grundkurs"
    assert len(proj["goals"]) == 2


def test_documents_and_knowledge_company_folder(client):
    csrf, trainer = login(client, "trainer@swissmem.ch")

    # Create a knowledge topic & page
    res_k = client.post(
        "/api/knowledge",
        json={
            "title": "Frästechnik",
            "description": "Grundlagen Fräsen",
            "content": "# Frästechnik\nSchnittgeschwindigkeit beachten.",
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert res_k.status_code == 201
    k_node = res_k.get_json()["data"]
    assert k_node["document"]["path"].startswith("swissmem-technik-ag/")

    # Path traversal check
    with client.application.app_context():
        with pytest.raises(PermissionError):
            resolve_safe_path("../../etc/passwd")


def test_grades_and_implementation_workflow(client):
    csrf_stu, student = login(client, "student@swissmem.ch")

    # Student adds a grade
    res_g = client.post(
        "/api/grades",
        json={
            "subject": "Mathematik",
            "title": "Trigonometrie",
            "grade": 5.5,
            "date": "2026-03-10",
        },
        headers={"X-CSRF-Token": csrf_stu},
    )
    assert res_g.status_code == 201
    assert res_g.get_json()["data"]["grade"] == 5.5

    # Student cannot create a new User
    res_forbidden = client.post(
        "/api/user",
        json={"name": "Neu", "surname": "User", "company_email": "x@y.ch", "job_title": "Test"},
        headers={"X-CSRF-Token": csrf_stu},
    )
    assert res_forbidden.status_code == 403
