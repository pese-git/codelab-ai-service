"""
Unit тесты для Value Objects в Approval Context.

Тестирует:
- ApprovalId: валидация, иммутабельность, сравнение
- ApprovalStatus: переходы состояний, терминальные состояния
- ApprovalType: валидация типов, проверки
- PolicyAction: валидация действий, проверки
"""

import pytest

from app.domain.approval_context.value_objects import (
    ApprovalId,
    ApprovalStatus,
    ApprovalStatusEnum,
    ApprovalType,
    ApprovalTypeEnum,
    PolicyAction,
    PolicyActionEnum,
)


# ============================================================================
# ApprovalId Tests
# ============================================================================

class TestApprovalId:
    """Тесты для ApprovalId Value Object."""
    
    def test_create_valid_approval_id(self):
        """Создание валидного ApprovalId."""
        approval_id = ApprovalId(value="req-tool-123")
        assert approval_id.value == "req-tool-123"
        assert str(approval_id) == "req-tool-123"
    
    def test_approval_id_empty_raises_error(self):
        """Пустой ID вызывает ошибку."""
        with pytest.raises(ValueError, match="cannot be empty"):
            ApprovalId(value="")
    
    def test_approval_id_whitespace_raises_error(self):
        """ID из пробелов вызывает ошибку."""
        with pytest.raises(ValueError, match="cannot be empty"):
            ApprovalId(value="   ")
    
    def test_approval_id_with_spaces_raises_error(self):
        """ID с пробелами вызывает ошибку."""
        with pytest.raises(ValueError, match="cannot contain spaces"):
            ApprovalId(value="req 123")
    
    def test_approval_id_equality(self):
        """Сравнение ApprovalId по значению."""
        id1 = ApprovalId(value="req-123")
        id2 = ApprovalId(value="req-123")
        id3 = ApprovalId(value="req-456")
        
        assert id1 == id2
        assert id1 != id3
        assert id1 != "req-123"  # Не равен строке
    
    def test_approval_id_hash(self):
        """ApprovalId можно использовать в множествах."""
        id1 = ApprovalId(value="req-123")
        id2 = ApprovalId(value="req-123")
        id3 = ApprovalId(value="req-456")
        
        id_set = {id1, id2, id3}
        assert len(id_set) == 2  # id1 и id2 одинаковые
    
    def test_approval_id_repr(self):
        """Отладочное представление ApprovalId."""
        approval_id = ApprovalId(value="req-tool-123")
        assert repr(approval_id) == "ApprovalId(value='req-tool-123')"


# ============================================================================
# ApprovalStatus Tests
# ============================================================================

