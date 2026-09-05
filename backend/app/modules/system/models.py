from __future__ import annotations

from sqlalchemy import BigInteger, CheckConstraint, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin


class SystemCleanupAudit(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "system_cleanup_audit"
    __table_args__ = (
        CheckConstraint(
            "status IN ('SUCCEEDED','FAILED','NO_CHANGES')", name="status_valid"
        ),
        CheckConstraint("deleted_files >= 0", name="deleted_files_nonnegative"),
        CheckConstraint("deleted_bytes >= 0", name="deleted_bytes_nonnegative"),
    )

    category: Mapped[str] = mapped_column(String(32), nullable=False)
    older_than_days: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    deleted_files: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deleted_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    candidate_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)


__all__ = ["SystemCleanupAudit"]
