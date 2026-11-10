import os
import tempfile
from contextlib import contextmanager
from datetime import date
import pytest
from backend.app import create_app
from backend.models import (
    db,
    Company,
    User,
    UserRouting,
    UserRelation,
    Project,
    Eval,
    Participation,
    Documents,
)
from backend.auth import hash_password
from backend.storage import resolve_safe_path
from backend import tenants

COMPANY_DOMAIN = "vektorwerk.ch"


@contextmanager
def company_context(client_or_app, domain=COMPANY_DOMAIN):
    """Open the fixture company's tenant database within an app context."""
    app = getattr(client_or_app, "application", client_or_app)
    with app.app_context():
        company = db.session.query(Company).filter_by(email_domain=domain).one()
        with tenants.tenant_context(company):
            yield company


def create_fixture_user(
    company,
    *,
    role,
    name,
    surname,
    company_email,
    job_title,
    password="Passwort123!",
    private_address="",
    private_email="",
    private_phone="",
    school_address="",
    school_email="",
    school_phone="",
    **extra_fields,
):
    """Create a user inside the company DB plus its control routing row."""
    user = User(
        role=role,
        name=name,
        surname=surname,
        company_id=company.id,
        password_hash=hash_password(password),
        private_address=private_address,
        private_email=private_email,
        private_phone=private_phone,
        school_address=school_address,
        school_email=school_email,
        school_phone=school_phone,
        company_address=company.address or "",
        company_email=company_email,
        company_phone="",
        job_title=job_title,
        **extra_fields,
    )
    with tenants.tenant_context(company):
        db.session.add(user)
        db.session.flush()
        db.session.add(
            UserRouting(
                id=user.id,
                company_id=company.id,
                company_email=user.company_email,
                private_email=user.private_email or "",
                school_email=user.school_email or "",
            )
        )
        db.session.commit()
    return user


def _company_user_map(client):
    """Log in and return {company_email: user_dict} of the fixture company."""
    _, _ = login(client, "trainer@vektorwerk.ch")
    return {
        u["company_email"]: u
        for u in client.get("/api/user").get_json()["data"]["users"]
    }


@pytest.fixture
def client():
    tmp_dir = tempfile.mkdtemp(prefix="lehrjahre_test_")
    db_file = os.path.join(tmp_dir, "control.db")
    companies_dir = os.path.join(tmp_dir, "companies")

    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_file}",
            "COMPANY_ROOT": companies_dir,
            "SECRET_KEY": "test-secret",
            "SESSION_COOKIE_SECURE": False,
            "IS_DEV": True,
            "DEBUG": False,
            # Isolate mail handling from the developer's .env: no SMTP host,
            # outgoing mail is captured in the dev outbox.
            "SMTP_HOST": "",
            "MAIL_DEV_OUTBOX": os.path.join(tmp_dir, "outbox.log"),
        }
    )

    with app.app_context():
        company = Company(
            name="Vektorwerk Technik AG",
            email_domain=COMPANY_DOMAIN,
            address="Industriestrasse 1",
        )
        foreign_company = Company(
            name="Fremd AG",
            email_domain="fremd.ch",
            address="Fremdstrasse 1",
        )
        db.session.add_all([company, foreign_company])
        db.session.commit()
        tenants.create_company_schema(company)
        tenants.create_company_schema(foreign_company)

        # Supervisor 1 (supervises student 1)
        trainer1 = create_fixture_user(
            company,
            role="ausbildner",
            name="Thomas",
            surname="Keller",
            private_address="Trainer1 Privatweg 1",
            private_email="trainer1@privat.ch",
            private_phone="079 111 11 11",
            school_address="BBW Winterthur",
            school_email="trainer1@bbw.ch",
            school_phone="052 111 11 11",
            company_email="trainer@vektorwerk.ch",
            job_title="Berufsbildner",
        )
        # Supervisor 2 (same company, supervises nobody initially)
        trainer2 = create_fixture_user(
            company,
            role="ausbildner",
            name="Marco",
            surname="Brunner",
            private_address="Trainer2 Privatweg 2",
            private_email="trainer2@privat.ch",
            private_phone="079 222 22 22",
            school_address="AZW Winterthur",
            school_email="trainer2@azw.ch",
            school_phone="052 222 22 22",
            company_email="trainer2@vektorwerk.ch",
            job_title="Fachvorgesetzter",
        )
        # Company administrator: user/relationship management is exclusively
        # hers; visibility rules are the same as a supervisor's.
        admin_user = create_fixture_user(
            company,
            role="admin",
            name="Sabine",
            surname="Adler",
            private_address="Adminweg 1",
            private_email="admin1@privat.ch",
            private_phone="079 100 10 10",
            school_address="",
            school_email="",
            school_phone="",
            company_email="admin@vektorwerk.ch",
            job_title="Administrator",
        )
        # Student 1 (subordinate to trainer1)
        student1 = create_fixture_user(
            company,
            role="lernender",
            name="Lukas",
            surname="Frei",
            private_address="Student1 Privatweg 10",
            private_email="student1@privat.ch",
            private_phone="079 333 33 33",
            school_address="BBW Winterthur",
            school_email="student1@bbw.ch",
            school_phone="052 333 33 33",
            company_email="student@vektorwerk.ch",
            job_title="Polymechanikerin / Polymechaniker EFZ",
            start_date=date(2024, 8, 12),
            end_date=date(2028, 7, 31),
        )
        # Student 2 (same company, NOT subordinate to trainer1 or trainer2)
        student2 = create_fixture_user(
            company,
            role="lernender",
            name="Elena",
            surname="Schmid",
            private_address="Student2 Privatweg 20",
            private_email="student2@privat.ch",
            private_phone="079 444 44 44",
            school_address="BBW Winterthur",
            school_email="student2@bbw.ch",
            school_phone="052 444 44 44",
            company_email="student2@vektorwerk.ch",
            job_title="Automatikerin / Automatiker EFZ",
            start_date=date(2025, 8, 11),
            end_date=date(2029, 7, 31),
        )
        # Users of a foreign company: each company lives in its own database.
        trainer3 = create_fixture_user(
            foreign_company,
            role="ausbildner",
            name="Nina",
            surname="Weber",
            private_address="Fremdweg 1",
            private_email="nina@privat.ch",
            private_phone="079 555 55 55",
            school_address="Berufsfachschule Fremd",
            school_email="nina@schule.ch",
            school_phone="052 555 55 55",
            company_email="nina@fremd.ch",
            job_title="Berufsbildnerin",
        )
        student3 = create_fixture_user(
            foreign_company,
            role="lernender",
            name="Ali",
            surname="Yilmaz",
            private_address="Fremdweg 2",
            private_email="ali@privat.ch",
            private_phone="079 666 66 66",
            school_address="Berufsfachschule Fremd",
            school_email="ali@schule.ch",
            school_phone="052 666 66 66",
            company_email="ali@fremd.ch",
            job_title="Automatiker EFZ",
            start_date=date(2025, 8, 11),
            end_date=date(2029, 7, 31),
        )
        with tenants.tenant_context(company):
            db.session.add(UserRelation(supervisor=trainer1.id, student=student1.id))
            db.session.commit()
        with tenants.tenant_context(foreign_company):
            db.session.add(UserRelation(supervisor=trainer3.id, student=student3.id))
            db.session.commit()

    with app.test_client() as test_client:
        yield test_client


def login(client, email, password="Passwort123!"):
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    data = res.get_json()["data"]
    return data["csrf_token"], data["user"]


def test_companies_have_separate_database_files_on_disk(client):
    """Every company owns its own SQLite file with only its own users in it.

    Nothing about another company — not even user rows — exists inside a
    company's database, so cross-company data leakage is structurally
    impossible.
    """
    expected_emails = {
        "vektorwerk.ch": {
            "trainer@vektorwerk.ch",
            "trainer2@vektorwerk.ch",
            "admin@vektorwerk.ch",
            "student@vektorwerk.ch",
            "student2@vektorwerk.ch",
        },
        "fremd.ch": {"nina@fremd.ch", "ali@fremd.ch"},
    }
    foreign_emails = set(expected_emails["fremd.ch"])

    with company_context(client) as company:
        paths = tenants.tenant_db_path(company)
        emails = {u.company_email for u in User.query.all()}
        company_ids = {u.company_id for u in User.query.all()}
    assert paths.endswith("vektorwerk-technik-ag/app.db")
    assert emails == expected_emails["vektorwerk.ch"]
    assert company_ids == {company.id}
    assert not (foreign_emails & emails)

    with company_context(client, "fremd.ch") as company:
        paths = tenants.tenant_db_path(company)
        emails = {u.company_email for u in User.query.all()}
        company_ids = {u.company_id for u in User.query.all()}
    assert paths.endswith("fremd-ag/app.db")
    assert emails == expected_emails["fremd.ch"]
    assert company_ids == {company.id}
    assert not (expected_emails["vektorwerk.ch"] & emails)


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
    companies_root = client.application.config["COMPANY_ROOT"]
    assert os.path.isdir(
        os.path.join(companies_root, "vektorwerk-technik-ag", "documents")
    )

    # Path traversal check
    with company_context(client):
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
            "score_type": "grade",
            "score_value": 5.5,
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
    assert s1_evals[0]["score_type"] is None
    assert s1_evals[0]["score_value"] is None
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
    assert s1_evals_after[0]["score_type"] == "grade"
    assert s1_evals_after[0]["score_value"] == 5.5
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
    csrf_t1, trainer1 = login(client, "trainer@vektorwerk.ch")
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
    assert res_fb.get_json()["data"]["feedback_author"] == trainer1["id"]
    assert res_fb.get_json()["data"]["feedback_author_name"] == "Thomas Keller"

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
    assert client.get(f"/api/grades?student={student1['id']}").status_code == 404
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
    # Creating users — and master-data changes — are admin capabilities now.
    _, trainer = login(client, "trainer@vektorwerk.ch")
    csrf, _ = login(client, "admin@vektorwerk.ch")

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


def test_project_planning_implementation_and_evaluation_workflow(client):
    csrf_tr, trainer = login(client, "trainer@vektorwerk.ch")
    students = client.get("/api/user?role=lernender").get_json()["data"]["users"]
    student_id = next(
        s["id"] for s in students if s["company_email"] == "student@vektorwerk.ch"
    )

    # 1. Supervisor creates a project draft with subtasks
    res_create = client.post(
        "/api/project",
        json={
            "title": "Fertigungsprojekt Fräsen",
            "description": "Hauptauftrag für das Fräsprojekt",
            "assigned_students": [student_id],
            "goals": ["Toleranz einhalten", "Arbeitssicherheit beachten"],
            "is_published": False,
            "tasks": [
                {"title": "Aufgabe 1: Rohteil vorbereiten", "description": "Zuschnitt"},
                {"title": "Aufgabe 2: Endbearbeitung", "description": "Schlichten"},
            ],
        },
        headers={"X-CSRF-Token": csrf_tr},
    )
    assert res_create.status_code == 201
    proj = res_create.get_json()["data"]
    assert len(proj["tasks"]) == 2
    task1_id = proj["tasks"][0]["id"]

    # 2. Student cannot see unpublished project
    csrf_stu, _ = login(client, "student@vektorwerk.ch")
    stu_projects = client.get("/api/project").get_json()["data"]
    assert len(stu_projects) == 0

    # 3. Supervisor releases project (is_published = True)
    csrf_tr, _ = login(client, "trainer@vektorwerk.ch")
    res_pub = client.put(
        f"/api/project/{proj['id']}",
        json={"is_published": True},
        headers={"X-CSRF-Token": csrf_tr},
    )
    assert res_pub.status_code == 200
    assert res_pub.get_json()["data"]["is_published"] is True

    # 4. Student now sees the project and submits Durchführung on Task 1
    csrf_stu, _ = login(client, "student@vektorwerk.ch")
    stu_projects = client.get("/api/project").get_json()["data"]
    assert len(stu_projects) == 1

    # Submitting on root project when subtasks exist is rejected
    res_root_impl = client.post(
        "/api/implementation",
        json={"project": proj["id"], "text": "Hauptbericht", "is_done": True},
        headers={"X-CSRF-Token": csrf_stu},
    )
    assert res_root_impl.status_code == 400

    # Submitting on Task 1 with is_done=True locks it
    res_task_impl = client.post(
        "/api/implementation",
        json={"project": task1_id, "text": "Rohteil erfolgreich gefräst.", "is_done": True},
        headers={"X-CSRF-Token": csrf_stu},
    )
    assert res_task_impl.status_code == 201
    impl_id = res_task_impl.get_json()["data"]["id"]

    # Student cannot modify after release/submission
    res_locked = client.put(
        f"/api/implementation/{impl_id}",
        json={"text": "Nachträgliche Änderung"},
        headers={"X-CSRF-Token": csrf_stu},
    )
    assert res_locked.status_code == 403

    # 5. Supervisor cannot edit student text, but can undo release (is_done=False)
    csrf_tr, _ = login(client, "trainer@vektorwerk.ch")
    res_tr_edit = client.put(
        f"/api/implementation/{impl_id}",
        json={"text": "Vom Ausbildner geändert"},
        headers={"X-CSRF-Token": csrf_tr},
    )
    assert res_tr_edit.status_code == 403

    res_tr_unlock = client.put(
        f"/api/implementation/{impl_id}",
        json={"is_done": False},
        headers={"X-CSRF-Token": csrf_tr},
    )
    assert res_tr_unlock.status_code == 200
    assert res_tr_unlock.get_json()["data"]["is_done"] is False

    # 6. Supervisor saves Auswertung (global, project, task, goal) and releases it
    res_eval = client.post(
        f"/api/evaluation/project/{proj['id']}",
        json={
            "global_eval_text": "Gutes Gesamtergebnis.",
            "is_completed": False,
            "student": student_id,
            "is_released": True,
            "project_eval": {
                "eval_text": "Saubere Ausführung über das gesamte Projekt.",
                "score_type": "grade",
                "score_value": 5.3,
            },
            "task_evals": [
                {
                    "task_id": task1_id,
                    "eval_text": "Masshaltig vorbereitet.",
                    "score_type": "percent",
                    "score_value": 92,
                }
            ],
            "goal_evals": [
                {"goal": "Toleranz einhalten", "eval_text": "Alle Toleranzen erreicht."}
            ],
        },
        headers={"X-CSRF-Token": csrf_tr},
    )
    assert res_eval.status_code == 200

    # Student can now read the released evaluation
    csrf_stu, _ = login(client, "student@vektorwerk.ch")
    detail = client.get(f"/api/project/{proj['id']}").get_json()["data"]
    assert detail["global_eval_text"] == "Gutes Gesamtergebnis."
    assert len(detail["evaluations"]) == 3


