import json
from datetime import date
from flask import Blueprint, request, jsonify
from backend.models import db, Project, Participation, Eval, User, Documents
from backend.auth import login_required, role_required, get_current_user
from backend.audit import audit
from backend.policies import (
    is_supervisor,
    visible_project_ids_for,
    can_view_project,
    can_manage_project,
    manageable_project_ids_for,
    supervised_student_ids,
    can_view_document,
    serialize_project,
    serialize_participation,
    serialize_eval,
)
from backend.validation import ValidationError, parse_bool, parse_int, parse_str

bp = Blueprint("api_project", __name__, url_prefix="/api/project")


def parse_date(val):
    if not val:
        return None
    if isinstance(val, date):
        return val
    try:
        return date.fromisoformat(str(val)[:10])
    except ValueError:
        return None


def serialize_goals(goals_input) -> str:
    if goals_input is None:
        return "[]"
    if isinstance(goals_input, list):
        cleaned = [str(g).strip() for g in goals_input if str(g).strip()]
        return json.dumps(cleaned, ensure_ascii=False)
    if isinstance(goals_input, str):
        lines = [line.strip() for line in goals_input.splitlines() if line.strip()]
        return json.dumps(lines, ensure_ascii=False)
    return "[]"


def _validated_assigned_students(actor: User, students_input):
    """Return (json_string, error). Only same-company learners are kept.

    Foreign-company IDs are rejected with a 400 rather than silently dropped:
    they usually indicate a client bug or a probing attempt.
    """
    if not students_input:
        return "[]", None
    if not isinstance(students_input, list):
        return None, "Ungültige Zuordnung von Lernenden."
    cleaned = []
    for s in students_input:
        try:
            val = int(s)
        except (TypeError, ValueError):
            return None, "Ungültige Zuordnung von Lernenden."
        if val not in cleaned:
            cleaned.append(val)
    for val in cleaned:
        user = db.session.get(User, val)
        if (
            not user
            or user.company_id != actor.company_id
            or user.role != "lernender"
        ):
            return None, "Ungültige Zuordnung von Lernenden."
    return json.dumps(cleaned), None


def serialize_students(students_input) -> str:
    if not students_input:
        return "[]"
    if isinstance(students_input, list):
        cleaned = []
        for s in students_input:
            try:
                val = int(s)
                if val not in cleaned:
                    cleaned.append(val)
            except (TypeError, ValueError):
                pass
        return json.dumps(cleaned)
    return "[]"


def _validated_project_document(actor: User, raw_doc_id, current_doc_id=None):
    """Return (document, error). Only own documents or company templates are attachable."""
    if raw_doc_id in (None, ""):
        return None, None
    try:
        doc_id = int(raw_doc_id)
    except (TypeError, ValueError):
        return None, "Ungültiges Dokument."
    doc = db.session.get(Documents, doc_id)
    if not doc or not can_view_document(actor, doc):
        return None, "Dokument nicht gefunden."
    if (
        doc.owner != actor.id
        and not doc.is_template
        and doc.id != current_doc_id
    ):
        return None, "Dokument nicht gefunden."
    return doc, None


def student_can_view_project(actor: User, root_project: Project) -> bool:
    if is_supervisor(actor):
        return True
    if not (root_project.is_published or root_project.planning_released):
        return False
    assigned = root_project.parsed_assigned_students()
    if assigned and actor.id not in assigned:
        return False
    return True


