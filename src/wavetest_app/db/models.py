"""
wavetest_app.db.models — Schema
==================================

Mirrors the four JSON databases the original waveImpact Console maintained:
``clients``, ``systems``, ``projects``, ``project_types``.

Stable fields are normalised; dynamic per-record details (system classification
metadata, project results) sit in JSON columns. Suitable for SQLite today and
Postgres later — JSON columns are portable.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import (
    Boolean, Date, DateTime, Float, ForeignKey, Index, JSON, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wavetest_app._time import utc_now
from wavetest_app.db.session import Base


# ---------------------------------------------------------------------------
# Project types
# ---------------------------------------------------------------------------
class ProjectType(Base):
    """A reusable bundle of standard services (e.g. 'Bias Detection & Mitigation')."""

    __tablename__ = "project_types"

    type_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    type_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    standard_services: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_date: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now,
    )
    updated_date: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now,
    )

    projects: Mapped[list["Project"]] = relationship(back_populates="project_type_ref")

    def __repr__(self) -> str:
        return f"<ProjectType {self.type_id} {self.type_name!r}>"


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------
class Client(Base):
    """A client organisation."""

    __tablename__ = "clients"

    client_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[Optional[str]] = mapped_column(String(64))
    languages: Mapped[list[str]] = mapped_column(JSON, default=list)
    folder_path: Mapped[Optional[str]] = mapped_column(Text)
    created_date: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now,
    )

    systems: Mapped[list["System"]] = relationship(
        back_populates="client", cascade="all, delete-orphan",
    )
    projects: Mapped[list["Project"]] = relationship(
        back_populates="client", cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Client {self.client_id} {self.company_name!r}>"


# ---------------------------------------------------------------------------
# Systems (AI systems classified per EU AI Act)
# ---------------------------------------------------------------------------
class System(Base):
    """A specific AI system the client has under assessment."""

    __tablename__ = "systems"

    system_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    client_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("clients.client_id"), nullable=False,
    )
    system_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    classification_date: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Full classification questionnaire data (entity_type, high_risk_categories,
    # prohibited_practices, transparency_requirements, results, …) lives here.
    classification_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    client: Mapped[Client] = relationship(back_populates="systems")

    def __repr__(self) -> str:
        return f"<System {self.system_id} {self.system_name!r}>"


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------
class Project(Base):
    """An engagement around one or more AI systems for a client."""

    __tablename__ = "projects"

    project_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    client_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("clients.client_id"), nullable=False,
    )
    project_type_id: Mapped[Optional[str]] = mapped_column(
        String(16), ForeignKey("project_types.type_id"),
    )
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    project_type: Mapped[str] = mapped_column(String(255), default="")
    project_type_description: Mapped[str] = mapped_column(Text, default="")
    standard_services: Mapped[list[str]] = mapped_column(JSON, default=list)
    description: Mapped[str] = mapped_column(Text, default="")
    start_date: Mapped[Optional[date]] = mapped_column(Date)
    folder_path: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_date: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now,
    )

    client: Mapped[Client] = relationship(back_populates="projects")
    project_type_ref: Mapped[Optional[ProjectType]] = relationship(
        back_populates="projects", foreign_keys=[project_type_id],
    )

    def __repr__(self) -> str:
        return f"<Project {self.project_id} {self.project_name!r}>"


# ---------------------------------------------------------------------------
# Audit log — one row per assessment run, survives project deletion
# ---------------------------------------------------------------------------
class AuditLog(Base):
    """One assessment-run record (who/when/what/result)."""

    __tablename__ = "audit_log"

    audit_id: Mapped[str] = mapped_column(String(16), primary_key=True)

    # FK is SET NULL on project delete so audit history outlives projects.
    # Snapshots below preserve readable client/project names for the viewer.
    project_id: Mapped[Optional[str]] = mapped_column(
        String(16),
        ForeignKey("projects.project_id", ondelete="SET NULL"),
        nullable=True,
    )
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    client_id: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    client_name: Mapped[str] = mapped_column(String(255), default="")

    # One of: data_quality, bias, explainability, logging, monitoring, combined
    module: Mapped[str] = mapped_column(String(32), nullable=False)

    run_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False,
    )

    # Module-specific short label (e.g. "GOOD", "HOCH", "85%")
    status: Mapped[str] = mapped_column(String(64), default="")
    # Normalised severity for filtering: ok | warning | critical | info
    status_color: Mapped[str] = mapped_column(String(16), default="info")
    status_detail: Mapped[str] = mapped_column(Text, default="")

    actor: Mapped[str] = mapped_column(String(64), default="system")
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float)

    __table_args__ = (
        Index("ix_audit_log_run_at", "run_at"),
        Index("ix_audit_log_project_id", "project_id"),
        Index("ix_audit_log_module", "module"),
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog {self.audit_id} {self.module} {self.status} "
            f"@ {self.run_at:%Y-%m-%d %H:%M}>"
        )
