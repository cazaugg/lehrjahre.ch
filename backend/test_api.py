import os
import tempfile
from datetime import date
import pytest
from backend.app import create_app
from backend.models import db, Company, User, UserRelation
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
        company = Company(
            name="Vektorwerk Technik AG",
            email_domain="vektorwerk.ch",
            address="Industriestrasse 1",
        )
        db.session.add(company)
        db.session.flush()
        # Supervisor 1 (supervises student 1)
        trainer1 = User(
            role="ausbildner",
            name="Thomas",
            surname="Keller",
            company_id=company.id,
            password_hash=hash_password("Passwort123!"),
            private_address="Trainer1 Privatweg 1",
            private_email="trainer1@privat.ch",
            private_phone="079 111 11 11",
            school_address="BBW Winterthur",
            school_email="trainer1@bbw.ch",
            school_phone="052 111 11 11",
            company_address="Industriestrasse 1",
            company_email="trainer@vektorwerk.ch",
            company_phone="052 500 10 01",
            job_title="Berufsbildner",
        )
        # Supervisor 2 (same company, supervises nobody initially)
        trainer2 = User(
            role="ausbildner",
            name="Marco",
            surname="Brunner",
            company_id=company.id,
            password_hash=hash_password("Passwort123!"),
            private_address="Trainer2 Privatweg 2",
            private_email="trainer2@privat.ch",
            private_phone="079 222 22 22",
            school_address="AZW Winterthur",
            school_email="trainer2@azw.ch",
            school_phone="052 222 22 22",
            company_address="Industriestrasse 1",
            company_email="trainer2@vektorwerk.ch",
            company_phone="052 500 10 02",
            job_title="Fachvorgesetzter",
        )
        # Student 1 (subordinate to trainer1)
        student1 = User(
            role="lernender",
            name="Lukas",
            surname="Frei",
            company_id=company.id,
            password_hash=hash_password("Passwort123!"),
            private_address="Student1 Privatweg 10",
            private_email="student1@privat.ch",
            private_phone="079 333 33 33",
            school_address="BBW Winterthur",
            school_email="student1@bbw.ch",
            school_phone="052 333 33 33",
            company_address="Industriestrasse 1",
            company_email="student@vektorwerk.ch",
            company_phone="052 500 10 51",
            job_title="Polymechanikerin / Polymechaniker EFZ",
            start_date=date(2024, 8, 12),
            end_date=date(2028, 7, 31),
        )
        # Student 2 (same company, NOT subordinate to trainer1 or trainer2)
        student2 = User(
            role="lernender",
            name="Elena",
            surname="Schmid",
            company_id=company.id,
            password_hash=hash_password("Passwort123!"),
            private_address="Student2 Privatweg 20",
            private_email="student2@privat.ch",
            private_phone="079 444 44 44",
            school_address="BBW Winterthur",
            school_email="student2@bbw.ch",
            school_phone="052 444 44 44",
            company_address="Industriestrasse 1",
            company_email="student2@vektorwerk.ch",
            company_phone="052 500 10 52",
            job_title="Automatikerin / Automatiker EFZ",
            start_date=date(2025, 8, 11),
            end_date=date(2029, 7, 31),
        )
        db.session.add_all([trainer1, trainer2, student1, student2])
        db.session.flush()
        db.session.add(UserRelation(supervisor=trainer1.id, student=student1.id))
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
    csrf, _ = login(client, "trainer@vektorwerk.ch")

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

    # A learner only sees their own entries (both via /api/knowledge and /api/documents?type=wissen)
    student_list = client.get("/api/knowledge").get_json()["data"]
    assert {node["title"] for node in student_list} == {"Lernenden-Thema"}
    assert student_list[0]["author"] == student["id"]
    assert student_list[0]["author_name"] == "Lukas Frei"

    student_wissen_docs = client.get("/api/documents?type=wissen").get_json()["data"]
    assert {d["name"] for d in student_wissen_docs} == {"Lernenden-Thema"}

    # A learner cannot even see, let alone edit, a trainer's entry
    res_edit = client.put(
        f"/api/knowledge/{trainer_node['id']}",
        json={"title": "Manipuliert"},
        headers={"X-CSRF-Token": csrf_student},
    )
    assert res_edit.status_code == 404

    # Trainer 1 sees their own entry and their assigned learner's entry
    csrf_trainer, _ = login(client, "trainer@vektorwerk.ch")
    trainer_list = client.get("/api/knowledge").get_json()["data"]
    trainer_titles = {node["title"] for node in trainer_list}
    assert {"Trainer-Thema", "Lernenden-Thema"} == trainer_titles

    # Trainer 1 can view, but not edit or delete, their learner's entry
    res_edit_learner = client.put(
        f"/api/knowledge/{student_node['id']}",
        json={"title": "Korrektur"},
        headers={"X-CSRF-Token": csrf_trainer},
    )
    assert res_edit_learner.status_code == 403

    res_del_learner = client.delete(
        f"/api/knowledge/{student_node['id']}",
        headers={"X-CSRF-Token": csrf_trainer},
    )
    assert res_del_learner.status_code == 403

    # Trainer 2 (not supervising student 1) cannot see student 1's or trainer 1's knowledge entries
    login(client, "trainer2@vektorwerk.ch")
    trainer2_list = client.get("/api/knowledge").get_json()["data"]
    assert trainer2_list == []


