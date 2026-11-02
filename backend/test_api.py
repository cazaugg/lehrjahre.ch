import os
import tempfile
from datetime import date
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
            company="Vektorwerk Technik AG",
            password_hash=hash_password("Passwort123!"),
            company_email="trainer@vektorwerk.ch",
            job_title="Berufsbildner",
        )
        student = User(
            role="lernender",
            name="Lukas",
            surname="Frei",
            company="Vektorwerk Technik AG",
            password_hash=hash_password("Passwort123!"),
            company_email="student@vektorwerk.ch",
            job_title="Polymechanikerin / Polymechaniker EFZ",
            start_date=date(2024, 8, 12),
            end_date=date(2028, 7, 31),
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


def test_health_and_api_only_routing(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.get_json()["status"] == "ok"

    # Frontend routes are handled by the reverse proxy, not Flask
    res = client.get("/personen")
    assert res.status_code == 404


def test_auth_and_csrf_protection(client):
    csrf, user = login(client, "trainer@vektorwerk.ch")
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
    csrf, trainer = login(client, "trainer@vektorwerk.ch")

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
    assert "path" not in k_node["document"]
    docs_root = client.application.config["DOCUMENTS_ROOT"]
    assert os.path.isdir(os.path.join(docs_root, "vektorwerk-technik-ag"))

    # Path traversal check
    with client.application.app_context():
        with pytest.raises(PermissionError):
            resolve_safe_path("../../etc/passwd")


def test_knowledge_visibility_and_ownership(client):
    csrf_trainer, _ = login(client, "trainer@vektorwerk.ch")
    res_t = client.post(
        "/api/knowledge",
        json={
            "title": "Trainer-Thema",
            "description": "Vom Ausbildner erstellt",
            "content": "# Trainer-Thema",
        },
        headers={"X-CSRF-Token": csrf_trainer},
    )
    assert res_t.status_code == 201
    trainer_node = res_t.get_json()["data"]

    csrf_student, student = login(client, "student@vektorwerk.ch")
    res_s = client.post(
        "/api/knowledge",
        json={
            "title": "Lernenden-Thema",
            "description": "Vom Lernenden erstellt",
            "content": "# Lernenden-Thema",
        },
        headers={"X-CSRF-Token": csrf_student},
    )
    assert res_s.status_code == 201
    student_node = res_s.get_json()["data"]

    # A learner cannot create a page under someone else's topic
    res_parent = client.post(
        "/api/knowledge",
        json={"title": "Fremde Seite", "parent_id": trainer_node["id"]},
        headers={"X-CSRF-Token": csrf_student},
    )
    assert res_parent.status_code == 403

    # A learner only sees their own entries
    student_list = client.get("/api/knowledge").get_json()["data"]
    assert {node["title"] for node in student_list} == {"Lernenden-Thema"}
    assert student_list[0]["author"] == student["id"]
    assert student_list[0]["author_name"] == "Lukas Frei"

    # A learner cannot even see, let alone edit, a trainer's entry
    res_edit = client.put(
        f"/api/knowledge/{trainer_node['id']}",
        json={"title": "Manipuliert"},
        headers={"X-CSRF-Token": csrf_student},
    )
    assert res_edit.status_code == 404

    # The trainer sees their own entry and the assigned learner's entry
    csrf_trainer, _ = login(client, "trainer@vektorwerk.ch")
    trainer_list = client.get("/api/knowledge").get_json()["data"]
    trainer_titles = {node["title"] for node in trainer_list}
    assert {"Trainer-Thema", "Lernenden-Thema"} <= trainer_titles

    # Trainers can view, but not edit, their learners' entries
    res_edit_learner = client.put(
        f"/api/knowledge/{student_node['id']}",
        json={"title": "Korrektur"},
        headers={"X-CSRF-Token": csrf_trainer},
    )
    assert res_edit_learner.status_code == 403


def test_grades_and_implementation_workflow(client):
    csrf_stu, student = login(client, "student@vektorwerk.ch")

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
    created = res_g.get_json()["data"]
    assert created["grade"] == 5.5
    assert created["semester"] == 4

    res_list = client.get("/api/grades")
    assert res_list.status_code == 200
    assert res_list.get_json()["data"][0]["semester"] == 4

    # Student cannot create a new User
    res_forbidden = client.post(
        "/api/user",
        json={"name": "Neu", "surname": "User", "company_email": "x@y.ch", "job_title": "Test"},
        headers={"X-CSRF-Token": csrf_stu},
    )
    assert res_forbidden.status_code == 403
