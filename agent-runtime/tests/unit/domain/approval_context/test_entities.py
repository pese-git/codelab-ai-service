"""
Unit тесты для Entities в Approval Context.

Тестирует:
- PolicyRule: pattern matching, условия, приоритеты
- ApprovalRequest: жизненный цикл, переходы состояний, события
- HITLPolicy: оценка правил, управление правилами
"""

import pytest
from datetime import datetime, timezone, timedelta

from app.domain.approval_context.entities import (
    ApprovalRequest,
    HITLPolicy,
    PolicyRule,
)
from app.domain.approval_context.value_objects import (
    ApprovalId,
    ApprovalStatus,
    ApprovalStatusEnum,
    ApprovalType,
    ApprovalTypeEnum,
    PolicyAction,
    PolicyActionEnum,
)
from app.domain.approval_context.events import (
    ApprovalRequested,
    ApprovalGranted,
    ApprovalRejected,
    ApprovalExpired,
    PolicyEvaluated,
    PolicyRuleMatched,
)


# ============================================================================
# PolicyRule Tests
# ============================================================================

class TestPolicyRule:
    """Тесты для PolicyRule."""
    
    def test_create_valid_rule(self):
        """Создание валидного правила."""
        rule = PolicyRule(
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            subject_pattern="write_file",
            action=PolicyAction(PolicyActionEnum.ASK_USER),
            priority=10,
        )
        
        assert rule.approval_type.is_tool_call()
        assert rule.subject_pattern == "write_file"
        assert rule.action.is_ask_user()
        assert rule.priority == 10
    
    def test_rule_invalid_regex_raises_error(self):
        """Невалидный regex паттерн вызывает ошибку."""
        with pytest.raises(ValueError, match="Invalid regex pattern"):
            PolicyRule(
                approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
                subject_pattern="[invalid",  # Невалидный regex
                action=PolicyAction(PolicyActionEnum.ASK_USER),
            )
    
    def test_rule_matches_exact_subject(self):
        """Правило совпадает с точным subject."""
        rule = PolicyRule(
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            subject_pattern="write_file",
            action=PolicyAction(PolicyActionEnum.ASK_USER),
        )
        
        assert rule.matches("write_file", {})
        assert not rule.matches("read_file", {})
    
    def test_rule_matches_regex_pattern(self):
        """Правило совпадает с regex паттерном."""
        rule = PolicyRule(
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            subject_pattern="write_.*",
            action=PolicyAction(PolicyActionEnum.ASK_USER),
        )
        
        assert rule.matches("write_file", {})
        assert rule.matches("write_to_file", {})
        assert not rule.matches("read_file", {})
    
    def test_rule_matches_with_conditions_gt(self):
        """Правило с условием 'больше чем'."""
        rule = PolicyRule(
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            subject_pattern="write_file",
            action=PolicyAction(PolicyActionEnum.ASK_USER),
            conditions={"size_gt": 1000},
        )
        
        assert rule.matches("write_file", {"size": 2000})
        assert not rule.matches("write_file", {"size": 500})
        assert not rule.matches("write_file", {})  # Нет поля size
    
    def test_rule_matches_with_conditions_lt(self):
        """Правило с условием 'меньше чем'."""
        rule = PolicyRule(
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            subject_pattern=".*",
            action=PolicyAction(PolicyActionEnum.APPROVE),
            conditions={"size_lt": 1000},
        )
        
        assert rule.matches("write_file", {"size": 500})
        assert not rule.matches("write_file", {"size": 2000})
    
    def test_rule_matches_with_conditions_eq(self):
        """Правило с условием 'равно'."""
        rule = PolicyRule(
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            subject_pattern=".*",
            action=PolicyAction(PolicyActionEnum.APPROVE),
            conditions={"extension_eq": ".txt"},
        )
        
        assert rule.matches("write_file", {"extension": ".txt"})
        assert not rule.matches("write_file", {"extension": ".py"})
    
    def test_rule_matches_with_conditions_contains(self):
        """Правило с условием 'содержит'."""
        rule = PolicyRule(
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            subject_pattern=".*",
            action=PolicyAction(PolicyActionEnum.REJECT),
            conditions={"path_contains": "/etc/"},
        )
        
        assert rule.matches("write_file", {"path": "/etc/config.conf"})
        assert not rule.matches("write_file", {"path": "/home/user/file.txt"})
    
    def test_rule_matches_multiple_conditions(self):
        """Правило с несколькими условиями (все должны выполняться)."""
        rule = PolicyRule(
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            subject_pattern="write_file",
            action=PolicyAction(PolicyActionEnum.ASK_USER),
            conditions={
                "size_gt": 1000,
                "extension_eq": ".py",
            },
        )
        
        # Все условия выполнены
        assert rule.matches("write_file", {"size": 2000, "extension": ".py"})
        
        # Одно условие не выполнено
        assert not rule.matches("write_file", {"size": 500, "extension": ".py"})
        assert not rule.matches("write_file", {"size": 2000, "extension": ".txt"})
    
    def test_rule_equality(self):
        """Сравнение правил по значению."""
        rule1 = PolicyRule(
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            subject_pattern="write_file",
            action=PolicyAction(PolicyActionEnum.ASK_USER),
            priority=10,
        )
        rule2 = PolicyRule(
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            subject_pattern="write_file",
            action=PolicyAction(PolicyActionEnum.ASK_USER),
            priority=10,
        )
        rule3 = PolicyRule(
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            subject_pattern="read_file",
            action=PolicyAction(PolicyActionEnum.APPROVE),
            priority=5,
        )
        
        assert rule1 == rule2
        assert rule1 != rule3
    
    def test_rule_hash(self):
        """Правила можно использовать в множествах."""
        rule1 = PolicyRule(
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            subject_pattern="write_file",
            action=PolicyAction(PolicyActionEnum.ASK_USER),
        )
        rule2 = PolicyRule(
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            subject_pattern="write_file",
            action=PolicyAction(PolicyActionEnum.ASK_USER),
        )
        
        rule_set = {rule1, rule2}
        assert len(rule_set) == 1  # Одинаковые правила


