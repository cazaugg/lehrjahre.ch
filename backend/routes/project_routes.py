import json
from datetime import date
from flask import Blueprint, request, jsonify
from backend.models import db, Project, Participation, Eval, User
from backend.auth import login_required, role_required, get_current_user

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


def student_can_view_project(actor: User, root_project: Project) -> bool:
    if actor.role == "ausbildner":
        return True
    if not root_project.is_published:
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
) -> dict:
    d = project.to_dict()
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
    d["tasks"] = [t.to_dict() for t in tasks]

    if include_details:
        project_and_task_ids = [project.id] + [t.id for t in tasks]
        part_query = Participation.query.filter(
            Participation.project.in_(project_and_task_ids)
        )
        eval_query = Eval.query.filter(Eval.project.in_(project_and_task_ids))

        if actor.role == "lernender":
            part_query = part_query.filter_by(student=actor.id)
            eval_query = eval_query.filter_by(student=actor.id)

        parts = part_query.order_by(Participation.id.asc()).all()
        evals = eval_query.order_by(Eval.id.asc()).all()

        if actor.role == "lernender":
            # Students only see evaluations that have been released or when project is completed
            visible_evals = [
                e for e in evals if e.is_released or project.is_completed
            ]
            if not project.is_completed and not visible_evals:
                d["global_eval_text"] = ""
            evals = visible_evals

        d["participations"] = [p.to_dict() for p in parts]
        d["evaluations"] = [e.to_dict() for e in evals]

    return d


def _sync_subtasks(parent_project: Project, tasks_payload: list, actor_id: int):
    existing_tasks = {
        t.id: t
        for t in Project.query.filter_by(parent_project=parent_project.id).all()
    }
    kept_ids = set()

    for idx, t_data in enumerate(tasks_payload):
        if not isinstance(t_data, dict):
            continue
        t_title = (t_data.get("title") or "").strip()
        if not t_title:
            continue
        t_id = t_data.get("id")
        doc_id = t_data.get("document_id")
        doc_id = int(doc_id) if doc_id else None

        if t_id and int(t_id) in existing_tasks:
            task = existing_tasks[int(t_id)]
            kept_ids.add(task.id)
            task.title = t_title
            task.description = (t_data.get("description") or "").strip()
            task.document_id = doc_id
            if "goals" in t_data:
                task.goals = serialize_goals(t_data.get("goals"))
            task.start_date = parse_date(t_data.get("start_date")) or parent_project.start_date
            task.due_date = parse_date(t_data.get("due_date")) or parent_project.due_date
            task.is_published = parent_project.is_published
            task.is_completed = parent_project.is_completed
            task.assigned_students = parent_project.assigned_students
        else:
            new_task = Project(
                parent_project=parent_project.id,
                title=t_title,
                description=(t_data.get("description") or "").strip(),
                document_id=doc_id,
                author=actor_id,
                goals=serialize_goals(t_data.get("goals")),
                assigned_students=parent_project.assigned_students,
                start_date=parse_date(t_data.get("start_date")) or parent_project.start_date,
                due_date=parse_date(t_data.get("due_date")) or parent_project.due_date,
                is_published=parent_project.is_published,
                is_completed=parent_project.is_completed,
            )
            db.session.add(new_task)

    for old_id, old_task in existing_tasks.items():
        if old_id not in kept_ids:
            db.session.delete(old_task)


