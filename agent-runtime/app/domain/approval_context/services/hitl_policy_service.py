"""
HITLPolicyService Domain Service.

Сервис для управления HITL политиками и оценки запросов.
"""

import logging
from typing import Any, Dict, Optional

from ..entities.hitl_policy import HITLPolicy
from ..entities.policy_rule import PolicyRule
from ..value_objects.approval_id import ApprovalId
from ..value_objects.approval_type import ApprovalType, ApprovalTypeEnum
from ..value_objects.policy_action import PolicyAction, PolicyActionEnum
from ..events.approval_events import AutoApprovalGranted

logger = logging.getLogger("agent-runtime.domain.hitl_policy_service")


class HITLPolicyService:
    """
    Domain Service для управления HITL политиками.
    
    Responsibilities:
    - Оценка запросов на основе политики
    - Определение необходимости утверждения
    - Автоматическое принятие решений
    - Управление правилами политики
    
    Примеры:
        >>> # Создание сервиса с политикой по умолчанию
        >>> service = HITLPolicyService.with_default_policy()
        >>> 
        >>> # Оценка запроса
        >>> action = await service.evaluate_request(
        ...     approval_id=ApprovalId("req-123"),
        ...     approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
        ...     subject="write_file",
        ...     request_data={"path": "test.py"}
        ... )
        >>> 
        >>> if action.requires_user_decision():
        ...     # Требуется решение пользователя
        ...     pass
    """
    
    def __init__(self, policy: HITLPolicy):
        """
        Создать HITLPolicyService.
        
        Args:
            policy: Политика HITL для оценки
        """
        self._policy = policy
        logger.info(
            f"HITLPolicyService initialized: "
            f"policy='{policy.name}', active={policy.is_active}"
        )
    
    @classmethod
    def with_default_policy(cls) -> "HITLPolicyService":
        """
        Создать сервис с политикой по умолчанию.
        
        Политика по умолчанию требует утверждения для:
        - write_file, delete_file, execute_command, create_directory, move_file
        - Все планы выполнения
        
        Returns:
            HITLPolicyService с политикой по умолчанию
        """
        policy = HITLPolicy.create(
            policy_id="default-hitl-policy",
            name="Default HITL Policy",
            default_action=PolicyAction(PolicyActionEnum.ASK_USER),
        )
        
        # Правила для инструментов
        dangerous_tools = [
            ("write_file", "File modification requires approval"),
            ("delete_file", "File deletion requires approval"),
            ("execute_command", "Command execution requires approval"),
            ("create_directory", "Directory creation requires approval"),
            ("move_file", "File move requires approval"),
        ]
        
        for tool_name, reason in dangerous_tools:
            rule = PolicyRule(
                approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
                subject_pattern=tool_name,
                action=PolicyAction(PolicyActionEnum.ASK_USER),
                priority=10,
            )
            policy.add_rule(rule)
        
        # Безопасные инструменты (явно не требуют утверждения)
        safe_tools = ["read_file", "list_files", "search_files"]
        for tool_name in safe_tools:
            rule = PolicyRule(
                approval_type=ApprovalType(ApprovalTypeEnum.TOOL_CALL),
                subject_pattern=tool_name,
                action=PolicyAction(PolicyActionEnum.APPROVE),
                priority=5,
            )
            policy.add_rule(rule)
        
        # Правило для планов (все планы требуют утверждения)
        plan_rule = PolicyRule(
            approval_type=ApprovalType(ApprovalTypeEnum.PLAN_EXECUTION),
            subject_pattern=".*",  # Любой план
            action=PolicyAction(PolicyActionEnum.ASK_USER),
            priority=10,
        )
        policy.add_rule(plan_rule)
        
        return cls(policy)
    
    async def evaluate_request(
        self,
        approval_id: ApprovalId,
        approval_type: ApprovalType,
        subject: str,
        request_data: Dict[str, Any],
    ) -> PolicyAction:
        """
        Оценить запрос и определить действие.
        
        Args:
            approval_id: ID запроса на утверждение
            approval_type: Тип запроса
            subject: Предмет запроса
            request_data: Данные запроса
            
        Returns:
            PolicyAction для этого запроса
        """
        # Оценка через политику (генерирует события)
        action = self._policy.evaluate(
            approval_id=approval_id,
            approval_type=approval_type,
            subject=subject,
            request_data=request_data,
        )
        
        # Если автоматическое одобрение, генерируем событие
        if action.is_approve():
            self._policy.add_domain_event(
                AutoApprovalGranted(
                    approval_id=approval_id,
                    policy_id=self._policy.id,
                )
            )
            logger.info(
                f"Auto-approval granted: id={approval_id}, "
                f"type={approval_type}, subject='{subject}'"
            )
        
        return action
    
    def add_policy_rule(self, rule: PolicyRule) -> None:
        """
        Добавить правило в политику.
        
        Args:
            rule: Правило для добавления
        """
        self._policy.add_rule(rule)
        logger.info(
            f"Policy rule added: pattern='{rule.subject_pattern}', "
            f"action={rule.action}, priority={rule.priority}"
        )
    
    def remove_policy_rule(self, rule: PolicyRule) -> bool:
        """
        Удалить правило из политики.
        
        Args:
            rule: Правило для удаления
            
        Returns:
            True если правило было удалено
        """
        removed = self._policy.remove_rule(rule)
        if removed:
            logger.info(f"Policy rule removed: pattern='{rule.subject_pattern}'")
        return removed
    
    def activate_policy(self) -> None:
        """Активировать политику."""
        self._policy.activate()
        logger.info(f"Policy activated: '{self._policy.name}'")
    
    def deactivate_policy(self) -> None:
        """Деактивировать политику."""
        self._policy.deactivate()
        logger.info(f"Policy deactivated: '{self._policy.name}'")
    
    def is_policy_active(self) -> bool:
        """
        Проверить, активна ли политика.
        
        Returns:
            True если политика активна
        """
        return self._policy.is_active
    
    def get_policy(self) -> HITLPolicy:
        """
        Получить текущую политику.
        
        Returns:
            HITLPolicy
        """
        return self._policy