def test_project_submission_markdown_document_lock(client):
    csrf_tr, trainer = login(client, "trainer@vektorwerk.ch")
    students = client.get("/api/user?role=lernender").get_json()["data"]["users"]
    student_id = next(
        s["id"] for s in students if s["company_email"] == "student@vektorwerk.ch"
    )

    # Trainers can create project planning documents.
    res_plan_doc = client.post(
        "/api/documents",
        json={
            "name": "Projektplan: Fräsen",
            "content": "# Projektplan",
            "type": "projekt",
            "owner": trainer["id"],
            "is_done": True,
        },
        headers={"X-CSRF-Token": csrf_tr},
    )
    assert res_plan_doc.status_code == 201
    plan_doc_id = res_plan_doc.get_json()["data"]["id"]

    res_proj = client.post(
        "/api/project",
        json={
            "title": "Dokumentabgabe",
            "description": "Projekt mit Dokumentabgabe",
            "assigned_students": [student_id],
            "is_published": False,
        },
        headers={"X-CSRF-Token": csrf_tr},
    )
    assert res_proj.status_code == 201
    proj_id = res_proj.get_json()["data"]["id"]
    assert (
        client.put(
            f"/api/project/{proj_id}",
            json={"is_published": True},
            headers={"X-CSRF-Token": csrf_tr},
        ).status_code
        == 200
    )

    # Students can create their own project submission document.
    csrf_stu, _ = login(client, "student@vektorwerk.ch")
    res_doc = client.post(
        "/api/documents",
        json={
            "name": "Abgabe: Dokumentabgabe",
            "content": "# Bericht\nErste Fassung",
            "type": "projekt",
            "owner": student_id,
            "is_done": True,
        },
        headers={"X-CSRF-Token": csrf_stu},
    )
    assert res_doc.status_code == 201
    doc_id = res_doc.get_json()["data"]["id"]

    res_imp = client.post(
        "/api/implementation",
        json={
            "project": proj_id,
            "title": "Dokumentabgabe",
            "document_id": doc_id,
            "is_done": True,
        },
        headers={"X-CSRF-Token": csrf_stu},
    )
    assert res_imp.status_code == 201
    imp_id = res_imp.get_json()["data"]["id"]

    # Released project documents are immutable for students and trainers.
    assert (
        client.put(
            f"/api/documents/{doc_id}",
            json={"content": "# Nachträglich geändert"},
            headers={"X-CSRF-Token": csrf_stu},
        ).status_code
        == 403
    )
    assert (
        client.delete(
            f"/api/documents/{doc_id}",
            headers={"X-CSRF-Token": csrf_stu},
        ).status_code
        == 403
    )

    csrf_tr, _ = login(client, "trainer@vektorwerk.ch")
    assert (
        client.put(
            f"/api/documents/{doc_id}",
            json={"content": "# Trainer ändert"},
            headers={"X-CSRF-Token": csrf_tr},
        ).status_code
        == 403
    )
    assert (
        client.delete(
            f"/api/documents/{doc_id}",
            headers={"X-CSRF-Token": csrf_tr},
        ).status_code
        == 403
    )

    # Reopening the submission makes the document editable again.
    assert (
        client.put(
            f"/api/implementation/{imp_id}",
            json={"is_done": False},
            headers={"X-CSRF-Token": csrf_tr},
        ).status_code
        == 200
    )

    csrf_stu, _ = login(client, "student@vektorwerk.ch")
    res_update = client.put(
        f"/api/documents/{doc_id}",
        json={"content": "# Bericht\nÜberarbeitet"},
        headers={"X-CSRF-Token": csrf_stu},
    )
    assert res_update.status_code == 200
    assert "Überarbeitet" in res_update.get_json()["data"]["content"]

    # The trainer's own project planning document can still be deleted.
    csrf_tr, _ = login(client, "trainer@vektorwerk.ch")
    assert (
        client.delete(
            f"/api/documents/{plan_doc_id}",
            headers={"X-CSRF-Token": csrf_tr},
        ).status_code
        == 200
    )


