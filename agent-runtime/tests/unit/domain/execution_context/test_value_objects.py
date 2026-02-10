"""
Unit тесты для Value Objects в Execution Context.

Тестируют:
- Валидацию и создание Value Objects
- Равенство и хеширование
- Переходы статусов
- Невалидные состояния
"""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from app.domain.execution_context.value_objects import (
    PlanId,
    SubtaskId,
    PlanStatus,
    SubtaskStatus
)
from app.domain.session_context.value_objects import ConversationId
from app.domain.agent_context.value_objects import AgentId


class TestPlanId:
    """Тесты для PlanId Value Object."""
    
    def test_create_valid_plan_id(self):
        """Создание валидного PlanId."""
        plan_id = PlanId(value="plan-123")
        assert plan_id.value == "plan-123"
    
    def test_create_plan_id_with_empty_string_raises_error(self):
        """Создание PlanId с пустой строкой вызывает ошибку."""
        with pytest.raises(ValidationError, match="PlanId value cannot be empty"):
            PlanId(value="")
    
    def test_create_plan_id_with_whitespace_raises_error(self):
        """Создание PlanId с пробелами вызывает ошибку."""
        with pytest.raises(ValidationError, match="PlanId value cannot be empty"):
            PlanId(value="   ")
    
    def test_plan_id_equality(self):
        """Два PlanId с одинаковым значением равны."""
        plan_id1 = PlanId(value="plan-123")
        plan_id2 = PlanId(value="plan-123")
        assert plan_id1 == plan_id2
    
    def test_plan_id_inequality(self):
        """Два PlanId с разными значениями не равны."""
        plan_id1 = PlanId(value="plan-123")
        plan_id2 = PlanId(value="plan-456")
        assert plan_id1 != plan_id2
    
    def test_plan_id_hash(self):
        """PlanId можно использовать в множествах и словарях."""
        plan_id1 = PlanId(value="plan-123")
        plan_id2 = PlanId(value="plan-123")
        plan_id3 = PlanId(value="plan-456")
        
        plan_set = {plan_id1, plan_id2, plan_id3}
        assert len(plan_set) == 2  # plan_id1 и plan_id2 считаются одинаковыми
    
    def test_plan_id_repr(self):
        """PlanId имеет читаемое строковое представление."""
        plan_id = PlanId(value="plan-123")
        assert repr(plan_id) == "PlanId(value='plan-123')"
    
    def test_plan_id_str(self):
        """PlanId можно преобразовать в строку."""
        plan_id = PlanId(value="plan-123")
        assert str(plan_id) == "plan-123"


class TestSubtaskId:
    """Тесты для SubtaskId Value Object."""
    
    def test_create_valid_subtask_id(self):
        """Создание валидного SubtaskId."""
        subtask_id = SubtaskId(value="subtask-456")
        assert subtask_id.value == "subtask-456"
    
    def test_create_subtask_id_with_empty_string_raises_error(self):
        """Создание SubtaskId с пустой строкой вызывает ошибку."""
        with pytest.raises(ValidationError, match="SubtaskId value cannot be empty"):
            SubtaskId(value="")
    
    def test_subtask_id_equality(self):
        """Два SubtaskId с одинаковым значением равны."""
        subtask_id1 = SubtaskId(value="subtask-456")
        subtask_id2 = SubtaskId(value="subtask-456")
        assert subtask_id1 == subtask_id2
    
    def test_subtask_id_hash(self):
        """SubtaskId можно использовать в множествах и словарях."""
        subtask_id1 = SubtaskId(value="subtask-456")
        subtask_id2 = SubtaskId(value="subtask-456")
        subtask_id3 = SubtaskId(value="subtask-789")
        
        subtask_set = {subtask_id1, subtask_id2, subtask_id3}
        assert len(subtask_set) == 2


class TestPlanStatus:
    """Тесты для PlanStatus Value Object."""
    
    def test_create_valid_plan_status(self):
        """Создание валидного PlanStatus."""
        status = PlanStatus.PENDING
        assert status.value == "pending"
    
    def test_all_plan_statuses_exist(self):
        """Все статусы плана определены."""
        assert PlanStatus.PENDING.value == "pending"
        assert PlanStatus.IN_PROGRESS.value == "in_progress"
        assert PlanStatus.COMPLETED.value == "completed"
        assert PlanStatus.FAILED.value == "failed"
        assert PlanStatus.CANCELLED.value == "cancelled"
    
    def test_can_transition_from_pending_to_in_progress(self):
        """Можно перейти из PENDING в IN_PROGRESS."""
        assert PlanStatus.PENDING.can_transition_to(PlanStatus.IN_PROGRESS)
    
    def test_can_transition_from_in_progress_to_completed(self):
        """Можно перейти из IN_PROGRESS в COMPLETED."""
        assert PlanStatus.IN_PROGRESS.can_transition_to(PlanStatus.COMPLETED)
    
    def test_can_transition_from_in_progress_to_failed(self):
        """Можно перейти из IN_PROGRESS в FAILED."""
        assert PlanStatus.IN_PROGRESS.can_transition_to(PlanStatus.FAILED)
    
    def test_can_transition_from_in_progress_to_cancelled(self):
        """Можно перейти из IN_PROGRESS в CANCELLED."""
        assert PlanStatus.IN_PROGRESS.can_transition_to(PlanStatus.CANCELLED)
    
    def test_cannot_transition_from_completed_to_in_progress(self):
        """Нельзя перейти из COMPLETED в IN_PROGRESS."""
        assert not PlanStatus.COMPLETED.can_transition_to(PlanStatus.IN_PROGRESS)
    
    def test_cannot_transition_from_failed_to_in_progress(self):
        """Нельзя перейти из FAILED в IN_PROGRESS."""
        assert not PlanStatus.FAILED.can_transition_to(PlanStatus.IN_PROGRESS)
    
    def test_cannot_transition_from_cancelled_to_in_progress(self):
        """Нельзя перейти из CANCELLED в IN_PROGRESS."""
        assert not PlanStatus.CANCELLED.can_transition_to(PlanStatus.IN_PROGRESS)
    
    def test_is_terminal_for_completed(self):
        """COMPLETED является терминальным статусом."""
        assert PlanStatus.COMPLETED.is_terminal()
    
    def test_is_terminal_for_failed(self):
        """FAILED является терминальным статусом."""
        assert PlanStatus.FAILED.is_terminal()
    
    def test_is_terminal_for_cancelled(self):
        """CANCELLED является терминальным статусом."""
        assert PlanStatus.CANCELLED.is_terminal()
    
    def test_is_not_terminal_for_pending(self):
        """PENDING не является терминальным статусом."""
        assert not PlanStatus.PENDING.is_terminal()
    
    def test_is_not_terminal_for_in_progress(self):
        """IN_PROGRESS не является терминальным статусом."""
        assert not PlanStatus.IN_PROGRESS.is_terminal()


