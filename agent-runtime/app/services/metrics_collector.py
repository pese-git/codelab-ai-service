"""
Metrics Collector - собирает метрики для сравнения single-agent vs multi-agent.

Этот сервис отвечает за сбор и хранение метрик POC эксперимента:
- Создание и завершение экспериментов
- Отслеживание выполнения задач
- Запись LLM вызовов
- Запись вызовов инструментов
- Отслеживание переключений агентов
- Оценка качества
- Обнаружение галлюцинаций
"""
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.metrics import (
    Experiment, TaskExecution, LLMCall,
    ToolCall, AgentSwitch, QualityEvaluation, Hallucination
)

logger = logging.getLogger("agent-runtime.metrics_collector")


class MetricsCollector:
    """
    Collects and stores experiment metrics for POC comparison.
    
    Usage:
        collector = MetricsCollector(db_session)
        
        # Start experiment
        exp_id = await collector.start_experiment(mode="multi-agent")
        
        # Start task
        task_id = await collector.start_task(
            experiment_id=exp_id,
            task_id="task_001",
            task_category="simple",
            task_type="coding",
            mode="multi-agent"
        )
        
        # Record metrics during execution
        await collector.record_llm_call(...)
        await collector.record_tool_call(...)
        
        # Complete task
        await collector.complete_task(task_id, success=True)
        
        # Complete experiment
        await collector.complete_experiment(exp_id)
    """
    
    def __init__(self, db_session: AsyncSession):
        """
        Initialize metrics collector.
        
        Args:
            db_session: Async database session
        """
        self.db = db_session
        self.current_experiment: Optional[Experiment] = None
        self.current_task: Optional[TaskExecution] = None
        logger.info("MetricsCollector initialized")
    
    async def start_experiment(
        self,
        mode: str,
        config: Optional[Dict[str, Any]] = None
    ) -> UUID:
        """
        Start new experiment.
        
        Args:
            mode: Experiment mode ('single-agent' or 'multi-agent')
            config: Optional experiment configuration (LLM model, temperature, etc.)
            
        Returns:
            Experiment UUID
            
        Raises:
            ValueError: If mode is invalid
        """
        if mode not in ("single-agent", "multi-agent"):
            raise ValueError(f"Invalid mode: {mode}. Must be 'single-agent' or 'multi-agent'")
        
        experiment = Experiment(
            mode=mode,
            started_at=datetime.now(timezone.utc),
            config=config or {}
        )
        
        self.db.add(experiment)
        await self.db.commit()
        await self.db.refresh(experiment)
        
        self.current_experiment = experiment
        
        logger.info(
            f"Started experiment: id={experiment.id}, mode={mode}, "
            f"config={config}"
        )
        
        return UUID(experiment.id)
    
    async def complete_experiment(self, experiment_id: UUID) -> None:
        """
        Mark experiment as completed.
        
        Args:
            experiment_id: Experiment UUID
            
        Raises:
            ValueError: If experiment not found
        """
        result = await self.db.execute(
            select(Experiment).where(Experiment.id == str(experiment_id))
        )
        experiment = result.scalar_one_or_none()
        
        if not experiment:
            raise ValueError(f"Experiment not found: {experiment_id}")
        
        experiment.completed_at = datetime.now(timezone.utc)
        await self.db.commit()
        
        logger.info(f"Completed experiment: id={experiment_id}")
        
        # Clear current experiment if it matches
        if self.current_experiment and self.current_experiment.id == str(experiment_id):
            self.current_experiment = None
    
    async def start_task(
        self,
        experiment_id: UUID,
        task_id: str,
        task_category: str,
        task_type: str,
        mode: str
    ) -> UUID:
        """
        Start task execution.
        
        Args:
            experiment_id: Parent experiment UUID
            task_id: Task identifier from benchmark (e.g., 'task_001')
            task_category: Task category ('simple', 'medium', 'complex', 'specialized')
            task_type: Task type ('coding', 'architecture', 'debug', 'question', 'mixed')
            mode: Execution mode ('single-agent' or 'multi-agent')
            
        Returns:
            Task execution UUID
            
        Raises:
            ValueError: If experiment not found or parameters invalid
        """
        # Validate experiment exists
        result = await self.db.execute(
            select(Experiment).where(Experiment.id == str(experiment_id))
        )
        experiment = result.scalar_one_or_none()
        
        if not experiment:
            raise ValueError(f"Experiment not found: {experiment_id}")
        
        # Validate parameters
        valid_categories = ("simple", "medium", "complex", "specialized")
        if task_category not in valid_categories:
            raise ValueError(
                f"Invalid task_category: {task_category}. "
                f"Must be one of {valid_categories}"
            )
        
        valid_types = ("coding", "architecture", "debug", "question", "mixed")
        if task_type not in valid_types:
            raise ValueError(
                f"Invalid task_type: {task_type}. "
                f"Must be one of {valid_types}"
            )
        
        if mode not in ("single-agent", "multi-agent"):
            raise ValueError(
                f"Invalid mode: {mode}. Must be 'single-agent' or 'multi-agent'"
            )
        
        task_execution = TaskExecution(
            experiment_id=str(experiment_id),
            task_id=task_id,
            task_category=task_category,
            task_type=task_type,
            mode=mode,
            started_at=datetime.now(timezone.utc)
        )
        
        self.db.add(task_execution)
        await self.db.commit()
        await self.db.refresh(task_execution)
        
        self.current_task = task_execution
        
        logger.info(
            f"Started task: id={task_execution.id}, task_id={task_id}, "
            f"category={task_category}, type={task_type}, mode={mode}"
        )
        
        return UUID(task_execution.id)
    
    async def complete_task(
        self,
        task_execution_id: UUID,
        success: bool,
        failure_reason: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Complete task execution.
        
        Args:
            task_execution_id: Task execution UUID
            success: Whether task completed successfully
            failure_reason: Optional reason for failure
            metrics: Optional additional metrics (duration, iterations, etc.)
            
        Raises:
            ValueError: If task execution not found
        """
        result = await self.db.execute(
            select(TaskExecution).where(TaskExecution.id == str(task_execution_id))
        )
        task_execution = result.scalar_one_or_none()
        
        if not task_execution:
            raise ValueError(f"Task execution not found: {task_execution_id}")
        
        task_execution.completed_at = datetime.now(timezone.utc)
        task_execution.success = success
        task_execution.failure_reason = failure_reason
        task_execution.metrics = metrics or {}
        
        # Calculate duration if not in metrics
        if task_execution.started_at and task_execution.completed_at:
            # Ensure both datetimes are timezone-aware
            started = task_execution.started_at
            completed = task_execution.completed_at
            
            # Convert to UTC if needed
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            if completed.tzinfo is None:
                completed = completed.replace(tzinfo=timezone.utc)
            
            duration = (completed - started).total_seconds()
            if "duration_seconds" not in task_execution.metrics:
                task_execution.metrics["duration_seconds"] = duration
        
        await self.db.commit()
        
        logger.info(
            f"Completed task: id={task_execution_id}, success={success}, "
            f"duration={task_execution.metrics.get('duration_seconds', 0):.2f}s"
        )
        
        # Clear current task if it matches
        if self.current_task and self.current_task.id == str(task_execution_id):
            self.current_task = None
    
    async def record_llm_call(
        self,
        task_execution_id: UUID,
        agent_type: str,
        input_tokens: int,
        output_tokens: int,
        model: str,
        duration_seconds: float
    ) -> UUID:
        """
        Record LLM API call.
        
        Args:
            task_execution_id: Task execution UUID
            agent_type: Agent type that made the call (e.g., 'coder', 'orchestrator')
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model: LLM model used (e.g., 'gpt-4', 'claude-3')
            duration_seconds: Call duration in seconds
            
        Returns:
            LLM call UUID
            
        Raises:
            ValueError: If task execution not found
        """
        # Validate task execution exists
        result = await self.db.execute(
            select(TaskExecution).where(TaskExecution.id == str(task_execution_id))
        )
        task_execution = result.scalar_one_or_none()
        
        if not task_execution:
            raise ValueError(f"Task execution not found: {task_execution_id}")
        
        llm_call = LLMCall(
            task_execution_id=str(task_execution_id),
            agent_type=agent_type,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=model,
            duration_seconds=duration_seconds
        )
        
        self.db.add(llm_call)
        await self.db.commit()
        await self.db.refresh(llm_call)
        
        logger.debug(
            f"Recorded LLM call: task={task_execution_id}, agent={agent_type}, "
            f"input_tokens={input_tokens}, output_tokens={output_tokens}, "
            f"model={model}, duration={duration_seconds:.2f}s"
        )
        
        return UUID(llm_call.id)
    
    async def record_tool_call(
        self,
        task_execution_id: UUID,
        tool_name: str,
        success: bool,
        duration_seconds: float,
        error: Optional[str] = None
    ) -> UUID:
        """
        Record tool invocation.
        
        Args:
            task_execution_id: Task execution UUID
            tool_name: Name of the tool called
            success: Whether tool call succeeded
            duration_seconds: Call duration in seconds
            error: Optional error message if call failed
            
        Returns:
            Tool call UUID
            
        Raises:
            ValueError: If task execution not found
        """
        # Validate task execution exists
        result = await self.db.execute(
            select(TaskExecution).where(TaskExecution.id == str(task_execution_id))
        )
        task_execution = result.scalar_one_or_none()
        
        if not task_execution:
            raise ValueError(f"Task execution not found: {task_execution_id}")
        
        tool_call = ToolCall(
            task_execution_id=str(task_execution_id),
            tool_name=tool_name,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            success=success,
            duration_seconds=duration_seconds,
            error=error
        )
        
        self.db.add(tool_call)
        await self.db.commit()
        await self.db.refresh(tool_call)
        
        logger.debug(
            f"Recorded tool call: task={task_execution_id}, tool={tool_name}, "
            f"success={success}, duration={duration_seconds:.2f}s"
        )
        
        return UUID(tool_call.id)
    
    async def record_agent_switch(
        self,
        task_execution_id: UUID,
        from_agent: Optional[str],
        to_agent: str,
        reason: str
    ) -> UUID:
        """
        Record agent switch (multi-agent only).
        
        Args:
            task_execution_id: Task execution UUID
            from_agent: Agent type before switch (None for initial agent)
            to_agent: Agent type after switch
            reason: Reason for agent switch
            
        Returns:
            Agent switch UUID
            
        Raises:
            ValueError: If task execution not found
        """
        # Validate task execution exists
        result = await self.db.execute(
            select(TaskExecution).where(TaskExecution.id == str(task_execution_id))
        )
        task_execution = result.scalar_one_or_none()
        
        if not task_execution:
            raise ValueError(f"Task execution not found: {task_execution_id}")
        
        agent_switch = AgentSwitch(
            task_execution_id=str(task_execution_id),
            from_agent=from_agent,
            to_agent=to_agent,
            reason=reason,
            timestamp=datetime.now(timezone.utc)
        )
        
        self.db.add(agent_switch)
        await self.db.commit()
        await self.db.refresh(agent_switch)
        
        logger.info(
            f"Recorded agent switch: task={task_execution_id}, "
            f"from={from_agent}, to={to_agent}, reason={reason}"
        )
        
        return UUID(agent_switch.id)
    
    async def record_quality_evaluation(
        self,
        task_execution_id: UUID,
        evaluation_type: str,
        score: Optional[float],
        passed: bool,
        details: Optional[Dict[str, Any]] = None
    ) -> UUID:
        """
        Record quality evaluation.
        
        Args:
            task_execution_id: Task execution UUID
            evaluation_type: Type of evaluation (e.g., 'syntax_check', 'test_pass')
            score: Optional numeric score (0.0-1.0)
            passed: Whether evaluation passed
            details: Optional detailed evaluation results
            
        Returns:
            Quality evaluation UUID
            
        Raises:
            ValueError: If task execution not found or score out of range
        """
        # Validate task execution exists
        result = await self.db.execute(
            select(TaskExecution).where(TaskExecution.id == str(task_execution_id))
        )
        task_execution = result.scalar_one_or_none()
        
        if not task_execution:
            raise ValueError(f"Task execution not found: {task_execution_id}")
        
        # Validate score range
        if score is not None and not (0.0 <= score <= 1.0):
            raise ValueError(f"Score must be between 0.0 and 1.0, got: {score}")
        
        quality_evaluation = QualityEvaluation(
            task_execution_id=str(task_execution_id),
            evaluation_type=evaluation_type,
            score=score,
            passed=passed,
            details=details or {},
            evaluated_at=datetime.now(timezone.utc)
        )
        
        self.db.add(quality_evaluation)
        await self.db.commit()
        await self.db.refresh(quality_evaluation)
        
        logger.info(
            f"Recorded quality evaluation: task={task_execution_id}, "
            f"type={evaluation_type}, passed={passed}, score={score}"
        )
        
        return UUID(quality_evaluation.id)
    
    async def record_hallucination(
        self,
        task_execution_id: UUID,
        hallucination_type: str,
        description: str
    ) -> UUID:
        """
        Record detected hallucination.
        
        Args:
            task_execution_id: Task execution UUID
            hallucination_type: Type of hallucination (e.g., 'import', 'api', 'file')
            description: Description of the hallucination
            
        Returns:
            Hallucination UUID
            
        Raises:
            ValueError: If task execution not found
        """
        # Validate task execution exists
        result = await self.db.execute(
            select(TaskExecution).where(TaskExecution.id == str(task_execution_id))
        )
        task_execution = result.scalar_one_or_none()
        
        if not task_execution:
            raise ValueError(f"Task execution not found: {task_execution_id}")
        
        hallucination = Hallucination(
            task_execution_id=str(task_execution_id),
            hallucination_type=hallucination_type,
            description=description,
            detected_at=datetime.now(timezone.utc)
        )
        
        self.db.add(hallucination)
        await self.db.commit()
        await self.db.refresh(hallucination)
        
        logger.warning(
            f"Recorded hallucination: task={task_execution_id}, "
            f"type={hallucination_type}, description={description[:100]}"
        )
        
        return UUID(hallucination.id)
    
    async def get_experiment_summary(self, experiment_id: UUID) -> Dict[str, Any]:
        """
        Get summary statistics for an experiment.
        
        Args:
            experiment_id: Experiment UUID
            
        Returns:
            Dictionary with experiment summary statistics
            
        Raises:
            ValueError: If experiment not found
        """
        result = await self.db.execute(
            select(Experiment).where(Experiment.id == str(experiment_id))
        )
        experiment = result.scalar_one_or_none()
        
        if not experiment:
            raise ValueError(f"Experiment not found: {experiment_id}")
        
        # Get task executions
        result = await self.db.execute(
            select(TaskExecution).where(
                TaskExecution.experiment_id == str(experiment_id)
            )
        )
        tasks = result.scalars().all()
        
        total_tasks = len(tasks)
        successful_tasks = sum(1 for t in tasks if t.success is True)
        failed_tasks = sum(1 for t in tasks if t.success is False)
        pending_tasks = sum(1 for t in tasks if t.success is None)
        
        # Calculate total tokens and cost (example pricing)
        total_input_tokens = 0
        total_output_tokens = 0
        
        for task in tasks:
            result = await self.db.execute(
                select(LLMCall).where(LLMCall.task_execution_id == task.id)
            )
            llm_calls = result.scalars().all()
            total_input_tokens += sum(call.input_tokens for call in llm_calls)
            total_output_tokens += sum(call.output_tokens for call in llm_calls)
        
        # Example pricing (adjust based on actual model)
        cost = (total_input_tokens * 0.003 + total_output_tokens * 0.015) / 1000
        
        summary = {
            "experiment_id": str(experiment_id),
            "mode": experiment.mode,
            "started_at": experiment.started_at.isoformat(),
            "completed_at": experiment.completed_at.isoformat() if experiment.completed_at else None,
            "total_tasks": total_tasks,
            "successful_tasks": successful_tasks,
            "failed_tasks": failed_tasks,
            "pending_tasks": pending_tasks,
            "success_rate": successful_tasks / total_tasks if total_tasks > 0 else 0.0,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "estimated_cost_usd": round(cost, 4)
        }
        
        logger.info(f"Generated experiment summary: {summary}")
        
        return summary


# Dependency injection helper
_metrics_collector_instance: Optional[MetricsCollector] = None


async def get_metrics_collector(db: AsyncSession) -> MetricsCollector:
    """
    Get or create MetricsCollector instance.
    
    Args:
        db: Async database session
        
    Returns:
        MetricsCollector instance
    """
    return MetricsCollector(db)
