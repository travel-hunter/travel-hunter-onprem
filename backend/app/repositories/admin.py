from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import AdminAuditLog, ExternalSourceRecord, Policy, PolicyDocument, User


def _is_sqlite(db: Session) -> bool:
    bind = db.get_bind()
    return bool(bind is not None and bind.dialect.name == "sqlite")


def _assign_sqlite_id(db: Session, row: object, model: type) -> None:
    if not _is_sqlite(db) or getattr(row, "id", None) is not None:
        return
    next_id = int(db.scalar(select(func.max(model.id))) or 0) + 1
    setattr(row, "id", next_id)


def list_users(
    db: Session,
    *,
    q: str | None = None,
    onboarding_completed: bool | None = None,
    limit: int = 30,
    offset: int = 0,
) -> tuple[list[User], int]:
    statement = select(User)
    count_statement = select(func.count()).select_from(User)
    filters = []
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(or_(User.email.ilike(pattern), User.nickname.ilike(pattern)))
    if onboarding_completed is not None:
        filters.append(User.onboarding_completed == onboarding_completed)
    for condition in filters:
        statement = statement.where(condition)
        count_statement = count_statement.where(condition)
    total = int(db.scalar(count_statement) or 0)
    rows = list(
        db.scalars(
            statement.order_by(User.created_at.desc(), User.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    )
    return rows, total


def get_user(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def get_user_by_nickname(db: Session, nickname: str) -> User | None:
    return db.scalar(select(User).where(User.nickname == nickname))


def count_admin_users(db: Session) -> int:
    return int(db.scalar(select(func.count()).select_from(User).where(User.role == "admin")) or 0)


def list_external_source_records(db: Session) -> list[ExternalSourceRecord]:
    statement = select(ExternalSourceRecord).order_by(
        ExternalSourceRecord.source_category,
        ExternalSourceRecord.id,
    )
    return list(db.scalars(statement).all())


def list_external_source_policies(db: Session) -> list[Policy]:
    statement = select(Policy).where(Policy.external_source_record_id.is_not(None))
    return list(db.scalars(statement).all())


def list_policies(
    db: Session,
    *,
    q: str | None = None,
    category: str | None = None,
    region: str | None = None,
    source_type: str | None = None,
    status: str | None = None,
    limit: int = 30,
    offset: int = 0,
) -> tuple[list[Policy], int]:
    statement = select(Policy).options(selectinload(Policy.documents))
    count_statement = select(func.count()).select_from(Policy)
    filters = []
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(or_(Policy.title.ilike(pattern), Policy.organization.ilike(pattern)))
    if category:
        filters.append(Policy.policy_type == category)
    if region:
        filters.append(Policy.region == region)
    if source_type:
        filters.append(Policy.source_type == source_type)
    if status:
        filters.append(Policy.status == status)
    for condition in filters:
        statement = statement.where(condition)
        count_statement = count_statement.where(condition)
    total = int(db.scalar(count_statement) or 0)
    rows = list(
        db.scalars(
            statement.order_by(Policy.updated_at.desc(), Policy.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    )
    return rows, total


def get_policy(db: Session, policy_id: int) -> Policy | None:
    statement = (
        select(Policy)
        .options(selectinload(Policy.documents))
        .where(Policy.id == policy_id)
    )
    return db.scalar(statement)


def get_policy_by_slug(db: Session, slug: str) -> Policy | None:
    return db.scalar(select(Policy).where(Policy.slug == slug))


def add_policy(db: Session, policy: Policy) -> Policy:
    _assign_sqlite_id(db, policy, Policy)
    db.add(policy)
    db.flush()
    return policy


def replace_policy_documents(db: Session, policy: Policy, document_names: list[str]) -> None:
    documents: list[PolicyDocument] = []
    next_id = int(db.scalar(select(func.max(PolicyDocument.id))) or 0) + 1 if _is_sqlite(db) else None
    for name in document_names:
        document = PolicyDocument(document_name=name)
        if next_id is not None:
            document.id = next_id
            next_id += 1
        documents.append(document)
    policy.documents = documents
    db.add(policy)
    db.flush()


def add_audit_log(
    db: Session,
    *,
    admin_user_id: int,
    action: str,
    target_type: str,
    target_id: str,
    summary: str | None,
    before_json: dict | None,
    after_json: dict | None,
) -> AdminAuditLog:
    row = AdminAuditLog(
        admin_user_id=admin_user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        summary=summary,
        before_json=before_json,
        after_json=after_json,
    )
    _assign_sqlite_id(db, row, AdminAuditLog)
    db.add(row)
    db.flush()
    return row


def list_audit_logs(
    db: Session,
    *,
    target_type: str | None = None,
    target_id: str | None = None,
    action: str | None = None,
    limit: int = 30,
    offset: int = 0,
) -> tuple[list[AdminAuditLog], int]:
    statement = select(AdminAuditLog).options(selectinload(AdminAuditLog.admin_user))
    count_statement = select(func.count()).select_from(AdminAuditLog)
    filters = []
    if target_type:
        filters.append(AdminAuditLog.target_type == target_type)
    if target_id:
        filters.append(AdminAuditLog.target_id == target_id)
    if action:
        filters.append(AdminAuditLog.action == action)
    for condition in filters:
        statement = statement.where(condition)
        count_statement = count_statement.where(condition)
    total = int(db.scalar(count_statement) or 0)
    rows = list(
        db.scalars(
            statement.order_by(AdminAuditLog.created_at.desc(), AdminAuditLog.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    )
    return rows, total
