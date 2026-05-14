from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.postgres import Base


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    keywords: Mapped[str | None] = mapped_column(Text)  # comma-separated
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_crawled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="topics")
    crawl_results: Mapped[list["CrawlResult"]] = relationship(back_populates="topic", cascade="all, delete-orphan")


class CrawlResult(Base):
    __tablename__ = "crawl_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"))
    url: Mapped[str] = mapped_column(Text)
    content_summary: Mapped[str | None] = mapped_column(Text)
    sentiment_score: Mapped[float | None] = mapped_column()
    sentiment_label: Mapped[str | None] = mapped_column(String(20))  # positive/negative/neutral
    crawled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    topic: Mapped["Topic"] = relationship(back_populates="crawl_results")