def test_cross_company_isolation_and_authorless_projects(client):
    # Foreign company creates its own project, grade, document, knowledge,
    # evaluation and implementation report.
    csrf_ft, foreign_trainer = login(client, "nina@fremd.ch")
    res = client.post(
        "/api/project",
        json={
            "title": "Fremdprojekt",
            "description": "Fremdbeschreibung",
            "planning_released": True,
        },
        headers={"X-CSRF-Token": csrf_ft},
    )
    assert res.status_code == 201
    foreign_project_id = res.get_json()["data"]["id"]

    csrf_fs, foreign_student = login(client, "ali@fremd.ch")
    res = client.post(
        "/api/documents",
        json={"name": "Fremdzeugnis", "type": "zeugnis", "content": "Geheim"},
        headers={"X-CSRF-Token": csrf_fs},
    )
    assert res.status_code == 201
    foreign_doc_id = res.get_json()["data"]["id"]

    res = client.post(
        "/api/grades",
        json={
            "subject": "Mathematik",
            "title": "Fremdnote",
            "grade": 5.0,
            "date": "2026-03-10",
        },
        headers={"X-CSRF-Token": csrf_fs},
    )
    assert res.status_code == 201
    foreign_grade_id = res.get_json()["data"]["id"]

    res = client.post(
        "/api/knowledge",
        json={"title": "Fremdwissen", "content": "# Geheim"},
        headers={"X-CSRF-Token": csrf_fs},
    )
    assert res.status_code == 201
    foreign_knowledge_id = res.get_json()["data"]["id"]

    csrf_ft, _ = login(client, "nina@fremd.ch")
    res = client.post(
        "/api/evaluation",
        json={
            "project": foreign_project_id,
            "student": foreign_student["id"],
            "goal": "Fremdziel",
            "eval_text": "Geheime Bewertung",
        },
        headers={"X-CSRF-Token": csrf_ft},
    )
    assert res.status_code == 201
    foreign_eval_id = res.get_json()["data"]["id"]

    csrf_fs, _ = login(client, "ali@fremd.ch")
    res = client.post(
        "/api/implementation",
        json={"project": foreign_project_id, "title": "Fremdbericht"},
        headers={"X-CSRF-Token": csrf_fs},
    )
    assert res.status_code == 201
    foreign_impl_id = res.get_json()["data"]["id"]

    # A Vektorwerk supervisor must not see or mutate any of it.
    csrf_t1, _ = login(client, "trainer@vektorwerk.ch")

    assert all(
        p["id"] != foreign_project_id
        for p in client.get("/api/project").get_json()["data"]
    )
    assert client.get(f"/api/project/{foreign_project_id}").status_code == 404
    # Per-company databases have independent id spaces: the foreign project
    # id does not reference anything in this company's database, so write
    # access also fails with "not found" instead of a policy error.
    assert (
        client.put(
            f"/api/project/{foreign_project_id}",
            json={"title": "Übernommen"},
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/project/{foreign_project_id}",
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 404
    )

    users = client.get("/api/user").get_json()["data"]["users"]
    assert all(u["company"] == "Vektorwerk Technik AG" for u in users)
    # With one database per company, user ids are company-local: the same
    # numeric id in both databases points to the respective local user and
    # never to the foreign person.
    local_me = client.get(f"/api/user/{foreign_student['id']}").get_json()[
        "data"
    ]
    assert local_me["company_email"] != "ali@fremd.ch"

    assert (
        client.get(f"/api/grades?student={foreign_student['id']}").status_code
        == 404
    )
    assert (
        client.put(
            f"/api/grades/{foreign_grade_id}",
            json={"grade": 4.0},
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/grades/{foreign_grade_id}",
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 404
    )

    assert all(
        n["id"] != foreign_knowledge_id
        for n in client.get("/api/knowledge").get_json()["data"]
    )
    assert client.get(f"/api/knowledge/{foreign_knowledge_id}").status_code == 404
    assert (
        client.put(
            f"/api/knowledge/{foreign_knowledge_id}",
            json={"title": "Übernommen"},
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/knowledge/{foreign_knowledge_id}",
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 404
    )

    assert all(
        d["id"] != foreign_doc_id
        for d in client.get("/api/documents?type=zeugnis").get_json()["data"]
    )
    assert client.get(f"/api/documents/{foreign_doc_id}").status_code == 404
    assert client.get(f"/api/documents/{foreign_doc_id}/file").status_code == 404
    assert (
        client.put(
            f"/api/documents/{foreign_doc_id}",
            json={"name": "Übernommen"},
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/documents/{foreign_doc_id}",
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 404
    )

    assert all(
        e["id"] != foreign_eval_id
        for e in client.get("/api/evaluation").get_json()["data"]
    )
    assert (
        client.put(
            f"/api/evaluation/{foreign_eval_id}",
            json={"eval_text": "Übernommen"},
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/evaluation/{foreign_eval_id}",
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 404
    )

    assert all(
        i["id"] != foreign_impl_id
        for i in client.get("/api/implementation").get_json()["data"]
    )
    assert (
        client.put(
            f"/api/implementation/{foreign_impl_id}",
            json={"is_done": True},
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/implementation/{foreign_impl_id}",
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 404
    )

    # A project without an author is not visible to anybody.
    with company_context(client):
        orphan = Project(
            title="Verwaistes Projekt", author=None, planning_released=True
        )
        db.session.add(orphan)
        db.session.commit()
        orphan_id = orphan.id

    def project_titles():
        return [
            p["title"] for p in client.get("/api/project").get_json()["data"]
        ]

    assert "Verwaistes Projekt" not in project_titles()
    assert client.get(f"/api/project/{orphan_id}").status_code == 404
    assert (
        client.put(
            f"/api/project/{orphan_id}",
            json={"title": "Übernommen"},
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 403
    )

    # The foreign company never sees it (id spaces are company-local).
    csrf_ft, _ = login(client, "nina@fremd.ch")
    assert "Verwaistes Projekt" not in project_titles()
    if client.get(f"/api/project/{orphan_id}").status_code == 200:
        remote = client.get(f"/api/project/{orphan_id}").get_json()["data"]
        assert remote["title"] != "Verwaistes Projekt"

    login(client, "student@vektorwerk.ch")
    assert "Verwaistes Projekt" not in project_titles()
    assert client.get(f"/api/project/{orphan_id}").status_code == 404


def test_eval_and_implementation_ignore_foreign_identity_fields(client):
    csrf_ft, foreign_trainer = login(client, "nina@fremd.ch")
    csrf_fs, foreign_student = login(client, "ali@fremd.ch")
    csrf_ft, foreign_trainer = login(client, "nina@fremd.ch")

    res = client.post(
        "/api/project",
        json={
            "title": "Fremdprojekt",
            "description": "Fremdbeschreibung",
            "planning_released": True,
        },
        headers={"X-CSRF-Token": csrf_ft},
    )
    assert res.status_code == 201
    foreign_project_id = res.get_json()["data"]["id"]

    res = client.post(
        "/api/evaluation",
        json={
            "project": foreign_project_id,
            "student": foreign_student["id"],
            "goal": "Fremdziel",
        },
        headers={"X-CSRF-Token": csrf_ft},
    )
    assert res.status_code == 201
    assert res.get_json()["data"]["supervisor"] == foreign_trainer["id"]

    csrf_fs, _ = login(client, "ali@fremd.ch")
    res = client.post(
        "/api/implementation",
        json={"project": foreign_project_id, "title": "Fremdbericht"},
        headers={"X-CSRF-Token": csrf_fs},
    )
    assert res.status_code == 201
    foreign_impl_id = res.get_json()["data"]["id"]

    csrf_s1, student1 = login(client, "student@vektorwerk.ch")
    csrf_t1, trainer1 = login(client, "trainer@vektorwerk.ch")

    res = client.post(
        "/api/project",
        json={
            "title": "Eigenes Projekt",
            "description": "Eigene Beschreibung",
            "planning_released": True,
        },
        headers={"X-CSRF-Token": csrf_t1},
    )
    assert res.status_code == 201
    project_id = res.get_json()["data"]["id"]

    # A participation from another company can never be attached.
    res = client.post(
        "/api/evaluation",
        json={
            "project": project_id,
            "student": student1["id"],
            "goal": "Ziel",
            "participation": foreign_impl_id,
            "supervisor": foreign_trainer["id"],
        },
        headers={"X-CSRF-Token": csrf_t1},
    )
    assert res.status_code == 400

    # A client-supplied supervisor is ignored; the acting supervisor is recorded.
    res = client.post(
        "/api/evaluation",
        json={
            "project": project_id,
            "student": student1["id"],
            "goal": "Ziel",
            "supervisor": foreign_trainer["id"],
            "eval_text": "Entwurf",
        },
        headers={"X-CSRF-Token": csrf_t1},
    )
    assert res.status_code == 201
    evaluation = res.get_json()["data"]
    assert evaluation["supervisor"] == trainer1["id"]
    assert evaluation["supervisor_name"] == "Thomas Keller"
    eval_id = evaluation["id"]

    res = client.put(
        f"/api/evaluation/{eval_id}",
        json={"supervisor": foreign_trainer["id"], "eval_text": "Aktualisiert"},
        headers={"X-CSRF-Token": csrf_t1},
    )
    assert res.status_code == 200
    assert res.get_json()["data"]["supervisor"] == trainer1["id"]
    assert res.get_json()["data"]["supervisor_name"] == "Thomas Keller"

    res = client.put(
        f"/api/evaluation/{eval_id}",
        json={"participation": foreign_impl_id},
        headers={"X-CSRF-Token": csrf_t1},
    )
    assert res.status_code == 400

    csrf_s1, _ = login(client, "student@vektorwerk.ch")
    res = client.post(
        "/api/implementation",
        json={"project": project_id, "title": "Eigener Bericht"},
        headers={"X-CSRF-Token": csrf_s1},
    )
    assert res.status_code == 201
    impl_id = res.get_json()["data"]["id"]

    csrf_t1, _ = login(client, "trainer@vektorwerk.ch")
    res = client.put(
        f"/api/implementation/{impl_id}",
        json={"is_done": True, "supervisor": foreign_trainer["id"]},
        headers={"X-CSRF-Token": csrf_t1},
    )
    assert res.status_code == 200
    assert res.get_json()["data"]["supervisor"] == trainer1["id"]
    assert res.get_json()["data"]["supervisor_name"] == "Thomas Keller"

    # Note: with one database (and consistent foreign keys) per company, a
    # row can never reference another company's users, so the old
    # "legacy foreign supervisor" masking scenario cannot occur anymore.
    # The masking policy itself is kept as defense-in-depth.


def test_profile_picture_must_belong_to_target(client):
    csrf_s1, student1 = login(client, "student@vektorwerk.ch")
    res = client.post(
        "/api/documents",
        json={"name": "Profilbild Lukas", "type": "profilbild", "content": "img"},
        headers={"X-CSRF-Token": csrf_s1},
    )
    assert res.status_code == 201
    picture_id = res.get_json()["data"]["id"]

    res = client.put(
        f"/api/user/{student1['id']}",
        json={"picture_document": picture_id},
        headers={"X-CSRF-Token": csrf_s1},
    )
    assert res.status_code == 200
    assert res.get_json()["data"]["picture_document"] == picture_id

    # Profile pictures are company contact data: colleagues may view them.
    login(client, "student2@vektorwerk.ch")
    assert client.get(f"/api/documents/{picture_id}/file").status_code == 200

    # A non-profile document cannot be used as a profile picture.
    csrf_s1, student1 = login(client, "student@vektorwerk.ch")
    res = client.post(
        "/api/documents",
        json={"name": "Zeugnis", "type": "zeugnis", "content": "Note 5"},
        headers={"X-CSRF-Token": csrf_s1},
    )
    assert res.status_code == 201
    other_doc_id = res.get_json()["data"]["id"]
    assert (
        client.put(
            f"/api/user/{student1['id']}",
            json={"picture_document": other_doc_id},
            headers={"X-CSRF-Token": csrf_s1},
        ).status_code
        == 400
    )

    # A document id from another company's database cannot be dereferenced
    # here: with one database per company the id spaces are independent, so
    # assigning it finds no document (400) and fetching it 404s.
    csrf_fs, foreign_student = login(client, "ali@fremd.ch")
    res = client.post(
        "/api/documents",
        json={"name": "Fremddatei", "type": "zeugnis", "content": "x"},
        headers={"X-CSRF-Token": csrf_fs},
    )
    assert res.status_code == 201
    other = res.get_json()["data"]["id"]

    res = client.post(
        "/api/documents",
        json={"name": "Fremdbild", "type": "profilbild", "content": "img"},
        headers={"X-CSRF-Token": csrf_fs},
    )
    assert res.status_code == 201
    foreign_picture_id = res.get_json()["data"]["id"]
    assert foreign_picture_id > other

    with company_context(client, "fremd.ch"):
        # Make the foreign ids deterministically unused in the Vektorwerk DB.
        unused_id = max(foreign_picture_id, other) + 100

    csrf_s1, student1 = login(client, "student@vektorwerk.ch")
    assert (
        client.put(
            f"/api/user/{student1['id']}",
            json={"picture_document": unused_id},
            headers={"X-CSRF-Token": csrf_s1},
        ).status_code
        == 400
    )
    assert (
        client.get(f"/api/documents/{unused_id}/file").status_code == 404
    )


def test_profile_picture_management_permissions(client):
    csrf_s1, student1 = login(client, "student@vektorwerk.ch")

    # A supervisor may upload and assign a profile picture for a subordinate.
    csrf_t1, _ = login(client, "trainer@vektorwerk.ch")
    res = client.post(
        "/api/documents",
        json={
            "name": "Profilbild Lukas",
            "type": "profilbild",
            "owner": student1["id"],
            "content": "img",
        },
        headers={"X-CSRF-Token": csrf_t1},
    )
    assert res.status_code == 201
    picture_id = res.get_json()["data"]["id"]
    assert (
        client.put(
            f"/api/user/{student1['id']}",
            json={"picture_document": picture_id},
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 200
    )

    # An unrelated supervisor may neither upload nor assign it.
    csrf_t2, _ = login(client, "trainer2@vektorwerk.ch")
    assert (
        client.post(
            "/api/documents",
            json={
                "name": "Fremdes Profilbild",
                "type": "profilbild",
                "owner": student1["id"],
                "content": "img",
            },
            headers={"X-CSRF-Token": csrf_t2},
        ).status_code
        == 403
    )
    assert (
        client.put(
            f"/api/user/{student1['id']}",
            json={"picture_document": picture_id},
            headers={"X-CSRF-Token": csrf_t2},
        ).status_code
        == 403
    )

    # Another learner may view the company profile picture but not delete it.
    csrf_s2, _ = login(client, "student2@vektorwerk.ch")
    assert client.get(f"/api/documents/{picture_id}/file").status_code == 200
    assert (
        client.delete(
            f"/api/documents/{picture_id}",
            headers={"X-CSRF-Token": csrf_s2},
        ).status_code
        == 403
    )

    # The supervisor may delete it; the user's reference is cleared by the FK.
    csrf_t1, _ = login(client, "trainer@vektorwerk.ch")
    assert (
        client.delete(
            f"/api/documents/{picture_id}",
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 200
    )
    with company_context(client):
        user = db.session.get(User, student1["id"])
        assert user.picture_document is None


def test_deleting_user_reassigns_projects(client):
    csrf_t2, _ = login(client, "trainer2@vektorwerk.ch")
    res = client.post(
        "/api/project",
        json={"title": "Projekt von Trainer 2"},
        headers={"X-CSRF-Token": csrf_t2},
    )
    assert res.status_code == 201
    project_id = res.get_json()["data"]["id"]

    csrf_t1, trainer1 = login(client, "trainer@vektorwerk.ch")
    users = {
        u["company_email"]: u
        for u in client.get("/api/user").get_json()["data"]["users"]
    }
    trainer2_id = users["trainer2@vektorwerk.ch"]["id"]

    # Deleting users is an admin capability: a supervisor's attempt fails.
    assert (
        client.delete(
            f"/api/user/{trainer2_id}",
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 403
    )

    csrf_admin, admin = login(client, "admin@vektorwerk.ch")
    res = client.delete(
        f"/api/user/{trainer2_id}",
        headers={"X-CSRF-Token": csrf_admin},
    )
    assert res.status_code == 200

    with company_context(client):
        project = db.session.get(Project, project_id)
        assert project is not None
        assert project.author == admin["id"]
        assert Project.query.filter(Project.author.is_(None)).count() == 0

    assert client.get(f"/api/project/{project_id}").status_code == 200


def test_project_tree_permissions(client):
    with company_context(client):
        trainer1 = User.query.filter_by(
            company_email="trainer@vektorwerk.ch"
        ).one()
        trainer2 = User.query.filter_by(
            company_email="trainer2@vektorwerk.ch"
        ).one()
        student1 = User.query.filter_by(
            company_email="student@vektorwerk.ch"
        ).one()

        # A tree spanning two supervisors:
        # trainer2 root -> trainer2 child (student1 participates)
        # trainer1 own_root -> trainer2 foreign_child
        root = Project(
            title="Fremde Wurzel", author=trainer2.id, planning_released=True
        )
        db.session.add(root)
        db.session.flush()

        child = Project(
            title="Fremdes Kind",
            parent_project=root.id,
            author=trainer2.id,
            planning_released=True,
        )
        own_root = Project(
            title="Eigene Wurzel", author=trainer1.id, planning_released=True
        )
        db.session.add_all([child, own_root])
        db.session.flush()

        foreign_child = Project(
            title="Fremdes Unterprojekt",
            parent_project=own_root.id,
            author=trainer2.id,
            planning_released=True,
        )
        db.session.add(foreign_child)
        db.session.flush()

        db.session.add(
            Participation(
                supervisor=trainer2.id,
                student=student1.id,
                project=child.id,
                title="Mitarbeit",
            )
        )
        db.session.commit()

        ids = {
            "root": root.id,
            "child": child.id,
            "own_root": own_root.id,
            "foreign_child": foreign_child.id,
        }

    # Trainer 1 sees the whole tree context, but manages only own projects and
    # projects where their learner participates.
    csrf_t1, _ = login(client, "trainer@vektorwerk.ch")
    projects_by_id = {}
    for project in client.get("/api/project").get_json()["data"]:
        projects_by_id[project["id"]] = project
        for task in project.get("tasks", []):
            projects_by_id[task["id"]] = task
    assert set(ids.values()) <= set(projects_by_id)
    assert projects_by_id[ids["root"]]["can_manage"] is False
    assert projects_by_id[ids["child"]]["can_manage"] is True
    assert projects_by_id[ids["own_root"]]["can_manage"] is True
    assert projects_by_id[ids["foreign_child"]]["can_manage"] is False

    assert client.get(f"/api/project/{ids['root']}").status_code == 200
    assert (
        client.put(
            f"/api/project/{ids['root']}",
            json={"title": "Übernommen"},
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 403
    )
    assert (
        client.delete(
            f"/api/project/{ids['root']}",
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 403
    )
    assert (
        client.put(
            f"/api/project/{ids['child']}",
            json={"title": "Kind aktualisiert"},
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 200
    )
    assert (
        client.put(
            f"/api/project/{ids['own_root']}",
            json={"title": "Eigene Wurzel aktualisiert"},
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 200
    )
    assert (
        client.put(
            f"/api/project/{ids['foreign_child']}",
            json={"title": "Übernommen"},
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 403
    )
    assert (
        client.delete(
            f"/api/project/{ids['foreign_child']}",
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 403
    )

    # Trainer 2 sees own_root as an ancestor, but cannot manage it.
    csrf_t2, _ = login(client, "trainer2@vektorwerk.ch")
    t2_projects = {}
    for project in client.get("/api/project").get_json()["data"]:
        t2_projects[project["id"]] = project
        for task in project.get("tasks", []):
            t2_projects[task["id"]] = task
    assert t2_projects[ids["own_root"]]["can_manage"] is False
    assert t2_projects[ids["foreign_child"]]["can_manage"] is True
    assert (
        client.put(
            f"/api/project/{ids['own_root']}",
            json={"title": "Übernommen"},
            headers={"X-CSRF-Token": csrf_t2},
        ).status_code
        == 403
    )
    assert (
        client.delete(
            f"/api/project/{ids['own_root']}",
            headers={"X-CSRF-Token": csrf_t2},
        ).status_code
        == 403
    )
    assert (
        client.put(
            f"/api/project/{ids['foreign_child']}",
            json={"title": "Eigenes Unterprojekt aktualisiert"},
            headers={"X-CSRF-Token": csrf_t2},
        ).status_code
        == 200
    )

    # The learner sees participating projects plus released parent containers,
    # but may only submit reports on the project they actually participate in.
    csrf_s1, _ = login(client, "student@vektorwerk.ch")
    student_ids = set()
    for project in client.get("/api/project").get_json()["data"]:
        student_ids.add(project["id"])
        student_ids.update(t["id"] for t in project.get("tasks", []))
    assert ids["root"] in student_ids
    assert ids["child"] in student_ids
    assert ids["own_root"] not in student_ids
    assert ids["foreign_child"] not in student_ids
    assert client.get(f"/api/project/{ids['root']}").status_code == 200
    assert client.get(f"/api/project/{ids['child']}").status_code == 200
    assert client.get(f"/api/project/{ids['own_root']}").status_code == 404

    assert (
        client.post(
            "/api/implementation",
            json={"project": ids["root"], "title": "Falsche Ebene"},
            headers={"X-CSRF-Token": csrf_s1},
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/implementation",
            json={"project": ids["own_root"], "title": "Fremdes Projekt"},
            headers={"X-CSRF-Token": csrf_s1},
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/implementation",
            json={"project": ids["child"], "title": "Richtige Ebene"},
            headers={"X-CSRF-Token": csrf_s1},
        ).status_code
        in {200, 201}
    )

    # Learners can never mutate projects.
    assert (
        client.post(
            "/api/project",
            json={"title": "Lernenden-Projekt"},
            headers={"X-CSRF-Token": csrf_s1},
        ).status_code
        == 403
    )
    assert (
        client.put(
            f"/api/project/{ids['child']}",
            json={"title": "Übernommen"},
            headers={"X-CSRF-Token": csrf_s1},
        ).status_code
        == 403
    )
    assert (
        client.delete(
            f"/api/project/{ids['child']}",
            headers={"X-CSRF-Token": csrf_s1},
        ).status_code
        == 403
    )

    # Managing a directly accessible project still includes deletion.
    csrf_t1, _ = login(client, "trainer@vektorwerk.ch")
    assert (
        client.delete(
            f"/api/project/{ids['child']}",
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 200
    )


def test_supervisor_can_manage_own_certificates(client):
    csrf_t1, _ = login(client, "trainer@vektorwerk.ch")

    for doc_type in ("zeugnis", "kursnachweis"):
        res = client.post(
            "/api/documents",
            json={
                "name": f"Eigenes {doc_type}",
                "type": doc_type,
                "content": "Inhalt",
            },
            headers={"X-CSRF-Token": csrf_t1},
        )
        assert res.status_code == 201
        doc_id = res.get_json()["data"]["id"]

        assert (
            client.put(
                f"/api/documents/{doc_id}",
                json={"name": "Aktualisiert"},
                headers={"X-CSRF-Token": csrf_t1},
            ).status_code
            == 200
        )
        assert (
            client.delete(
                f"/api/documents/{doc_id}",
                headers={"X-CSRF-Token": csrf_t1},
            ).status_code
            == 200
        )


def test_remaining_crud_permissions(client):
    csrf_s1, student1 = login(client, "student@vektorwerk.ch")
    csrf_t1, _ = login(client, "trainer@vektorwerk.ch")

    # Grades: both roles may edit their accessible grades; unrelated trainers
    # may do neither.
    res = client.post(
        "/api/grades",
        json={
            "student": student1["id"],
            "subject": "Deutsch",
            "title": "Prüfung",
            "grade": 5.0,
            "date": "2026-03-10",
        },
        headers={"X-CSRF-Token": csrf_t1},
    )
    assert res.status_code == 201
    grade_id = res.get_json()["data"]["id"]
    assert (
        client.put(
            f"/api/grades/{grade_id}",
            json={"grade": 4.5},
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 200
    )

    csrf_s1, _ = login(client, "student@vektorwerk.ch")
    assert (
        client.put(
            f"/api/grades/{grade_id}",
            json={"grade": 5.5},
            headers={"X-CSRF-Token": csrf_s1},
        ).status_code
        == 200
    )
    assert (
        client.delete(
            f"/api/grades/{grade_id}",
            headers={"X-CSRF-Token": csrf_s1},
        ).status_code
        == 200
    )

    # Documents: supervisors may edit/delete their learners' documents.
    csrf_t1, _ = login(client, "trainer@vektorwerk.ch")
    res = client.post(
        "/api/documents",
        json={
            "name": "Gespräch",
            "type": "ausbildungsgespraech",
            "owner": student1["id"],
            "content": "Erstes Gespräch",
        },
        headers={"X-CSRF-Token": csrf_t1},
    )
    assert res.status_code == 201
    talk_id = res.get_json()["data"]["id"]
    assert (
        client.put(
            f"/api/documents/{talk_id}",
            json={"content": "Aktualisiertes Gespräch"},
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 200
    )
    assert (
        client.delete(
            f"/api/documents/{talk_id}",
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 200
    )

    res = client.post(
        "/api/documents",
        json={
            "name": "Bewerbung",
            "type": "bewerbung",
            "owner": student1["id"],
            "content": "Bewerbung",
        },
        headers={"X-CSRF-Token": csrf_t1},
    )
    assert res.status_code == 201
    application_id = res.get_json()["data"]["id"]
    assert (
        client.put(
            f"/api/documents/{application_id}",
            json={"content": "Aktualisierte Bewerbung"},
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 200
    )

    # An unrelated trainer cannot even address the document.
    csrf_t2, _ = login(client, "trainer2@vektorwerk.ch")
    assert (
        client.put(
            f"/api/documents/{application_id}",
            json={"content": "Übernommen"},
            headers={"X-CSRF-Token": csrf_t2},
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/documents/{application_id}",
            headers={"X-CSRF-Token": csrf_t2},
        ).status_code
        == 404
    )

    # Learners can view their Bewerbung but cannot edit or delete it.
    csrf_s1, _ = login(client, "student@vektorwerk.ch")
    assert client.get(f"/api/documents/{application_id}").status_code == 200
    assert (
        client.put(
            f"/api/documents/{application_id}",
            json={"content": "Übernommen"},
            headers={"X-CSRF-Token": csrf_s1},
        ).status_code
        == 403
    )
    assert (
        client.delete(
            f"/api/documents/{application_id}",
            headers={"X-CSRF-Token": csrf_s1},
        ).status_code
        == 403
    )

    # Lernjournal: learners edit/delete their entry, supervisors only feedback.
    res = client.post(
        "/api/documents",
        json={
            "name": "Lernjournal",
            "type": "lernjournal",
            "content": "Erster Eintrag",
        },
        headers={"X-CSRF-Token": csrf_s1},
    )
    assert res.status_code == 201
    journal_id = res.get_json()["data"]["id"]
    assert (
        client.put(
            f"/api/documents/{journal_id}",
            json={"content": "Überarbeiteter Eintrag"},
            headers={"X-CSRF-Token": csrf_s1},
        ).status_code
        == 200
    )

    csrf_t1, _ = login(client, "trainer@vektorwerk.ch")
    assert (
        client.put(
            f"/api/documents/{journal_id}",
            json={"feedback": "Gute Arbeit"},
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 200
    )
    res = client.put(
        f"/api/documents/{journal_id}",
        json={"feedback": ""},
        headers={"X-CSRF-Token": csrf_t1},
    )
    assert res.status_code == 200
    assert res.get_json()["data"]["feedback"] == ""

    csrf_s1, _ = login(client, "student@vektorwerk.ch")
    assert (
        client.delete(
            f"/api/documents/{journal_id}",
            headers={"X-CSRF-Token": csrf_s1},
        ).status_code
        == 200
    )

    # Templates are visible company-wide but only supervisors manage them.
    csrf_t1, _ = login(client, "trainer@vektorwerk.ch")
    res = client.post(
        "/api/documents",
        json={
            "name": "Vorlage Gespräch",
            "type": "ausbildungsgespraech",
            "content": "Vorlage",
            "is_template": True,
        },
        headers={"X-CSRF-Token": csrf_t1},
    )
    assert res.status_code == 201
    template_id = res.get_json()["data"]["id"]

    csrf_s1, _ = login(client, "student@vektorwerk.ch")
    templates = client.get("/api/documents?is_template=true").get_json()["data"]
    assert template_id in {d["id"] for d in templates}
    assert (
        client.put(
            f"/api/documents/{template_id}",
            json={"name": "Übernommen"},
            headers={"X-CSRF-Token": csrf_s1},
        ).status_code
        == 403
    )
    assert (
        client.delete(
            f"/api/documents/{template_id}",
            headers={"X-CSRF-Token": csrf_s1},
        ).status_code
        == 403
    )

    csrf_t1, _ = login(client, "trainer@vektorwerk.ch")
    assert (
        client.delete(
            f"/api/documents/{template_id}",
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 200
    )

    # Evaluations and reports: learners cannot create or mutate supervisor data,
    # and unrelated supervisors cannot mutate another supervisor's data.
    res = client.post(
        "/api/project",
        json={
            "title": "CRUD Projekt",
            "description": "CRUD Beschreibung",
            "planning_released": True,
        },
        headers={"X-CSRF-Token": csrf_t1},
    )
    assert res.status_code == 201
    project_id = res.get_json()["data"]["id"]
    res = client.post(
        "/api/evaluation",
        json={
            "project": project_id,
            "student": student1["id"],
            "goal": "Ziel",
        },
        headers={"X-CSRF-Token": csrf_t1},
    )
    assert res.status_code == 201
    eval_id = res.get_json()["data"]["id"]

    csrf_s1, _ = login(client, "student@vektorwerk.ch")
    assert (
        client.post(
            "/api/evaluation",
            json={
                "project": project_id,
                "student": student1["id"],
                "goal": "Ziel",
            },
            headers={"X-CSRF-Token": csrf_s1},
        ).status_code
        == 403
    )
    assert (
        client.put(
            f"/api/evaluation/{eval_id}",
            json={"eval_text": "Übernommen"},
            headers={"X-CSRF-Token": csrf_s1},
        ).status_code
        == 403
    )
    assert (
        client.delete(
            f"/api/evaluation/{eval_id}",
            headers={"X-CSRF-Token": csrf_s1},
        ).status_code
        == 403
    )

    csrf_t2, _ = login(client, "trainer2@vektorwerk.ch")
    assert (
        client.put(
            f"/api/evaluation/{eval_id}",
            json={"eval_text": "Übernommen"},
            headers={"X-CSRF-Token": csrf_t2},
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/evaluation/{eval_id}",
            headers={"X-CSRF-Token": csrf_t2},
        ).status_code
        == 404
    )

    csrf_s1, _ = login(client, "student@vektorwerk.ch")
    res = client.post(
        "/api/implementation",
        json={"project": project_id, "title": "Bericht"},
        headers={"X-CSRF-Token": csrf_s1},
    )
    assert res.status_code == 201
    impl_id = res.get_json()["data"]["id"]

    csrf_t2, _ = login(client, "trainer2@vektorwerk.ch")
    assert (
        client.put(
            f"/api/implementation/{impl_id}",
            json={"is_done": True},
            headers={"X-CSRF-Token": csrf_t2},
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/implementation/{impl_id}",
            headers={"X-CSRF-Token": csrf_t2},
        ).status_code
        == 404
    )

    csrf_t1, _ = login(client, "trainer@vektorwerk.ch")
    assert (
        client.delete(
            f"/api/implementation/{impl_id}",
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 404
    )

    csrf_s1, _ = login(client, "student@vektorwerk.ch")
    assert (
        client.delete(
            f"/api/implementation/{impl_id}",
            headers={"X-CSRF-Token": csrf_s1},
        ).status_code
        == 200
    )

    # Knowledge: unrelated supervisors cannot address another user's entry.
    csrf_t1, _ = login(client, "trainer@vektorwerk.ch")
    res = client.post(
        "/api/knowledge",
        json={"title": "Trainerwissen", "content": "# Inhalt"},
        headers={"X-CSRF-Token": csrf_t1},
    )
    assert res.status_code == 201
    knowledge_id = res.get_json()["data"]["id"]

    csrf_t2, _ = login(client, "trainer2@vektorwerk.ch")
    assert client.get(f"/api/knowledge/{knowledge_id}").status_code == 404
    assert (
        client.put(
            f"/api/knowledge/{knowledge_id}",
            json={"title": "Übernommen"},
            headers={"X-CSRF-Token": csrf_t2},
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/knowledge/{knowledge_id}",
            headers={"X-CSRF-Token": csrf_t2},
        ).status_code
        == 404
    )

    csrf_s1, _ = login(client, "student@vektorwerk.ch")
    res = client.post(
        "/api/knowledge",
        json={"title": "Eigenes Wissen", "content": "# Inhalt"},
        headers={"X-CSRF-Token": csrf_s1},
    )
    assert res.status_code == 201
    own_knowledge_id = res.get_json()["data"]["id"]
    assert (
        client.delete(
            f"/api/knowledge/{own_knowledge_id}",
            headers={"X-CSRF-Token": csrf_s1},
        ).status_code
        == 200
    )


def test_unauthenticated_api_access_is_rejected(client):
    for path in (
        "/api/user",
        "/api/project",
        "/api/implementation",
        "/api/evaluation",
        "/api/documents",
        "/api/grades",
        "/api/knowledge",
    ):
        assert client.get(path).status_code == 401

    csrf = client.get("/api/auth/me").get_json()["data"]["csrf_token"]
    assert (
        client.post(
            "/api/project",
            json={"title": "Nicht erlaubt"},
            headers={"X-CSRF-Token": csrf},
        ).status_code
        == 401
    )


def test_project_evaluation_save_requires_manage_and_company(client):
    csrf_t1, _ = login(client, "trainer@vektorwerk.ch")
    res = client.post(
        "/api/project",
        json={
            "title": "Eval-Projekt",
            "description": "Beschreibung",
            "planning_released": True,
        },
        headers={"X-CSRF-Token": csrf_t1},
    )
    assert res.status_code == 201
    project_id = res.get_json()["data"]["id"]

    # A supervisor who neither owns nor manages the project cannot save it.
    csrf_t2, _ = login(client, "trainer2@vektorwerk.ch")
    assert (
        client.post(
            f"/api/evaluation/project/{project_id}",
            json={"global_eval_text": "Übernommen", "is_completed": True},
            headers={"X-CSRF-Token": csrf_t2},
        ).status_code
        == 403
    )

    # Company databases have independent id spaces: the foreign project
    # (id 1 in the fremd database) is fully separate from the Vektorwerk
    # project. Each user only ever reaches their own company's project id 1,
    # so cross-company mutations cannot happen at all.
    csrf_ft, _ = login(client, "nina@fremd.ch")
    res = client.post(
        "/api/project",
        json={
            "title": "Fremdprojekt",
            "description": "Fremd",
            "planning_released": True,
        },
        headers={"X-CSRF-Token": csrf_ft},
    )
    assert res.status_code == 201
    foreign_project_id = res.get_json()["data"]["id"]

    remote = client.get(f"/api/project/{foreign_project_id}").get_json()["data"]
    assert remote["title"] == "Fremdprojekt"

    csrf_t1, _ = login(client, "trainer@vektorwerk.ch")
    local = client.get(f"/api/project/{project_id}").get_json()["data"]
    assert local["title"] == "Eval-Projekt"

    # The manager can still save.
    res = client.post(
        f"/api/evaluation/project/{project_id}",
        json={"global_eval_text": "Gutes Ergebnis", "is_completed": False},
        headers={"X-CSRF-Token": csrf_t1},
    )
    assert res.status_code == 200


def test_project_detail_filters_other_learners(client):
    csrf_t1, _ = login(client, "trainer@vektorwerk.ch")
    users = {
        u["company_email"]: u
        for u in client.get("/api/user?role=lernender").get_json()["data"]["users"]
    }
    student1_id = users["student@vektorwerk.ch"]["id"]
    student2_id = users["student2@vektorwerk.ch"]["id"]

    res = client.post(
        "/api/project",
        json={
            "title": "Geteiltes Projekt",
            "description": "Gemeinsame Aufgabe",
            "assigned_students": [student1_id, student2_id],
            "planning_released": True,
        },
        headers={"X-CSRF-Token": csrf_t1},
    )
    assert res.status_code == 201
    project_id = res.get_json()["data"]["id"]

    csrf_s1, _ = login(client, "student@vektorwerk.ch")
    res = client.post(
        "/api/implementation",
        json={"project": project_id, "text": "S1 Bericht"},
        headers={"X-CSRF-Token": csrf_s1},
    )
    assert res.status_code == 201

    csrf_s2, _ = login(client, "student2@vektorwerk.ch")
    res = client.post(
        "/api/implementation",
        json={"project": project_id, "text": "S2 Bericht"},
        headers={"X-CSRF-Token": csrf_s2},
    )
    assert res.status_code == 201

    with company_context(client):
        db.session.add(
            Eval(
                project=project_id,
                target_type="goal",
                goal="S2 Ziel",
                student=student2_id,
                planning_text="S2 Planung",
                eval_text="S2 Bewertung",
                is_released=True,
                eval_released=True,
            )
        )
        db.session.commit()

    csrf_t1, _ = login(client, "trainer@vektorwerk.ch")
    detail = client.get(f"/api/project/{project_id}").get_json()["data"]
    assert [p["text"] for p in detail["participations"]] == ["S1 Bericht"]
    assert detail["evaluations"] == []

    raw = client.get(f"/api/project/{project_id}").get_data(as_text=True)
    assert "S2 Bericht" not in raw
    assert "S2 Bewertung" not in raw
    assert "S2 Planung" not in raw


def test_project_document_visibility_follows_project_access(client):
    csrf_t1, _ = login(client, "trainer@vektorwerk.ch")
    users = {
        u["company_email"]: u
        for u in client.get("/api/user?role=lernender").get_json()["data"]["users"]
    }
    student1_id = users["student@vektorwerk.ch"]["id"]

    res = client.post(
        "/api/documents",
        json={
            "name": "Projektanleitung",
            "type": "projekt",
            "content": "Nur für Team A",
        },
        headers={"X-CSRF-Token": csrf_t1},
    )
    assert res.status_code == 201
    doc_id = res.get_json()["data"]["id"]

    res = client.post(
        "/api/project",
        json={
            "title": "Team-A-Projekt",
            "description": "Team A",
            "document_id": doc_id,
            "assigned_students": [student1_id],
            "planning_released": True,
        },
        headers={"X-CSRF-Token": csrf_t1},
    )
    assert res.status_code == 201

    # Owner and assigned learner can read it.
    assert client.get(f"/api/documents/{doc_id}").status_code == 200
    csrf_s1, _ = login(client, "student@vektorwerk.ch")
    assert client.get(f"/api/documents/{doc_id}").status_code == 200

    # An unassigned learner must not see it in the list or directly.
    csrf_s2, _ = login(client, "student2@vektorwerk.ch")
    assert client.get(f"/api/documents/{doc_id}").status_code == 404
    listed = client.get("/api/documents?type=projekt&include_content=true").get_json()[
        "data"
    ]
    assert doc_id not in {d["id"] for d in listed}

    # An unrelated supervisor cannot see it either.
    csrf_t2, _ = login(client, "trainer2@vektorwerk.ch")
    assert client.get(f"/api/documents/{doc_id}").status_code == 404


def test_template_conversion_requires_document_ownership(client):
    csrf_t1, _ = login(client, "trainer@vektorwerk.ch")
    student1_id = {
        u["company_email"]: u
        for u in client.get("/api/user?role=lernender").get_json()["data"]["users"]
    }["student@vektorwerk.ch"]["id"]

    # A supervisor may not turn a learner's private document into a template.
    res = client.post(
        "/api/documents",
        json={
            "name": "Zeugnis Lukas",
            "type": "zeugnis",
            "owner": student1_id,
            "content": "Privat",
        },
        headers={"X-CSRF-Token": csrf_t1},
    )
    assert res.status_code == 201
    learner_doc_id = res.get_json()["data"]["id"]

    assert (
        client.put(
            f"/api/documents/{learner_doc_id}",
            json={"is_template": True},
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 403
    )

    # It stays private.
    csrf_s2, _ = login(client, "student2@vektorwerk.ch")
    assert client.get(f"/api/documents/{learner_doc_id}").status_code == 404

    # Converting one's own document is still allowed.
    csrf_t1, _ = login(client, "trainer@vektorwerk.ch")
    res = client.post(
        "/api/documents",
        json={"name": "Eigenes Zeugnis", "type": "zeugnis", "content": "Eigen"},
        headers={"X-CSRF-Token": csrf_t1},
    )
    assert res.status_code == 201
    own_doc_id = res.get_json()["data"]["id"]
    res = client.put(
        f"/api/documents/{own_doc_id}",
        json={"is_template": True},
        headers={"X-CSRF-Token": csrf_t1},
    )
    assert res.status_code == 200
    assert res.get_json()["data"]["is_template"] is True

    # The string "false" must not be coerced to a truthy template flag.
    res = client.post(
        "/api/documents",
        json={
            "name": "Keine Vorlage",
            "type": "sonstiges",
            "content": "Inhalt",
            "is_template": "false",
        },
        headers={"X-CSRF-Token": csrf_t1},
    )
    assert res.status_code == 201
    assert res.get_json()["data"]["is_template"] is False


def test_template_listing_lists_all_types_company_wide(client):
    csrf_t1, _ = login(client, "trainer@vektorwerk.ch")

    created = []
    for name, doc_type in [("Vorlage Gespräch", "ausbildungsgespraech"), ("Vorlage Bericht", "sonstiges")]:
        res = client.post(
            "/api/documents",
            json={
                "name": name,
                "type": doc_type,
                "content": f"Inhalt {name}",
                "is_template": True,
            },
            headers={"X-CSRF-Token": csrf_t1},
        )
        assert res.status_code == 201
        created.append(res.get_json()["data"]["id"])

    # A non-template document of the same company must not appear.
    res = client.post(
        "/api/documents",
        json={"name": "Normales Dokument", "type": "sonstiges", "content": "Inhalt"},
        headers={"X-CSRF-Token": csrf_t1},
    )
    assert res.status_code == 201
    normal_doc_id = res.get_json()["data"]["id"]

    # Learners see all company templates across every document type.
    csrf_s1, _ = login(client, "student@vektorwerk.ch")
    listed = client.get(
        "/api/documents?is_template=true&include_content=true"
    ).get_json()["data"]
    listed_ids = {d["id"] for d in listed}
    assert created[0] in listed_ids
    assert created[1] in listed_ids
    assert normal_doc_id not in listed_ids
    assert all(d["is_template"] for d in listed)
    first = next(d for d in listed if d["id"] == created[0])
    assert first["content"]


def test_document_references_are_validated(client):
    csrf_t1, _ = login(client, "trainer@vektorwerk.ch")
    users = {
        u["company_email"]: u
        for u in client.get("/api/user?role=lernender").get_json()["data"]["users"]
    }
    student1_id = users["student@vektorwerk.ch"]["id"]
    student2_id = users["student2@vektorwerk.ch"]["id"]

    res = client.post(
        "/api/project",
        json={
            "title": "Abgabe-Projekt",
            "description": "Beschreibung",
            "assigned_students": [student1_id],
            "planning_released": True,
        },
        headers={"X-CSRF-Token": csrf_t1},
    )
    assert res.status_code == 201
    project_id = res.get_json()["data"]["id"]

    # A document owned by another learner.
    csrf_s2, _ = login(client, "student2@vektorwerk.ch")
    res = client.post(
        "/api/documents",
        json={"name": "Zeugnis Elena", "type": "zeugnis", "content": "Geheim"},
        headers={"X-CSRF-Token": csrf_s2},
    )
    assert res.status_code == 201
    other_learner_doc_id = res.get_json()["data"]["id"]

    # A document from another company.
    csrf_fs, _ = login(client, "ali@fremd.ch")
    res = client.post(
        "/api/documents",
        json={"name": "Fremdzeugnis", "type": "zeugnis", "content": "Fremd"},
        headers={"X-CSRF-Token": csrf_fs},
    )
    assert res.status_code == 201
    foreign_doc_id = res.get_json()["data"]["id"]

    csrf_s1, _ = login(client, "student@vektorwerk.ch")
    for bad_doc_id in (other_learner_doc_id, foreign_doc_id):
        assert (
            client.post(
                "/api/implementation",
                json={
                    "project": project_id,
                    "text": "Bericht",
                    "document_id": bad_doc_id,
                },
                headers={"X-CSRF-Token": csrf_s1},
            ).status_code
            == 400
        )

    # The learner's own document is accepted.
    res = client.post(
        "/api/documents",
        json={"name": "Eigener Bericht", "type": "projekt", "content": "Inhalt"},
        headers={"X-CSRF-Token": csrf_s1},
    )
    assert res.status_code == 201
    own_doc_id = res.get_json()["data"]["id"]
    res = client.post(
        "/api/implementation",
        json={
            "project": project_id,
            "text": "Bericht",
            "document_id": own_doc_id,
        },
        headers={"X-CSRF-Token": csrf_s1},
    )
    assert res.status_code == 201

    # Project and task attachments cannot reference another user's document.
    csrf_t1, _ = login(client, "trainer@vektorwerk.ch")
    assert (
        client.post(
            "/api/project",
            json={
                "title": "Ungültige Anlage",
                "description": "Beschreibung",
                "document_id": other_learner_doc_id,
            },
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/project",
            json={
                "title": "Ungültige Aufgabe",
                "description": "Beschreibung",
                "tasks": [
                    {"title": "Aufgabe", "document_id": other_learner_doc_id}
                ],
            },
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 400
    )

    # Legacy rows pointing at an unauthorized document must not leak metadata.
    with company_context(client):
        part = Participation.query.filter_by(
            student=student1_id, project=project_id
        ).one()
        part.document_id = other_learner_doc_id
        db.session.commit()

    detail = client.get(f"/api/project/{project_id}").get_json()["data"]
    assert detail["participations"][0]["document"] is None


def test_password_change_invalidates_other_sessions(client):
    csrf, student = login(client, "student@vektorwerk.ch")
    old_cookie = client.get_cookie("session").value

    res = client.put(
        f"/api/user/{student['id']}",
        json={
            "current_password": "Passwort123!",
            "new_password": "NeuesPasswort123!",
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert res.status_code == 200

    # The session that changed its own password stays logged in.
    assert client.get("/api/user").status_code == 200

    # Replay the pre-change cookie: the version bump must revoke it.
    client.set_cookie("session", old_cookie)
    assert client.get("/api/user").status_code == 401


def test_logout_all_revokes_all_sessions(client):
    csrf, _ = login(client, "student@vektorwerk.ch")
    old_cookie = client.get_cookie("session").value

    res = client.post(
        "/api/auth/logout-all",
        headers={"X-CSRF-Token": csrf},
    )
    assert res.status_code == 200
    assert client.get("/api/user").status_code == 401

    # A stolen cookie from before logout-all must also be rejected.
    client.set_cookie("session", old_cookie)
    assert client.get("/api/user").status_code == 401


def test_invalid_payloads_return_400(client):
    # Relation management requires an admin; even with an admin session the
    # invalid payload must return a clean 400.
    _, _ = login(client, "trainer@vektorwerk.ch")
    csrf_admin, _ = login(client, "admin@vektorwerk.ch")

    assert (
        client.post(
            "/api/project",
            json={"title": "Ungültiges Elternprojekt", "parent_project": "abc"},
            headers={"X-CSRF-Token": csrf_admin},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/user/relation",
            json={"supervisor": "abc", "student": 1},
            headers={"X-CSRF-Token": csrf_admin},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/project",
            json={"title": "Ungültige Freigabe", "is_published": "maybe"},
            headers={"X-CSRF-Token": csrf_admin},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/project",
            json={"title": 123},
            headers={"X-CSRF-Token": csrf_admin},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/project",
            json=["not", "an", "object"],
            headers={"X-CSRF-Token": csrf_admin},
        ).status_code
        == 400
    )


def test_document_download_has_hardening_headers(client):
    csrf, _ = login(client, "trainer@vektorwerk.ch")
    res = client.post(
        "/api/documents",
        json={"name": "Header-Test", "type": "sonstiges", "content": "Inhalt"},
        headers={"X-CSRF-Token": csrf},
    )
    assert res.status_code == 201
    doc_id = res.get_json()["data"]["id"]

    res = client.get(f"/api/documents/{doc_id}/file")
    assert res.status_code == 200
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["Cache-Control"] == "private, no-store"


def test_login_rejects_wildcards_and_requires_exact_email(client):
    for wildcard in ("%", "_", "%@vektorwerk.ch"):
        res = client.post(
            "/api/auth/login",
            json={"email": wildcard, "password": "Passwort123!"},
        )
        assert res.status_code in {400, 401}

    # Exact matching still works.
    csrf, user = login(client, "trainer@vektorwerk.ch")
    assert user["role"] == "ausbildner"
    assert csrf


def test_login_rate_limit(client):
    email = "does-not-exist@vektorwerk.ch"
    environ = {"REMOTE_ADDR": "203.0.113.77"}
    for _ in range(10):
        res = client.post(
            "/api/auth/login",
            json={"email": email, "password": "wrong-password"},
            environ_base=environ,
        )
        assert res.status_code == 401

    res = client.post(
        "/api/auth/login",
        json={"email": email, "password": "wrong-password"},
        environ_base=environ,
    )
    assert res.status_code == 429
    assert "Retry-After" in res.headers


def test_create_user_with_password_field_is_rejected(client):
    """Accounts have no initial password: the person sets it themselves
    via the invitation link."""
    csrf, _ = login(client, "admin@vektorwerk.ch")
    res = client.post(
        "/api/user",
        json={
            "role": "lernender",
            "name": "Max",
            "surname": "Muster",
            "company_email": "max.muster@vektorwerk.ch",
            "job_title": "Polymechanikerin / Polymechaniker EFZ",
            "password": "Passwort123!",
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert res.status_code == 400
    assert "Einladungs-E-Mail" in res.get_json()["error"]


def test_user_and_relation_management_is_admin_only(client):
    # A supervisor can no longer create or delete people, nor manage
    # relationships at all — those are exclusively admin capabilities.
    csrf_t1, trainer1 = login(client, "trainer@vektorwerk.ch")
    res = client.post(
        "/api/user",
        json={
            "role": "lernender",
            "name": "Max",
            "surname": "Muster",
            "company_email": "max.muster@vektorwerk.ch",
            "job_title": "Polymechanikerin / Polymechaniker EFZ",
        },
        headers={"X-CSRF-Token": csrf_t1},
    )
    assert res.status_code == 403

    csrf_s1, _ = login(client, "student@vektorwerk.ch")
    assert (
        client.post(
            "/api/user/relation",
            json={"supervisor": trainer1["id"], "student": trainer1["id"]},
            headers={"X-CSRF-Token": csrf_s1},
        ).status_code
        == 403
    )
    assert (
        client.delete(
            "/api/user/relation/1",
            headers={"X-CSRF-Token": csrf_s1},
        ).status_code
        == 403
    )

    # The admin has full user and relationship management.
    csrf_admin, _ = login(client, "admin@vektorwerk.ch")
    res = client.post(
        "/api/user",
        json={
            "role": "lernender",
            "name": "Max",
            "surname": "Muster",
            "company_email": "max.muster@vektorwerk.ch",
            "job_title": "Polymechanikerin / Polymechaniker EFZ",
        },
        headers={"X-CSRF-Token": csrf_admin},
    )
    assert res.status_code == 201
    new_user = res.get_json()["data"]

    res = client.post(
        "/api/user/relation",
        json={"supervisor": trainer1["id"], "student": new_user["id"]},
        headers={"X-CSRF-Token": csrf_admin},
    )
    assert res.status_code == 201
    relation_id = res.get_json()["data"]["id"]

    res = client.delete(
        f"/api/user/relation/{relation_id}",
        headers={"X-CSRF-Token": csrf_admin},
    )
    assert res.status_code == 200

    res = client.delete(
        f"/api/user/{new_user['id']}",
        headers={"X-CSRF-Token": csrf_admin},
    )
    assert res.status_code == 200


def test_production_security_config_is_enforced(tmp_path):
    base = {
        "IS_DEV": False,
        "DEBUG": False,
        "SECRET_KEY": None,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}",
        "COMPANY_ROOT": str(tmp_path / "companies"),
    }
    with pytest.raises(RuntimeError):
        create_app(base)

    base["SECRET_KEY"] = "x" * 40
    base["DEBUG"] = True
    with pytest.raises(RuntimeError):
        create_app(base)

    base["DEBUG"] = False
    base["SECRET_KEY"] = "short"
    with pytest.raises(RuntimeError):
        create_app(base)


def test_deleting_user_removes_document_files(client):
    csrf_s1, student1 = login(client, "student@vektorwerk.ch")
    res = client.post(
        "/api/documents",
        json={"name": "Zeugnis", "type": "zeugnis", "content": "Inhalt"},
        headers={"X-CSRF-Token": csrf_s1},
    )
    assert res.status_code == 201
    doc_id = res.get_json()["data"]["id"]

    with company_context(client):
        rel_path = db.session.get(Documents, doc_id).path
        abs_path = resolve_safe_path(rel_path)
    assert os.path.isfile(abs_path)

    # Deleting users is an admin capability.
    csrf_admin, _ = login(client, "admin@vektorwerk.ch")
    res = client.delete(
        f"/api/user/{student1['id']}",
        headers={"X-CSRF-Token": csrf_admin},
    )
    assert res.status_code == 200
    assert not os.path.isfile(abs_path)


def test_seed_creates_official_templates(tmp_path, monkeypatch):
    from backend import seed as seed_module
    from backend.app import create_app
    from backend.storage import read_text_document

    real_create_app = create_app

    config = {
        "TESTING": True,
        "DEBUG": False,
        "IS_DEV": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path}/control.db",
        "COMPANY_ROOT": str(tmp_path / "seed_companies"),
        "SECRET_KEY": "seed-test-secret-key" * 5,
    }

    def configured_create_app(overrides=None):
        return real_create_app({**config, **(overrides or {})})

    monkeypatch.setattr(seed_module, "create_app", configured_create_app)
    seed_module.seed_database()

    app = configured_create_app()
    with company_context(app) as _company:
        templates = Documents.query.filter_by(is_template=True).all()
        names = {d.name for d in templates}
        # Templates are neutral about the profession (no Handlungskompetenz refs).
        contents = {d.name: read_text_document(d.path) for d in templates}
    assert names == {
        "Vorlage Bildungsbericht",
        "Vorlage Lernjournal-Eintrag",
        "Vorlage Projektplanung",
        "Vorlage Projektdurchführung",
    }
    assert {d.type for d in templates} == {
        "ausbildungsgespraech",
        "lernjournal",
        "projekt",
    }
    # Templates are neutral about the profession (no Handlungskompetenz refs).
    for tpl_name, content in contents.items():
        assert content.strip(), f"Empty template content: {tpl_name}"
        assert "Handlungskompetenz" not in content


def test_relation_requires_ausbildner_to_lernender_pair(client):
    # Relation management is admin-only; the admin validates the pair rules.
    csrf_admin, _ = login(client, "admin@vektorwerk.ch")
    users = {
        u["company_email"]: u
        for u in client.get("/api/user").get_json()["data"]["users"]
    }
    trainer1 = users["trainer@vektorwerk.ch"]
    trainer2 = users["trainer2@vektorwerk.ch"]
    student2 = users["student2@vektorwerk.ch"]

    # ausbildner -> ausbildner is rejected.
    assert (
        client.post(
            "/api/user/relation",
            json={"supervisor": trainer1["id"], "student": trainer2["id"]},
            headers={"X-CSRF-Token": csrf_admin},
        ).status_code
        == 400
    )
    # Self-pair is rejected.
    assert (
        client.post(
            "/api/user/relation",
            json={"supervisor": trainer1["id"], "student": trainer1["id"]},
            headers={"X-CSRF-Token": csrf_admin},
        ).status_code
        == 400
    )
    # Any valid ausbildner/admin -> lernender pair may be assigned
    # (product decision), and the pair is unique in the database.
    res = client.post(
        "/api/user/relation",
        json={"supervisor": trainer2["id"], "student": student2["id"]},
        headers={"X-CSRF-Token": csrf_admin},
    )
    assert res.status_code == 201
    relation_id = res.get_json()["data"]["id"]

    # The same pair is idempotent, not duplicated.
    res_dup = client.post(
        "/api/user/relation",
        json={"supervisor": trainer2["id"], "student": student2["id"]},
        headers={"X-CSRF-Token": csrf_admin},
    )
    assert res_dup.status_code == 200
    assert res_dup.get_json()["data"]["id"] == relation_id


def test_only_admin_removes_relation(client):
    # Relations are managed exclusively by the admin; supervisors (even the
    # party of the pair) cannot sever them. The admin removes any relation.
    users = _company_user_map(client)
    trainer1 = users["trainer@vektorwerk.ch"]
    student1 = users["student@vektorwerk.ch"]

    csrf_admin, _ = login(client, "admin@vektorwerk.ch")
    res = client.post(
        "/api/user/relation",
        json={"supervisor": trainer1["id"], "student": student1["id"]},
        headers={"X-CSRF-Token": csrf_admin},
    )
    assert res.status_code in {200, 201}
    relation_id = res.get_json()["data"]["id"]

    # A supervisor — even a party of the pair — may not sever it.
    csrf_t1, _ = login(client, "trainer@vektorwerk.ch")
    assert (
        client.delete(
            f"/api/user/relation/{relation_id}",
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 403
    )

    csrf_admin, _ = login(client, "admin@vektorwerk.ch")
    assert (
        client.delete(
            f"/api/user/relation/{relation_id}",
            headers={"X-CSRF-Token": csrf_admin},
        ).status_code
        == 200
    )


def test_assigned_students_must_be_same_company_learners(client):
    csrf_t1, _ = login(client, "trainer@vektorwerk.ch")
    users = {
        u["company_email"]: u
        for u in client.get("/api/user").get_json()["data"]["users"]
    }
    student1 = users["student@vektorwerk.ch"]

    # Foreign-company ID: the fixture's foreign student is not in this
    # company directory, so use a clearly-bogus ID to exercise the same
    # rejection path.
    assert (
        client.post(
            "/api/project",
            json={
                "title": "Fremd Zuordnung",
                "assigned_students": [999999],
            },
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 400
    )
    # Supervisor ID is rejected: assigned students must be learners.
    assert (
        client.post(
            "/api/project",
            json={
                "title": "Supervisor Zuordnung",
                "assigned_students": [users["trainer@vektorwerk.ch"]["id"]],
            },
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 400
    )
    # Same-company learner is accepted.
    res = client.post(
        "/api/project",
        json={
            "title": "Gueltige Zuordnung",
            "assigned_students": [student1["id"]],
        },
        headers={"X-CSRF-Token": csrf_t1},
    )
    assert res.status_code == 201
    assert res.get_json()["data"]["assigned_students"] == [student1["id"]]


def test_login_company_hint_scopes_identity(client):
    # Wrong company hint fails even with the correct password.
    res = client.post(
        "/api/auth/login",
        json={
            "email": "trainer@vektorwerk.ch",
            "password": "Passwort123!",
            "company_domain": "fremd.ch",
        },
    )
    assert res.status_code == 401

    # Matching company hint succeeds.
    res = client.post(
        "/api/auth/login",
        json={
            "email": "trainer@vektorwerk.ch",
            "password": "Passwort123!",
            "company_domain": "vektorwerk.ch",
        },
    )
    assert res.status_code == 200


def test_role_elevation_requires_explicit_confirmation(client):
    users = _company_user_map(client)
    trainer1 = users["trainer@vektorwerk.ch"]
    student1 = users["student@vektorwerk.ch"]

    # A supervisor can no longer change roles — not even self-promotion.
    csrf_t1, _ = login(client, "trainer@vektorwerk.ch")
    assert (
        client.put(
            f"/api/user/{student1['id']}",
            json={"role": "ausbildner", "confirm_role_elevation": True},
            headers={"X-CSRF-Token": csrf_t1},
        ).status_code
        == 403
    )

    # Roles are changed exclusively by admins — and only with an explicit
    # confirmation flag.
    csrf_admin, _ = login(client, "admin@vektorwerk.ch")
    res = client.put(
        f"/api/user/{student1['id']}",
        json={"role": "ausbildner"},
        headers={"X-CSRF-Token": csrf_admin},
    )
    assert res.status_code == 403
    assert "confirm_role_elevation" in res.get_json()["error"]

    res = client.put(
        f"/api/user/{student1['id']}",
        json={"role": "ausbildner", "confirm_role_elevation": True},
        headers={"X-CSRF-Token": csrf_admin},
    )
    assert res.status_code == 200
    assert res.get_json()["data"]["role"] == "ausbildner"


def test_lehrplan_requires_login_and_delivers_static_data(client):
    # Anonymous requests are rejected.
    assert client.get("/api/lehrplan/jobs").status_code == 401
    assert client.get("/api/lehrplan/ET").status_code == 401

    # Any logged-in user (regardless of role) can read the lehrplan data.
    login(client, "trainer@vektorwerk.ch")
    res_jobs = client.get("/api/lehrplan/jobs")
    assert res_jobs.status_code == 200
    jobs = res_jobs.get_json()["data"]
    codes = {j["code"] for j in jobs}
    assert {"AA", "KR", "MP", "PR", "PM", "AM", "AU", "ET"} <= codes
    et_meta = next(j for j in jobs if j["code"] == "ET")
    assert et_meta["name"] == "Elektroniker/in EFZ"
    assert et_meta["accent"] == "#245029"

    res_tree = client.get("/api/lehrplan/ET")
    assert res_tree.status_code == 200
    tree = res_tree.get_json()["data"]
    assert tree["code"] == "ET"
    assert tree["stats"]["lz_count"] > 0
    assert tree["stats"]["lk_count"] > 0
    first_hkb = tree["handlungskompetenzbereiche"][0]
    assert "handlungskompetenzen" in first_hkb
    assert first_hkb["handlungskompetenzen"][0]["lernkriterien"][0]["lernziele"]

    # Unknown job codes yield a 404.
    assert client.get("/api/lehrplan/XX").status_code == 404

    # Lernziel lookup resolves IDs against every job tree (display helper).
    res_lz = client.get("/api/lehrplan/lz/LZ_6957")
    assert res_lz.status_code == 200
    lz = res_lz.get_json()["data"]
    assert lz["lz_id"] == "LZ_6957"
    assert lz["description"]
    assert lz["code"] in {"AA", "KR", "MP", "PR", "PM", "AM", "AU", "ET"}
    assert lz["lk_id"]
    assert client.get("/api/lehrplan/lz/LZ_nothing").status_code == 404


def test_spa_static_serving(client, tmp_path):
    """The built frontend is served with an SPA fallback; the API keeps its
    JSON 404 behavior."""
    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text("<html><body>lehrjahre</body></html>")
    (assets / "app-abc123.js").write_text("console.log('hi')")

    app = client.application
    app.config["FRONTEND_DIST"] = str(dist)

    # Client-side route falls back to index.html with no-cache.
    res = client.get("/dashboard")
    assert res.status_code == 200
    assert res.get_data(as_text=True).startswith("<html")
    assert res.headers["Cache-Control"] == "no-cache"

    # Empty path (/) also falls back to index.html.
    res = client.get("/")
    assert res.status_code == 200

    # Hashed build assets are cached forever.
    res = client.get("/assets/app-abc123.js")
    assert res.status_code == 200
    assert res.headers["Cache-Control"] == "public, max-age=31536000, immutable"

    # A missing real asset is a genuine 404.
    assert client.get("/assets/missing.js").status_code == 404

    # Unknown API paths still return the JSON API 404.
    res = client.get("/api/nonexistent")
    assert res.status_code == 404
    assert res.get_json() == {"error": "Endpunkt nicht gefunden."}
    res = client.get("/api")
    assert res.status_code == 404

    # Path traversal cannot escape the dist folder: send_from_directory
    # rejects it and the SPA fallback serves index.html from dist only.
    res = client.get("/..%2f..%2fetc%2fpasswd")
    assert res.status_code == 200
    assert "lehrjahre" in res.get_data(as_text=True)


def test_spa_missing_dist_returns_404(client):
    """Without a built frontend the SPA route reports a clear error."""
    client.application.config["FRONTEND_DIST"] = "/does/not/exist"

    assert client.get("/dashboard").status_code == 404
    assert client.get("/").status_code == 404


# ---------------------------------------------------------------------------
# Company self-service signup (verify-by-mail flow)
# ---------------------------------------------------------------------------

import email as email_module
import re as signup_re
from email import policy as email_policy
from datetime import datetime, timedelta, timezone as dt_timezone

import backend.ratelimit as _ratelimit
from backend.models import CompanySignup


SIGNUP_PAYLOAD = {
    "name": "Nadia",
    "surname": "Roth",
    "job_title": "Administrator",
    "email": "nadia.roth@roth-mechanik.ch",
    "company_name": "Roth Mechanik AG",
    "address": "Bergstrasse 3",
    "password": "SicheresPasswort1!",
}


def _signup_payload(**overrides):
    payload = dict(SIGNUP_PAYLOAD)
    payload.update(overrides)
    return payload


def _reset_signup_limiters():
    """Signup limiters are process-global; give each test a clean slate."""
    for attribute in dir(_ratelimit):
        limiter = getattr(_ratelimit, attribute)
        if isinstance(limiter, _ratelimit.SlidingWindowLimiter):
            limiter._events.clear()


def _outbox_messages(client):
    path = client.application.config["MAIL_DEV_OUTBOX"]
    if not os.path.exists(path):
        return []
    raw = open(path, "rb").read()
    messages = []
    for chunk in raw.split(b"===== MAIL =====\n"):
        if not chunk.strip():
            continue
        messages.append(
            email_module.message_from_bytes(chunk, policy=email_policy.default)
        )
    return messages


def _outbox_count(client):
    return len(_outbox_messages(client))


def _outbox_tokens(client):
    tokens = []
    for message in _outbox_messages(client):
        body = message.get_body(preferencelist=("plain",)).get_content()
        match = signup_re.search(r"\?token=([A-Za-z0-9_-]+)", body)
        if match:
            tokens.append(match.group(1))
    return tokens


@pytest.fixture(autouse=True)
def _clean_signup_limiters():
    _reset_signup_limiters()
    yield
    _reset_signup_limiters()


def _pending_signup(client):
    app = client.application
    with app.app_context():
        return db.session.query(CompanySignup).one()


def test_company_signup_full_flow_creates_company_and_admin(client):
    """Submit -> mail link -> verify -> company + admin account + session."""
    # No CSRF header anywhere: the signup endpoints are unauthenticated.
    res = client.post("/api/company-signup", json=_signup_payload())
    assert res.status_code == 200
    # Generic message: it cannot reveal whether the e-mail was accepted.
    assert "E-Mail" in res.get_json()["data"]["message"]

    # Nothing is provisioned before verification.
    with client.application.app_context():
        assert (
            Company.query.filter_by(email_domain="roth-mechanik.ch").first()
            is None
        )

    messages = _outbox_messages(client)
    assert len(messages) == 1
    assert messages[0]["From"] == '"lehrjahre.ch" <kontakt@lehrjahre.ch>'
    assert messages[0]["To"] == "nadia.roth@roth-mechanik.ch"
    token = _outbox_tokens(client)[0]

    res = client.post("/api/company-signup/verify", json={"token": token})
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["user"]["role"] == "admin"
    assert data["user"]["company"] == "Roth Mechanik AG"
    assert data["user"]["company_email"] == "nadia.roth@roth-mechanik.ch"

    # The verification established the session (same envelope as login).
    res = client.get("/api/auth/me")
    assert res.status_code == 200
    me = res.get_json()["data"]["user"]
    assert me["company_domain"] == "roth-mechanik.ch"
    assert me["role"] == "admin"

    # Registry row + tenant folder + tenant DB + routing exist.
    with client.application.app_context():
        company = Company.query.filter_by(email_domain="roth-mechanik.ch").one()
        assert os.path.isfile(tenants.tenant_db_path(company))
        assert (
            UserRouting.query.filter_by(company_id=company.id).one().company_email
            == "nadia.roth@roth-mechanik.ch"
        )

    # Password carried over from the signup: normal login works.
    csrf_token, _user = login(
        client, "nadia.roth@roth-mechanik.ch", "SicheresPasswort1!"
    )
    assert csrf_token  # CSRF token issued on login


def test_company_signup_duplicate_email_is_generic_and_mails_nothing(client):
    res = client.post("/api/company-signup", json=_signup_payload())
    assert res.status_code == 200
    assert len(_outbox_messages(client)) == 1

    # Same address again: generic 200, no second mail, no error leaks.
    res = client.post("/api/company-signup", json=_signup_payload())
    assert res.status_code == 200
    assert "E-Mail" in res.get_json()["data"]["message"]
    assert len(_outbox_messages(client)) == 1

    # An address already used by an existing user behaves identically
    # (trainer1's private address; its domain is not claimed by any company).
    res = client.post(
        "/api/company-signup",
        json=_signup_payload(
            email="trainer1@privat.ch",
            company_name="Andere GmbH",
        ),
    )
    assert res.status_code == 200
    assert len(_outbox_messages(client)) == 1
    with client.application.app_context():
        emails = {s.email for s in CompanySignup.query.all()}
    assert "trainer1@privat.ch" not in emails


def test_company_signup_rejects_public_email_domain(client):
    _reset_signup_limiters()
    res = client.post(
        "/api/company-signup",
        json=_signup_payload(email="some.person@gmail.com", company_name="Nope GmbH"),
    )
    assert res.status_code == 400
    assert "@gmail.com" in res.get_json()["error"]


def test_company_signup_rejects_taken_domain_and_existing_name(client):
    res = client.post(
        "/api/company-signup",
        json=_signup_payload(email="erika.muster@vektorwerk.ch"),
    )
    assert res.status_code == 400
    assert "bereits einer Firma zugeordnet" in res.get_json()["error"]

    res = client.post(
        "/api/company-signup",
        json=_signup_payload(company_name="vektorwerk technik ag"),
    )
    assert res.status_code == 400
    assert "existiert bereits" in res.get_json()["error"]


def test_company_signup_validation_errors(client):
    weak = _signup_payload(password="kurz")
    res = client.post("/api/company-signup", json=weak)
    assert res.status_code == 400
    assert "mindestens 8 Zeichen" in res.get_json()["error"]

    missing = {key: value for key, value in _signup_payload().items() if key != "surname"}
    res = client.post("/api/company-signup", json=missing)
    assert res.status_code == 400
    assert "Pflichtfelder" in res.get_json()["error"]

    res = client.post("/api/company-signup", json=_signup_payload(email="keine-mail"))
    assert res.status_code == 400
    assert "Ungültige E-Mail-Adresse" in res.get_json()["error"]


def test_signup_disabled_returns_403(client):
    client.application.config["SIGNUP_ENABLED"] = False
    try:
        res = client.post("/api/company-signup", json=_signup_payload())
        assert res.status_code == 403
        res = client.post(
            "/api/company-signup/verify", json={"token": "irgendein-token"}
        )
        assert res.status_code == 403
    finally:
        client.application.config["SIGNUP_ENABLED"] = True


def test_company_signup_rate_limits_submit(client):
    _reset_signup_limiters()
    # Limit is 5 per hour per IP: the sixth accepted-for-validation request
    # gets a 429 (each accepted submission consumes one slot).
    for index in range(5):
        res = client.post(
            "/api/company-signup",
            json=_signup_payload(
                email=f"firma{index}@roth-mechanik.ch",
                company_name=f"Roth Mechanik {index} AG",
            ),
        )
        assert res.status_code == 200
    res = client.post(
        "/api/company-signup",
        json=_signup_payload(
            email="vierte@roth-mechanik.ch",
            company_name="Vierte AG",
        ),
    )
    assert res.status_code == 429
    assert "Retry-After" in res.headers


def test_company_signup_token_expiry_and_resend(client):
    res = client.post("/api/company-signup", json=_signup_payload())
    assert res.status_code == 200
    old_token = _outbox_tokens(client)[0]

    signup = _pending_signup(client)
    with client.application.app_context():
        row = db.session.get(CompanySignup, signup.id)
        row.expires_at = (
            datetime.now(dt_timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
        )
        db.session.commit()

    res = client.post("/api/company-signup/verify", json={"token": old_token})
    assert res.status_code == 400
    assert "abgelaufen" in res.get_json()["error"]

    # Resend refreshes validity and invalidates the old link.
    res = client.post(
        "/api/company-signup/resend", json={"email": SIGNUP_PAYLOAD["email"]}
    )
    assert res.status_code == 200
    new_token = _outbox_tokens(client)[-1]
    assert new_token != old_token

    res = client.post("/api/company-signup/verify", json={"token": old_token})
    assert res.status_code == 400
    res = client.post("/api/company-signup/verify", json={"token": new_token})
    assert res.status_code == 200
    assert res.get_json()["data"]["user"]["role"] == "admin"


def test_company_signup_token_single_use_and_garbage(client):
    res = client.post("/api/company-signup", json=_signup_payload())
    assert res.status_code == 200
    token = _outbox_tokens(client)[0]

    res = client.post("/api/company-signup/verify", json={"token": token})
    assert res.status_code == 200

    res = client.post("/api/company-signup/verify", json={"token": token})
    assert res.status_code == 400
    assert "bereits verwendet" in res.get_json()["error"]

    res = client.post("/api/company-signup/verify", json={"token": "BABABABABA"})
    assert res.status_code == 400

    res = client.post("/api/company-signup/verify", json={})
    assert res.status_code == 400


def test_company_signup_resend_unknown_email_is_generic(client):
    mails_before = _outbox_count(client)
    res = client.post(
        "/api/company-signup/resend", json={"email": "unbekannt@roth-mechanik.ch"}
    )
    assert res.status_code == 200
    assert "Postfach" in res.get_json()["data"]["message"]
    assert _outbox_count(client) == mails_before


def test_company_signup_domain_check(client):
    res = client.get("/api/company-signup/domain-check?domain=vektorwerk.ch")
    assert res.get_json()["data"]["available"] is False

    res = client.get("/api/company-signup/domain-check?domain=nagelneu-firma.ch")
    assert res.get_json()["data"]["available"] is True

    res = client.get("/api/company-signup/domain-check?domain=gmail.com")
    assert res.get_json()["data"]["available"] is False

    res = client.get("/api/company-signup/domain-check?domain=nicht/domain")
    assert res.get_json()["data"]["valid"] is False


def test_load_dotenv(tmp_path, monkeypatch):
    """The backend config loads `.env` (dev convenience) without ever
    overriding variables that are already present in the environment."""
    from backend import config

    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment line\n"
        "LEHRJAHRE_TEST_PLAIN=wert\n"
        'LEHRJAHRE_TEST_QUOTED="quoted wert"\n'
        "export LEHRJAHRE_TEST_EXPORTED=exportiert\n"
        "LEHRJAHRE_TEST_PRESET=aus-datei\n"
        "kein-key-ohne-gleichzeile\n"
        "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LEHRJAHRE_TEST_PRESET", "preset-value")
    keys = [
        "LEHRJAHRE_TEST_PLAIN",
        "LEHRJAHRE_TEST_QUOTED",
        "LEHRJAHRE_TEST_EXPORTED",
        "LEHRJAHRE_TEST_PRESET",
    ]
    try:
        config._load_dotenv(str(env_file))
        assert os.environ["LEHRJAHRE_TEST_PLAIN"] == "wert"
        assert os.environ["LEHRJAHRE_TEST_QUOTED"] == "quoted wert"
        assert os.environ["LEHRJAHRE_TEST_EXPORTED"] == "exportiert"
        # Pre-set environment variables are never overridden.
        assert os.environ["LEHRJAHRE_TEST_PRESET"] == "preset-value"
    finally:
        for key in keys:
            os.environ.pop(key, None)


# ---------------------------------------------------------------------------
# First-login invitations (invite mails always go to company emails)
# ---------------------------------------------------------------------------

INVITE_PAYLOAD = {
    "role": "lernender",
    "name": "Max",
    "surname": "Muster",
    "company_email": "max.muster@vektorwerk.ch",
    "job_title": "Polymechanikerin / Polymechaniker EFZ",
    "private_email": "max.muster@privat-chaos.example",
}


def _invite_from_outbox(client, index=0):
    """Return (token, company_id) from the n-th invite mail."""
    message = _outbox_messages(client)[index]
    body = message.get_body(preferencelist=("plain",)).get_content()
    token = signup_re.search(r"\?token=([A-Za-z0-9_-]+)", body).group(1)
    company_id = signup_re.search(r"&c=(\d+)", body).group(1)
    return message, token, company_id


def _create_invited_user(client, **overrides):
    csrf, _admin = login(client, "admin@vektorwerk.ch")
    payload = dict(INVITE_PAYLOAD)
    payload.update(overrides)
    res = client.post("/api/user", json=payload, headers={"X-CSRF-Token": csrf})
    assert res.status_code == 201, res.get_json()
    return res.get_json()["data"], csrf


def test_user_invite_flow_sets_own_password_and_logs_in(client):
    created, _csrf = _create_invited_user(client)
    assert created["password_pending"] is True

    # The invitation goes to the company address, never to private ones.
    message, token, company_id = _invite_from_outbox(client)
    assert message["To"] == "max.muster@vektorwerk.ch"

    # No usable password yet: login is a generic 401 like any wrong one.
    res = client.post(
        "/api/auth/login",
        json={"email": INVITE_PAYLOAD["company_email"], "password": "Beliebig123!"},
    )
    assert res.status_code == 401

    # Garbage token is a 400 (and the endpoint needs no CSRF header).
    res = client.post(
        "/api/user/invite/accept",
        json={"token": "NICHT-GUELTIG", "company_id": company_id,
              "password": "NeuesPasswort1!"},
    )
    assert res.status_code == 400
    assert "ungültig" in res.get_json()["error"]

    # Accepting works without a CSRF token (token = capability).
    res = client.post(
        "/api/user/invite/accept",
        json={"token": token, "company_id": company_id,
              "password": "NeuesPasswort1!"},
    )
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["user"]["company"] == "Vektorwerk Technik AG"

    # A session was established by the accept call.
    res = client.get("/api/auth/me")
    assert res.get_json()["data"]["user"]["company_email"] == (
        INVITE_PAYLOAD["company_email"]
    )

    # Single use: the token is dead afterwards.
    res = client.post(
        "/api/user/invite/accept",
        json={"token": token, "company_id": company_id,
              "password": "AndersPassw0rt!"},
    )
    assert res.status_code == 400
    assert "bereits verwendet" in res.get_json()["error"]

    # The chosen password works on the normal login page.
    csrf, invited_user = login(
        client, INVITE_PAYLOAD["company_email"], "NeuesPasswort1!"
    )
    assert invited_user["role"] == "lernender"

    # And the admin sees the invitation as consumed.
    _, admin_user = login(client, "admin@vektorwerk.ch")
    res = client.get(f"/api/user/{invited_user['id']}")
    assert res.get_json()["data"]["password_pending"] is False


def test_user_invite_expired_then_admin_resend(client):
    created, _csrf = _create_invited_user(client)
    _message, old_token, company_id = _invite_from_outbox(client)

    # Force the invite into the past.
    with company_context(client) as company:
        target = db.session.get(User, created["id"])
        target.invite_expires_at = (
            datetime.now(dt_timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
        )
        db.session.commit()

    res = client.post(
        "/api/user/invite/accept",
        json={"token": old_token, "company_id": company_id,
              "password": "NeuesPasswort1!"},
    )
    assert res.status_code == 400
    assert "abgelaufen" in res.get_json()["error"]

    _csrf_admin, _admin = login(client, "admin@vektorwerk.ch")
    res = client.post(
        f"/api/user/{created['id']}/invite/resend",
        headers={"X-CSRF-Token": _csrf_admin},
    )
    assert res.status_code == 200
    assert res.get_json()["data"]["password_pending"] is True

    message, new_token, company_id2 = _invite_from_outbox(client, index=1)
    assert new_token != old_token

    # Old link is dead, the re-sent one works.
    res = client.post(
        "/api/user/invite/accept",
        json={"token": old_token, "company_id": company_id2,
              "password": "NeuesPasswort1!"},
    )
    assert res.status_code == 400
    res = client.post(
        "/api/user/invite/accept",
        json={"token": new_token, "company_id": company_id2,
              "password": "NeuesPasswort1!"},
    )
    assert res.status_code == 200


def test_user_invite_resend_is_admin_only_and_unusable_after_password(client):
    created, _csrf = _create_invited_user(client)
    _message, token, company_id = _invite_from_outbox(client)

    # Supervisors cannot re-send invitations.
    csrf_trainer, _ = login(client, "trainer@vektorwerk.ch")
    res = client.post(
        f"/api/user/{created['id']}/invite/resend",
        headers={"X-CSRF-Token": csrf_trainer},
    )
    assert res.status_code == 403

    # After the invitation was honoured, resend is refused (and the
    # password-change endpoint kills any outstanding invite anyway).
    res = client.post(
        "/api/user/invite/accept",
        json={"token": token, "company_id": company_id,
              "password": "NeuesPasswort1!"},
    )
    assert res.status_code == 200

    csrf_admin, _ = login(client, "admin@vektorwerk.ch")
    res = client.post(
        f"/api/user/{created['id']}/invite/resend",
        headers={"X-CSRF-Token": csrf_admin},
    )
    assert res.status_code == 400
    assert "bereits ein Passwort" in res.get_json()["error"]


def test_user_invite_accept_validates_password(client):
    created, _csrf = _create_invited_user(client)
    _message, token, company_id = _invite_from_outbox(client)

    res = client.post(
        "/api/user/invite/accept",
        json={"token": token, "company_id": company_id, "password": "kurz"},
    )
    assert res.status_code == 400
    assert "mindestens 8 Zeichen" in res.get_json()["error"]

    # The invite was not consumed by the failed attempts.
    res = client.post(
        "/api/user/invite/accept",
        json={"token": token, "company_id": company_id,
              "password": "NeuesPasswort1!"},
    )
    assert res.status_code == 200


def test_user_invite_accept_without_company_id_rejected(client):
    created, _csrf = _create_invited_user(client)
    _message, token, _company_id = _invite_from_outbox(client)

    res = client.post(
        "/api/user/invite/accept",
        json={"token": token, "password": "NeuesPasswort1!"},
    )
    assert res.status_code == 400


def test_health_reports_mail_configuration(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "ok"
    # Test fixture disables SMTP explicitly -> mail is "not configured",
    # which development outbox handling covers.
    assert data["mail_configured"] is False


def test_production_without_smtp_warns_at_startup(tmp_path, caplog):
    import logging

    with caplog.at_level(logging.WARNING, logger="backend.app"):
        app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'c.db'}",
                "COMPANY_ROOT": str(tmp_path / "companies"),
                "SECRET_KEY": "x" * 40,
                "IS_DEV": False,
                "DEBUG": False,
                "SESSION_COOKIE_SECURE": True,
                "SMTP_HOST": "",
                "MAIL_DEV_OUTBOX": str(tmp_path / "outbox.log"),
                "SIGNUP_ENABLED": True,
            }
        )
    assert any(
        "SMTP_HOST is not configured" in record.message for record in caplog.records
    )
    assert (
        app.test_client().get("/api/health").get_json()["mail_configured"] is False
    )


def test_startup_warning_suppressed_when_signup_disabled(tmp_path, caplog):
    import logging

    with caplog.at_level(logging.WARNING, logger="backend.app"):
        app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'c.db'}",
                "COMPANY_ROOT": str(tmp_path / "companies"),
                "SECRET_KEY": "x" * 40,
                "IS_DEV": False,
                "DEBUG": False,
                "SESSION_COOKIE_SECURE": True,
                "SMTP_HOST": "",
                "SIGNUP_ENABLED": False,
            }
        )
    assert not any("SMTP_HOST is not configured" in record.message for record in caplog.records)
    assert app.test_client().get("/api/health").get_json()["mail_configured"] is False