class TestApprovalStatus:
    """Тесты для ApprovalStatus Value Object."""
    
    def test_create_valid_status(self):
        """Создание валидного статуса."""
        status = ApprovalStatus(value=ApprovalStatusEnum.PENDING)
        assert status.value == ApprovalStatusEnum.PENDING
        assert str(status) == "pending"
    
    def test_status_invalid_type_raises_error(self):
        """Невалидный тип вызывает ошибку."""
        with pytest.raises(ValueError, match="must be ApprovalStatusEnum"):
            ApprovalStatus(value="pending")  # type: ignore
    
    def test_pending_can_transition_to_approved(self):
        """PENDING может перейти в APPROVED."""
        pending = ApprovalStatus(value=ApprovalStatusEnum.PENDING)
        approved = ApprovalStatus(value=ApprovalStatusEnum.APPROVED)
        
        assert pending.can_transition_to(approved)
    
    def test_pending_can_transition_to_rejected(self):
        """PENDING может перейти в REJECTED."""
        pending = ApprovalStatus(value=ApprovalStatusEnum.PENDING)
        rejected = ApprovalStatus(value=ApprovalStatusEnum.REJECTED)
        
        assert pending.can_transition_to(rejected)
    
    def test_pending_can_transition_to_expired(self):
        """PENDING может перейти в EXPIRED."""
        pending = ApprovalStatus(value=ApprovalStatusEnum.PENDING)
        expired = ApprovalStatus(value=ApprovalStatusEnum.EXPIRED)
        
        assert pending.can_transition_to(expired)
    
    def test_approved_cannot_transition(self):
        """APPROVED не может перейти в другие состояния (терминальный)."""
        approved = ApprovalStatus(value=ApprovalStatusEnum.APPROVED)
        pending = ApprovalStatus(value=ApprovalStatusEnum.PENDING)
        rejected = ApprovalStatus(value=ApprovalStatusEnum.REJECTED)
        
        assert not approved.can_transition_to(pending)
        assert not approved.can_transition_to(rejected)
    
    def test_rejected_cannot_transition(self):
        """REJECTED не может перейти в другие состояния (терминальный)."""
        rejected = ApprovalStatus(value=ApprovalStatusEnum.REJECTED)
        pending = ApprovalStatus(value=ApprovalStatusEnum.PENDING)
        approved = ApprovalStatus(value=ApprovalStatusEnum.APPROVED)
        
        assert not rejected.can_transition_to(pending)
        assert not rejected.can_transition_to(approved)
    
    def test_expired_cannot_transition(self):
        """EXPIRED не может перейти в другие состояния (терминальный)."""
        expired = ApprovalStatus(value=ApprovalStatusEnum.EXPIRED)
        pending = ApprovalStatus(value=ApprovalStatusEnum.PENDING)
        
        assert not expired.can_transition_to(pending)
    
    def test_pending_is_not_terminal(self):
        """PENDING не является терминальным."""
        pending = ApprovalStatus(value=ApprovalStatusEnum.PENDING)
        assert not pending.is_terminal()
    
    def test_approved_is_terminal(self):
        """APPROVED является терминальным."""
        approved = ApprovalStatus(value=ApprovalStatusEnum.APPROVED)
        assert approved.is_terminal()
    
    def test_rejected_is_terminal(self):
        """REJECTED является терминальным."""
        rejected = ApprovalStatus(value=ApprovalStatusEnum.REJECTED)
        assert rejected.is_terminal()
    
    def test_expired_is_terminal(self):
        """EXPIRED является терминальным."""
        expired = ApprovalStatus(value=ApprovalStatusEnum.EXPIRED)
        assert expired.is_terminal()
    
    def test_status_helper_methods(self):
        """Вспомогательные методы проверки статуса."""
        pending = ApprovalStatus(value=ApprovalStatusEnum.PENDING)
        approved = ApprovalStatus(value=ApprovalStatusEnum.APPROVED)
        rejected = ApprovalStatus(value=ApprovalStatusEnum.REJECTED)
        expired = ApprovalStatus(value=ApprovalStatusEnum.EXPIRED)
        
        assert pending.is_pending()
        assert not pending.is_approved()
        
        assert approved.is_approved()
        assert not approved.is_pending()
        
        assert rejected.is_rejected()
        assert not rejected.is_approved()
        
        assert expired.is_expired()
        assert not expired.is_pending()
    
    def test_status_equality(self):
        """Сравнение статусов по значению."""
        status1 = ApprovalStatus(value=ApprovalStatusEnum.PENDING)
        status2 = ApprovalStatus(value=ApprovalStatusEnum.PENDING)
        status3 = ApprovalStatus(value=ApprovalStatusEnum.APPROVED)
        
        assert status1 == status2
        assert status1 != status3
        assert status1 != "pending"  # Не равен строке
    
    def test_status_hash(self):
        """Статусы можно использовать в множествах."""
        status1 = ApprovalStatus(value=ApprovalStatusEnum.PENDING)
        status2 = ApprovalStatus(value=ApprovalStatusEnum.PENDING)
        status3 = ApprovalStatus(value=ApprovalStatusEnum.APPROVED)
        
        status_set = {status1, status2, status3}
        assert len(status_set) == 2  # status1 и status2 одинаковые
    
    def test_status_repr(self):
        """Отладочное представление статуса."""
        status = ApprovalStatus(value=ApprovalStatusEnum.PENDING)
        assert repr(status) == "ApprovalStatus(PENDING)"


