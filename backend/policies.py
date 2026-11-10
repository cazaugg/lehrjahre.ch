from flask import g
from backend.models import (
    db,
    User,
    UserRelation,
    Project,
    Participation,
    Eval,
    Documents,
    Knowledge,
)


def is_admin(actor: User | None) -> bool:
    """Administrators manage people and relationships company-wide."""
    return bool(actor and actor.role == "admin")


def is_supervisor(actor: User | None) -> bool:
    """Supervisor capabilities (projects, evals, grades, documents).

    An admin inherits all supervisor capabilities; supervisors keep exactly
    their current reach (own data + subordinate students).
    """
    return bool(actor and actor.role in ("ausbildner", "admin"))


def is_student(actor: User | None) -> bool:
    return bool(actor and actor.role == "lernender")


def supervised_student_ids(actor: User | None) -> set[int]:
    """Return IDs of students directly subordinate to supervisor `actor`."""
    if not is_supervisor(actor):
        return set()
    cache = getattr(g, "_supervised_student_ids", None)
    if cache is None:
        cache = {}
        g._supervised_student_ids = cache
    if actor.id not in cache:
        rels = (
            UserRelation.query.join(User, UserRelation.student == User.id)
            .filter(
                UserRelation.supervisor == actor.id,
                User.company_id == actor.company_id,
                User.role == "lernender",
            )
            .all()
        )
        cache[actor.id] = {r.student for r in rels}
    return cache[actor.id]


def is_supervisor_of(actor: User | None, student_id: int | None) -> bool:
    if not student_id or not is_supervisor(actor):
        return False
    return int(student_id) in supervised_student_ids(actor)


def can_access_student(actor: User | None, student_id: int | None) -> bool:
    """
    Check whether `actor` can access student-scoped records (Lerndokumentation, etc.).
    - Lernende: only own records (actor.id == student_id)
    - Vorgesetzter: only records of subordinate students (user_relation)
    """
    if not actor or not student_id:
        return False
    student_id = int(student_id)
    if is_student(actor):
        return actor.id == student_id
    if is_supervisor(actor):
        return student_id in supervised_student_ids(actor)
    return False


# ---------------------------------------------------------------------------
# Personen & Account Policies
# ---------------------------------------------------------------------------

def can_view_private_contacts(actor: User | None, target: User | None) -> bool:
    """
    - Admins can view the private contacts of everyone in the company.
    - Everyone can view their own private contacts.
    - Supervisors can view private contacts ONLY of their subordinate students.
    - Never visible for other supervisors or non-subordinate students.
    """
    if not actor or not target or actor.company_id != target.company_id:
        return False
    if actor.id == target.id:
        return True
    if is_admin(actor):
        return True
    if is_supervisor(actor) and target.role == "lernender":
        return target.id in supervised_student_ids(actor)
    return False


def can_edit_user_contacts(actor: User | None, target: User | None) -> bool:
    """
    - Admins can edit the contacts of everyone in the company.
    - Supervisors can edit their own contacts (company, school, private)
      and all contacts of their subordinate students.
    - Students cannot edit any contact fields (not even their own).
    """
    if not actor or not target or actor.company_id != target.company_id:
        return False
    if is_admin(actor):
        return True
    if not is_supervisor(actor):
        return False
    if actor.id == target.id:
        return True
    if target.role == "lernender" and target.id in supervised_student_ids(actor):
        return True
    return False


def can_edit_student_master_data(actor: User | None, target: User | None) -> bool:
    """Admins edit master data of everyone; supervisors of their subordinate
    students (and themselves)."""
    if not actor or not target or actor.company_id != target.company_id:
        return False
    if is_admin(actor):
        return True
    if not is_supervisor(actor):
        return False
    if actor.id == target.id:
        return True
    return target.role == "lernender" and target.id in supervised_student_ids(actor)