@bp.route("", methods=["GET"])
@login_required
def list_projects():
    actor = get_current_user()
    company_users = User.query.filter_by(company=actor.company).all()
    company_user_ids = [u.id for u in company_users]
    user_map = {u.id: u for u in company_users}

    projects = (
        Project.query.filter(
            (Project.author.in_(company_user_ids)) | (Project.author.is_(None))
        )
        .order_by(Project.start_date.desc().nullslast(), Project.id.desc())
        .all()
    )

    root_projects = [p for p in projects if not p.parent_project]
    all_tasks = [p for p in projects if p.parent_project]

    visible_roots = [
        p for p in root_projects if student_can_view_project(actor, p)
    ]

    return jsonify(
        {
            "data": [
                enrich_project_dict(
                    p, actor, all_tasks, user_map, include_details=True
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
    if not project:
        return jsonify({"error": "Projekt nicht gefunden."}), 404

    root = (
        db.session.get(Project, project.parent_project)
        if project.parent_project
        else project
    )
    if not root or not student_can_view_project(actor, root):
        return jsonify({"error": "Projekt nicht gefunden oder noch nicht freigegeben."}), 404

    company_users = User.query.filter_by(company=actor.company).all()
    user_map = {u.id: u for u in company_users}
    all_tasks = (
        Project.query.filter_by(parent_project=project.id)
        .order_by(Project.id.asc())
        .all()
    )

    return jsonify(
        {
            "data": enrich_project_dict(
                project, actor, all_tasks, user_map, include_details=True
            )
        }
    )


@bp.route("", methods=["POST"])
@role_required("ausbildner")
def create_project():
    actor = get_current_user()
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "Projekttitel ist erforderlich."}), 400

    parent_id = data.get("parent_project")
    if parent_id:
        parent = db.session.get(Project, int(parent_id))
        if not parent:
            return jsonify({"error": "Übergeordnetes Projekt nicht gefunden."}), 400
    else:
        parent_id = None

    description = (data.get("description") or "").strip()
    doc_id = data.get("document_id")
    doc_id = int(doc_id) if doc_id else None
    is_published = bool(data.get("is_published", False))

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
        assigned_students=serialize_students(data.get("assigned_students")),
        start_date=parse_date(data.get("start_date")),
        due_date=parse_date(data.get("due_date")),
        is_published=is_published,
        is_completed=bool(data.get("is_completed", False)),
        global_eval_text=(data.get("global_eval_text") or "").strip(),
    )
    db.session.add(project)
    db.session.flush()

    if isinstance(data.get("tasks"), list):
        _sync_subtasks(project, data["tasks"], actor.id)

    db.session.commit()

    company_users = User.query.filter_by(company=actor.company).all()
    user_map = {u.id: u for u in company_users}
    all_tasks = Project.query.filter_by(parent_project=project.id).all()
    return (
        jsonify(
            {
                "data": enrich_project_dict(
                    project, actor, all_tasks, user_map, include_details=True
                )
            }
        ),
        201,
    )


@bp.route("/<int:project_id>", methods=["PUT"])
@role_required("ausbildner")
def update_project(project_id):
    actor = get_current_user()
    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"error": "Projekt nicht gefunden."}), 404

    data = request.get_json(silent=True) or {}
    if "title" in data and data["title"].strip():
        project.title = data["title"].strip()
    if "description" in data:
        project.description = (data.get("description") or "").strip()
    if "document_id" in data:
        doc_id = data.get("document_id")
        project.document_id = int(doc_id) if doc_id else None
    if "parent_project" in data:
        parent_id = data.get("parent_project")
        if parent_id and int(parent_id) != project.id:
            project.parent_project = int(parent_id)
        else:
            project.parent_project = None
    if "goals" in data:
        project.goals = serialize_goals(data.get("goals"))
    if "assigned_students" in data:
        project.assigned_students = serialize_students(data.get("assigned_students"))
    if "start_date" in data:
        project.start_date = parse_date(data.get("start_date"))
    if "due_date" in data:
        project.due_date = parse_date(data.get("due_date"))
    if "is_published" in data:
        project.is_published = bool(data.get("is_published"))
    if "is_completed" in data:
        project.is_completed = bool(data.get("is_completed"))
    if "global_eval_text" in data:
        project.global_eval_text = (data.get("global_eval_text") or "").strip()

    if project.is_published and not project.description and not project.document_id:
        return jsonify(
            {
                "error": "Für die Freigabe muss mindestens ein Beschreibungstext oder ein Dokument vorhanden sein."
            }
        ), 400

    if isinstance(data.get("tasks"), list):
        _sync_subtasks(project, data["tasks"], actor.id)
    else:
        # Keep existing child tasks in sync with publication/completion/students
        for child in Project.query.filter_by(parent_project=project.id).all():
            child.is_published = project.is_published
            child.is_completed = project.is_completed
            child.assigned_students = project.assigned_students

    db.session.commit()

    company_users = User.query.filter_by(company=actor.company).all()
    user_map = {u.id: u for u in company_users}
    all_tasks = Project.query.filter_by(parent_project=project.id).all()
    return jsonify(
        {
            "data": enrich_project_dict(
                project, actor, all_tasks, user_map, include_details=True
            )
        }
    )


@bp.route("/<int:project_id>", methods=["DELETE"])
@role_required("ausbildner")
def delete_project(project_id):
    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"error": "Projekt nicht gefunden."}), 404

    db.session.delete(project)
    db.session.commit()
    return jsonify({"data": {"deleted": project_id}})
