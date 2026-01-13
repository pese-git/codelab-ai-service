#!/usr/bin/env python3
"""
Test script for metrics collection infrastructure.

Tests:
1. Database initialization
2. Table creation
3. MetricsCollector basic operations
4. Data persistence
"""
import asyncio
import sys
from pathlib import Path
from uuid import UUID

# Add agent-runtime directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "agent-runtime"))

from app.core.config import AppConfig, logger
from app.services.database import init_database, get_db, init_db, close_db
from app.services.metrics_collector import MetricsCollector


async def test_database_initialization():
    """Test 1: Database initialization"""
    logger.info("=" * 60)
    logger.info("Test 1: Database initialization")
    logger.info("=" * 60)
    
    try:
        # Use test database
        test_db_url = "sqlite:///data/test_metrics.db"
        logger.info(f"Initializing test database: {test_db_url}")
        
        init_database(test_db_url)
        await init_db()
        
        logger.info("✓ Database initialized successfully")
        return True
    except Exception as e:
        logger.error(f"✗ Database initialization failed: {e}", exc_info=True)
        return False


async def test_table_creation():
    """Test 2: Metrics table creation"""
    logger.info("\n" + "=" * 60)
    logger.info("Test 2: Metrics table creation")
    logger.info("=" * 60)
    
    try:
        from app.models.metrics import Base as MetricsBase
        from app.services.database import engine
        
        async with engine.begin() as conn:
            await conn.run_sync(MetricsBase.metadata.create_all)
        
        logger.info("✓ Metrics tables created successfully")
        
        # List created tables
        from sqlalchemy import inspect
        async with engine.connect() as conn:
            inspector = await conn.run_sync(lambda sync_conn: inspect(sync_conn))
            tables = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())
        
        metrics_tables = [t for t in tables if t.startswith('poc_')]
        logger.info(f"Created {len(metrics_tables)} metrics tables:")
        for table in metrics_tables:
            logger.info(f"  - {table}")
        
        expected_tables = [
            'poc_experiments',
            'poc_task_executions',
            'poc_llm_calls',
            'poc_tool_calls',
            'poc_agent_switches',
            'poc_quality_evaluations',
            'poc_hallucinations'
        ]
        
        missing_tables = set(expected_tables) - set(metrics_tables)
        if missing_tables:
            logger.error(f"✗ Missing tables: {missing_tables}")
            return False
        
        logger.info("✓ All expected tables created")
        return True
        
    except Exception as e:
        logger.error(f"✗ Table creation failed: {e}", exc_info=True)
        return False