def serialize_user(target: User, actor: User | None) -> dict:
    """Serialize a User while stripping private contact fields if unauthorized."""
    data = target.to_dict()
    # Pending first-login invitation (admins use it for the resend button).
    data["password_pending"] = bool(target.invite_token_hash)
    if can_view_private_contacts(actor, target):
        data["can_view_private"] = True
    else:
        data.pop("private_address", None)
        data.pop("private_email", None)
        data.pop("private_phone", None)
        data["can_view_private"] = False
    data["can_edit_contacts"] = can_edit_user_contacts(actor, target)
    data["can_edit_master_data"] = can_edit_student_master_data(actor, target)
    data["is_subordinate"] = is_supervisor_of(actor, target.id)
    if actor and actor.id == target.id and is_supervisor(actor):
        data["supervised_student_ids"] = sorted(supervised_student_ids(actor))
    return data


# ---------------------------------------------------------------------------
# Projekte, Themen & Praktika Policies
# ---------------------------------------------------------------------------

def _company_projects_by_id(company_id: int) -> dict[int, Project]:
    company_user_ids = [
        u.id for u in User.query.filter_by(company_id=company_id).all()
    ]
    if not company_user_ids:
        return {}
    # Every visible project must have an author in the actor's company.
    # Authorless projects are not accessible to anyone (see delete_user, which
    # reassigns projects before deleting their author).
    projects = Project.query.filter(Project.author.in_(company_user_ids)).all()
    return {p.id: p for p in projects}


def _direct_supervisor_project_ids(
    actor: User | None, proj_map: dict[int, Project]
) -> set[int]:
    """Projects a supervisor may manage: their own and their learners'."""
    if not is_supervisor(actor):
        return set()

    direct_ids = {pid for pid, p in proj_map.items() if p.author == actor.id}
    sub_ids = supervised_student_ids(actor)
    if sub_ids:
        part_pids = {
            r.project
            for r in Participation.query.filter(
                Participation.student.in_(sub_ids)
            ).all()
            if r.project in proj_map
        }
        eval_pids = {
            r.project
            for r in Eval.query.filter(Eval.student.in_(sub_ids)).all()
            if r.project in proj_map
        }
        assigned_pids = {
            pid
            for pid, p in proj_map.items()
            if set(p.parsed_assigned_students()) & sub_ids
        }
        direct_ids |= part_pids | eval_pids | assigned_pids
    return direct_ids


def visible_project_ids_for(actor: User | None) -> set[int]:
    """
    Compute the set of Project IDs visible to `actor`:
    - Vorgesetzter: Own projects (author == actor.id) and projects where a
      subordinate student participates (via Participation or Eval), plus
      associated child/parent projects in the tree.
    - Lernende: Only projects where the student participates (via Participation
      or Eval) AND `planning_released == True` (plus released parent containers).

    Visibility is broader than management; see `can_manage_project`.
    """
    if not actor:
        return set()

    proj_map = _company_projects_by_id(actor.company_id)
    if not proj_map:
        return set()

    if is_supervisor(actor):
        direct_ids = _direct_supervisor_project_ids(actor, proj_map)

        # Include descendants of visible projects and ancestors up to root
        visible = set(direct_ids)
        changed = True
        while changed:
            changed = False
            for pid, p in proj_map.items():
                if pid not in visible and p.parent_project in visible:
                    visible.add(pid)
                    changed = True
                if pid in visible and p.parent_project and p.parent_project in proj_map and p.parent_project not in visible:
                    visible.add(p.parent_project)
                    changed = True
        return visible

    if is_student(actor):
        part_pids = {
            r.project
            for r in Participation.query.filter_by(student=actor.id).all()
            if r.project in proj_map
        }
        eval_pids = {
            r.project
            for r in Eval.query.filter_by(student=actor.id).all()
            if r.project in proj_map
        }
        assigned_pids = {
            pid
            for pid, p in proj_map.items()
            if actor.id in p.parsed_assigned_students()
        }
        participating_pids = {
            pid
            for pid in (part_pids | eval_pids | assigned_pids)
            if proj_map[pid].planning_released or proj_map[pid].is_published
        }
        visible = set(participating_pids)
        # Walk up parent_project chain ONLY if ancestor is also released
        for pid in list(participating_pids):
            curr = proj_map.get(pid)
            while curr and curr.parent_project:
                parent = proj_map.get(curr.parent_project)
                if parent and (parent.planning_released or parent.is_published):
                    visible.add(parent.id)
                    curr = parent
                else:
                    break
        return visible

    return set()


