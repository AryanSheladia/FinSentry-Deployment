from datetime import datetime, timezone
from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class SparkovPayment(Base):
    __tablename__ = "sparkov_payments"
    transaction_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(48), index=True)
    event_timestamp: Mapped[int] = mapped_column(BigInteger, index=True)
    context: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SparkovInvestigation(Base):
    __tablename__ = "sparkov_investigations"
    investigation_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("sparkov_payments.transaction_id"))
    status: Mapped[str] = mapped_column(String(16), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    completed_stages: Mapped[list] = mapped_column(JSON, default=list)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(String(256), nullable=True)


class SparkovReview(Base):
    __tablename__ = "sparkov_reviews"
    review_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("sparkov_investigations.investigation_id"), index=True)
    reviewer: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(32))
    notes: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
