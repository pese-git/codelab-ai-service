"""
Unit-тесты для SSEUnitOfWork.

Проверяют:
- Создание новой сессии
- Использование существующей сессии
- Commit с метриками
- Rollback при ошибках
- Управление владением сессией
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.unit_of_work import SSEUnitOfWork


class TestSSEUnitOfWorkInitialization:
    """Тесты инициализации UoW."""
    
    def test_init_with_session_factory(self):
        """Тест инициализации с фабрикой сессий."""
        factory = Mock()
        uow = SSEUnitOfWork(session_factory=factory)
        
        assert uow._session_factory is factory
        assert uow._session is None
        assert uow._owns_session is True
    
    def test_init_with_existing_session(self):
        """Тест инициализации с существующей сессией."""
        session = Mock(spec=AsyncSession)
        uow = SSEUnitOfWork(existing_session=session)
        
        assert uow._session is session
        assert uow._session_factory is None
        assert uow._owns_session is False
    
    def test_init_without_arguments_raises_error(self):
        """Тест ошибки при инициализации без аргументов."""
        with pytest.raises(ValueError, match="Either session_factory or existing_session"):
            SSEUnitOfWork()


class TestSSEUnitOfWorkContextManager:
    """Тесты контекстного менеджера."""
    
    @pytest.mark.asyncio
    async def test_enter_with_session_factory(self):
        """Тест входа в контекст с фабрикой."""
        mock_session = Mock(spec=AsyncSession)
        factory = Mock(return_value=mock_session)
        
        uow = SSEUnitOfWork(session_factory=factory)
        
        async with uow as entered_uow:
            assert entered_uow is uow
            assert uow._session is mock_session
            factory.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_enter_with_existing_session(self):
        """Тест входа в контекст с существующей сессией."""
        mock_session = Mock(spec=AsyncSession)
        
        uow = SSEUnitOfWork(existing_session=mock_session)
        
        async with uow as entered_uow:
            assert entered_uow is uow
            assert uow._session is mock_session
    
    @pytest.mark.asyncio
    async def test_exit_closes_owned_session(self):
        """Тест закрытия сессии при выходе (если владеем)."""
        mock_session = AsyncMock(spec=AsyncSession)
        factory = Mock(return_value=mock_session)
        
        uow = SSEUnitOfWork(session_factory=factory)
        
        async with uow:
            pass
        
        mock_session.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_exit_does_not_close_external_session(self):
        """Тест НЕ закрытия внешней сессии при выходе."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        uow = SSEUnitOfWork(existing_session=mock_session)
        
        async with uow:
            pass
        
        mock_session.close.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_exit_rollback_on_exception(self):
        """Тест rollback при исключении."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        uow = SSEUnitOfWork(existing_session=mock_session)
        
        try:
            async with uow:
                raise ValueError("Test error")
        except ValueError:
            pass
        
        mock_session.rollback.assert_called_once()


class TestSSEUnitOfWorkSession:
    """Тесты доступа к сессии."""
    
    @pytest.mark.asyncio
    async def test_session_property_in_context(self):
        """Тест доступа к сессии внутри контекста."""
        mock_session = Mock(spec=AsyncSession)
        
        uow = SSEUnitOfWork(existing_session=mock_session)
        
        async with uow:
            assert uow.session is mock_session
    
    def test_session_property_outside_context_raises_error(self):
        """Тест ошибки при доступе к сессии вне контекста."""
        mock_session = Mock(spec=AsyncSession)
        uow = SSEUnitOfWork(existing_session=mock_session)
        
        with pytest.raises(RuntimeError, match="not in context"):
            _ = uow.session


class TestSSEUnitOfWorkCommit:
    """Тесты commit операций."""
    
    @pytest.mark.asyncio
    async def test_commit_success(self):
        """Тест успешного commit."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        uow = SSEUnitOfWork(existing_session=mock_session)
        
        async with uow:
            await uow.commit(operation="test_operation")
        
        mock_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_commit_outside_context_raises_error(self):
        """Тест ошибки при commit вне контекста."""
        mock_session = AsyncMock(spec=AsyncSession)
        uow = SSEUnitOfWork(existing_session=mock_session)
        
        with pytest.raises(RuntimeError, match="not in context"):
            await uow.commit()
    
    @pytest.mark.asyncio
    @patch('app.infrastructure.persistence.unit_of_work.PROMETHEUS_AVAILABLE', True)
    @patch('app.infrastructure.persistence.unit_of_work.transaction_duration')
    @patch('app.infrastructure.persistence.unit_of_work.transaction_commits')
    async def test_commit_records_metrics(self, mock_commits, mock_duration):
        """Тест записи метрик при commit."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_duration_labels = Mock()
        mock_commits_labels = Mock()
        mock_duration.labels.return_value = mock_duration_labels
        mock_commits.labels.return_value = mock_commits_labels
        
        uow = SSEUnitOfWork(existing_session=mock_session)
        
        async with uow:
            await uow.commit(operation="test_op")
        
        # Проверить вызовы метрик
        mock_duration.labels.assert_called_once_with(operation="test_op")
        mock_duration_labels.observe.assert_called_once()
        
        mock_commits.labels.assert_called_once_with(operation="test_op", status="success")
        mock_commits_labels.inc.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('app.infrastructure.persistence.unit_of_work.PROMETHEUS_AVAILABLE', True)
    @patch('app.infrastructure.persistence.unit_of_work.transaction_commits')
    async def test_commit_records_error_metric(self, mock_commits):
        """Тест записи метрики ошибки при неудачном commit."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.commit.side_effect = Exception("Commit failed")
        mock_commits_labels = Mock()
        mock_commits.labels.return_value = mock_commits_labels
        
        uow = SSEUnitOfWork(existing_session=mock_session)
        
        with pytest.raises(Exception, match="Commit failed"):
            async with uow:
                await uow.commit(operation="test_op")
        
        # Проверить метрику ошибки
        mock_commits.labels.assert_called_with(operation="test_op", status="error")
        mock_commits_labels.inc.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('app.infrastructure.persistence.unit_of_work.logger')
    async def test_commit_warns_on_slow_transaction(self, mock_logger):
        """Тест предупреждения о медленной транзакции."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Симулировать медленный commit (> 100ms)
        async def slow_commit():
            import asyncio
            await asyncio.sleep(0.15)
        
        mock_session.commit = slow_commit
        
        uow = SSEUnitOfWork(existing_session=mock_session)
        
        async with uow:
            await uow.commit(operation="slow_op")
        
        # Проверить, что было предупреждение
        warning_calls = [
            call for call in mock_logger.warning.call_args_list
            if "SLOW TRANSACTION" in str(call)
        ]
        assert len(warning_calls) > 0


class TestSSEUnitOfWorkFlush:
    """Тесты flush операций."""
    
    @pytest.mark.asyncio
    async def test_flush_success(self):
        """Тест успешного flush."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        uow = SSEUnitOfWork(existing_session=mock_session)
        
        async with uow:
            await uow.flush()
        
        mock_session.flush.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_flush_outside_context_raises_error(self):
        """Тест ошибки при flush вне контекста."""
        mock_session = AsyncMock(spec=AsyncSession)
        uow = SSEUnitOfWork(existing_session=mock_session)
        
        with pytest.raises(RuntimeError, match="not in context"):
            await uow.flush()


