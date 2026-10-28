from datetime import datetime
from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from db.postgres import Base


class ListeningCampaign(Base):
    """One X search target, e.g. "BetEye live alerts, Nigeria"."""
    __tablename__ = "listening_campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    x_query: Mapped[str] = mapped_column(Text, nullable=False)
    harm_terms: Mapped[list] = mapped_column(JSON, default=list)       # extra terms on top of the built-in list
    allowed_markets: Mapped[list] = mapped_column(JSON, default=list)  # ISO codes, e.g. ["NG"]
    link_base: Mapped[str] = mapped_column(String(512), default="")    # e.g. https://t.me/Beteyebot/BETEYE
    daily_cap: Mapped[int] = mapped_column(Integer, default=30)
    monthly_budget_usd: Mapped[float] = mapped_column(Float, default=50.0)
    max_results_per_poll: Mapped[int] = mapped_column(Integer, default=50)
    poll_every_minutes: Mapped[int] = mapped_column(Integer, default=10)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    since_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="paused")  # active | paused
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class OutreachTemplate(Base):
    """Approved reply copy. Only approved, active templates can be drafted."""
    __tablename__ = "outreach_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("listening_campaigns.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    intent: Mapped[str] = mapped_column(String(32), default="any")
    body: Mapped[str] = mapped_column(Text, nullable=False)
    arcon_cert_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ListeningCandidate(Base):
    """One found post moving through the pipeline. Text is deleted early (see purge)."""
    __tablename__ = "listening_candidates"
    __table_args__ = (UniqueConstraint("campaign_id", "x_post_id", name="uq_candidate_campaign_post"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("listening_campaigns.id", ondelete="CASCADE"))
    x_post_id: Mapped[str] = mapped_column(String(32), nullable=False)
    x_author_id: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    x_author_handle: Mapped[str | None] = mapped_column(String(64), nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    lang: Mapped[str | None] = mapped_column(String(8), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    matched_terms: Mapped[list] = mapped_column(JSON, default=list)
    stage: Mapped[str] = mapped_column(String(16), default="new")  # new | classified | drafted | sent | dropped
    drop_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verdict: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OutreachDraft(Base):
    """What the reviewer sends. Each draft has its own code for attribution."""
    __tablename__ = "outreach_drafts"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("listening_candidates.id", ondelete="CASCADE"), unique=True)
    template_id: Mapped[int | None] = mapped_column(ForeignKey("outreach_templates.id", ondelete="SET NULL"), nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    proof: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="queued")  # queued | sent | skipped
    edited: Mapped[bool] = mapped_column(Boolean, default=False)
    sent_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reply_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    reply_post_id: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OutreachEvent(Base):
    """Results: replies from X mentions, signups and payments from BetEye."""
    __tablename__ = "outreach_events"
    __table_args__ = (UniqueConstraint("code", "type", name="uq_outreach_event_code_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False)  # replied | bot_start | paid | opt_out
    source: Mapped[str] = mapped_column(String(16), nullable=False)  # x | beteye
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DoNotContact(Base):
    """Permanent, shared across campaigns."""
    __tablename__ = "do_not_contact"

    x_author_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class XApiUsage(Base):
    """Every billed X call: the spend meter and the budget guard read this."""
    __tablename__ = "x_api_usage"

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("listening_campaigns.id", ondelete="SET NULL"), nullable=True)
    endpoint: Mapped[str] = mapped_column(String(64), nullable=False)
    resources: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class ListeningState(Base):
    """Small key-value store for poll cursors, e.g. the mentions since_id."""
    __tablename__ = "listening_state"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