def can_view_project(actor: User | None, project: Project | None) -> bool:
    if not actor or not project:
        return False
    return project.id in visible_project_ids_for(actor)


def manageable_project_ids_for(actor: User | None) -> set[int]:
    if not is_supervisor(actor):
        return set()
    proj_map = _company_projects_by_id(actor.company_id)
    return _direct_supervisor_project_ids(actor, proj_map)


def can_manage_project(actor: User | None, project: Project | None) -> bool:
    """
    Supervisors may edit/delete only their own projects and projects their
    subordinate learners participate in. Parent/child context projects are
    visible but not automatically manageable.
    """
    if not is_supervisor(actor) or not project:
        return False
    proj_map = _company_projects_by_id(actor.company_id)
    if project.id not in proj_map:
        return False
    return project.id in _direct_supervisor_project_ids(actor, proj_map)


def serialize_project(
    project: Project,
    actor: User | None,
    manageable_ids: set[int] | None = None,
) -> dict:
    data = project.to_dict()
    data["document"] = serialize_document_for(project.document, actor)
    if manageable_ids is None:
        data["can_manage"] = can_manage_project(actor, project)
    else:
        data["can_manage"] = project.id in manageable_ids
    return data


def can_participate_in_project(actor: User | None, project: Project | None) -> bool:
    """Students may report only on projects they are directly assigned to."""
    if not is_student(actor) or not project:
        return False
    proj_map = _company_projects_by_id(actor.company_id)
    if project.id not in proj_map:
        return False

    root = (
        proj_map.get(project.parent_project)
        if project.parent_project
        else project
    )
    if root and actor.id in root.parsed_assigned_students():
        return True

    return bool(
        Participation.query.filter_by(
            student=actor.id, project=project.id
        ).first()
        or Eval.query.filter_by(student=actor.id, project=project.id).first()
    )


def serialize_eval(
    evaluation: Eval, actor: User | None, project_completed: bool = False
) -> dict:
    """Mask eval_text for students until eval_released is True."""
    data = evaluation.to_dict()
    if is_student(actor) and not (
        evaluation.eval_released or evaluation.is_released or project_completed
    ):
        data["eval_text"] = ""
        data["score_type"] = None
        data["score_value"] = None
        # Beigefügte Auswertungsdateien folgen der Freigabe: erst nach der
        # Freigabe (oder dem Projektabschluss) sind sie für Lernende sichtbar.
        data["document_id"] = None
        data["document"] = None
    # Never expose a supervisor from another company, even for legacy rows.
    if (
        evaluation.supervisor_user
        and actor
        and evaluation.supervisor_user.company_id != actor.company_id
    ):
        data["supervisor"] = None
        data["supervisor_name"] = ""
    return data


def serialize_participation(participation: Participation, actor: User | None) -> dict:
    """Serialize a Participation without leaking foreign-company supervisors."""
    data = participation.to_dict()
    data["document"] = serialize_document_for(participation.document, actor)
    if (
        participation.supervisor_user
        and actor
        and participation.supervisor_user.company_id != actor.company_id
    ):
        data["supervisor"] = None
        data["supervisor_name"] = ""
    return data


# ---------------------------------------------------------------------------
# Documents & Wissen Policies
# ---------------------------------------------------------------------------

def visible_knowledge_owner_ids(actor: User | None) -> set[int]:
    """
    - Vorgesetzter: Own entries and entries of subordinate students.
    - Lernende: Only own entries.
    """
    if not actor:
        return set()
    if is_student(actor):
        return {actor.id}
    if is_supervisor(actor):
        return {actor.id} | supervised_student_ids(actor)
    return set()


def _project_document_visible(actor: User | None, doc: Documents) -> bool:
    """Return True when a project document is attached to a visible project."""
    if not actor:
        return False
    visible_ids = visible_project_ids_for(actor)
    if not visible_ids:
        return False
    return (
        Project.query.filter(
            Project.document_id == doc.id,
            Project.id.in_(visible_ids),
        ).first()
        is not None
    )