class TestSubtaskStatus:
    """Тесты для SubtaskStatus Value Object."""
    
    def test_create_valid_subtask_status(self):
        """Создание валидного SubtaskStatus."""
        status = SubtaskStatus.PENDING
        assert status.value == "pending"
    
    def test_all_subtask_statuses_exist(self):
        """Все статусы подзадачи определены."""
        assert SubtaskStatus.PENDING.value == "pending"
        assert SubtaskStatus.IN_PROGRESS.value == "in_progress"
        assert SubtaskStatus.RUNNING.value == "running"  # Alias
        assert SubtaskStatus.DONE.value == "done"
        assert SubtaskStatus.FAILED.value == "failed"
    
    def test_can_transition_from_pending_to_in_progress(self):
        """Можно перейти из PENDING в IN_PROGRESS."""
        assert SubtaskStatus.PENDING.can_transition_to(SubtaskStatus.RUNNING)
    
    def test_can_transition_from_in_progress_to_done(self):
        """Можно перейти из IN_PROGRESS в DONE."""
        assert SubtaskStatus.RUNNING.can_transition_to(SubtaskStatus.DONE)
    
    def test_can_transition_from_in_progress_to_failed(self):
        """Можно перейти из IN_PROGRESS в FAILED."""
        assert SubtaskStatus.RUNNING.can_transition_to(SubtaskStatus.FAILED)
    
    def test_can_transition_from_failed_to_pending(self):
        """Можно перейти из FAILED в PENDING (retry)."""
        assert SubtaskStatus.FAILED.can_transition_to(SubtaskStatus.PENDING)
    
    def test_cannot_transition_from_done_to_in_progress(self):
        """Нельзя перейти из DONE в IN_PROGRESS."""
        assert not SubtaskStatus.DONE.can_transition_to(SubtaskStatus.RUNNING)
    
    def test_cannot_transition_from_pending_to_done(self):
        """Нельзя перейти из PENDING в DONE напрямую."""
        assert not SubtaskStatus.PENDING.can_transition_to(SubtaskStatus.DONE)
    
    def test_is_terminal_for_done(self):
        """DONE является терминальным статусом."""
        assert SubtaskStatus.DONE.is_terminal()
    
    def test_is_not_terminal_for_failed(self):
        """FAILED не является терминальным (можно retry)."""
        assert not SubtaskStatus.FAILED.is_terminal()
    
    def test_is_not_terminal_for_pending(self):
        """PENDING не является терминальным статусом."""
        assert not SubtaskStatus.PENDING.is_terminal()
    
    def test_is_not_terminal_for_in_progress(self):
        """IN_PROGRESS не является терминальным статусом."""
        assert not SubtaskStatus.RUNNING.is_terminal()


class TestStatusTransitions:
    """Интеграционные тесты для переходов статусов."""
    
    def test_plan_lifecycle_happy_path(self):
        """Успешный жизненный цикл плана."""
        status = PlanStatus.PENDING
        
        # PENDING -> IN_PROGRESS
        assert status.can_transition_to(PlanStatus.IN_PROGRESS)
        status = PlanStatus.IN_PROGRESS
        
        # IN_PROGRESS -> COMPLETED
        assert status.can_transition_to(PlanStatus.COMPLETED)
        status = PlanStatus.COMPLETED
        
        # COMPLETED - терминальный статус
        assert status.is_terminal()
        assert not status.can_transition_to(PlanStatus.IN_PROGRESS)
    
    def test_plan_lifecycle_with_failure(self):
        """Жизненный цикл плана с ошибкой."""
        status = PlanStatus.PENDING
        
        # PENDING -> IN_PROGRESS
        status = PlanStatus.IN_PROGRESS
        
        # IN_PROGRESS -> FAILED
        assert status.can_transition_to(PlanStatus.FAILED)
        status = PlanStatus.FAILED
        
        # FAILED - терминальный статус
        assert status.is_terminal()
    
    def test_subtask_lifecycle_with_retry(self):
        """Жизненный цикл подзадачи с retry."""
        status = SubtaskStatus.PENDING
        
        # PENDING -> IN_PROGRESS
        status = SubtaskStatus.RUNNING
        
        # IN_PROGRESS -> FAILED
        status = SubtaskStatus.FAILED
        
        # FAILED -> PENDING (retry)
        assert status.can_transition_to(SubtaskStatus.PENDING)
        status = SubtaskStatus.PENDING
        
        # PENDING -> IN_PROGRESS -> DONE
        status = SubtaskStatus.RUNNING
        status = SubtaskStatus.DONE
        
        # DONE - терминальный статус
        assert status.is_terminal()