async def test_metrics_collector():
    """Test 3: MetricsCollector operations"""
    logger.info("\n" + "=" * 60)
    logger.info("Test 3: MetricsCollector operations")
    logger.info("=" * 60)
    
    try:
        async for db in get_db():
            collector = MetricsCollector(db)
            logger.info("✓ MetricsCollector instantiated")
            
            # Test: Start experiment
            logger.info("\nTesting start_experiment...")
            exp_id = await collector.start_experiment(
                mode="multi-agent",
                config={"test": True, "llm_model": "test-model"}
            )
            logger.info(f"✓ Experiment started: {exp_id}")
            
            # Test: Start task
            logger.info("\nTesting start_task...")
            task_id = await collector.start_task(
                experiment_id=exp_id,
                task_id="test_task_001",
                task_category="simple",
                task_type="coding",
                mode="multi-agent"
            )
            logger.info(f"✓ Task started: {task_id}")
            
            # Test: Record LLM call
            logger.info("\nTesting record_llm_call...")
            llm_call_id = await collector.record_llm_call(
                task_execution_id=task_id,
                agent_type="coder",
                input_tokens=500,
                output_tokens=200,
                model="test-model",
                duration_seconds=2.5
            )
            logger.info(f"✓ LLM call recorded: {llm_call_id}")
            
            # Test: Record tool call
            logger.info("\nTesting record_tool_call...")
            tool_call_id = await collector.record_tool_call(
                task_execution_id=task_id,
                tool_name="write_file",
                success=True,
                duration_seconds=0.1
            )
            logger.info(f"✓ Tool call recorded: {tool_call_id}")
            
            # Test: Record agent switch
            logger.info("\nTesting record_agent_switch...")
            switch_id = await collector.record_agent_switch(
                task_execution_id=task_id,
                from_agent="orchestrator",
                to_agent="coder",
                reason="Coding task detected"
            )
            logger.info(f"✓ Agent switch recorded: {switch_id}")
            
            # Test: Record quality evaluation
            logger.info("\nTesting record_quality_evaluation...")
            eval_id = await collector.record_quality_evaluation(
                task_execution_id=task_id,
                evaluation_type="syntax_check",
                score=0.95,
                passed=True,
                details={"checks_passed": 10, "checks_failed": 0}
            )
            logger.info(f"✓ Quality evaluation recorded: {eval_id}")
            
            # Test: Record hallucination
            logger.info("\nTesting record_hallucination...")
            hall_id = await collector.record_hallucination(
                task_execution_id=task_id,
                hallucination_type="import",
                description="Non-existent import: package:fake/fake.dart"
            )
            logger.info(f"✓ Hallucination recorded: {hall_id}")
            
            # Test: Complete task
            logger.info("\nTesting complete_task...")
            await collector.complete_task(
                task_execution_id=task_id,
                success=True,
                metrics={"iterations": 3, "test": True}
            )
            logger.info("✓ Task completed")
            
            # Test: Complete experiment
            logger.info("\nTesting complete_experiment...")
            await collector.complete_experiment(exp_id)
            logger.info("✓ Experiment completed")
            
            # Test: Get experiment summary
            logger.info("\nTesting get_experiment_summary...")
            summary = await collector.get_experiment_summary(exp_id)
            logger.info("✓ Experiment summary retrieved:")
            logger.info(f"  - Mode: {summary['mode']}")
            logger.info(f"  - Total tasks: {summary['total_tasks']}")
            logger.info(f"  - Successful tasks: {summary['successful_tasks']}")
            logger.info(f"  - Success rate: {summary['success_rate']:.2%}")
            logger.info(f"  - Total input tokens: {summary['total_input_tokens']}")
            logger.info(f"  - Total output tokens: {summary['total_output_tokens']}")
            logger.info(f"  - Estimated cost: ${summary['estimated_cost_usd']:.4f}")
            
            logger.info("\n✓ All MetricsCollector operations successful")
            return True
            
    except Exception as e:
        logger.error(f"✗ MetricsCollector test failed: {e}", exc_info=True)
        return False


async def test_data_persistence():
    """Test 4: Data persistence"""
    logger.info("\n" + "=" * 60)
    logger.info("Test 4: Data persistence")
    logger.info("=" * 60)
    
    try:
        from sqlalchemy import select, func
        from app.models.metrics import (
            Experiment, TaskExecution, LLMCall, ToolCall,
            AgentSwitch, QualityEvaluation, Hallucination
        )
        
        async for db in get_db():
            # Count records in each table
            tables = [
                ("Experiments", Experiment),
                ("Task Executions", TaskExecution),
                ("LLM Calls", LLMCall),
                ("Tool Calls", ToolCall),
                ("Agent Switches", AgentSwitch),
                ("Quality Evaluations", QualityEvaluation),
                ("Hallucinations", Hallucination)
            ]
            
            logger.info("\nRecord counts:")
            for name, model in tables:
                result = await db.execute(select(func.count()).select_from(model))
                count = result.scalar()
                logger.info(f"  - {name}: {count}")
            
            # Verify we have at least one record in each table
            result = await db.execute(select(func.count()).select_from(Experiment))
            if result.scalar() == 0:
                logger.error("✗ No experiments found in database")
                return False
            
            logger.info("\n✓ Data persisted successfully")
            return True
            
    except Exception as e:
        logger.error(f"✗ Data persistence test failed: {e}", exc_info=True)
        return False


async def main():
    """Run all tests"""
    logger.info("\n" + "=" * 60)
    logger.info("POC METRICS INFRASTRUCTURE TEST SUITE")
    logger.info("=" * 60 + "\n")
    
    results = []
    
    # Test 1: Database initialization
    results.append(("Database initialization", await test_database_initialization()))
    
    # Test 2: Table creation
    results.append(("Table creation", await test_table_creation()))
    
    # Test 3: MetricsCollector operations
    results.append(("MetricsCollector operations", await test_metrics_collector()))
    
    # Test 4: Data persistence
    results.append(("Data persistence", await test_data_persistence()))
    
    # Close database
    await close_db()
    
    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        logger.info(f"{status}: {test_name}")
    
    logger.info(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("\n🎉 All tests passed! Metrics infrastructure is ready.")
        return 0
    else:
        logger.error(f"\n❌ {total - passed} test(s) failed. Please check the logs.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