def enrich_project_dict(
    project: Project,
    actor: User,
    all_tasks: list[Project],
    user_map: dict[int, User],
    include_details: bool = False,
    manageable_ids: set[int] | None = None,
) -> dict:
    d = serialize_project(project, actor, manageable_ids)
    assigned_ids = d["assigned_students"]
    d["assigned_student_users"] = [
        {
            "id": uid,
            "full_name": f"{user_map[uid].name} {user_map[uid].surname}".strip(),
            "job_title": user_map[uid].job_title,
        }
        for uid in assigned_ids
        if uid in user_map
    ]
    tasks = [t for t in all_tasks if t.parent_project == project.id]
    tasks.sort(key=lambda x: x.id)
    d["tasks"] = [
        serialize_project(t, actor, manageable_ids) for t in tasks
    ]

    if include_details:
        project_and_task_ids = [project.id] + [t.id for t in tasks]
        if actor.role == "lernender":
            allowed_student_ids = {actor.id}
        else:
            allowed_student_ids = supervised_student_ids(actor)

        if allowed_student_ids:
            parts = (
                Participation.query.filter(
                    Participation.project.in_(project_and_task_ids),
                    Participation.student.in_(allowed_student_ids),
                )
                .order_by(Participation.id.asc())
                .all()
            )
            evals = (
                Eval.query.filter(
                    Eval.project.in_(project_and_task_ids),
                    Eval.student.in_(allowed_student_ids),
                )
                .order_by(Eval.id.asc())
                .all()
            )
        else:
            parts = []
            evals = []

        d["participations"] = [serialize_participation(p, actor) for p in parts]
        if actor.role == "lernender":
            # Planning is visible once the project is released, but evaluation
            # text stays hidden until it has been explicitly released.
            released_evals = [
                e for e in evals if e.is_released or e.eval_released
            ]
            if not project.is_completed and not released_evals:
                d["global_eval_text"] = ""

            d["evaluations"] = [
                serialize_eval(e, actor, project_completed=project.is_completed)
                for e in evals
            ]
        else:
            d["evaluations"] = [serialize_eval(e, actor) for e in evals]

    return d


def _sync_subtasks(parent_project: Project, tasks_payload: list, actor: User):
    existing_tasks = {
        t.id: t
        for t in Project.query.filter_by(parent_project=parent_project.id).all()
    }
    kept_ids = set()

    for t_data in tasks_payload:
        if not isinstance(t_data, dict):
            continue
        try:
            t_title = parse_str(t_data.get("title"), "Aufgabentitel")
            t_description = parse_str(
                t_data.get("description"), "Aufgabenbeschreibung"
            )
        except ValidationError as exc:
            return str(exc)
        if not t_title:
            continue
        raw_task_id = t_data.get("id")
        task_id = None
        if raw_task_id not in (None, ""):
            try:
                task_id = int(raw_task_id)
            except (TypeError, ValueError):
                return "Ungültige Aufgabe."

        existing_task = (
            existing_tasks.get(task_id) if task_id is not None else None
        )
        doc, error = _validated_project_document(
            actor,
            t_data.get("document_id"),
            current_doc_id=existing_task.document_id if existing_task else None,
        )
        if error:
            return error
        doc_id = doc.id if doc else None

        if existing_task:
            if not can_manage_project(actor, existing_task):
                return "Keine Berechtigung für eine der Teilaufgaben."
            task = existing_task
            kept_ids.add(task.id)
            task.title = t_title
            task.description = t_description
            task.document_id = doc_id
            if "goals" in t_data:
                task.goals = serialize_goals(t_data.get("goals"))
            task.start_date = parse_date(t_data.get("start_date")) or parent_project.start_date
            task.due_date = parse_date(t_data.get("due_date")) or parent_project.due_date
            task.is_published = parent_project.is_published
            task.planning_released = parent_project.planning_released
            task.is_completed = parent_project.is_completed
            task.assigned_students = parent_project.assigned_students
        else:
            new_task = Project(
                parent_project=parent_project.id,
                title=t_title,
                description=t_description,
                document_id=doc_id,
                author=actor.id,
                goals=serialize_goals(t_data.get("goals")),
                assigned_students=parent_project.assigned_students,
                start_date=parse_date(t_data.get("start_date")) or parent_project.start_date,
                due_date=parse_date(t_data.get("due_date")) or parent_project.due_date,
                is_published=parent_project.is_published,
                planning_released=parent_project.planning_released,
                is_completed=parent_project.is_completed,
            )
            db.session.add(new_task)

    for old_id, old_task in existing_tasks.items():
        if old_id not in kept_ids:
            if not can_manage_project(actor, old_task):
                return "Keine Berechtigung für eine der Teilaufgaben."
            db.session.delete(old_task)

    return None


