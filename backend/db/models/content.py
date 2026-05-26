from datetime import datetime
from typing import Any
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, SmallInteger, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.postgres import Base


class GeneratedContent(Base):
    __tablename__ = "generated_content"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"))
    platform: Mapped[str] = mapped_column(String(50))  # twitter, instagram, facebook, telegram
    content_type: Mapped[str] = mapped_column(String(50))  # idea, long_form, thread, article
    title: Mapped[str | None] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON)  # hashtags, thread_count, etc.
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("generated_content.id", ondelete="SET NULL"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    rating: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="contents")
    versions: Mapped[list["ContentVersion"]] = relationship(back_populates="content_item", cascade="all, delete-orphan")
    parent: Mapped["GeneratedContent | None"] = relationship(remote_side="GeneratedContent.id")


class ContentVersion(Base):
    __tablename__ = "content_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    content_id: Mapped[int] = mapped_column(ForeignKey("generated_content.id", ondelete="CASCADE"))
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    edit_instruction: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    content_item: Mapped["GeneratedContent"] = relationship(back_populates="versions")


