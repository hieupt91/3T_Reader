from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, JSON, String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid_col():
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class LicenseV2(Base):
    __tablename__ = "licenses_v2"

    license_id: Mapped[uuid.UUID] = _uuid_col()
    license_key_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    key_type: Mapped[str] = mapped_column(String, nullable=False, default="3TR-E")
    desktop_seat_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    mobile_companion_per_desktop: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    mobile_companion_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    devices: Mapped[list["Device"]] = relationship(back_populates="license")


class Device(Base):
    __tablename__ = "devices"

    device_id: Mapped[uuid.UUID] = _uuid_col()
    license_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("licenses_v2.license_id"), nullable=False)
    device_type: Mapped[str] = mapped_column(String, nullable=False)  # desktop | iphone | ipad
    public_key: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String)
    parent_desktop_device_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.device_id")
    )
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    license: Mapped["LicenseV2"] = relationship(back_populates="devices")

    __table_args__ = (Index("ix_devices_license_id", "license_id"),)


class PairingSession(Base):
    __tablename__ = "pairing_sessions"

    pairing_session_id: Mapped[uuid.UUID] = _uuid_col()
    code_hash: Mapped[str] = mapped_column(String, nullable=False)
    initiator_device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devices.device_id"), nullable=False)
    intended_direction: Mapped[str] = mapped_column(String, nullable=False, default="add_companion")
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    nonce: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TransferSession(Base):
    __tablename__ = "transfer_sessions"

    transfer_session_id: Mapped[uuid.UUID] = _uuid_col()
    sender_device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devices.device_id"), nullable=False)
    receiver_device_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.device_id")
    )
    auth_mode: Mapped[str] = mapped_column(String, nullable=False)  # business_key | public_premium
    file_manifest_meta: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String, nullable=False, default="created")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AppleEntitlement(Base):
    __tablename__ = "apple_entitlements"

    entitlement_id: Mapped[uuid.UUID] = _uuid_col()
    original_transaction_id_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    product_id: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revocation_state: Mapped[str | None] = mapped_column(String)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditEvent(Base):
    __tablename__ = "audit_events"

    event_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    device_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    correlation_id: Mapped[str] = mapped_column(String, nullable=False)
    result: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
