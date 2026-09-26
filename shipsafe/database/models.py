"""SQLAlchemy models for ShipSafe AI V2 persistent storage."""

import datetime
from typing import Optional, List, Any
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime,
    ForeignKey, Text, JSON
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Repository(Base):
    __tablename__ = "repositories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True, nullable=False)
    repo_url = Column(String(1024), nullable=False)
    local_path = Column(String(1024), nullable=True)
    default_branch = Column(String(100), default="main", nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    runs = relationship("AnalysisRun", back_populates="repository", cascade="all, delete-orphan")


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True, index=True)
    delivery_id = Column(String(100), unique=True, index=True, nullable=False)
    event_type = Column(String(50), index=True, nullable=False)
    payload = Column(JSON, nullable=False)
    received_at = Column(DateTime, default=datetime.datetime.utcnow)
    processed = Column(Boolean, default=False)

    analysis_runs = relationship("AnalysisRun", back_populates="webhook_event")


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=False, index=True)
    webhook_event_id = Column(Integer, ForeignKey("webhook_events.id"), nullable=True)
    
    event_type = Column(String(50), nullable=False)  # 'push', 'pull_request', 'manual'
    branch = Column(String(100), nullable=False, default="main")
    base_sha = Column(String(100), nullable=True)
    head_sha = Column(String(100), nullable=True)

    status = Column(String(50), default="PENDING", index=True)  # PENDING, RUNNING, COMPLETED, FAILED
    release_status = Column(String(50), default="PENDING")     # READY, ATTENTION, BLOCKED, PENDING
    error_message = Column(Text, nullable=True)

    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, default=0.0)

    # Serialized summary: tests, blast radius, simulation, etc.
    summary = Column(JSON, default=dict)

    repository = relationship("Repository", back_populates="runs")
    webhook_event = relationship("WebhookEvent", back_populates="analysis_runs")
    agent_runs = relationship("AgentRun", back_populates="analysis_run", cascade="all, delete-orphan")
    findings = relationship("Finding", back_populates="analysis_run", cascade="all, delete-orphan")
    requirement_checks = relationship("RequirementCheck", back_populates="analysis_run", cascade="all, delete-orphan")
    remediations = relationship("RemediationAction", back_populates="analysis_run", cascade="all, delete-orphan")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(Integer, primary_key=True, index=True)
    analysis_run_id = Column(Integer, ForeignKey("analysis_runs.id"), nullable=False, index=True)
    agent_name = Column(String(50), nullable=False)  # impact, test_gap, security, contract, database
    status = Column(String(50), default="PENDING")  # PENDING, RUNNING, COMPLETED, FAILED
    raw_output = Column(JSON, default=dict)
    duration_seconds = Column(Float, default=0.0)

    analysis_run = relationship("AnalysisRun", back_populates="agent_runs")


class Finding(Base):
    __tablename__ = "findings"

    id = Column(Integer, primary_key=True, index=True)
    analysis_run_id = Column(Integer, ForeignKey("analysis_runs.id"), nullable=False, index=True)
    agent_name = Column(String(50), nullable=False)
    finding_id = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False)  # CRITICAL, HIGH, MEDIUM, LOW, INFO
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    file = Column(String(1024), nullable=False)
    line_start = Column(Integer, nullable=True)
    line_end = Column(Integer, nullable=True)
    evidence = Column(Text, nullable=True)
    affected_components = Column(JSON, default=list)
    recommendation = Column(Text, nullable=True)
    confidence = Column(Float, default=1.0)
    
    # Deterministic verification
    verified = Column(Boolean, default=False)
    verification_notes = Column(String(255), nullable=True)

    analysis_run = relationship("AnalysisRun", back_populates="findings")


class RequirementCheck(Base):
    __tablename__ = "requirement_checks"

    id = Column(Integer, primary_key=True, index=True)
    analysis_run_id = Column(Integer, ForeignKey("analysis_runs.id"), nullable=False, index=True)
    requirement_id = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    status = Column(String(50), default="UNVERIFIED")  # COMPLIANT, NON_COMPLIANT, UNVERIFIED
    evidence = Column(Text, nullable=True)
    related_findings = Column(JSON, default=list)

    analysis_run = relationship("AnalysisRun", back_populates="requirement_checks")


class RemediationAction(Base):
    __tablename__ = "remediation_actions"

    id = Column(Integer, primary_key=True, index=True)
    analysis_run_id = Column(Integer, ForeignKey("analysis_runs.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    target_file = Column(String(1024), nullable=False)
    patch_diff = Column(Text, nullable=False)
    status = Column(String(50), default="PROPOSED")  # PROPOSED, APPLIED, FAILED
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    applied_at = Column(DateTime, nullable=True)

    analysis_run = relationship("AnalysisRun", back_populates="remediations")
