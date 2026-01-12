"""
SQLAlchemy models for POC experiment metrics collection.

Models for tracking and comparing single-agent vs multi-agent performance:
- Experiment: Top-level experiment tracking
- TaskExecution: Individual task execution metrics
- LLMCall: LLM API call tracking
- ToolCall: Tool invocation tracking
- AgentSwitch: Agent switching events (multi-agent only)
- QualityEvaluation: Quality assessment results
- Hallucination: Detected hallucinations
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Text, Integer, Float, DateTime, Boolean, ForeignKey, Index, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.services.database import Base


class Experiment(Base):
    """
    Top-level experiment tracking.
    
    Represents a complete experiment run (single-agent or multi-agent mode).
    """
    __tablename__ = "poc_experiments"
    
    # Primary key
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Experiment UUID"
    )
    
    mode: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Experiment mode: 'single-agent' or 'multi-agent'"
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
        comment="Experiment start timestamp"
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Experiment completion timestamp"
    )
    config: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Experiment configuration (LLM model, temperature, etc.)"
    )
    
    # Relationships
    task_executions = relationship(
        "TaskExecution",
        back_populates="experiment",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    
    __table_args__ = (
        Index('idx_poc_experiments_mode_started', 'mode', 'started_at'),
    )
    
    def __repr__(self) -> str:
        return f"<Experiment(id='{self.id}', mode='{self.mode}', started_at='{self.started_at}')>"


class TaskExecution(Base):
    """
    Individual task execution tracking.
    
    Tracks execution of a single benchmark task within an experiment.
    """
    __tablename__ = "poc_task_executions"
    
    # Primary key
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Task execution UUID"
    )
    
    experiment_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("poc_experiments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to parent experiment"
    )
    task_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Task identifier from benchmark (e.g., 'task_001')"
    )
    task_category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Task category: 'simple', 'medium', 'complex', 'specialized'"
    )
    task_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Task type: 'coding', 'architecture', 'debug', 'question', 'mixed'"
    )
    mode: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Execution mode: 'single-agent' or 'multi-agent'"
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
        comment="Task start timestamp"
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Task completion timestamp"
    )
    success: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
        index=True,
        comment="Whether task completed successfully"
    )
    failure_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for failure if task failed"
    )
    metrics: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Additional metrics (duration, iterations, etc.)"
    )
    
    # Relationships
    experiment = relationship("Experiment", back_populates="task_executions")
    llm_calls = relationship(
        "LLMCall",
        back_populates="task_execution",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    tool_calls = relationship(
        "ToolCall",
        back_populates="task_execution",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    agent_switches = relationship(
        "AgentSwitch",
        back_populates="task_execution",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    quality_evaluations = relationship(
        "QualityEvaluation",
        back_populates="task_execution",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    hallucinations = relationship(
        "Hallucination",
        back_populates="task_execution",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    
    __table_args__ = (
        Index('idx_poc_task_exec_experiment_task', 'experiment_id', 'task_id'),
        Index('idx_poc_task_exec_category_type', 'task_category', 'task_type'),
        Index('idx_poc_task_exec_success', 'success'),
    )
    
    def __repr__(self) -> str:
        return (
            f"<TaskExecution(id='{self.id}', task_id='{self.task_id}', "
            f"mode='{self.mode}', success={self.success})>"
        )


class LLMCall(Base):
    """
    LLM API call tracking.
    
    Records each LLM API call for token counting and cost analysis.
    """
    __tablename__ = "poc_llm_calls"
    
    # Primary key
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="LLM call UUID"
    )
    
    task_execution_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("poc_task_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to task execution"
    )
    agent_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Agent type that made the call (e.g., 'coder', 'orchestrator')"
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="Call start timestamp"
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Call completion timestamp"
    )
    input_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of input tokens"
    )
    output_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of output tokens"
    )
    model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="LLM model used (e.g., 'gpt-4', 'claude-3')"
    )
    duration_seconds: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Call duration in seconds"
    )
    
    # Relationship
    task_execution = relationship("TaskExecution", back_populates="llm_calls")
    
    __table_args__ = (
        Index('idx_poc_llm_calls_task_agent', 'task_execution_id', 'agent_type'),
        Index('idx_poc_llm_calls_started', 'started_at'),
    )
    
    def __repr__(self) -> str:
        return (
            f"<LLMCall(id='{self.id}', agent_type='{self.agent_type}', "
            f"input_tokens={self.input_tokens}, output_tokens={self.output_tokens})>"
        )


class ToolCall(Base):
    """
    Tool invocation tracking.
    
    Records each tool call for usage analysis and success rate.
    """
    __tablename__ = "poc_tool_calls"
    
    # Primary key
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Tool call UUID"
    )
    
    task_execution_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("poc_task_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to task execution"
    )
    tool_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Name of the tool called"
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="Call start timestamp"
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Call completion timestamp"
    )
    success: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether tool call succeeded"
    )
    duration_seconds: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Call duration in seconds"
    )
    error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if call failed"
    )
    
    # Relationship
    task_execution = relationship("TaskExecution", back_populates="tool_calls")
    
    __table_args__ = (
        Index('idx_poc_tool_calls_task_tool', 'task_execution_id', 'tool_name'),
        Index('idx_poc_tool_calls_success', 'success'),
    )
    
    def __repr__(self) -> str:
        return (
            f"<ToolCall(id='{self.id}', tool_name='{self.tool_name}', "
            f"success={self.success})>"
        )


class AgentSwitch(Base):
    """
    Agent switching event tracking (multi-agent only).
    
    Records when and why agents are switched in multi-agent mode.
    """
    __tablename__ = "poc_agent_switches"
    
    # Primary key
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Agent switch UUID"
    )
    
    task_execution_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("poc_task_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to task execution"
    )
    from_agent: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Agent type before switch (NULL for initial agent)"
    )
    to_agent: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Agent type after switch"
    )
    reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for agent switch"
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
        comment="Switch timestamp"
    )
    
    # Relationship
    task_execution = relationship("TaskExecution", back_populates="agent_switches")
    
    __table_args__ = (
        Index('idx_poc_agent_switches_task_time', 'task_execution_id', 'timestamp'),
        Index('idx_poc_agent_switches_agents', 'from_agent', 'to_agent'),
    )
    
    def __repr__(self) -> str:
        return (
            f"<AgentSwitch(id='{self.id}', from_agent='{self.from_agent}', "
            f"to_agent='{self.to_agent}')>"
        )


class QualityEvaluation(Base):
    """
    Quality evaluation results.
    
    Stores automated and manual quality assessments of task results.
    """
    __tablename__ = "poc_quality_evaluations"
    
    # Primary key
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Evaluation UUID"
    )
    
    task_execution_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("poc_task_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to task execution"
    )
    evaluation_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Type of evaluation (e.g., 'syntax_check', 'test_pass', 'manual_review')"
    )
    score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Numeric score (0.0-1.0) if applicable"
    )
    passed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether evaluation passed"
    )
    details: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Detailed evaluation results"
    )
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="Evaluation timestamp"
    )
    
    # Relationship
    task_execution = relationship("TaskExecution", back_populates="quality_evaluations")
    
    __table_args__ = (
        Index('idx_poc_quality_eval_task_type', 'task_execution_id', 'evaluation_type'),
        Index('idx_poc_quality_eval_passed', 'passed'),
    )
    
    def __repr__(self) -> str:
        return (
            f"<QualityEvaluation(id='{self.id}', evaluation_type='{self.evaluation_type}', "
            f"passed={self.passed}, score={self.score})>"
        )


class Hallucination(Base):
    """
    Detected hallucination tracking.
    
    Records instances where the LLM hallucinates (non-existent APIs, files, etc.).
    """
    __tablename__ = "poc_hallucinations"
    
    # Primary key
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Hallucination UUID"
    )
    
    task_execution_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("poc_task_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to task execution"
    )
    hallucination_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Type of hallucination (e.g., 'import', 'api', 'file', 'parameter')"
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Description of the hallucination"
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
        comment="Detection timestamp"
    )
    
    # Relationship
    task_execution = relationship("TaskExecution", back_populates="hallucinations")
    
    __table_args__ = (
        Index('idx_poc_hallucinations_task_type', 'task_execution_id', 'hallucination_type'),
    )
    
    def __repr__(self) -> str:
        return (
            f"<Hallucination(id='{self.id}', hallucination_type='{self.hallucination_type}', "
            f"description='{self.description[:50]}...')>"
        )
