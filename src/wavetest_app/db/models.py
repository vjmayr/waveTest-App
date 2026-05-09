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


# ---------------------------------------------------------------------------
# Risk register — Art. 9 risk management system
# ---------------------------------------------------------------------------
class RiskEntry(Base):
    """One risk recorded against a project for Art. 9 risk management."""

    __tablename__ = "risk_register"

    risk_id: Mapped[str] = mapped_column(String(16), primary_key=True)

    # Cascade-delete with the project — the risk register is per-engagement
    project_id: Mapped[str] = mapped_column(
        String(16),
        ForeignKey("projects.project_id", ondelete="CASCADE"),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")

    # data_quality / bias / security / oversight / performance / governance / other
    category: Mapped[str] = mapped_column(String(32), default="other")

    # Pre-mitigation severity × likelihood
    severity: Mapped[str] = mapped_column(String(16), default="MEDIUM")
    likelihood: Mapped[str] = mapped_column(String(16), default="POSSIBLE")
    risk_level: Mapped[str] = mapped_column(String(16), default="MEDIUM")

    mitigation: Mapped[str] = mapped_column(Text, default="")
    # proposed / in_progress / implemented / verified
    mitigation_status: Mapped[str] = mapped_column(String(16), default="proposed")

    # Post-mitigation (residual) — what's left after the mitigation works
    residual_severity: Mapped[Optional[str]] = mapped_column(String(16))
    residual_likelihood: Mapped[Optional[str]] = mapped_column(String(16))
    residual_level: Mapped[Optional[str]] = mapped_column(String(16))

    owner: Mapped[str] = mapped_column(String(128), default="")
    next_review_date: Mapped[Optional[date]] = mapped_column(Date)

    created_by: Mapped[str] = mapped_column(String(64), default="system")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False,
    )

    notes: Mapped[str] = mapped_column(Text, default="")

    project: Mapped[Project] = relationship()

    __table_args__ = (
        Index("ix_risk_register_project_id", "project_id"),
        Index("ix_risk_register_risk_level", "risk_level"),
    )

    def __repr__(self) -> str:
        return (
            f"<RiskEntry {self.risk_id} {self.project_id} "
            f"{self.title!r} [{self.risk_level}]>"
        )


# ---------------------------------------------------------------------------
# Human-oversight plan — Art. 14
# ---------------------------------------------------------------------------
class OversightPlan(Base):
    """One oversight plan per project: Art. 14.4 (a)–(e) checklist + notes.

    Each yes / partial / no answer maps to a 0–3 score; the sum drives
    ``compliance_percent``. A unique constraint on ``project_id`` enforces
    "one plan per engagement" — analysts edit the existing plan rather
    than creating new ones.
    """

    __tablename__ = "oversight_plans"

    plan_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(16),
        ForeignKey("projects.project_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    # Free-text profile of who oversees the system + how
    operator_profile: Mapped[str] = mapped_column(Text, default="")

    # Six yes/partial/no checkpoints. Stored as strings so the UI can keep
    # the human-readable labels and the migration story stays simple.
    has_documentation: Mapped[str] = mapped_column(String(8), default="no")
    automation_bias_training: Mapped[str] = mapped_column(String(8), default="no")
    outputs_include_uncertainty: Mapped[str] = mapped_column(String(8), default="no")
    override_mechanism: Mapped[str] = mapped_column(String(8), default="no")
    override_logged: Mapped[str] = mapped_column(String(8), default="no")
    stop_mechanism: Mapped[str] = mapped_column(String(8), default="no")

    gaps: Mapped[str] = mapped_column(Text, default="")
    mitigation_plan: Mapped[str] = mapped_column(Text, default="")
    next_review_date: Mapped[Optional[date]] = mapped_column(Date)

    compliance_percent: Mapped[float] = mapped_column(Float, default=0.0)

    created_by: Mapped[str] = mapped_column(String(64), default="system")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False,
    )

    project: Mapped[Project] = relationship()

    def __repr__(self) -> str:
        return (
            f"<OversightPlan {self.plan_id} {self.project_id} "
            f"{self.compliance_percent:.0f}%>"
        )