def can_view_document(actor: User | None, doc: Documents | None) -> bool:
    if not actor or not doc:
        return False
    owner = db.session.get(User, doc.owner)
    if not owner or owner.company_id != actor.company_id:
        return False

    # Everyone may see their own documents and documents they authored.
    if doc.owner == actor.id or doc.author == actor.id:
        return True

    # Profile pictures belong to company contact data -> visible within company
    if doc.type == "profilbild":
        return True

    # Templates are deliberately company-wide.
    if doc.is_template:
        return True

    # Knowledge documents follow knowledge visibility rules
    if doc.type == "wissen":
        return doc.owner in visible_knowledge_owner_ids(actor)

    if doc.type == "projekt":
        # Supervisors may see their learners' submitted project documents.
        if is_supervisor_of(actor, doc.owner):
            return True
        # Trainer-owned project documents are readable by users who can see the
        # project they are attached to (not by the whole company).
        return _project_document_visible(actor, doc)

    # All other documents (zeugnis, kursnachweis, ausbildungsgespraech,
    # lernjournal, vertrag, bewerbung, sonstiges):
    # - Student: own documents (doc.owner == actor.id)
    # - Supervisor: own documents or subordinate students' documents
    return is_supervisor_of(actor, doc.owner)


def serialize_document_for(doc: Documents | None, actor: User | None) -> dict | None:
    """Return document metadata only when the actor may view the document."""
    if not doc or not can_view_document(actor, doc):
        return None
    return doc.to_dict()


def can_create_document(
    actor: User | None, doc_type: str, owner_id: int, is_template: bool = False
) -> bool:
    if not actor:
        return False
    owner = db.session.get(User, owner_id)
    if not owner or owner.company_id != actor.company_id:
        return False

    if is_template:
        return is_supervisor(actor)

    if doc_type == "profilbild":
        return actor.id == owner_id or is_supervisor_of(actor, owner_id)

    if doc_type == "projekt":
        return actor.id == owner_id or is_supervisor_of(actor, owner_id)

    if doc_type == "wissen":
        return actor.id == owner_id

    if doc_type in {"zeugnis", "kursnachweis", "sonstiges"}:
        if is_student(actor):
            return actor.id == owner_id
        return is_supervisor_of(actor, owner_id) or actor.id == owner_id

    if doc_type in {"ausbildungsgespraech", "vertrag", "bewerbung"}:
        # Only supervisors can create these for subordinate students
        return is_supervisor_of(actor, owner_id)

    if doc_type == "lernjournal":
        # Only students create their own journal entries
        return is_student(actor) and actor.id == owner_id

    return False


def can_delete_document(actor: User | None, doc: Documents | None) -> bool:
    if not actor or not doc or not can_view_document(actor, doc):
        return False

    if doc.is_template:
        return is_supervisor(actor)

    if doc.type == "wissen":
        return doc.owner == actor.id

    if doc.type == "profilbild":
        return doc.owner == actor.id or is_supervisor_of(actor, doc.owner)

    if doc.type in {"zeugnis", "kursnachweis"}:
        # Supervisors can delete their own and subordinate students' documents;
        # students can only create & edit (no delete).
        return is_supervisor(actor) and (
            doc.owner == actor.id or is_supervisor_of(actor, doc.owner)
        )

    if doc.type in {"ausbildungsgespraech", "vertrag", "bewerbung"}:
        # Only supervisors can delete for subordinate students
        return is_supervisor_of(actor, doc.owner)

    if doc.type == "lernjournal":
        # Only the student can delete their own journal entry
        return is_student(actor) and doc.owner == actor.id

    if doc.type == "sonstiges":
        if is_student(actor):
            return doc.owner == actor.id
        return doc.owner == actor.id or is_supervisor_of(actor, doc.owner)

    if doc.type == "projekt":
        if is_student(actor):
            return doc.owner == actor.id
        return doc.owner == actor.id or is_supervisor_of(actor, doc.owner)

    return False
