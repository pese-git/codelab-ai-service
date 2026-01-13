#!/usr/bin/env python3
"""
Metrics Report Generator - генерация детального отчета по метрикам POC.

Этот скрипт извлекает данные из базы метрик и генерирует детальный отчет
в формате Markdown для сравнения single-agent и multi-agent режимов.

Usage:
    python scripts/generate_metrics_report.py --output report.md
    python scripts/generate_metrics_report.py --experiment-id <uuid> --output report.md
    python scripts/generate_metrics_report.py --latest --output report.md
"""
import argparse
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from uuid import UUID

# Add agent-runtime directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "agent-runtime"))

from app.core.config import AppConfig
from app.services.database import init_database, get_db, init_db
from app.services.metrics_collector import MetricsCollector
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.metrics import (
    Experiment, TaskExecution, LLMCall, ToolCall,
    AgentSwitch, QualityEvaluation, Hallucination
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("metrics_report")


class MetricsReportGenerator:
    """
    Генератор отчетов по метрикам POC экспериментов.
    
    Извлекает данные из базы и создает детальный Markdown отчет
    с таблицами, графиками и анализом результатов.
    """
    
    def __init__(self, db: AsyncSession):
        """
        Initialize report generator.
        
        Args:
            db: Database session
        """
        self.db = db
        self.collector = MetricsCollector(db)
    
    async def get_latest_experiments(self, limit: int = 2) -> List[Experiment]:
        """
        Get latest experiments (one for each mode).
        
        Args:
            limit: Maximum number of experiments to retrieve
            
        Returns:
            List of Experiment objects
        """
        result = await self.db.execute(
            select(Experiment)
            .order_by(Experiment.started_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def get_experiment_by_id(self, experiment_id: UUID) -> Optional[Experiment]:
        """
        Get experiment by ID.
        
        Args:
            experiment_id: Experiment UUID
            
        Returns:
            Experiment object or None
        """
        result = await self.db.execute(
            select(Experiment).where(Experiment.id == experiment_id)
        )
        return result.scalar_one_or_none()
    
    async def get_task_executions(self, experiment_id: UUID) -> List[TaskExecution]:
        """
        Get all task executions for an experiment.
        
        Args:
            experiment_id: Experiment UUID
            
        Returns:
            List of TaskExecution objects
        """
        result = await self.db.execute(
            select(TaskExecution)
            .where(TaskExecution.experiment_id == experiment_id)
            .order_by(TaskExecution.started_at)
        )
        return list(result.scalars().all())
    
    async def get_llm_calls(self, task_execution_id: UUID) -> List[LLMCall]:
        """
        Get all LLM calls for a task execution.
        
        Args:
            task_execution_id: Task execution UUID
            
        Returns:
            List of LLMCall objects
        """
        result = await self.db.execute(
            select(LLMCall)
            .where(LLMCall.task_execution_id == task_execution_id)
            .order_by(LLMCall.started_at)
        )
        return list(result.scalars().all())
    
    async def get_tool_calls(self, task_execution_id: UUID) -> List[ToolCall]:
        """
        Get all tool calls for a task execution.
        
        Args:
            task_execution_id: Task execution UUID
            
        Returns:
            List of ToolCall objects
        """
        result = await self.db.execute(
            select(ToolCall)
            .where(ToolCall.task_execution_id == task_execution_id)
            .order_by(ToolCall.started_at)
        )
        return list(result.scalars().all())
    
    async def get_agent_switches(self, task_execution_id: UUID) -> List[AgentSwitch]:
        """
        Get all agent switches for a task execution.
        
        Args:
            task_execution_id: Task execution UUID
            
        Returns:
            List of AgentSwitch objects
        """
        result = await self.db.execute(
            select(AgentSwitch)
            .where(AgentSwitch.task_execution_id == task_execution_id)
            .order_by(AgentSwitch.timestamp)
        )
        return list(result.scalars().all())
    
    async def get_quality_evaluations(self, task_execution_id: UUID) -> List[QualityEvaluation]:
        """
        Get all quality evaluations for a task execution.
        
        Args:
            task_execution_id: Task execution UUID
            
        Returns:
            List of QualityEvaluation objects
        """
        result = await self.db.execute(
            select(QualityEvaluation)
            .where(QualityEvaluation.task_execution_id == task_execution_id)
            .order_by(QualityEvaluation.evaluated_at)
        )
        return list(result.scalars().all())
    
    async def get_hallucinations(self, task_execution_id: UUID) -> List[Hallucination]:
        """
        Get all hallucinations for a task execution.
        
        Args:
            task_execution_id: Task execution UUID
            
        Returns:
            List of Hallucination objects
        """
        result = await self.db.execute(
            select(Hallucination)
            .where(Hallucination.task_execution_id == task_execution_id)
            .order_by(Hallucination.detected_at)
        )
        return list(result.scalars().all())
    
    async def calculate_experiment_stats(self, experiment: Experiment) -> Dict[str, Any]:
        """
        Calculate detailed statistics for an experiment.
        
        Args:
            experiment: Experiment object
            
        Returns:
            Dictionary with statistics
        """
        tasks = await self.get_task_executions(experiment.id)
        
        # Helper function to get duration from metrics JSON
        def get_duration(task: TaskExecution) -> float:
            if task.metrics and isinstance(task.metrics, dict):
                return task.metrics.get('duration_seconds', 0) or 0
            return 0
        
        stats = {
            "experiment_id": str(experiment.id),
            "mode": experiment.mode,
            "started_at": experiment.started_at.isoformat(),
            "completed_at": experiment.completed_at.isoformat() if experiment.completed_at else None,
            "total_tasks": len(tasks),
            "successful_tasks": sum(1 for t in tasks if t.success),
            "failed_tasks": sum(1 for t in tasks if not t.success),
            "success_rate": sum(1 for t in tasks if t.success) / len(tasks) if tasks else 0,
            "total_duration": sum(get_duration(t) for t in tasks),
            "avg_task_duration": sum(get_duration(t) for t in tasks) / len(tasks) if tasks else 0,
            "total_llm_calls": 0,
            "total_tool_calls": 0,
            "total_agent_switches": 0,
            "total_hallucinations": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "estimated_cost_usd": 0,
            "tasks_by_category": {},
            "tasks_by_type": {},
        }
        
        # Collect detailed metrics
        for task in tasks:
            # Count by category and type
            category = task.task_category
            task_type = task.task_type
            
            if category not in stats["tasks_by_category"]:
                stats["tasks_by_category"][category] = {"total": 0, "successful": 0}
            stats["tasks_by_category"][category]["total"] += 1
            if task.success:
                stats["tasks_by_category"][category]["successful"] += 1
            
            if task_type not in stats["tasks_by_type"]:
                stats["tasks_by_type"][task_type] = {"total": 0, "successful": 0}
            stats["tasks_by_type"][task_type]["total"] += 1
            if task.success:
                stats["tasks_by_type"][task_type]["successful"] += 1
            
            # LLM calls
            llm_calls = await self.get_llm_calls(task.id)
            stats["total_llm_calls"] += len(llm_calls)
            stats["total_input_tokens"] += sum(c.input_tokens for c in llm_calls)
            stats["total_output_tokens"] += sum(c.output_tokens for c in llm_calls)
            
            # Tool calls
            tool_calls = await self.get_tool_calls(task.id)
            stats["total_tool_calls"] += len(tool_calls)
            
            # Agent switches (multi-agent only)
            agent_switches = await self.get_agent_switches(task.id)
            stats["total_agent_switches"] += len(agent_switches)
            
            # Hallucinations
            hallucinations = await self.get_hallucinations(task.id)
            stats["total_hallucinations"] += len(hallucinations)
        
        # Calculate cost (example rates for GPT-4)
        input_cost_per_1k = 0.03  # $0.03 per 1K input tokens
        output_cost_per_1k = 0.06  # $0.06 per 1K output tokens
        
        stats["estimated_cost_usd"] = (
            (stats["total_input_tokens"] / 1000) * input_cost_per_1k +
            (stats["total_output_tokens"] / 1000) * output_cost_per_1k
        )
        
        return stats
    
    def generate_markdown_report(
        self,
        single_agent_stats: Optional[Dict[str, Any]],
        multi_agent_stats: Optional[Dict[str, Any]]
    ) -> str:
        """
        Generate Markdown report from statistics.
        
        Args:
            single_agent_stats: Statistics for single-agent mode
            multi_agent_stats: Statistics for multi-agent mode
            
        Returns:
            Markdown formatted report
        """
        report = []
        
        # Header
        report.append("# POC Metrics Report: Single-Agent vs Multi-Agent")
        report.append("")
        report.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        report.append("---")
        report.append("")
        
        # Executive Summary
        report.append("## Executive Summary")
        report.append("")
        
        if single_agent_stats and multi_agent_stats:
            report.append("### Key Findings")
            report.append("")
            
            # Success rate comparison
            sa_success = single_agent_stats["success_rate"]
            ma_success = multi_agent_stats["success_rate"]
            winner = "Multi-Agent" if ma_success > sa_success else "Single-Agent"
            diff = abs(ma_success - sa_success) * 100
            
            report.append(f"- **Success Rate Winner:** {winner} (+{diff:.1f}%)")
            
            # Cost comparison
            sa_cost = single_agent_stats["estimated_cost_usd"]
            ma_cost = multi_agent_stats["estimated_cost_usd"]
            cost_winner = "Single-Agent" if sa_cost < ma_cost else "Multi-Agent"
            cost_diff = abs(ma_cost - sa_cost)
            cost_pct = (cost_diff / min(sa_cost, ma_cost)) * 100 if min(sa_cost, ma_cost) > 0 else 0
            
            report.append(f"- **Cost Efficiency Winner:** {cost_winner} (${cost_diff:.4f} or {cost_pct:.1f}% cheaper)")
            
            # Token usage
            sa_tokens = single_agent_stats["total_input_tokens"] + single_agent_stats["total_output_tokens"]
            ma_tokens = multi_agent_stats["total_input_tokens"] + multi_agent_stats["total_output_tokens"]
            token_winner = "Single-Agent" if sa_tokens < ma_tokens else "Multi-Agent"
            
            report.append(f"- **Token Efficiency Winner:** {token_winner}")
            
            report.append("")
        
        # Single-Agent Results
        if single_agent_stats:
            report.append("## Single-Agent Mode Results")
            report.append("")
            report.append(f"**Experiment ID:** `{single_agent_stats['experiment_id']}`")
            report.append(f"**Started:** {single_agent_stats['started_at']}")
            report.append(f"**Completed:** {single_agent_stats['completed_at']}")
            report.append("")
            
            report.append("### Overall Metrics")
            report.append("")
            report.append("| Metric | Value |")
            report.append("|--------|-------|")
            report.append(f"| Total Tasks | {single_agent_stats['total_tasks']} |")
            report.append(f"| Successful Tasks | {single_agent_stats['successful_tasks']} |")
            report.append(f"| Failed Tasks | {single_agent_stats['failed_tasks']} |")
            report.append(f"| Success Rate | {single_agent_stats['success_rate']:.2%} |")
            report.append(f"| Total Duration | {single_agent_stats['total_duration']:.2f}s |")
            report.append(f"| Avg Task Duration | {single_agent_stats['avg_task_duration']:.2f}s |")
            report.append(f"| Total LLM Calls | {single_agent_stats['total_llm_calls']} |")
            report.append(f"| Total Tool Calls | {single_agent_stats['total_tool_calls']} |")
            report.append(f"| Total Hallucinations | {single_agent_stats['total_hallucinations']} |")
            report.append("")
            
            report.append("### Token Usage")
            report.append("")
            report.append("| Metric | Value |")
            report.append("|--------|-------|")
            report.append(f"| Input Tokens | {single_agent_stats['total_input_tokens']:,} |")
            report.append(f"| Output Tokens | {single_agent_stats['total_output_tokens']:,} |")
            report.append(f"| Total Tokens | {single_agent_stats['total_input_tokens'] + single_agent_stats['total_output_tokens']:,} |")
            report.append(f"| Estimated Cost | ${single_agent_stats['estimated_cost_usd']:.4f} |")
            report.append("")
            
            # Tasks by category
            if single_agent_stats["tasks_by_category"]:
                report.append("### Tasks by Category")
                report.append("")
                report.append("| Category | Total | Successful | Success Rate |")
                report.append("|----------|-------|------------|--------------|")
                for category, data in single_agent_stats["tasks_by_category"].items():
                    success_rate = data["successful"] / data["total"] if data["total"] > 0 else 0
                    report.append(f"| {category} | {data['total']} | {data['successful']} | {success_rate:.2%} |")
                report.append("")
            
            # Tasks by type
            if single_agent_stats["tasks_by_type"]:
                report.append("### Tasks by Type")
                report.append("")
                report.append("| Type | Total | Successful | Success Rate |")
                report.append("|------|-------|------------|--------------|")
                for task_type, data in single_agent_stats["tasks_by_type"].items():
                    success_rate = data["successful"] / data["total"] if data["total"] > 0 else 0
                    report.append(f"| {task_type} | {data['total']} | {data['successful']} | {success_rate:.2%} |")
                report.append("")
        
        # Multi-Agent Results
        if multi_agent_stats:
            report.append("## Multi-Agent Mode Results")
            report.append("")
            report.append(f"**Experiment ID:** `{multi_agent_stats['experiment_id']}`")
            report.append(f"**Started:** {multi_agent_stats['started_at']}")
            report.append(f"**Completed:** {multi_agent_stats['completed_at']}")
            report.append("")
            
            report.append("### Overall Metrics")
            report.append("")
            report.append("| Metric | Value |")
            report.append("|--------|-------|")
            report.append(f"| Total Tasks | {multi_agent_stats['total_tasks']} |")
            report.append(f"| Successful Tasks | {multi_agent_stats['successful_tasks']} |")
            report.append(f"| Failed Tasks | {multi_agent_stats['failed_tasks']} |")
            report.append(f"| Success Rate | {multi_agent_stats['success_rate']:.2%} |")
            report.append(f"| Total Duration | {multi_agent_stats['total_duration']:.2f}s |")
            report.append(f"| Avg Task Duration | {multi_agent_stats['avg_task_duration']:.2f}s |")
            report.append(f"| Total LLM Calls | {multi_agent_stats['total_llm_calls']} |")
            report.append(f"| Total Tool Calls | {multi_agent_stats['total_tool_calls']} |")
            report.append(f"| Total Agent Switches | {multi_agent_stats['total_agent_switches']} |")
            report.append(f"| Total Hallucinations | {multi_agent_stats['total_hallucinations']} |")
            report.append("")
            
            report.append("### Token Usage")
            report.append("")
            report.append("| Metric | Value |")
            report.append("|--------|-------|")
            report.append(f"| Input Tokens | {multi_agent_stats['total_input_tokens']:,} |")
            report.append(f"| Output Tokens | {multi_agent_stats['total_output_tokens']:,} |")
            report.append(f"| Total Tokens | {multi_agent_stats['total_input_tokens'] + multi_agent_stats['total_output_tokens']:,} |")
            report.append(f"| Estimated Cost | ${multi_agent_stats['estimated_cost_usd']:.4f} |")
            report.append("")
            
            # Tasks by category
            if multi_agent_stats["tasks_by_category"]:
                report.append("### Tasks by Category")
                report.append("")
                report.append("| Category | Total | Successful | Success Rate |")
                report.append("|----------|-------|------------|--------------|")
                for category, data in multi_agent_stats["tasks_by_category"].items():
                    success_rate = data["successful"] / data["total"] if data["total"] > 0 else 0
                    report.append(f"| {category} | {data['total']} | {data['successful']} | {success_rate:.2%} |")
                report.append("")
            
            # Tasks by type
            if multi_agent_stats["tasks_by_type"]:
                report.append("### Tasks by Type")
                report.append("")
                report.append("| Type | Total | Successful | Success Rate |")
                report.append("|------|-------|------------|--------------|")
                for task_type, data in multi_agent_stats["tasks_by_type"].items():
                    success_rate = data["successful"] / data["total"] if data["total"] > 0 else 0
                    report.append(f"| {task_type} | {data['total']} | {data['successful']} | {success_rate:.2%} |")
                report.append("")
        
        # Comparison
        if single_agent_stats and multi_agent_stats:
            report.append("## Detailed Comparison")
            report.append("")
            
            report.append("### Success Metrics")
            report.append("")
            report.append("| Metric | Single-Agent | Multi-Agent | Difference |")
            report.append("|--------|--------------|-------------|------------|")
            
            sa_success = single_agent_stats["success_rate"]
            ma_success = multi_agent_stats["success_rate"]
            diff = (ma_success - sa_success) * 100
            report.append(f"| Success Rate | {sa_success:.2%} | {ma_success:.2%} | {diff:+.1f}% |")
            
            sa_tasks = single_agent_stats["successful_tasks"]
            ma_tasks = multi_agent_stats["successful_tasks"]
            diff_tasks = ma_tasks - sa_tasks
            report.append(f"| Successful Tasks | {sa_tasks} | {ma_tasks} | {diff_tasks:+d} |")
            
            report.append("")
            
            report.append("### Performance Metrics")
            report.append("")
            report.append("| Metric | Single-Agent | Multi-Agent | Difference |")
            report.append("|--------|--------------|-------------|------------|")
            
            sa_duration = single_agent_stats["avg_task_duration"]
            ma_duration = multi_agent_stats["avg_task_duration"]
            diff_duration = ma_duration - sa_duration
            diff_pct = (diff_duration / sa_duration * 100) if sa_duration > 0 else 0
            report.append(f"| Avg Task Duration | {sa_duration:.2f}s | {ma_duration:.2f}s | {diff_duration:+.2f}s ({diff_pct:+.1f}%) |")
            
            sa_llm = single_agent_stats["total_llm_calls"]
            ma_llm = multi_agent_stats["total_llm_calls"]
            diff_llm = ma_llm - sa_llm
            report.append(f"| Total LLM Calls | {sa_llm} | {ma_llm} | {diff_llm:+d} |")
            
            sa_tools = single_agent_stats["total_tool_calls"]
            ma_tools = multi_agent_stats["total_tool_calls"]
            diff_tools = ma_tools - sa_tools
            report.append(f"| Total Tool Calls | {sa_tools} | {ma_tools} | {diff_tools:+d} |")
            
            report.append("")
            
            report.append("### Cost Metrics")
            report.append("")
            report.append("| Metric | Single-Agent | Multi-Agent | Difference |")
            report.append("|--------|--------------|-------------|------------|")
            
            sa_tokens = single_agent_stats["total_input_tokens"] + single_agent_stats["total_output_tokens"]
            ma_tokens = multi_agent_stats["total_input_tokens"] + multi_agent_stats["total_output_tokens"]
            diff_tokens = ma_tokens - sa_tokens
            diff_tokens_pct = (diff_tokens / sa_tokens * 100) if sa_tokens > 0 else 0
            report.append(f"| Total Tokens | {sa_tokens:,} | {ma_tokens:,} | {diff_tokens:+,} ({diff_tokens_pct:+.1f}%) |")
            
            sa_cost = single_agent_stats["estimated_cost_usd"]
            ma_cost = multi_agent_stats["estimated_cost_usd"]
            diff_cost = ma_cost - sa_cost
            diff_cost_pct = (diff_cost / sa_cost * 100) if sa_cost > 0 else 0
            report.append(f"| Estimated Cost | ${sa_cost:.4f} | ${ma_cost:.4f} | ${diff_cost:+.4f} ({diff_cost_pct:+.1f}%) |")
            
            report.append("")
            
            report.append("### Quality Metrics")
            report.append("")
            report.append("| Metric | Single-Agent | Multi-Agent | Difference |")
            report.append("|--------|--------------|-------------|------------|")
            
            sa_hall = single_agent_stats["total_hallucinations"]
            ma_hall = multi_agent_stats["total_hallucinations"]
            diff_hall = ma_hall - sa_hall
            report.append(f"| Total Hallucinations | {sa_hall} | {ma_hall} | {diff_hall:+d} |")
            
            # Hallucination rate per task
            sa_hall_rate = sa_hall / single_agent_stats["total_tasks"] if single_agent_stats["total_tasks"] > 0 else 0
            ma_hall_rate = ma_hall / multi_agent_stats["total_tasks"] if multi_agent_stats["total_tasks"] > 0 else 0
            diff_hall_rate = ma_hall_rate - sa_hall_rate
            report.append(f"| Hallucinations per Task | {sa_hall_rate:.2f} | {ma_hall_rate:.2f} | {diff_hall_rate:+.2f} |")
            
            report.append("")
        
        # Conclusions
        report.append("## Conclusions")
        report.append("")
        
        if single_agent_stats and multi_agent_stats:
            # Determine winner
            sa_success = single_agent_stats["success_rate"]
            ma_success = multi_agent_stats["success_rate"]
            
            if ma_success > sa_success:
                report.append("### Winner: Multi-Agent Mode")
                report.append("")
                report.append(f"Multi-agent mode achieved a **{(ma_success - sa_success) * 100:.1f}%** higher success rate.")
            elif sa_success > ma_success:
                report.append("### Winner: Single-Agent Mode")
                report.append("")
                report.append(f"Single-agent mode achieved a **{(sa_success - ma_success) * 100:.1f}%** higher success rate.")
            else:
                report.append("### Result: Tie")
                report.append("")
                report.append("Both modes achieved the same success rate.")
            
            report.append("")
            
            # Trade-offs
            report.append("### Trade-offs")
            report.append("")
            
            sa_cost = single_agent_stats["estimated_cost_usd"]
            ma_cost = multi_agent_stats["estimated_cost_usd"]
            
            if ma_cost > sa_cost:
                cost_increase = ((ma_cost - sa_cost) / sa_cost * 100) if sa_cost > 0 else 0
                report.append(f"- Multi-agent mode costs **{cost_increase:.1f}%** more (${ma_cost - sa_cost:.4f})")
            else:
                cost_decrease = ((sa_cost - ma_cost) / sa_cost * 100) if sa_cost > 0 else 0
                report.append(f"- Multi-agent mode costs **{cost_decrease:.1f}%** less (${sa_cost - ma_cost:.4f})")
            
            sa_duration = single_agent_stats["avg_task_duration"]
            ma_duration = multi_agent_stats["avg_task_duration"]
            
            if ma_duration > sa_duration:
                duration_increase = ((ma_duration - sa_duration) / sa_duration * 100) if sa_duration > 0 else 0
                report.append(f"- Multi-agent mode takes **{duration_increase:.1f}%** longer per task")
            else:
                duration_decrease = ((sa_duration - ma_duration) / sa_duration * 100) if sa_duration > 0 else 0
                report.append(f"- Multi-agent mode is **{duration_decrease:.1f}%** faster per task")
            
            report.append("")
        
        # Recommendations
        report.append("## Recommendations")
        report.append("")
        
        if single_agent_stats and multi_agent_stats:
            ma_success = multi_agent_stats["success_rate"]
            sa_success = single_agent_stats["success_rate"]
            
            if ma_success > sa_success + 0.05:  # 5% threshold
                report.append("**Recommendation:** Proceed with multi-agent architecture")
                report.append("")
                report.append("The multi-agent mode shows significantly better success rates, justifying the additional complexity and cost.")
            elif sa_success > ma_success + 0.05:
                report.append("**Recommendation:** Stick with single-agent architecture")
                report.append("")
                report.append("The single-agent mode performs better while being simpler and more cost-effective.")
            else:
                report.append("**Recommendation:** Further evaluation needed")
                report.append("")
                report.append("The performance difference is marginal. Consider:")
                report.append("- Running more benchmark tasks")
                report.append("- Testing with more complex scenarios")
                report.append("- Evaluating maintainability and scalability factors")
        
        report.append("")
        report.append("---")
        report.append("")
        report.append("*Report generated by POC Metrics Infrastructure*")
        
        return "\n".join(report)
    
    async def generate_report(
        self,
        experiment_id: Optional[UUID] = None,
        latest: bool = False
    ) -> str:
        """
        Generate metrics report.
        
        Args:
            experiment_id: Specific experiment ID to report on
            latest: Use latest experiments (one for each mode)
            
        Returns:
            Markdown formatted report
        """
        single_agent_stats = None
        multi_agent_stats = None
        
        if experiment_id:
            # Get specific experiment
            experiment = await self.get_experiment_by_id(experiment_id)
            if not experiment:
                raise ValueError(f"Experiment not found: {experiment_id}")
            
            stats = await self.calculate_experiment_stats(experiment)
            
            if experiment.mode == "single-agent":
                single_agent_stats = stats
            else:
                multi_agent_stats = stats
        
        elif latest:
            # Get latest experiments
            experiments = await self.get_latest_experiments(limit=10)
            
            # Find latest for each mode
            for exp in experiments:
                if exp.mode == "single-agent" and not single_agent_stats:
                    single_agent_stats = await self.calculate_experiment_stats(exp)
                elif exp.mode == "multi-agent" and not multi_agent_stats:
                    multi_agent_stats = await self.calculate_experiment_stats(exp)
                
                if single_agent_stats and multi_agent_stats:
                    break
        
        else:
            raise ValueError("Must specify either experiment_id or latest=True")
        
        # Generate report
        return self.generate_markdown_report(single_agent_stats, multi_agent_stats)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate POC metrics report"
    )
    parser.add_argument(
        "--experiment-id",
        type=str,
        default=None,
        help="Specific experiment ID to report on"
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Use latest experiments (one for each mode)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("poc_metrics_report.md"),
        help="Output file path (default: poc_metrics_report.md)"
    )
    parser.add_argument(
        "--db-url",
        type=str,
        default=None,
        help="Database URL (default: from config)"
    )
    
    args = parser.parse_args()
    
    if not args.experiment_id and not args.latest:
        parser.error("Must specify either --experiment-id or --latest")
    
    # Initialize database
    db_url = args.db_url or AppConfig.DB_URL
    logger.info(f"Initializing database: {db_url}")
    init_database(db_url)
    await init_db()
    logger.info("Database initialized")
    
    try:
        # Generate report
        async for db in get_db():
            generator = MetricsReportGenerator(db)
            
            try:
                experiment_id = UUID(args.experiment_id) if args.experiment_id else None
                report = await generator.generate_report(
                    experiment_id=experiment_id,
                    latest=args.latest
                )
                
                # Write to file
                args.output.write_text(report, encoding='utf-8')
                logger.info(f"Report generated: {args.output}")
                
                # Also print to console
                print("\n" + report)
                
            except Exception as e:
                logger.error(f"Failed to generate report: {e}", exc_info=True)
                sys.exit(1)
    finally:
        # Close database connections
        from app.services.database import close_db
        await close_db()
        logger.info("Database connections closed")


if __name__ == "__main__":
    asyncio.run(main())