# ---------------------------------------------------------------------------
# Cybersecurity plan — Art. 15(5) cybersecurity slice
# ---------------------------------------------------------------------------
class CybersecurityPlan(Base):
    """Cybersecurity questionnaire + plan per project — Art. 15(5).

    Article 15(5) requires high-risk AI systems to be resilient against
    attacks that try to alter use, outputs, or performance. This is the
    v0 questionnaire — eight yes / partial / no checkpoints covering
    classical infosec hygiene plus AI-specific attack vectors. A future
    iteration can wrap ART (Adversarial Robustness Toolbox) for active
    testing.
    """

    __tablename__ = "cybersecurity_plans"

    plan_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(16),
        ForeignKey("projects.project_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    # Eight yes/partial/no checkpoints
    threat_model_documented: Mapped[str] = mapped_column(String(8), default="no")
    sbom_maintained: Mapped[str] = mapped_column(String(8), default="no")
    pentest_performed: Mapped[str] = mapped_column(String(8), default="no")
    data_poisoning_controls: Mapped[str] = mapped_column(String(8), default="no")
    adversarial_input_controls: Mapped[str] = mapped_column(String(8), default="no")
    privacy_attack_controls: Mapped[str] = mapped_column(String(8), default="no")
    access_controls_documented: Mapped[str] = mapped_column(String(8), default="no")
    incident_response_playbook: Mapped[str] = mapped_column(String(8), default="no")

    pentest_last_date: Mapped[Optional[date]] = mapped_column(Date)
    threat_model_notes: Mapped[str] = mapped_column(Text, default="")
    open_findings: Mapped[str] = mapped_column(Text, default="")
    mitigation_plan: Mapped[str] = mapped_column(Text, default="")
    next_review_date: Mapped[Optional[date]] = mapped_column(Date)

    compliance_percent: Mapped[float] = mapped_column(Float, default=0.0)

    created_by: Mapped[str] = mapped_column(String(64), default="system")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False,
    )

    project: Mapped[Project] = relationship()

    def __repr__(self) -> str:
        return (
            f"<CybersecurityPlan {self.plan_id} {self.project_id} "
            f"{self.compliance_percent:.0f}%>"
        )


# ---------------------------------------------------------------------------
# Sustainability record — voluntary, CSRD-friendly
# ---------------------------------------------------------------------------
class SustainabilityRecord(Base):
    """Per-project carbon footprint estimate. Voluntary, not Art-mandated.

    Stores inputs (training compute, inference energy, deployment region,
    monthly volume) plus an editable region carbon-intensity factor. The
    derived totals (training kg, annual kg) are computed on render —
    cheap and avoids stale-cache risks.
    """

    __tablename__ = "sustainability_records"

    record_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(16),
        ForeignKey("projects.project_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    # --- Training-time inputs
    training_compute_kwh: Mapped[Optional[float]] = mapped_column(Float)
    # If the client has measured the training carbon directly (CodeCarbon /
    # eco2AI / etc.), they can set the override and skip the kWh × intensity
    # calculation.
    training_carbon_override_kg: Mapped[Optional[float]] = mapped_column(Float)

    # --- Inference-time inputs
    inference_kwh_per_1k_predictions: Mapped[Optional[float]] = mapped_column(Float)
    monthly_predictions: Mapped[Optional[int]] = mapped_column()

    # --- Region + intensity (gCO2eq / kWh)
    deployment_region: Mapped[str] = mapped_column(String(64), default="EU-Average")
    carbon_intensity_g_per_kwh: Mapped[float] = mapped_column(Float, default=250.0)

    assumptions: Mapped[str] = mapped_column(Text, default="")
    data_source: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")

    created_by: Mapped[str] = mapped_column(String(64), default="system")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False,
    )

    project: Mapped[Project] = relationship()

    def __repr__(self) -> str:
        return (
            f"<SustainabilityRecord {self.record_id} {self.project_id} "
            f"{self.deployment_region!r}>"
        )


