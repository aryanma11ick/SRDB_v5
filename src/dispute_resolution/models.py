import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Text, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector


class Base(DeclarativeBase):
    pass


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc)  # ✅ Fixed
    )

    disputes: Mapped[List["Dispute"]] = relationship(back_populates="supplier")
    emails: Mapped[List["Email"]] = relationship(back_populates="supplier")


class Dispute(Base):
    __tablename__ = "disputes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="CASCADE"),
    )
    status: Mapped[str] = mapped_column(Text, default="OPEN")
    summary: Mapped[Optional[str]] = mapped_column(Text)
    summary_embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(1024))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc)\
    )

    supplier: Mapped["Supplier"] = relationship(back_populates="disputes")
    emails: Mapped[List["Email"]] = relationship(back_populates="dispute")


from typing import Optional

class Email(Base):
    __tablename__ = "emails"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dispute_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("disputes.id", ondelete="CASCADE"),
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="CASCADE"),
    )

    subject: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(1024))
    gmail_message_id: Mapped[str] = mapped_column(Text, unique=True)
    thread_id : Mapped[Optional[str]] = mapped_column(Text, index=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )

    intent_status: Mapped[Optional[str]] = mapped_column(Text)
    intent_reason: Mapped[Optional[str]] = mapped_column(Text)
    intent_confidence: Mapped[Optional[float]] = mapped_column(Float)

    clarification_sent: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    dispute: Mapped[Optional["Dispute"]] = relationship(back_populates="emails")
    supplier: Mapped["Supplier"] = relationship(back_populates="emails")
    

class ProcessedGmailMessage(Base):
    __tablename__ = "processed_gmail_messages"

    gmail_message_id: Mapped[str] = mapped_column(Text, primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )
    was_dispute: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