def test_projects_access_and_workflow(client):
    # Trainer 1 creates a project (planning_released defaults to False)
    csrf_t1, _ = login(client, "trainer@vektorwerk.ch")
    _, student1 = login(client, "student@vektorwerk.ch")
    csrf_t1, _ = login(client, "trainer@vektorwerk.ch")

    res_proj = client.post(
        "/api/project",
        json={
            "title": "Fräsen Grundmodul",
            "description": "Auftrag Fräsen",
            "goals": ["Ziel A"],
            "planning_released": False,
        },
        headers={"X-CSRF-Token": csrf_t1},
    )
    assert res_proj.status_code == 201
    proj_id = res_proj.get_json()["data"]["id"]

    # Trainer 1 assigns student 1 via Phase 1 planning (Eval) with unreleased evaluation text
    res_eval = client.post(
        "/api/evaluation",
        json={
            "project": proj_id,
            "student": student1["id"],
            "goal": "Ziel A",
            "planning_text": "Toleranz 0.02mm beachten",
            "eval_text": "Geheimer Entwurf der Bewertung",
            "eval_released": False,
        },
        headers={"X-CSRF-Token": csrf_t1},
    )
    assert res_eval.status_code == 201
    eval_id = res_eval.get_json()["data"]["id"]

    # Trainer 2 (unassigned) cannot see Trainer 1's project
    login(client, "trainer2@vektorwerk.ch")
    assert client.get("/api/project").get_json()["data"] == []

    # Student 1 participates, but planning_released is False -> cannot see project or eval yet
    csrf_s1, _ = login(client, "student@vektorwerk.ch")
    assert client.get("/api/project").get_json()["data"] == []
    assert client.get("/api/evaluation").get_json()["data"] == []
    assert (
        client.post(
            "/api/implementation",
            json={"project": proj_id, "title": "Mein Bericht"},
            headers={"X-CSRF-Token": csrf_s1},
        ).status_code
        == 404
    )

    # Trainer 1 releases planning
    csrf_t1, _ = login(client, "trainer@vektorwerk.ch")
    res_rel = client.put(
        f"/api/project/{proj_id}",
        json={"planning_released": True},
        headers={"X-CSRF-Token": csrf_t1},
    )
    assert res_rel.status_code == 200
    assert res_rel.get_json()["data"]["planning_released"] is True

    # Student 2 (not participating) still cannot see the project
    login(client, "student2@vektorwerk.ch")
    assert client.get("/api/project").get_json()["data"] == []

    # Student 1 now sees the project and planning, but eval_text is masked because eval_released is False
    csrf_s1, _ = login(client, "student@vektorwerk.ch")
    s1_projects = client.get("/api/project").get_json()["data"]
    assert len(s1_projects) == 1
    s1_evals = client.get("/api/evaluation").get_json()["data"]
    assert len(s1_evals) == 1
    assert s1_evals[0]["planning_text"] == "Toleranz 0.02mm beachten"
    assert s1_evals[0]["eval_text"] == ""
    assert s1_evals[0]["eval_released"] is False

    # Student 1 creates an implementation report (not done yet)
    res_imp = client.post(
        "/api/implementation",
        json={
            "project": proj_id,
            "title": "Bericht Teil 1",
            "text": "Schritte ausgeführt",
            "is_done": False,
        },
        headers={"X-CSRF-Token": csrf_s1},
    )
    assert res_imp.status_code == 201
    imp_id = res_imp.get_json()["data"]["id"]

    # Student 1 can edit while not done
    res_imp_edit = client.put(
        f"/api/implementation/{imp_id}",
        json={"text": "Schritte ausgeführt und geprüft"},
        headers={"X-CSRF-Token": csrf_s1},
    )
    assert res_imp_edit.status_code == 200

    # Supervisor cannot edit the student's report text/title (Projektdurchführung: Anzeigen)
    csrf_t1, _ = login(client, "trainer@vektorwerk.ch")
    res_sup_edit_text = client.put(
        f"/api/implementation/{imp_id}",
        json={"text": "Vom Vorgesetzten überschrieben"},
        headers={"X-CSRF-Token": csrf_t1},
    )
    assert res_sup_edit_text.status_code == 403

    # Student 1 submits the report (is_done = True)
    csrf_s1, _ = login(client, "student@vektorwerk.ch")
    res_submit = client.put(
        f"/api/implementation/{imp_id}",
        json={"is_done": True},
        headers={"X-CSRF-Token": csrf_s1},
    )
    assert res_submit.status_code == 200
    assert res_submit.get_json()["data"]["is_done"] is True

    # Once submitted, Student 1 cannot reopen, edit, or delete it
    assert (
        client.put(
            f"/api/implementation/{imp_id}",
            json={"is_done": False},
            headers={"X-CSRF-Token": csrf_s1},
        ).status_code
        == 403
    )
    assert (
        client.put(
            f"/api/implementation/{imp_id}",
            json={"text": "Nachträgliche Änderung"},
            headers={"X-CSRF-Token": csrf_s1},
        ).status_code
        == 403
    )
    assert (
        client.delete(
            f"/api/implementation/{imp_id}",
            headers={"X-CSRF-Token": csrf_s1},
        ).status_code
        == 403
    )

    # Supervisor CAN reopen the submitted report and release the evaluation
    csrf_t1, _ = login(client, "trainer@vektorwerk.ch")
    res_reopen = client.put(
        f"/api/implementation/{imp_id}",
        json={"is_done": False},
        headers={"X-CSRF-Token": csrf_t1},
    )
    assert res_reopen.status_code == 200
    assert res_reopen.get_json()["data"]["is_done"] is False

    res_rel_eval = client.put(
        f"/api/evaluation/{eval_id}",
        json={"eval_released": True},
        headers={"X-CSRF-Token": csrf_t1},
    )
    assert res_rel_eval.status_code == 200

    # Student 1 now sees the released evaluation text
    login(client, "student@vektorwerk.ch")
    s1_evals_after = client.get("/api/evaluation").get_json()["data"]
    assert s1_evals_after[0]["eval_text"] == "Geheimer Entwurf der Bewertung"
    assert s1_evals_after[0]["eval_released"] is True


