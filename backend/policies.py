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


def is_supervisor(actor: User | None) -> bool:
    return bool(actor and actor.role == "ausbildner")


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
    - Everyone can view their own private contacts.
    - Supervisors can view private contacts ONLY of their subordinate students.
    - Never visible for other supervisors or non-subordinate students.
    """
    if not actor or not target or actor.company_id != target.company_id:
        return False
    if actor.id == target.id:
        return True
    if is_supervisor(actor) and target.role == "lernender":
        return target.id in supervised_student_ids(actor)
    return False


def can_edit_user_contacts(actor: User | None, target: User | None) -> bool:
    """
    - Supervisors can edit their own contacts (company, school, private)
      and all contacts of their subordinate students.
    - Students cannot edit any contact fields (not even their own).
    """
    if not actor or not target or actor.company_id != target.company_id:
        return False
    if not is_supervisor(actor):
        return False
    if actor.id == target.id:
        return True
    if target.role == "lernender" and target.id in supervised_student_ids(actor):
        return True
    return False


def can_edit_student_master_data(actor: User | None, target: User | None) -> bool:
    """Supervisors can edit master data of their subordinate students."""
    if not actor or not target or actor.company_id != target.company_id:
        return False
    if not is_supervisor(actor):
        return False
    if actor.id == target.id:
        return True
    return target.role == "lernender" and target.id in supervised_student_ids(actor)


def serialize_user(target: User, actor: User | None) -> dict:
    """Serialize a User while stripping private contact fields if unauthorized."""
    data = target.to_dict()
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
    projects = Project.query.filter(
        (Project.author.in_(company_user_ids)) | (Project.author.is_(None))
    ).all()
    return {p.id: p for p in projects}


def visible_project_ids_for(actor: User | None) -> set[int]:
    """
    Compute the set of Project IDs visible to `actor`:
    - Vorgesetzter: Own projects (author == actor.id) and projects where a
      subordinate student participates (via Participation or Eval), plus
      associated child/parent projects in the tree.
    - Lernende: Only projects where the student participates (via Participation
      or Eval) AND `planning_released == True` (plus released parent containers).
    """
    if not actor:
        return set()

    proj_map = _company_projects_by_id(actor.company_id)
    if not proj_map:
        return set()

    if is_supervisor(actor):
        sub_ids = supervised_student_ids(actor)
        direct_ids = {
            pid for pid, p in proj_map.items() if p.author == actor.id
        }
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
            direct_ids |= part_pids | eval_pids

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
        participating_pids = {
            pid
            for pid in (part_pids | eval_pids)
            if proj_map[pid].planning_released
        }
        visible = set(participating_pids)
        # Walk up parent_project chain ONLY if ancestor also has planning_released == True
        for pid in list(participating_pids):
            curr = proj_map.get(pid)
            while curr and curr.parent_project:
                parent = proj_map.get(curr.parent_project)
                if parent and parent.planning_released:
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


def can_manage_project(actor: User | None, project: Project | None) -> bool:
    """Only supervisors with access to the project can edit/delete it."""
    if not is_supervisor(actor) or not project:
        return False
    return project.id in visible_project_ids_for(actor)


def serialize_eval(evaluation: Eval, actor: User | None) -> dict:
    """Mask eval_text for students until eval_released is True."""
    data = evaluation.to_dict()
    if is_student(actor) and not evaluation.eval_released:
        data["eval_text"] = ""
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


def can_view_document(actor: User | None, doc: Documents | None) -> bool:
    if not actor or not doc:
        return False
    owner = db.session.get(User, doc.owner)
    if not owner or owner.company_id != actor.company_id:
        return False

    # Profile pictures belong to company contact data -> visible within company
    if doc.type == "profilbild":
        return True

    # Templates in the same company
    if doc.is_template:
        return True

    # Knowledge documents follow knowledge visibility rules
    if doc.type == "wissen":
        return doc.owner in visible_knowledge_owner_ids(actor)

    # All other documents (zeugnis, kursnachweis, ausbildungsgespraech,
    # lernjournal, vertrag, bewerbung, sonstiges):
    # - Student: own documents (doc.owner == actor.id)
    # - Supervisor: own documents or subordinate students' documents
    if doc.owner == actor.id:
        return True
    return is_supervisor_of(actor, doc.owner)


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
        # Supervisors can delete; students can only create & edit (no delete)
        return is_supervisor_of(actor, doc.owner)

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

    return False