class TestSSEUnitOfWorkRollback:
    """Тесты rollback операций."""
    
    @pytest.mark.asyncio
    async def test_rollback_success(self):
        """Тест успешного rollback."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        uow = SSEUnitOfWork(existing_session=mock_session)
        
        async with uow:
            await uow.rollback()
        
        mock_session.rollback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_rollback_outside_context_raises_error(self):
        """Тест ошибки при rollback вне контекста."""
        mock_session = AsyncMock(spec=AsyncSession)
        uow = SSEUnitOfWork(existing_session=mock_session)
        
        with pytest.raises(RuntimeError, match="not in context"):
            await uow.rollback()


class TestSSEUnitOfWorkIntegration:
    """Интеграционные тесты UoW."""
    
    @pytest.mark.asyncio
    async def test_multiple_commits_in_single_context(self):
        """Тест нескольких commit'ов в одном контексте."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        uow = SSEUnitOfWork(existing_session=mock_session)
        
        async with uow:
            await uow.commit(operation="op1")
            await uow.commit(operation="op2")
            await uow.commit(operation="op3")
        
        assert mock_session.commit.call_count == 3
    
    @pytest.mark.asyncio
    async def test_commit_flush_commit_sequence(self):
        """Тест последовательности commit-flush-commit."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        uow = SSEUnitOfWork(existing_session=mock_session)
        
        async with uow:
            await uow.commit(operation="op1")
            await uow.flush()
            await uow.commit(operation="op2")
        
        assert mock_session.commit.call_count == 2
        assert mock_session.flush.call_count == 1
    
    @pytest.mark.asyncio
    async def test_error_after_commit_triggers_rollback(self):
        """Тест rollback после ошибки (даже после успешного commit)."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        uow = SSEUnitOfWork(existing_session=mock_session)
        
        try:
            async with uow:
                await uow.commit(operation="op1")
                raise ValueError("Error after commit")
        except ValueError:
            pass
        
        # Должен быть и commit, и rollback
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_called_once()