# ============================================================================
# ApprovalType Tests
# ============================================================================

class TestApprovalType:
    """Тесты для ApprovalType Value Object."""
    
    def test_create_valid_type(self):
        """Создание валидного типа."""
        approval_type = ApprovalType(value=ApprovalTypeEnum.TOOL_CALL)
        assert approval_type.value == ApprovalTypeEnum.TOOL_CALL
        assert str(approval_type) == "tool_call"
    
    def test_type_invalid_type_raises_error(self):
        """Невалидный тип вызывает ошибку."""
        with pytest.raises(ValueError, match="must be ApprovalTypeEnum"):
            ApprovalType(value="tool_call")  # type: ignore
    
    def test_type_helper_methods(self):
        """Вспомогательные методы проверки типа."""
        tool_call = ApprovalType(value=ApprovalTypeEnum.TOOL_CALL)
        plan = ApprovalType(value=ApprovalTypeEnum.PLAN_EXECUTION)
        agent_switch = ApprovalType(value=ApprovalTypeEnum.AGENT_SWITCH)
        file_op = ApprovalType(value=ApprovalTypeEnum.FILE_OPERATION)
        
        assert tool_call.is_tool_call()
        assert not tool_call.is_plan_execution()
        
        assert plan.is_plan_execution()
        assert not plan.is_tool_call()
        
        assert agent_switch.is_agent_switch()
        assert not agent_switch.is_file_operation()
        
        assert file_op.is_file_operation()
        assert not file_op.is_agent_switch()
    
    def test_type_equality(self):
        """Сравнение типов по значению."""
        type1 = ApprovalType(value=ApprovalTypeEnum.TOOL_CALL)
        type2 = ApprovalType(value=ApprovalTypeEnum.TOOL_CALL)
        type3 = ApprovalType(value=ApprovalTypeEnum.PLAN_EXECUTION)
        
        assert type1 == type2
        assert type1 != type3
        assert type1 != "tool_call"  # Не равен строке
    
    def test_type_hash(self):
        """Типы можно использовать в множествах."""
        type1 = ApprovalType(value=ApprovalTypeEnum.TOOL_CALL)
        type2 = ApprovalType(value=ApprovalTypeEnum.TOOL_CALL)
        type3 = ApprovalType(value=ApprovalTypeEnum.PLAN_EXECUTION)
        
        type_set = {type1, type2, type3}
        assert len(type_set) == 2  # type1 и type2 одинаковые
    
    def test_type_repr(self):
        """Отладочное представление типа."""
        approval_type = ApprovalType(value=ApprovalTypeEnum.TOOL_CALL)
        assert repr(approval_type) == "ApprovalType(TOOL_CALL)"


# ============================================================================
# PolicyAction Tests
# ============================================================================

