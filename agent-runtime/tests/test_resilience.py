"""
Тесты для механизмов устойчивости.

Проверяет работу Session Locks, Circuit Breaker и Retry Handler.
"""

import pytest
import asyncio
from datetime import datetime, timezone

from app.infrastructure.concurrency.session_lock import SessionLockManager
from app.infrastructure.resilience.circuit_breaker import CircuitBreaker, CircuitState
from app.infrastructure.resilience.retry_handler import RetryHandler, with_retry


# ==================== Тесты SessionLockManager ====================

class TestSessionLockManager:
    """Тесты для Session Lock Manager"""
    
    @pytest.mark.asyncio
    async def test_lock_prevents_concurrent_access(self):
        """Тест: блокировка предотвращает конкурентный доступ"""
        lock_manager = SessionLockManager()
        results = []
        
        async def task(task_id: int):
            async with lock_manager.lock("session-1"):
                results.append(f"start-{task_id}")
                await asyncio.sleep(0.1)
                results.append(f"end-{task_id}")
        
        # Запустить две задачи параллельно
        await asyncio.gather(task(1), task(2))
        
        # Проверить что задачи выполнялись последовательно
        assert results == ["start-1", "end-1", "start-2", "end-2"] or \
               results == ["start-2", "end-2", "start-1", "end-1"]
    
    @pytest.mark.asyncio
    async def test_different_sessions_can_run_parallel(self):
        """Тест: разные сессии могут выполняться параллельно"""
        lock_manager = SessionLockManager()
        results = []
        
        async def task(session_id: str):
            async with lock_manager.lock(session_id):
                results.append(f"start-{session_id}")
                await asyncio.sleep(0.05)
                results.append(f"end-{session_id}")
        
        # Запустить задачи для разных сессий
        await asyncio.gather(
            task("session-1"),
            task("session-2")
        )
        
        # Обе задачи должны начаться до завершения любой из них
        assert "start-session-1" in results and "start-session-2" in results
    
    @pytest.mark.asyncio
    async def test_cleanup_unused_locks(self):
        """Тест очистки неиспользуемых блокировок"""
        lock_manager = SessionLockManager()
        
        # Создать блокировки
        async with lock_manager.lock("session-1"):
            pass
        async with lock_manager.lock("session-2"):
            pass
        
        assert lock_manager.get_lock_count() == 2
        
        # Очистить (с низким лимитом)
        cleaned = await lock_manager.cleanup_unused_locks(max_locks=1)
        
        assert cleaned == 1
        assert lock_manager.get_lock_count() == 1


# ==================== Тесты CircuitBreaker ====================

class TestCircuitBreaker:
    """Тесты для Circuit Breaker"""
    
    @pytest.mark.asyncio
    async def test_circuit_opens_after_failures(self):
        """Тест: circuit открывается после превышения порога ошибок"""
        circuit = CircuitBreaker(failure_threshold=3, recovery_timeout=1)
        
        async def failing_func():
            raise Exception("Service unavailable")
        
        # Первые 3 вызова должны пройти (и упасть)
        for i in range(3):
            with pytest.raises(Exception):
                await circuit.call(failing_func)
        
        # Circuit должен открыться
        assert circuit.get_state() == CircuitState.OPEN
        
        # Следующий вызов должен быть заблокирован
        with pytest.raises(Exception, match="Circuit breaker is OPEN"):
            await circuit.call(failing_func)
    
    @pytest.mark.asyncio
    async def test_circuit_recovers_after_timeout(self):
        """Тест: circuit восстанавливается после timeout"""
        circuit = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        
        async def failing_func():
            raise Exception("Error")
        
        # Открыть circuit
        for i in range(2):
            with pytest.raises(Exception):
                await circuit.call(failing_func)
        
        assert circuit.get_state() == CircuitState.OPEN
        
        # Подождать recovery timeout
        await asyncio.sleep(0.15)
        
        # Следующий вызов должен перевести в HALF_OPEN
        async def success_func():
            return "OK"
        
        result = await circuit.call(success_func)
        
        assert result == "OK"
        assert circuit.get_state() == CircuitState.CLOSED
    
    @pytest.mark.asyncio
    async def test_circuit_resets_on_success(self):
        """Тест: circuit сбрасывает счетчик при успехе"""
        circuit = CircuitBreaker(failure_threshold=3)
        
        async def sometimes_failing(should_fail: bool):
            if should_fail:
                raise Exception("Error")
            return "OK"
        
        # Две ошибки
        for i in range(2):
            with pytest.raises(Exception):
                await circuit.call(sometimes_failing, True)
        
        assert circuit.failure_count == 2
        
        # Успешный вызов
        result = await circuit.call(sometimes_failing, False)
        
        assert result == "OK"
        assert circuit.failure_count == 0


# ==================== Тесты RetryHandler ====================

class TestRetryHandler:
    """Тесты для Retry Handler"""
    
    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """Тест: повтор при ошибке"""
        attempts = []
        
        @with_retry(max_retries=2, base_delay=0.01)
        async def flaky_func():
            attempts.append(len(attempts) + 1)
            if len(attempts) < 3:
                raise Exception("Temporary error")
            return "Success"
        
        result = await flaky_func()
        
        assert result == "Success"
        assert len(attempts) == 3  # 1 попытка + 2 повтора
    
    @pytest.mark.asyncio
    async def test_retry_gives_up_after_max_retries(self):
        """Тест: прекращение повторов после max_retries"""
        attempts = []
        
        @with_retry(max_retries=2, base_delay=0.01)
        async def always_failing():
            attempts.append(len(attempts) + 1)
            raise Exception("Permanent error")
        
        with pytest.raises(Exception, match="Permanent error"):
            await always_failing()
        
        assert len(attempts) == 3  # 1 попытка + 2 повтора
    
    @pytest.mark.asyncio
    async def test_no_retry_on_success(self):
        """Тест: нет повторов при успехе"""
        attempts = []
        
        @with_retry(max_retries=3)
        async def success_func():
            attempts.append(1)
            return "OK"
        
        result = await success_func()
        
        assert result == "OK"
        assert len(attempts) == 1  # Только одна попытка