# ============================================================================
# ApprovalRequest Tests
# ============================================================================

class TestApprovalRequest:
    """Тесты для ApprovalRequest Entity."""
    
    def test_create_approval_request(self):
        """Создание запроса на утверждение."""
        request = ApprovalRequest.create(
            approval_id=ApprovalId("req-tool-123"),
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            session_id="session-abc",
            subject="write_file",
            request_data={"path": "test.py", "content": "..."},
            reason="File modification requires approval",
        )
        
        assert request.approval_id == ApprovalId("req-tool-123")
        assert request.approval_type.is_tool_call()
        assert request.status.is_pending()
        assert request.session_id == "session-abc"
        assert request.subject == "write_file"
        assert request.reason == "File modification requires approval"
    
    def test_create_generates_approval_requested_event(self):
        """Создание генерирует событие ApprovalRequested."""
        request = ApprovalRequest.create(
            approval_id=ApprovalId("req-123"),
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            session_id="session-abc",
            subject="write_file",
            request_data={},
        )
        
        events = request.domain_events
        assert len(events) == 1
        assert isinstance(events[0], ApprovalRequested)
        assert events[0].approval_id == ApprovalId("req-123")
    
    def test_approve_request(self):
        """Одобрение запроса."""
        request = ApprovalRequest.create(
            approval_id=ApprovalId("req-123"),
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            session_id="session-abc",
            subject="write_file",
            request_data={},
        )
        
        request.approve("User confirmed")
        
        assert request.status.is_approved()
        assert request.decision == "User confirmed"
        assert request.decided_at is not None
    
    def test_approve_generates_approval_granted_event(self):
        """Одобрение генерирует событие ApprovalGranted."""
        request = ApprovalRequest.create(
            approval_id=ApprovalId("req-123"),
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            session_id="session-abc",
            subject="write_file",
            request_data={},
        )
        
        request.clear_domain_events()  # Очистка события создания
        request.approve("User confirmed")
        
        events = request.domain_events
        assert len(events) == 1
        assert isinstance(events[0], ApprovalGranted)
        assert events[0].decision == "User confirmed"
    
    def test_reject_request(self):
        """Отклонение запроса."""
        request = ApprovalRequest.create(
            approval_id=ApprovalId("req-123"),
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            session_id="session-abc",
            subject="write_file",
            request_data={},
        )
        
        request.reject("Too risky")
        
        assert request.status.is_rejected()
        assert request.decision == "Too risky"
        assert request.decided_at is not None
    
    def test_reject_generates_approval_rejected_event(self):
        """Отклонение генерирует событие ApprovalRejected."""
        request = ApprovalRequest.create(
            approval_id=ApprovalId("req-123"),
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            session_id="session-abc",
            subject="write_file",
            request_data={},
        )
        
        request.clear_domain_events()
        request.reject("Too risky")
        
        events = request.domain_events
        assert len(events) == 1
        assert isinstance(events[0], ApprovalRejected)
        assert events[0].reason == "Too risky"
    
    def test_expire_request(self):
        """Истечение запроса."""
        request = ApprovalRequest.create(
            approval_id=ApprovalId("req-123"),
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            session_id="session-abc",
            subject="write_file",
            request_data={},
        )
        
        request.expire()
        
        assert request.status.is_expired()
        assert request.decided_at is not None
    
    def test_expire_generates_approval_expired_event(self):
        """Истечение генерирует событие ApprovalExpired."""
        request = ApprovalRequest.create(
            approval_id=ApprovalId("req-123"),
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            session_id="session-abc",
            subject="write_file",
            request_data={},
        )
        
        request.clear_domain_events()
        request.expire()
        
        events = request.domain_events
        assert len(events) == 1
        assert isinstance(events[0], ApprovalExpired)
    
    def test_cannot_approve_already_approved(self):
        """Нельзя одобрить уже одобренный запрос."""
        request = ApprovalRequest.create(
            approval_id=ApprovalId("req-123"),
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            session_id="session-abc",
            subject="write_file",
            request_data={},
        )
        
        request.approve("First approval")
        
        with pytest.raises(ValueError, match="invalid transition"):
            request.approve("Second approval")
    
    def test_cannot_reject_already_rejected(self):
        """Нельзя отклонить уже отклоненный запрос."""
        request = ApprovalRequest.create(
            approval_id=ApprovalId("req-123"),
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            session_id="session-abc",
            subject="write_file",
            request_data={},
        )
        
        request.reject("First rejection")
        
        with pytest.raises(ValueError, match="invalid transition"):
            request.reject("Second rejection")
    
    def test_is_expired_check(self):
        """Проверка истечения таймаута."""
        # Создаем запрос с created_at в прошлом
        past_time = datetime.now(timezone.utc) - timedelta(seconds=2)
        
        # Создаем запрос напрямую с прошлым временем
        request = ApprovalRequest(
            id=ApprovalId("req-123"),
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            status=ApprovalStatus(ApprovalStatusEnum.PENDING),
            session_id="session-abc",
            subject="write_file",
            request_data={},
            timeout_seconds=1,
            created_at=past_time,
        )
        
        # Должен быть истекшим
        assert request.is_expired()
    
    def test_approved_request_not_expired(self):
        """Одобренный запрос не считается истекшим."""
        request = ApprovalRequest.create(
            approval_id=ApprovalId("req-123"),
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            session_id="session-abc",
            subject="write_file",
            request_data={},
            timeout_seconds=1,
        )
        
        request.approve("Approved")
        
        # Даже если прошло время, одобренный запрос не истекает
        request._created_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        assert not request.is_expired()