@bp.route("", methods=["GET"])
@login_required
def list_projects():
    actor = get_current_user()
    visible_ids = visible_project_ids_for(actor)
    if not visible_ids:
        return jsonify({"data": []})

    company_users = User.query.filter_by(company_id=actor.company_id).all()
    user_map = {u.id: u for u in company_users}

    projects = (
        Project.query.filter(Project.id.in_(visible_ids))
        .order_by(Project.start_date.desc().nullslast(), Project.id.desc())
        .all()
    )
    manageable_ids = manageable_project_ids_for(actor)

    root_projects = [p for p in projects if not p.parent_project]
    all_tasks = [p for p in projects if p.parent_project]

    visible_roots = [
        p for p in root_projects if student_can_view_project(actor, p)
    ]

    return jsonify(
        {
            "data": [
                enrich_project_dict(
                    p,
                    actor,
                    all_tasks,
                    user_map,
                    include_details=True,
                    manageable_ids=manageable_ids,
                )
                for p in visible_roots
            ]
        }
    )


@bp.route("/<int:project_id>", methods=["GET"])
@login_required
def get_project(project_id):
    actor = get_current_user()
    project = db.session.get(Project, project_id)
    if not project or not can_view_project(actor, project):
        return jsonify({"error": "Projekt nicht gefunden."}), 404
    root = (
        db.session.get(Project, project.parent_project)
        if project.parent_project
        else project
    )
    if not root or not student_can_view_project(actor, root):
        return jsonify({"error": "Projekt nicht gefunden oder noch nicht freigegeben."}), 404

    company_users = User.query.filter_by(company_id=actor.company_id).all()
    user_map = {u.id: u for u in company_users}
    all_tasks = (
        Project.query.filter_by(parent_project=project.id)
        .order_by(Project.id.asc())
        .all()
    )

    return jsonify(
        {
            "data": enrich_project_dict(
                project,
                actor,
                all_tasks,
                user_map,
                include_details=True,
                manageable_ids=manageable_project_ids_for(actor),
            )
        }
    )


@bp.route("", methods=["POST"])
@role_required("ausbildner", "admin")
def create_project():
    actor = get_current_user()
    data = request.get_json(silent=True) or {}
    title = parse_str(data.get("title"), "Projekttitel")
    if not title:
        return jsonify({"error": "Projekttitel ist erforderlich."}), 400

    parent_id = parse_int(
        data.get("parent_project"), "Übergeordnetes Projekt", allow_none=True
    )
    if parent_id:
        parent = db.session.get(Project, parent_id)
        if not parent or not can_manage_project(actor, parent):
            return jsonify({"error": "Übergeordnetes Projekt nicht gefunden."}), 400
        parent_id = parent.id

    description = parse_str(data.get("description"), "Beschreibung")
    doc, document_error = _validated_project_document(actor, data.get("document_id"))
    if document_error:
        return jsonify({"error": document_error}), 400
    assigned_students_json, students_error = _validated_assigned_students(
        actor, data.get("assigned_students")
    )
    if students_error:
        return jsonify({"error": students_error}), 400
    doc_id = doc.id if doc else None
    is_published = parse_bool(
        data.get("is_published", data.get("planning_released")),
        "Freigabe",
    )

    if is_published and not description and not doc_id:
        return jsonify(
            {
                "error": "Für die Freigabe muss mindestens ein Beschreibungstext oder ein Dokument vorhanden sein."
            }
        ), 400

    project = Project(
        parent_project=parent_id,
        title=title,
        description=description,
        document_id=doc_id,
        author=actor.id,
        goals=serialize_goals(data.get("goals")),
        assigned_students=assigned_students_json,
        start_date=parse_date(data.get("start_date")),
        due_date=parse_date(data.get("due_date")),
        is_published=is_published,
        is_completed=parse_bool(data.get("is_completed"), "Abgeschlossen"),
        global_eval_text=parse_str(
            data.get("global_eval_text"), "Gesamtbeurteilung"
        ),
        planning_released=is_published,
    )
    db.session.add(project)
    db.session.flush()

    if isinstance(data.get("tasks"), list):
        task_error = _sync_subtasks(project, data["tasks"], actor)
        if task_error:
            db.session.rollback()
            return jsonify({"error": task_error}), 400

    db.session.commit()
    audit("project_created", project_id=project.id, parent_id=project.parent_project)
    company_users = User.query.filter_by(company_id=actor.company_id).all()
    user_map = {u.id: u for u in company_users}
    all_tasks = Project.query.filter_by(parent_project=project.id).all()
    return (
        jsonify(
            {
                "data": enrich_project_dict(
                    project,
                    actor,
                    all_tasks,
                    user_map,
                    include_details=True,
                    manageable_ids=manageable_project_ids_for(actor),
                )
            }
        ),
        201,
    )