class TestPolicyAction:
    """Тесты для PolicyAction Value Object."""
    
    def test_create_valid_action(self):
        """Создание валидного действия."""
        action = PolicyAction(value=PolicyActionEnum.ASK_USER)
        assert action.value == PolicyActionEnum.ASK_USER
        assert str(action) == "ask_user"
    
    def test_action_invalid_type_raises_error(self):
        """Невалидный тип вызывает ошибку."""
        with pytest.raises(ValueError, match="must be PolicyActionEnum"):
            PolicyAction(value="ask_user")  # type: ignore
    
    def test_action_helper_methods(self):
        """Вспомогательные методы проверки действия."""
        approve = PolicyAction(value=PolicyActionEnum.APPROVE)
        reject = PolicyAction(value=PolicyActionEnum.REJECT)
        ask_user = PolicyAction(value=PolicyActionEnum.ASK_USER)
        
        assert approve.is_approve()
        assert not approve.is_reject()
        assert not approve.is_ask_user()
        
        assert reject.is_reject()
        assert not reject.is_approve()
        
        assert ask_user.is_ask_user()
        assert not ask_user.is_approve()
    
    def test_action_requires_user_decision(self):
        """Проверка требования решения пользователя."""
        approve = PolicyAction(value=PolicyActionEnum.APPROVE)
        reject = PolicyAction(value=PolicyActionEnum.REJECT)
        ask_user = PolicyAction(value=PolicyActionEnum.ASK_USER)
        
        assert not approve.requires_user_decision()
        assert not reject.requires_user_decision()
        assert ask_user.requires_user_decision()
    
    def test_action_is_automatic(self):
        """Проверка автоматического действия."""
        approve = PolicyAction(value=PolicyActionEnum.APPROVE)
        reject = PolicyAction(value=PolicyActionEnum.REJECT)
        ask_user = PolicyAction(value=PolicyActionEnum.ASK_USER)
        
        assert approve.is_automatic()
        assert reject.is_automatic()
        assert not ask_user.is_automatic()
    
    def test_action_equality(self):
        """Сравнение действий по значению."""
        action1 = PolicyAction(value=PolicyActionEnum.ASK_USER)
        action2 = PolicyAction(value=PolicyActionEnum.ASK_USER)
        action3 = PolicyAction(value=PolicyActionEnum.APPROVE)
        
        assert action1 == action2
        assert action1 != action3
        assert action1 != "ask_user"  # Не равен строке
    
    def test_action_hash(self):
        """Действия можно использовать в множествах."""
        action1 = PolicyAction(value=PolicyActionEnum.ASK_USER)
        action2 = PolicyAction(value=PolicyActionEnum.ASK_USER)
        action3 = PolicyAction(value=PolicyActionEnum.APPROVE)
        
        action_set = {action1, action2, action3}
        assert len(action_set) == 2  # action1 и action2 одинаковые
    
    def test_action_repr(self):
        """Отладочное представление действия."""
        action = PolicyAction(value=PolicyActionEnum.ASK_USER)
        assert repr(action) == "PolicyAction(ASK_USER)"


# ============================================================================
# Status Transitions Tests
# ============================================================================

class TestStatusTransitions:
    """Тесты для переходов между статусами."""
    
    def test_all_valid_transitions_from_pending(self):
        """Все допустимые переходы из PENDING."""
        pending = ApprovalStatus(value=ApprovalStatusEnum.PENDING)
        
        # Допустимые переходы
        assert pending.can_transition_to(
            ApprovalStatus(value=ApprovalStatusEnum.APPROVED)
        )
        assert pending.can_transition_to(
            ApprovalStatus(value=ApprovalStatusEnum.REJECTED)
        )
        assert pending.can_transition_to(
            ApprovalStatus(value=ApprovalStatusEnum.EXPIRED)
        )
        
        # Недопустимый переход (в себя)
        assert not pending.can_transition_to(
            ApprovalStatus(value=ApprovalStatusEnum.PENDING)
        )
    
    def test_terminal_states_have_no_transitions(self):
        """Терминальные состояния не имеют переходов."""
        approved = ApprovalStatus(value=ApprovalStatusEnum.APPROVED)
        rejected = ApprovalStatus(value=ApprovalStatusEnum.REJECTED)
        expired = ApprovalStatus(value=ApprovalStatusEnum.EXPIRED)
        pending = ApprovalStatus(value=ApprovalStatusEnum.PENDING)
        
        # Терминальные состояния не могут перейти никуда
        for terminal in [approved, rejected, expired]:
            assert not terminal.can_transition_to(pending)
            assert not terminal.can_transition_to(approved)
            assert not terminal.can_transition_to(rejected)
            assert not terminal.can_transition_to(expired)
    
    def test_terminal_state_detection(self):
        """Определение терминальных состояний."""
        pending = ApprovalStatus(value=ApprovalStatusEnum.PENDING)
        approved = ApprovalStatus(value=ApprovalStatusEnum.APPROVED)
        rejected = ApprovalStatus(value=ApprovalStatusEnum.REJECTED)
        expired = ApprovalStatus(value=ApprovalStatusEnum.EXPIRED)
        
        assert not pending.is_terminal()
        assert approved.is_terminal()
        assert rejected.is_terminal()
        assert expired.is_terminal()
