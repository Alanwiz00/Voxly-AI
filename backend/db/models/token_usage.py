from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from db.postgres import Base


class UserTokenUsage(Base):
    __tablename__ = "user_token_usage"
    __table_args__ = (UniqueConstraint("user_id", "year_month", name="uq_user_token_month"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    year_month: Mapped[str] = mapped_column(String(7), nullable=False)  # e.g. "2026-07"
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
