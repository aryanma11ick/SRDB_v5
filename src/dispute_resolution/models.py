import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
from pgvector.sqlalchemy import Vector

Base = declarative_base()


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    domain = Column(Text, nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    disputes = relationship("Dispute", back_populates="supplier")
    emails = relationship("Email", back_populates="supplier")


class Dispute(Base):
    __tablename__ = "disputes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="CASCADE"))
    status = Column(Text, default="OPEN")
    summary = Column(Text)
    summary_embedding = Column(Vector(1024))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    supplier = relationship("Supplier", back_populates="disputes")
    emails = relationship("Email", back_populates="dispute")


class Email(Base):
    __tablename__ = "emails"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dispute_id = Column(UUID(as_uuid=True), ForeignKey("disputes.id", ondelete="CASCADE"))
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="CASCADE"))
    subject = Column(Text)
    body = Column(Text)
    embedding = Column(Vector(1024))
    gmail_message_id = Column(Text, unique=True)
    received_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    dispute = relationship("Dispute", back_populates="emails")
    supplier = relationship("Supplier", back_populates="emails")


class ProcessedGmailMessage(Base):
    __tablename__ = "processed_gmail_messages"

    gmail_message_id = Column(Text, primary_key=True)
    processed_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    was_dispute = Column(Boolean, nullable=False, default=False)
