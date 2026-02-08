"""
Сервис классификации задач.

Определяет, является ли задача атомарной или требует планирования.
"""

import logging
import json
from typing import Optional

from app.domain.entities.task_classification import TaskClassification
from app.infrastructure.llm.llm_client import LLMProxyClient
from app.core.config import AppConfig

logger = logging.getLogger("agent-runtime.task_classifier")


# Промпт для классификации задач
CLASSIFICATION_PROMPT = """You are a task classifier for a multi-agent system.

Your job is to determine:
1. Is the task ATOMIC (single-step, can be done by one agent) or COMPLEX (multi-step, requires planning)?
2. Which agent should handle it?

**Atomic tasks** (is_atomic=true):
- Single file changes
- Simple questions
- Direct commands
- Bug fixes in one place
- Code refactoring in one file

**Complex tasks** (is_atomic=false):
- Multi-file changes
- Feature implementations
- System design
- Creating new applications
- Refactoring multiple components

**Available agents:**
- "code" - for writing, modifying, and refactoring code
- "plan" - for planning and decomposing complex tasks (ONLY for is_atomic=false)
- "debug" - for troubleshooting, investigating errors, and debugging
- "explain" - for answering questions, explaining concepts, and providing documentation

**CRITICAL RULE:**
If is_atomic=false, then agent MUST be "plan". This ensures complex tasks go through planning phase.

Respond with ONLY a JSON object (no markdown, no code blocks):
{{
  "is_atomic": true|false,
  "agent": "code|plan|debug|explain",
  "confidence": "high|medium|low",
  "reason": "brief explanation"
}}

Task to classify: {user_message}"""


