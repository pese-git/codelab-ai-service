"""
HITLPolicy Entity.

Политика HITL для автоматического принятия решений об утверждениях.
"""

from typing import Any, Dict, List, Optional
from pydantic import Field

from app.domain.shared.base_entity import Entity
from ..value_objects.approval_type import ApprovalType
from ..value_objects.policy_action import PolicyAction, PolicyActionEnum
from .policy_rule import PolicyRule
from ..events.approval_events import PolicyEvaluated, PolicyRuleMatched
from ..value_objects.approval_id import ApprovalId


class HITLPolicy(Entity):
    """
    Политика HITL для автоматического принятия решений.
    
    Aggregate Root для управления правилами политики и оценки запросов.
    
    Обеспечивает:
    - Оценку запросов на основе правил
    - Управление правилами с приоритетами
    - Генерацию Domain Events
    - Включение/выключение политики
    
    Attributes:
        id: Уникальный идентификатор политики
        name: Название политики
        rules: Список правил политики (отсортированы по приоритету)
        is_active: Активна ли политика
        default_action: Действие по умолчанию, если ни одно правило не сработало
    
    Примеры:
        >>> # Создание политики
        >>> policy = HITLPolicy.create(
        ...     policy_id="policy-default",
        ...     name="Default HITL Policy",
        ...     default_action=PolicyAction(PolicyActionEnum.ASK_USER)
        ... )
        >>> 
        >>> # Добавление правила
        >>> rule = PolicyRule(
        ...     approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
        ...     subject_pattern="write_file",
        ...     action=PolicyAction(PolicyActionEnum.ASK_USER),
        ...     priority=10
        ... )
        >>> policy.add_rule(rule)
        >>> 
        >>> # Оценка запроса
        >>> action = policy.evaluate(
        ...     approval_id=ApprovalId("req-123"),
        ...     approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
        ...     subject="write_file",
        ...     request_data={}
        ... )
    """
    
    id: str = Field(..., description="Уникальный идентификатор")
    name: str = Field(..., description="Название политики")
    rules: List[PolicyRule] = Field(default_factory=list, description="Список правил")
    is_active: bool = Field(True, description="Активна ли политика")
    default_action: PolicyAction = Field(
        default_factory=lambda: PolicyAction(PolicyActionEnum.ASK_USER),
        description="Действие по умолчанию"
    )
    
    @classmethod
    def create(
        cls,
        policy_id: str,
        name: str,
        default_action: Optional[PolicyAction] = None,
    ) -> "HITLPolicy":
        """
        Создать новую политику HITL.
        
        Factory method для создания политики без правил.
        
        Args:
            policy_id: Уникальный идентификатор
            name: Название политики
            default_action: Действие по умолчанию
            
        Returns:
            Новая HITLPolicy
        """
        return cls(
            id=policy_id,
            name=name,
            rules=[],
            is_active=True,
            default_action=default_action or PolicyAction(PolicyActionEnum.ASK_USER),
        )
    
    def evaluate(
        self,
        approval_id: ApprovalId,
        approval_type: ApprovalType,
        subject: str,
        request_data: Dict[str, Any],
    ) -> PolicyAction:
        """
        Оценить запрос и определить действие.
        
        Проверяет правила в порядке приоритета (от высшего к низшему).
        Возвращает действие первого совпавшего правила или default_action.
        
        Args:
            approval_id: ID запроса на утверждение
            approval_type: Тип запроса
            subject: Предмет запроса
            request_data: Данные запроса
            
        Returns:
            PolicyAction для этого запроса
        """
        # Если политика неактивна, автоматически одобряем
        if not self.is_active:
            return PolicyAction(PolicyActionEnum.APPROVE)
        
        # Проверка правил по приоритету
        for rule in self.rules:
            # Проверка типа запроса
            if rule.approval_type != approval_type:
                continue
            
            # Проверка совпадения правила
            if rule.matches(subject, request_data):
                # Генерация события о совпадении правила
                self.add_domain_event(
                    PolicyRuleMatched(
                        approval_id=approval_id,
                        rule_condition=rule.subject_pattern,
                        action=rule.action,
                    )
                )
                
                # Генерация события об оценке политики
                self.add_domain_event(
                    PolicyEvaluated(
                        approval_id=approval_id,
                        policy_id=self.id,
                        action=rule.action,
                    )
                )
                
                return rule.action
        
        # Ни одно правило не сработало, используем default_action
        self.add_domain_event(
            PolicyEvaluated(
                approval_id=approval_id,
                policy_id=self.id,
                action=self.default_action,
            )
        )
        
        return self.default_action
    
    def add_rule(self, rule: PolicyRule) -> None:
        """
        Добавить правило в политику.
        
        Правила автоматически сортируются по приоритету.
        
        Args:
            rule: Правило для добавления
        """
        self.rules.append(rule)
        # Пересортировка по приоритету (от высшего к низшему)
        self.rules = sorted(self.rules, key=lambda r: r.priority, reverse=True)
    
    def remove_rule(self, rule: PolicyRule) -> bool:
        """
        Удалить правило из политики.
        
        Args:
            rule: Правило для удаления
            
        Returns:
            True если правило было удалено, False если не найдено
        """
        try:
            self.rules.remove(rule)
            return True
        except ValueError:
            return False
    
    def activate(self) -> None:
        """Активировать политику."""
        self.is_active = True
    
    def deactivate(self) -> None:
        """Деактивировать политику."""
        self.is_active = False
    
    def __repr__(self) -> str:
        """Отладочное представление."""
        return (
            f"HITLPolicy(id='{self.id}', "
            f"name='{self.name}', "
            f"rules={len(self.rules)}, "
            f"active={self.is_active})"
        )
