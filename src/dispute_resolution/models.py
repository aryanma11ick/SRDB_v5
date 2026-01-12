import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    Float,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector


# =================================================
# Base
# =================================================

class Base(DeclarativeBase):
    pass


# =================================================
# Supplier
# =================================================

class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    domain: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        unique=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    disputes: Mapped[List["Dispute"]] = relationship(
        back_populates="supplier",
    )

    emails: Mapped[List["Email"]] = relationship(
        back_populates="supplier",
    )


# =================================================
# Dispute
# =================================================

class Dispute(Base):
    __tablename__ = "disputes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        Text,
        default="OPEN",
        nullable=False,
    )

    summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    summary_embedding: Mapped[Optional[list[float]]] = mapped_column(
        Vector(1024),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    supplier: Mapped["Supplier"] = relationship(
        back_populates="disputes",
    )

    emails: Mapped[List["Email"]] = relationship(
        back_populates="dispute",
    )


# =================================================
# Email
# =================================================

class Email(Base):
    __tablename__ = "emails"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    dispute_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("disputes.id", ondelete="CASCADE"),
        nullable=True,
    )

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
    )

    subject: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    embedding: Mapped[Optional[list[float]]] = mapped_column(
        Vector(1024),
        nullable=True,
    )

    gmail_message_id: Mapped[str] = mapped_column(
        Text,
        unique=True,
        nullable=False,
    )

    thread_id: Mapped[Optional[str]] = mapped_column(
        Text,
        index=True,
        nullable=True,
    )

    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # -----------------------------
    # Intent classification
    # -----------------------------

    intent_status: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    intent_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    intent_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # -----------------------------
    # Clarification
    # -----------------------------

    clarification_sent: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    clarification_sent_at: Mapped[Optional[datetime]] = mapped_column(
    DateTime(timezone=True),
    nullable=True,
)

    # -----------------------------
    # Fact extraction (NEW)
    # -----------------------------

    extracted_facts: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )

    fact_confidence: Mapped[Optional[Dict[str, float]]] = mapped_column(
        JSONB,
        nullable=True,
    )

    missing_fields: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(Text),
        nullable=True,
    )

    # -----------------------------
    # Relationships
    # -----------------------------

    dispute: Mapped[Optional["Dispute"]] = relationship(
        back_populates="emails",
    )

    supplier: Mapped["Supplier"] = relationship(
        back_populates="emails",
    )


# =================================================
# Processed Gmail Messages
# =================================================

class ProcessedGmailMessage(Base):
    __tablename__ = "processed_gmail_messages"

    gmail_message_id: Mapped[str] = mapped_column(
        Text,
        primary_key=True,
    )

    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    was_dispute: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