class TaskClassifier:
    """
    Классификатор задач с LLM и fallback стратегией.
    
    Определяет:
    - Является ли задача атомарной (is_atomic)
    - Какой агент должен её обработать
    - Уровень уверенности в классификации
    
    Использует:
    1. LLM-based классификацию (primary)
    2. Keyword-based fallback (если LLM недоступен)
    """
    
    def __init__(self, llm_client: LLMProxyClient = None):
        """Инициализация классификатора"""
        self.llm_client = llm_client or LLMProxyClient()
        self.model = AppConfig.LLM_MODEL
    
    async def classify(self, message: str) -> TaskClassification:
        """
        Классифицировать задачу.
        
        Args:
            message: Сообщение пользователя с описанием задачи
            
        Returns:
            TaskClassification с результатом классификации
            
        Raises:
            ValueError: Если классификация нарушает правила
        """
        try:
            # Попытка LLM-based классификации
            classification = await self._classify_with_llm(message)
            logger.info(
                f"LLM classification: is_atomic={classification.is_atomic}, "
                f"agent={classification.agent}, confidence={classification.confidence}"
            )
            return classification
        
        except Exception as e:
            logger.error(f"LLM classification failed: {e}", exc_info=True)
            logger.warning("Falling back to keyword-based classification")
            
            # Fallback на keyword matching
            classification = self._classify_with_keywords(message)
            logger.info(
                f"Keyword classification: is_atomic={classification.is_atomic}, "
                f"agent={classification.agent}"
            )
            return classification
    
    async def _classify_with_llm(self, message: str) -> TaskClassification:
        """
        Классифицировать задачу используя LLM.
        
        Args:
            message: Сообщение пользователя
            
        Returns:
            TaskClassification
            
        Raises:
            Exception: Если LLM недоступен или вернул невалидный ответ
        """
        # Подготовить промпт
        prompt = CLASSIFICATION_PROMPT.format(user_message=message)
        
        # Вызвать LLM
        response = await self.llm_client.chat_completion(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a task classifier. Respond only with JSON."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            tools=[],
            temperature=0.3  # Низкая температура для консистентности
        )
        
        # Извлечь содержимое ответа из LLMResponse объекта
        content = response.content
        
        # Парсинг JSON (с обработкой markdown code blocks)
        classification_dict = self._parse_json_response(content)
        
        # Создать и валидировать TaskClassification
        # Pydantic автоматически проверит правило: is_atomic=false → agent=plan
        classification = TaskClassification(**classification_dict)
        
        return classification
    
    def _parse_json_response(self, content: str) -> dict:
        """
        Парсинг JSON из ответа LLM.
        
        Обрабатывает случаи, когда LLM возвращает JSON в markdown code blocks
        или использует Python boolean (True/False) вместо JSON (true/false).
        
        Args:
            content: Содержимое ответа LLM
            
        Returns:
            Словарь с данными классификации
            
        Raises:
            json.JSONDecodeError: Если не удалось распарсить JSON
        """
        # Извлечь JSON из markdown code block если есть
        json_str = content
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0].strip()
        
        # Заменить Python boolean на JSON boolean
        json_str = json_str.replace("True", "true").replace("False", "false")
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # Не удалось распарсить JSON
            raise
    
    def _classify_with_keywords(self, message: str) -> TaskClassification:
        """
        Fallback классификация используя keyword matching.
        
        Используется когда LLM недоступен или вернул ошибку.
        
        Args:
            message: Сообщение пользователя
            
        Returns:
            TaskClassification с низкой уверенностью
        """
        message_lower = message.lower()
        
        # Определение сложности задачи
        is_atomic = self._is_atomic_by_keywords(message_lower)
        
        # Если задача сложная → agent=plan (обязательное правило)
        if not is_atomic:
            return TaskClassification(
                is_atomic=False,
                agent="plan",
                confidence="low",
                reason="Keyword-based: Complex task detected, requires planning"
            )
        
        # Для атомарных задач определяем агента
        agent = self._determine_agent_by_keywords(message_lower)
        
        return TaskClassification(
            is_atomic=True,
            agent=agent,
            confidence="low",
            reason=f"Keyword-based: Atomic task for {agent} agent"
        )
    
    def _is_atomic_by_keywords(self, message_lower: str) -> bool:
        """
        Определить атомарность задачи по ключевым словам.
        
        Args:
            message_lower: Сообщение в нижнем регистре
            
        Returns:
            True если задача атомарная, False если сложная
        """
        # Индикаторы сложной задачи
        complex_indicators = [
            "create application", "create app", "build system",
            "implement feature", "design system", "architecture",
            "multiple files", "several components", "full implementation",
            "создай приложение", "мобильное приложение", "реализуй систему",
            "разработай", "несколько файлов", "полная реализация",
            "с логином", "с регистрацией", "с авторизацией"
        ]
        
        # Индикаторы атомарной задачи
        atomic_indicators = [
            "fix bug in", "change in file", "update function",
            "add method", "refactor class", "explain",
            "what is", "how does", "why",
            "исправь ошибку", "измени в файле", "обнови функцию"
        ]
        
        # Подсчет совпадений
        complex_score = sum(1 for ind in complex_indicators if ind in message_lower)
        atomic_score = sum(1 for ind in atomic_indicators if ind in message_lower)
        
        # Если есть явные индикаторы сложности
        if complex_score > 0:
            return False
        
        # Если есть явные индикаторы атомарности
        if atomic_score > 0:
            return True
        
        # По умолчанию: если сообщение длинное → сложная задача
        # Короткое сообщение обычно = простая задача
        return len(message_lower.split()) < 10
    
    def _determine_agent_by_keywords(self, message_lower: str) -> str:
        """
        Определить агента по ключевым словам (для атомарных задач).
        
        Args:
            message_lower: Сообщение в нижнем регистре
            
        Returns:
            Название агента: "code", "debug", или "explain"
        """
        # Ключевые слова для каждого агента
        code_keywords = [
            "create", "write", "implement", "code", "refactor",
            "modify", "add", "update", "change",
            "создай", "напиши", "реализуй", "измени"
        ]
        
        debug_keywords = [
            "debug", "error", "bug", "problem", "fix",
            "investigate", "crash", "why not working",
            "отладь", "ошибка", "баг", "проблема", "исправь"
        ]
        
        explain_keywords = [
            "explain", "what is", "how does", "help",
            "understand", "describe", "tell me about",
            "объясни", "что такое", "как работает", "расскажи"
        ]
        
        # Подсчет совпадений
        code_score = sum(1 for kw in code_keywords if kw in message_lower)
        debug_score = sum(1 for kw in debug_keywords if kw in message_lower)
        explain_score = sum(1 for kw in explain_keywords if kw in message_lower)
        
        # Выбор агента с максимальным score
        scores = {
            "code": code_score,
            "debug": debug_score,
            "explain": explain_score
        }
        
        max_agent = max(scores, key=scores.get)
        
        # Если все scores = 0, по умолчанию code
        if scores[max_agent] == 0:
            return "code"
        
        return max_agent
    
    async def validate_classification(
        self,
        classification: TaskClassification
    ) -> bool:
        """
        Валидировать классификацию по бизнес-правилам.
        
        Args:
            classification: Результат классификации
            
        Returns:
            True если классификация валидна
            
        Raises:
            ValueError: Если классификация нарушает правила
        """
        # Правило уже проверяется в Pydantic валидаторе TaskClassification
        # Но можно добавить дополнительные проверки здесь
        
        # Проверка: agent должен быть валидным
        valid_agents = ["code", "plan", "debug", "explain"]
        if classification.agent not in valid_agents:
            raise ValueError(
                f"Invalid agent: {classification.agent}. "
                f"Must be one of: {valid_agents}"
            )
        
        # Проверка: confidence должен быть валидным
        valid_confidences = ["high", "medium", "low"]
        if classification.confidence not in valid_confidences:
            raise ValueError(
                f"Invalid confidence: {classification.confidence}. "
                f"Must be one of: {valid_confidences}"
            )
        
        # Проверка: reason не должен быть пустым
        if not classification.reason or len(classification.reason.strip()) == 0:
            raise ValueError("Classification reason cannot be empty")
        
        return True
