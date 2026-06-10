from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.postgres import Base


class PersonaProfile(Base):
    __tablename__ = "persona_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255), default="Default")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    niche: Mapped[str | None] = mapped_column(String(255))
    target_audience: Mapped[str | None] = mapped_column(Text)
    tone: Mapped[str | None] = mapped_column(Text)
    brand_voice: Mapped[str | None] = mapped_column(Text)
    writing_style_notes: Mapped[str | None] = mapped_column(Text)
    sample_content: Mapped[str | None] = mapped_column(Text)
    learned_style: Mapped[str | None] = mapped_column(Text)
    style_synthesized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="personas")