def test_lerndokumentation_permissions(client):
    csrf_s1, student1 = login(client, "student@vektorwerk.ch")

    # 1. Grades: Student 1 creates a grade
    res_g = client.post(
        "/api/grades",
        json={
            "subject": "Mathematik",
            "title": "Trigonometrie",
            "grade": 5.5,
            "date": "2026-03-10",
        },
        headers={"X-CSRF-Token": csrf_s1},
    )
    assert res_g.status_code == 201
    grade_id = res_g.get_json()["data"]["id"]

    # 2. Zeugnis: Student 1 can create and edit, but CANNOT delete
    res_z = client.post(
        "/api/documents",
        json={
            "name": "Semesterzeugnis 1",
            "type": "zeugnis",
            "content": "Note 5.2",
        },
        headers={"X-CSRF-Token": csrf_s1},
    )
    assert res_z.status_code == 201
    zeugnis_id = res_z.get_json()["data"]["id"]

    assert (
        client.put(
            f"/api/documents/{zeugnis_id}",
            json={"name": "Semesterzeugnis 1 (Aktualisiert)"},
            headers={"X-CSRF-Token": csrf_s1},
        ).status_code
        == 200
    )
    assert (
        client.delete(
            f"/api/documents/{zeugnis_id}",
            headers={"X-CSRF-Token": csrf_s1},
        ).status_code
        == 403
    )

    # 3. Ausbildungsgespräch: Student 1 CANNOT create, edit, or delete
    assert (
        client.post(
            "/api/documents",
            json={
                "name": "Gespräch",
                "type": "ausbildungsgespraech",
                "content": "Inhalt",
            },
            headers={"X-CSRF-Token": csrf_s1},
        ).status_code
        == 403
    )

    # 4. Lernjournal: Student 1 creates entry, cannot write feedback
    res_j = client.post(
        "/api/documents",
        json={
            "name": "Lernjournal KW 12",
            "type": "lernjournal",
            "content": "Heute gedreht.",
        },
        headers={"X-CSRF-Token": csrf_s1},
    )
    assert res_j.status_code == 201
    journal_id = res_j.get_json()["data"]["id"]

    assert (
        client.put(
            f"/api/documents/{journal_id}",
            json={"feedback": "Selbst gelobt"},
            headers={"X-CSRF-Token": csrf_s1},
        ).status_code
        == 403
    )

    # Trainer 1 (assigned supervisor) can write/edit/clear feedback on Lernjournal,
    # but CANNOT edit the entry content or delete the Lernjournal entry
    csrf_t1, _ = login(client, "trainer@vektorwerk.ch")
    assert (
        client.put(
            f"/api/documents/{journal_id}",
            json={"content": "Manipulierter Eintrag"},
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 403
    )
    assert (
        client.delete(
            f"/api/documents/{journal_id}",
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 403
    )
    res_fb = client.put(
        f"/api/documents/{journal_id}",
        json={"feedback": "Sehr guter Bericht!"},
        headers={"X-CSRF-Token": csrf_t1},
    )
    assert res_fb.status_code == 200
    assert res_fb.get_json()["data"]["feedback"] == "Sehr guter Bericht!"

    # Trainer 1 CAN create Ausbildungsgespräch and delete Zeugnis for Student 1
    res_ag = client.post(
        "/api/documents",
        json={
            "name": "Probezeitgespräch",
            "type": "ausbildungsgespraech",
            "owner": student1["id"],
            "content": "Alles bestens.",
        },
        headers={"X-CSRF-Token": csrf_t1},
    )
    assert res_ag.status_code == 201
    ag_id = res_ag.get_json()["data"]["id"]

    assert (
        client.delete(
            f"/api/documents/{zeugnis_id}",
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 200
    )

    # Student 1 can view Ausbildungsgespräch, but cannot edit or delete it
    csrf_s1, _ = login(client, "student@vektorwerk.ch")
    assert client.get(f"/api/documents/{ag_id}").status_code == 200
    assert (
        client.put(
            f"/api/documents/{ag_id}",
            json={"content": "Geändert"},
            headers={"X-CSRF-Token": csrf_s1},
        ).status_code
        == 403
    )
    assert (
        client.delete(
            f"/api/documents/{ag_id}",
            headers={"X-CSRF-Token": csrf_s1},
        ).status_code
        == 403
    )

    # Trainer 2 (not supervising Student 1) cannot see Student 1's grades or documents
    login(client, "trainer2@vektorwerk.ch")
    assert client.get("/api/grades").get_json()["data"] == []
    assert client.get(f"/api/grades?student={student1['id']}").status_code == 403
    assert client.get("/api/documents?type=lernjournal").get_json()["data"] == []
    assert client.get(f"/api/documents/{journal_id}").status_code == 404
    assert client.get(f"/api/documents/{grade_id}").status_code == 404


def test_personen_and_account_contact_privacy(client):
    # 1. Student 1 logs in and fetches /api/user
    csrf_s1, s1_me = login(client, "student@vektorwerk.ch")
    users_for_s1 = {
        u["company_email"]: u
        for u in client.get("/api/user").get_json()["data"]["users"]
    }

    # Student 1 sees own private contacts
    assert users_for_s1["student@vektorwerk.ch"]["private_email"] == "student1@privat.ch"
    assert users_for_s1["student@vektorwerk.ch"]["can_view_private"] is True
    assert users_for_s1["student@vektorwerk.ch"]["can_edit_contacts"] is False

    # Student 1 sees school & company contacts of supervisors and other students, but NEVER private contacts
    for other_email in (
        "trainer@vektorwerk.ch",
        "trainer2@vektorwerk.ch",
        "student2@vektorwerk.ch",
    ):
        other = users_for_s1[other_email]
        assert "private_email" not in other
        assert "private_address" not in other
        assert "private_phone" not in other
        assert other["can_view_private"] is False
        assert "company_email" in other
        assert "school_email" in other

    # Student 1 cannot edit own contact data
    assert (
        client.put(
            f"/api/user/{s1_me['id']}",
            json={"private_phone": "079 000 00 00"},
            headers={"X-CSRF-Token": csrf_s1},
        ).status_code
        == 403
    )

    # 2. Trainer 1 (supervises Student 1, not Student 2) logs in
    csrf_t1, t1_me = login(client, "trainer@vektorwerk.ch")
    users_for_t1 = {
        u["company_email"]: u
        for u in client.get("/api/user").get_json()["data"]["users"]
    }

    # Trainer 1 sees own private contacts and subordinate Student 1's private contacts
    assert users_for_t1["trainer@vektorwerk.ch"]["private_email"] == "trainer1@privat.ch"
    assert users_for_t1["student@vektorwerk.ch"]["private_email"] == "student1@privat.ch"

    # Trainer 1 does NOT see Trainer 2's private contacts or non-subordinate Student 2's private contacts
    assert "private_email" not in users_for_t1["trainer2@vektorwerk.ch"]
    assert "private_email" not in users_for_t1["student2@vektorwerk.ch"]

    # Trainer 1 can edit own contacts and Student 1's contacts, but NOT Student 2's or Trainer 2's
    assert (
        client.put(
            f"/api/user/{t1_me['id']}",
            json={"private_phone": "079 999 99 99"},
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 200
    )
    s1_id = users_for_t1["student@vektorwerk.ch"]["id"]
    s2_id = users_for_t1["student2@vektorwerk.ch"]["id"]
    t2_id = users_for_t1["trainer2@vektorwerk.ch"]["id"]

    assert (
        client.put(
            f"/api/user/{s1_id}",
            json={"private_phone": "079 888 88 88"},
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 200
    )
    assert (
        client.put(
            f"/api/user/{s2_id}",
            json={"private_phone": "079 777 77 77"},
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 403
    )
    assert (
        client.put(
            f"/api/user/{t2_id}",
            json={"company_phone": "052 000 00 00"},
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 403
    )

    # 3. Lehrvertrag / Bewerbung documents: Trainer 1 can create & edit for Student 1, not Student 2
    res_v = client.post(
        "/api/documents",
        json={
            "name": "Lehrvertrag Lukas",
            "type": "vertrag",
            "owner": s1_id,
            "content": "Vertragsinhalt",
        },
        headers={"X-CSRF-Token": csrf_t1},
    )
    assert res_v.status_code == 201
    vertrag_id = res_v.get_json()["data"]["id"]

    assert (
        client.post(
            "/api/documents",
            json={
                "name": "Lehrvertrag Elena",
                "type": "vertrag",
                "owner": s2_id,
                "content": "Vertragsinhalt",
            },
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 403
    )

    # Student 1 can view own Lehrvertrag, but cannot edit or delete it
    csrf_s1, _ = login(client, "student@vektorwerk.ch")
    assert client.get(f"/api/documents/{vertrag_id}").status_code == 200
    assert (
        client.put(
            f"/api/documents/{vertrag_id}",
            json={"name": "Geändert"},
            headers={"X-CSRF-Token": csrf_s1},
        ).status_code
        == 403
    )
    assert (
        client.delete(
            f"/api/documents/{vertrag_id}",
            headers={"X-CSRF-Token": csrf_s1},
        ).status_code
        == 403
    )


def test_company_membership_and_email_domain(client):
    csrf, trainer = login(client, "trainer@vektorwerk.ch")

    def create_user(email, **extra):
        payload = {
            "role": "lernender",
            "name": "Max",
            "surname": "Muster",
            "company_email": email,
            "job_title": "Polymechanikerin / Polymechaniker EFZ",
            "supervisor_id": trainer["id"],
            **extra,
        }
        return client.post(
            "/api/user", json=payload, headers={"X-CSRF-Token": csrf}
        )

    # A company email outside the company domain is rejected
    res = create_user("max.muster@other.ch")
    assert res.status_code == 400
    assert "vektorwerk.ch" in res.get_json()["error"]

    # A matching company email is accepted and the company address is inherited
    res = create_user("max.muster@vektorwerk.ch")
    assert res.status_code == 201
    created = res.get_json()["data"]
    assert created["company"] == "Vektorwerk Technik AG"
    assert created["company_id"] == trainer["company_id"]
    assert created["company_domain"] == "vektorwerk.ch"
    assert created["company_address"] == "Industriestrasse 1"

    # Company membership cannot be changed through the user endpoint
    for payload in ({"company_id": 999}, {"company": "Andere AG"}):
        res = client.put(
            f"/api/user/{created['id']}",
            json=payload,
            headers={"X-CSRF-Token": csrf},
        )
        assert res.status_code == 400
        assert "Firma" in res.get_json()["error"]

    # Changing the company email still respects the company domain
    res = client.put(
        f"/api/user/{created['id']}",
        json={"company_email": "max.muster@other.ch"},
        headers={"X-CSRF-Token": csrf},
    )
    assert res.status_code == 400
    assert "vektorwerk.ch" in res.get_json()["error"]

    res = client.put(
        f"/api/user/{created['id']}",
        json={"company_email": "max.neu@vektorwerk.ch"},
        headers={"X-CSRF-Token": csrf},
    )
    assert res.status_code == 200
    updated = res.get_json()["data"]
    assert updated["company_email"] == "max.neu@vektorwerk.ch"
    assert updated["company_id"] == trainer["company_id"]
