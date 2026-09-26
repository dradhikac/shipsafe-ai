"""Pydantic schemas enforcing the Agent Output Contract."""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class AgentFinding(BaseModel):
    finding_id: str = Field(..., description="Unique finding identifier, e.g. SEC-001, IMP-001")
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"] = Field(
        ..., description="Finding severity rating"
    )
    title: str = Field(..., description="Brief summary title of the finding")
    description: str = Field(..., description="Detailed technical explanation of the issue")
    file: str = Field(..., description="Relative repository file path")
    line_start: Optional[int] = Field(None, description="Starting line number (1-indexed)")
    line_end: Optional[int] = Field(None, description="Ending line number (1-indexed)")
    evidence: str = Field("", description="Exact code snippet or test trace ground truth")
    affected_components: List[str] = Field(default_factory=list, description="Downstream services or routes affected")
    recommendation: str = Field("", description="Actionable remediation guidance")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0")


class AgentReport(BaseModel):
    agent: str = Field(..., description="Name of the specialist agent, e.g. impact, test_gap, security")
    findings: List[AgentFinding] = Field(default_factory=list, description="List of structured findings")