# ============================================================================
# HITLPolicy Tests
# ============================================================================

class TestHITLPolicy:
    """Тесты для HITLPolicy Entity."""
    
    def test_create_policy(self):
        """Создание политики."""
        policy = HITLPolicy.create(
            policy_id="policy-1",
            name="Test Policy",
            default_action=PolicyAction(PolicyActionEnum.ASK_USER),
        )
        
        assert policy.id == "policy-1"
        assert policy.name == "Test Policy"
        assert policy.is_active
        assert policy.default_action.is_ask_user()
        assert len(policy.rules) == 0
    
    def test_add_rule_to_policy(self):
        """Добавление правила в политику."""
        policy = HITLPolicy.create(
            policy_id="policy-1",
            name="Test Policy",
        )
        
        rule = PolicyRule(
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            subject_pattern="write_file",
            action=PolicyAction(PolicyActionEnum.ASK_USER),
            priority=10,
        )
        
        policy.add_rule(rule)
        
        assert len(policy.rules) == 1
        assert policy.rules[0] == rule
    
    def test_rules_sorted_by_priority(self):
        """Правила сортируются по приоритету (от высшего к низшему)."""
        policy = HITLPolicy.create(
            policy_id="policy-1",
            name="Test Policy",
        )
        
        rule1 = PolicyRule(
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            subject_pattern="write_file",
            action=PolicyAction(PolicyActionEnum.ASK_USER),
            priority=5,
        )
        rule2 = PolicyRule(
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            subject_pattern="read_file",
            action=PolicyAction(PolicyActionEnum.APPROVE),
            priority=10,
        )
        rule3 = PolicyRule(
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            subject_pattern="delete_file",
            action=PolicyAction(PolicyActionEnum.REJECT),
            priority=15,
        )
        
        policy.add_rule(rule1)
        policy.add_rule(rule2)
        policy.add_rule(rule3)
        
        rules = policy.rules
        assert rules[0].priority == 15  # Самый высокий приоритет
        assert rules[1].priority == 10
        assert rules[2].priority == 5
    
    def test_remove_rule_from_policy(self):
        """Удаление правила из политики."""
        policy = HITLPolicy.create(
            policy_id="policy-1",
            name="Test Policy",
        )
        
        rule = PolicyRule(
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            subject_pattern="write_file",
            action=PolicyAction(PolicyActionEnum.ASK_USER),
        )
        
        policy.add_rule(rule)
        assert len(policy.rules) == 1
        
        removed = policy.remove_rule(rule)
        assert removed
        assert len(policy.rules) == 0
    
    def test_remove_nonexistent_rule_returns_false(self):
        """Удаление несуществующего правила возвращает False."""
        policy = HITLPolicy.create(
            policy_id="policy-1",
            name="Test Policy",
        )
        
        rule = PolicyRule(
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            subject_pattern="write_file",
            action=PolicyAction(PolicyActionEnum.ASK_USER),
        )
        
        removed = policy.remove_rule(rule)
        assert not removed
    
    def test_evaluate_with_matching_rule(self):
        """Оценка с совпадающим правилом."""
        policy = HITLPolicy.create(
            policy_id="policy-1",
            name="Test Policy",
            default_action=PolicyAction(PolicyActionEnum.APPROVE),
        )
        
        rule = PolicyRule(
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            subject_pattern="write_file",
            action=PolicyAction(PolicyActionEnum.ASK_USER),
            priority=10,
        )
        policy.add_rule(rule)
        
        action = policy.evaluate(
            approval_id=ApprovalId("req-123"),
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            subject="write_file",
            request_data={},
        )
        
        assert action.is_ask_user()
    
    def test_evaluate_without_matching_rule_uses_default(self):
        """Оценка без совпадающих правил использует default_action."""
        policy = HITLPolicy.create(
            policy_id="policy-1",
            name="Test Policy",
            default_action=PolicyAction(PolicyActionEnum.APPROVE),
        )
        
        rule = PolicyRule(
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            subject_pattern="write_file",
            action=PolicyAction(PolicyActionEnum.ASK_USER),
        )
        policy.add_rule(rule)
        
        # Запрос не совпадает с правилом
        action = policy.evaluate(
            approval_id=ApprovalId("req-123"),
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            subject="read_file",  # Не совпадает с "write_file"
            request_data={},
        )
        
        assert action.is_approve()  # default_action
    
    def test_evaluate_generates_events(self):
        """Оценка генерирует события."""
        policy = HITLPolicy.create(
            policy_id="policy-1",
            name="Test Policy",
        )
        
        rule = PolicyRule(
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            subject_pattern="write_file",
            action=PolicyAction(PolicyActionEnum.ASK_USER),
        )
        policy.add_rule(rule)
        
        policy.evaluate(
            approval_id=ApprovalId("req-123"),
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            subject="write_file",
            request_data={},
        )
        
        events = policy.domain_events
        # Должны быть события: PolicyRuleMatched и PolicyEvaluated
        assert len(events) >= 2
        assert any(isinstance(e, PolicyRuleMatched) for e in events)
        assert any(isinstance(e, PolicyEvaluated) for e in events)
    
    def test_evaluate_inactive_policy_auto_approves(self):
        """Неактивная политика автоматически одобряет."""
        policy = HITLPolicy.create(
            policy_id="policy-1",
            name="Test Policy",
            default_action=PolicyAction(PolicyActionEnum.REJECT),
        )
        
        policy.deactivate()
        
        action = policy.evaluate(
            approval_id=ApprovalId("req-123"),
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            subject="write_file",
            request_data={},
        )
        
        assert action.is_approve()  # Автоматическое одобрение
    
    def test_activate_deactivate_policy(self):
        """Активация и деактивация политики."""
        policy = HITLPolicy.create(
            policy_id="policy-1",
            name="Test Policy",
        )
        
        assert policy.is_active
        
        policy.deactivate()
        assert not policy.is_active
        
        policy.activate()
        assert policy.is_active
    
    def test_evaluate_respects_rule_priority(self):
        """Оценка учитывает приоритет правил."""
        policy = HITLPolicy.create(
            policy_id="policy-1",
            name="Test Policy",
        )
        
        # Низкий приоритет - одобрить
        rule1 = PolicyRule(
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            subject_pattern=".*",  # Совпадает со всем
            action=PolicyAction(PolicyActionEnum.APPROVE),
            priority=5,
        )
        
        # Высокий приоритет - запросить пользователя
        rule2 = PolicyRule(
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            subject_pattern="write_file",
            action=PolicyAction(PolicyActionEnum.ASK_USER),
            priority=10,
        )
        
        policy.add_rule(rule1)
        policy.add_rule(rule2)
        
        # Должно сработать правило с высшим приоритетом
        action = policy.evaluate(
            approval_id=ApprovalId("req-123"),
            approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
            subject="write_file",
            request_data={},
        )
        
        assert action.is_ask_user()  # rule2 с приоритетом 10