@bp.route("/<int:project_id>", methods=["PUT"])
@role_required("ausbildner", "admin")
def update_project(project_id):
    actor = get_current_user()
    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"error": "Projekt nicht gefunden."}), 404
    if not can_manage_project(actor, project):
        return jsonify({"error": "Keine Berechtigung für dieses Projekt."}), 403

    data = request.get_json(silent=True) or {}
    document = None
    document_changed = "document_id" in data
    if document_changed:
        document, document_error = _validated_project_document(
            actor, data.get("document_id"), current_doc_id=project.document_id
        )
        if document_error:
            return jsonify({"error": document_error}), 400

    if "title" in data:
        title = parse_str(data.get("title"), "Projekttitel")
        if title:
            project.title = title
    if "description" in data:
        project.description = parse_str(data.get("description"), "Beschreibung")
    if document_changed:
        project.document_id = document.id if document else None
    if "parent_project" in data:
        parent_id = parse_int(
            data.get("parent_project"), "Übergeordnetes Projekt", allow_none=True
        )
        if parent_id and parent_id != project.id:
            parent = db.session.get(Project, parent_id)
            if not parent or not can_manage_project(actor, parent):
                return jsonify({"error": "Ungültiges übergeordnetes Projekt."}), 400
            project.parent_project = parent.id
        else:
            project.parent_project = None
    if "goals" in data:
        project.goals = serialize_goals(data.get("goals"))
    if "assigned_students" in data:
        assigned_students_json, students_error = _validated_assigned_students(
            actor, data.get("assigned_students")
        )
        if students_error:
            return jsonify({"error": students_error}), 400
        project.assigned_students = assigned_students_json
    if "start_date" in data:
        project.start_date = parse_date(data.get("start_date"))
    if "due_date" in data:
        project.due_date = parse_date(data.get("due_date"))
    if "is_published" in data or "planning_released" in data:
        released = parse_bool(
            data.get("is_published", data.get("planning_released")),
            "Freigabe",
            default=bool(project.is_published),
        )
        project.is_published = released
        project.planning_released = released
    if "is_completed" in data:
        project.is_completed = parse_bool(
            data.get("is_completed"), "Abgeschlossen"
        )
    if "global_eval_text" in data:
        project.global_eval_text = parse_str(
            data.get("global_eval_text"), "Gesamtbeurteilung"
        )

    if project.is_published and not project.description and not project.document_id:
        return jsonify(
            {
                "error": "Für die Freigabe muss mindestens ein Beschreibungstext oder ein Dokument vorhanden sein."
            }
        ), 400

    if isinstance(data.get("tasks"), list):
        task_error = _sync_subtasks(project, data["tasks"], actor)
        if task_error:
            db.session.rollback()
            return jsonify({"error": task_error}), 400
    else:
        # Keep existing child tasks in sync with publication/completion/students
        for child in Project.query.filter_by(parent_project=project.id).all():
            # Visibility of a child via its parent does not grant management of
            # the child itself. Flag sync must never mutate a foreign child;
            # leave it unchanged rather than failing the whole parent update.
            if can_manage_project(actor, child):
                child.is_published = project.is_published
                child.planning_released = project.planning_released
                child.is_completed = project.is_completed
                child.assigned_students = project.assigned_students

    db.session.commit()
    audit("project_updated", project_id=project.id)
    company_users = User.query.filter_by(company_id=actor.company_id).all()
    user_map = {u.id: u for u in company_users}
    all_tasks = Project.query.filter_by(parent_project=project.id).all()
    return jsonify(
        {
            "data": enrich_project_dict(
                project,
                actor,
                all_tasks,
                user_map,
                include_details=True,
                manageable_ids=manageable_project_ids_for(actor),
            )
        }
    )


@bp.route("/<int:project_id>", methods=["DELETE"])
@role_required("ausbildner", "admin")
def delete_project(project_id):
    actor = get_current_user()
    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"error": "Projekt nicht gefunden."}), 404
    if not can_manage_project(actor, project):
        return jsonify({"error": "Keine Berechtigung für dieses Projekt."}), 403

    db.session.delete(project)
    db.session.commit()
    audit("project_deleted", project_id=project_id)
    return jsonify({"data": {"deleted": project_id}})