# ---------------------------------------------------------------------------
# Incident report — Art. 73 serious-incident reporting
# ---------------------------------------------------------------------------
class IncidentReport(Base):
    """One incident reported under Art. 73.

    FK is SET NULL on project delete (incidents outlive engagements);
    project / client name are snapshotted so the report stays readable.
    """

    __tablename__ = "incident_reports"

    incident_id: Mapped[str] = mapped_column(String(16), primary_key=True)

    project_id: Mapped[Optional[str]] = mapped_column(
        String(16),
        ForeignKey("projects.project_id", ondelete="SET NULL"),
        nullable=True,
    )
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    client_name: Mapped[str] = mapped_column(String(255), default="")

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")

    # death_or_serious_health / fundamental_rights / property_damage / near_miss
    severity: Mapped[str] = mapped_column(String(32), default="near_miss")
    affected_persons: Mapped[int] = mapped_column(default=0)

    date_occurred: Mapped[Optional[date]] = mapped_column(Date)
    date_detected: Mapped[Optional[date]] = mapped_column(Date)
    date_reported: Mapped[Optional[date]] = mapped_column(Date)

    root_cause: Mapped[str] = mapped_column(Text, default="")
    corrective_action: Mapped[str] = mapped_column(Text, default="")

    # open / investigating / corrective_actions / closed
    status: Mapped[str] = mapped_column(String(32), default="open")

    authority_notified: Mapped[bool] = mapped_column(Boolean, default=False)
    authority_name: Mapped[str] = mapped_column(String(255), default="")
    authority_reference: Mapped[str] = mapped_column(String(128), default="")

    created_by: Mapped[str] = mapped_column(String(64), default="system")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False,
    )

    notes: Mapped[str] = mapped_column(Text, default="")

    project: Mapped[Optional[Project]] = relationship()

    __table_args__ = (
        Index("ix_incident_reports_project_id", "project_id"),
        Index("ix_incident_reports_status", "status"),
        Index("ix_incident_reports_severity", "severity"),
    )

    def __repr__(self) -> str:
        return (
            f"<IncidentReport {self.incident_id} "
            f"[{self.severity}] {self.status}>"
        )


# ---------------------------------------------------------------------------
# Individual-explanation request — Art. 86
# ---------------------------------------------------------------------------
class ExplanationRequest(Base):
    """One Art. 86 right-to-explanation request from an affected person.

    Deployers must provide clear and meaningful explanations of the role
    of the AI system + the main elements of the decision when an affected
    natural person asks. The deliverable is a *letter*, not a notified-
    body packet.
    """

    __tablename__ = "explanation_requests"

    request_id: Mapped[str] = mapped_column(String(16), primary_key=True)

    project_id: Mapped[Optional[str]] = mapped_column(
        String(16),
        ForeignKey("projects.project_id", ondelete="SET NULL"),
        nullable=True,
    )
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    client_name: Mapped[str] = mapped_column(String(255), default="")

    # Opaque case reference / customer ID — never store the natural person's
    # identity directly here (GDPR data-minimisation).
    subject_reference: Mapped[str] = mapped_column(String(128), default="")

    decision_date: Mapped[Optional[date]] = mapped_column(Date)
    decision_outcome: Mapped[str] = mapped_column(Text, default="")

    request_received_date: Mapped[Optional[date]] = mapped_column(Date)
    response_due_date: Mapped[Optional[date]] = mapped_column(Date)
    response_sent_date: Mapped[Optional[date]] = mapped_column(Date)

    factors_text: Mapped[str] = mapped_column(Text, default="")
    alternative_paths: Mapped[str] = mapped_column(Text, default="")
    human_review_offered: Mapped[bool] = mapped_column(Boolean, default=False)

    # open / in_progress / sent / closed
    status: Mapped[str] = mapped_column(String(32), default="open")

    created_by: Mapped[str] = mapped_column(String(64), default="system")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False,
    )

    notes: Mapped[str] = mapped_column(Text, default="")

    project: Mapped[Optional[Project]] = relationship()

    __table_args__ = (
        Index("ix_explanation_requests_project_id", "project_id"),
        Index("ix_explanation_requests_status", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<ExplanationRequest {self.request_id} "
            f"{self.subject_reference!r} {self.status}>"
        )
