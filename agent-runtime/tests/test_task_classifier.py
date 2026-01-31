"""
Unit тесты для TaskClassifier.

Проверяют:
- Валидацию TaskClassification модели
- LLM-based классификацию
- Keyword-based fallback
- Обязательное правило: is_atomic=false → agent=plan
"""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.domain.entities.task_classification import TaskClassification
from app.domain.services.task_classifier import TaskClassifier


class TestTaskClassificationModel:
    """Тесты для Pydantic модели TaskClassification"""
    
    def test_valid_atomic_task_code(self):
        """Тест: валидная атомарная задача для code агента"""
        classification = TaskClassification(
            is_atomic=True,
            agent="code",
            confidence="high",
            reason="Simple code change"
        )
        
        assert classification.is_atomic is True
        assert classification.agent == "code"
        assert classification.confidence == "high"
    
    def test_valid_complex_task_plan(self):
        """Тест: валидная сложная задача для plan агента"""
        classification = TaskClassification(
            is_atomic=False,
            agent="plan",
            confidence="high",
            reason="Complex task requires planning"
        )
        
        assert classification.is_atomic is False
        assert classification.agent == "plan"
    
    def test_rule_violation_non_atomic_must_be_plan(self):
        """Тест: ОБЯЗАТЕЛЬНОЕ ПРАВИЛО - is_atomic=false → agent=plan"""
        # Попытка создать is_atomic=False с agent="code" должна вызвать ошибку
        with pytest.raises(ValueError) as exc_info:
            TaskClassification(
                is_atomic=False,
                agent="code",  # ← НАРУШЕНИЕ ПРАВИЛА
                confidence="high",
                reason="Test"
            )
        
        assert "RULE VIOLATION" in str(exc_info.value)
        assert "Non-atomic tasks MUST be assigned to 'plan' agent" in str(exc_info.value)
    
    def test_rule_violation_non_atomic_debug(self):
        """Тест: нельзя назначить сложную задачу debug агенту"""
        with pytest.raises(ValueError) as exc_info:
            TaskClassification(
                is_atomic=False,
                agent="debug",  # ← НАРУШЕНИЕ
                confidence="high",
                reason="Test"
            )
        
        assert "RULE VIOLATION" in str(exc_info.value)
    
    def test_rule_violation_non_atomic_explain(self):
        """Тест: нельзя назначить сложную задачу explain агенту"""
        with pytest.raises(ValueError) as exc_info:
            TaskClassification(
                is_atomic=False,
                agent="explain",  # ← НАРУШЕНИЕ
                confidence="high",
                reason="Test"
            )
        
        assert "RULE VIOLATION" in str(exc_info.value)
    
    def test_to_dict(self):
        """Тест: преобразование в словарь"""
        classification = TaskClassification(
            is_atomic=True,
            agent="code",
            confidence="high",
            reason="Test reason"
        )
        
        result = classification.to_dict()
        
        assert result["is_atomic"] is True
        assert result["agent"] == "code"
        assert result["confidence"] == "high"
        assert result["reason"] == "Test reason"


class TestTaskClassifierKeywordBased:
    """Тесты для keyword-based классификации"""
    
    def test_classify_simple_code_task(self):
        """Тест: простая задача для code агента"""
        classifier = TaskClassifier()
        
        classification = classifier._classify_with_keywords("Update function in login.py")
        
        assert classification.is_atomic is True
        assert classification.agent == "code"
        assert classification.confidence == "low"
    
    def test_classify_debug_task(self):
        """Тест: задача для debug агента"""
        classifier = TaskClassifier()
        
        classification = classifier._classify_with_keywords("Debug error in authentication")
        
        assert classification.is_atomic is True
        assert classification.agent == "debug"
        assert classification.confidence == "low"
    
    def test_classify_explain_task(self):
        """Тест: задача для explain агента"""
        classifier = TaskClassifier()
        
        classification = classifier._classify_with_keywords("Explain how JWT works")
        
        assert classification.is_atomic is True
        assert classification.agent == "explain"
        assert classification.confidence == "low"
    
    def test_classify_complex_task_requires_plan(self):
        """Тест: сложная задача → agent=plan"""
        classifier = TaskClassifier()
        
        classification = classifier._classify_with_keywords(
            "Create application with login, dashboard, and user management"
        )
        
        assert classification.is_atomic is False
        assert classification.agent == "plan"  # ← ОБЯЗАТЕЛЬНО plan
        assert classification.confidence == "low"
    
    def test_classify_russian_complex_task(self):
        """Тест: сложная задача на русском → agent=plan"""
        classifier = TaskClassifier()
        
        classification = classifier._classify_with_keywords(
            "Создай мобильное приложение с логином и регистрацией"
        )
        
        assert classification.is_atomic is False
        assert classification.agent == "plan"
    
    def test_is_atomic_by_keywords_short_message(self):
        """Тест: короткое сообщение → атомарная задача"""
        classifier = TaskClassifier()
        
        is_atomic = classifier._is_atomic_by_keywords("fix bug")
        
        assert is_atomic is True
    
    def test_is_atomic_by_keywords_long_message(self):
        """Тест: длинное сообщение → сложная задача"""
        classifier = TaskClassifier()
        
        message = "create a full mobile application with authentication system and user dashboard"
        is_atomic = classifier._is_atomic_by_keywords(message.lower())
        
        assert is_atomic is False
    
    def test_determine_agent_default_to_code(self):
        """Тест: по умолчанию выбирается code агент"""
        classifier = TaskClassifier()
        
        agent = classifier._determine_agent_by_keywords("some random text")
        
        assert agent == "code"


@pytest.mark.asyncio
class TestTaskClassifierLLMBased:
    """Тесты для LLM-based классификации"""
    
    async def test_classify_with_llm_atomic_task(self):
        """Тест: LLM классифицирует атомарную задачу"""
        classifier = TaskClassifier()
        
        # Mock LLM response
        mock_response = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "is_atomic": True,
                        "agent": "code",
                        "confidence": "high",
                        "reason": "Simple file modification"
                    })
                }
            }]
        }
        
        with patch.object(
            classifier.llm_client,
            'chat_completion',
            new=AsyncMock(return_value=mock_response)
        ):
            classification = await classifier._classify_with_llm("Fix bug in app.py")
        
        assert classification.is_atomic is True
        assert classification.agent == "code"
        assert classification.confidence == "high"
    
    async def test_classify_with_llm_complex_task(self):
        """Тест: LLM классифицирует сложную задачу"""
        classifier = TaskClassifier()
        
        # Mock LLM response
        mock_response = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "is_atomic": False,
                        "agent": "plan",
                        "confidence": "high",
                        "reason": "Multi-step feature implementation"
                    })
                }
            }]
        }
        
        with patch.object(
            classifier.llm_client,
            'chat_completion',
            new=AsyncMock(return_value=mock_response)
        ):
            classification = await classifier._classify_with_llm(
                "Create mobile app with login"
            )
        
        assert classification.is_atomic is False
        assert classification.agent == "plan"
    
    async def test_classify_with_llm_markdown_code_block(self):
        """Тест: LLM возвращает JSON в markdown code block"""
        classifier = TaskClassifier()
        
        # Mock LLM response с markdown
        mock_response = {
            "choices": [{
                "message": {
                    "content": """```json
{
  "is_atomic": True,
  "agent": "debug",
  "confidence": "medium",
  "reason": "Error investigation"
}
```"""
                }
            }]
        }
        
        with patch.object(
            classifier.llm_client,
            'chat_completion',
            new=AsyncMock(return_value=mock_response)
        ):
            classification = await classifier._classify_with_llm("Debug login error")
        
        assert classification.is_atomic is True
        assert classification.agent == "debug"
    
    async def test_classify_with_llm_rule_violation_auto_corrected(self):
        """Тест: LLM нарушает правило → Pydantic валидатор выбрасывает ошибку"""
        classifier = TaskClassifier()
        
        # Mock LLM response с нарушением правила
        mock_response = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "is_atomic": False,
                        "agent": "code",  # ← НАРУШЕНИЕ: должно быть "plan"
                        "confidence": "high",
                        "reason": "Test"
                    })
                }
            }]
        }
        
        with patch.object(
            classifier.llm_client,
            'chat_completion',
            new=AsyncMock(return_value=mock_response)
        ):
            # Должно выбросить ValueError из Pydantic валидатора
            with pytest.raises(ValueError) as exc_info:
                await classifier._classify_with_llm("Create app")
            
            assert "RULE VIOLATION" in str(exc_info.value)
    
    async def test_parse_json_response_plain_json(self):
        """Тест: парсинг обычного JSON"""
        classifier = TaskClassifier()
        
        content = '{"is_atomic": true, "agent": "code", "confidence": "high", "reason": "test"}'
        result = classifier._parse_json_response(content)
        
        assert result["is_atomic"] is True
        assert result["agent"] == "code"
    
    async def test_parse_json_response_with_json_marker(self):
        """Тест: парсинг JSON с ```json маркером"""
        classifier = TaskClassifier()
        
        content = '```json\n{"is_atomic": true, "agent": "code", "confidence": "high", "reason": "test"}\n```'
        result = classifier._parse_json_response(content)
        
        assert result["is_atomic"] is True
    
    async def test_parse_json_response_with_generic_marker(self):
        """Тест: парсинг JSON с ``` маркером"""
        classifier = TaskClassifier()
        
        content = '```\n{"is_atomic": true, "agent": "code", "confidence": "high", "reason": "test"}\n```'
        result = classifier._parse_json_response(content)
        
        assert result["is_atomic"] is True


@pytest.mark.asyncio
class TestTaskClassifierIntegration:
    """Integration тесты для TaskClassifier"""
    
    async def test_classify_fallback_on_llm_error(self):
        """Тест: fallback на keywords при ошибке LLM"""
        classifier = TaskClassifier()
        
        # Mock LLM error
        with patch.object(
            classifier.llm_client,
            'chat_completion',
            new=AsyncMock(side_effect=Exception("LLM unavailable"))
        ):
            classification = await classifier.classify("Update function in app.py")
        
        # Должен использовать keyword fallback
        assert classification.is_atomic is True
        assert classification.agent == "code"
        assert classification.confidence == "low"
    
    async def test_validate_classification_valid(self):
        """Тест: валидация корректной классификации"""
        classifier = TaskClassifier()
        
        classification = TaskClassification(
            is_atomic=True,
            agent="code",
            confidence="high",
            reason="Test reason"
        )
        
        result = await classifier.validate_classification(classification)
        
        assert result is True
    
    async def test_validate_classification_invalid_agent(self):
        """Тест: валидация с невалидным агентом"""
        classifier = TaskClassifier()
        
        # Создаем classification напрямую (обходя Pydantic валидацию)
        classification = MagicMock()
        classification.agent = "invalid_agent"
        classification.confidence = "high"
        classification.reason = "Test"
        
        with pytest.raises(ValueError) as exc_info:
            await classifier.validate_classification(classification)
        
        assert "Invalid agent" in str(exc_info.value)
    
    async def test_validate_classification_empty_reason(self):
        """Тест: валидация с пустым reason"""
        classifier = TaskClassifier()
        
        classification = MagicMock()
        classification.agent = "code"
        classification.confidence = "high"
        classification.reason = ""
        
        with pytest.raises(ValueError) as exc_info:
            await classifier.validate_classification(classification)
        
        assert "reason cannot be empty" in str(exc_info.value)


@pytest.mark.asyncio
class TestTaskClassifierEdgeCases:
    """Тесты граничных случаев"""
    
    async def test_classify_empty_message(self):
        """Тест: пустое сообщение"""
        classifier = TaskClassifier()
        
        # Mock LLM error для пустого сообщения
        with patch.object(
            classifier.llm_client,
            'chat_completion',
            new=AsyncMock(side_effect=Exception("Empty message"))
        ):
            classification = await classifier.classify("")
        
        # Fallback должен обработать
        assert classification is not None
        assert classification.confidence == "low"
    
    async def test_classify_very_long_message(self):
        """Тест: очень длинное сообщение"""
        classifier = TaskClassifier()
        
        long_message = "Create " + " and ".join([f"feature{i}" for i in range(50)])
        
        # Mock LLM response
        mock_response = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "is_atomic": False,
                        "agent": "plan",
                        "confidence": "high",
                        "reason": "Very complex task"
                    })
                }
            }]
        }
        
        with patch.object(
            classifier.llm_client,
            'chat_completion',
            new=AsyncMock(return_value=mock_response)
        ):
            classification = await classifier.classify(long_message)
        
        assert classification.is_atomic is False
        assert classification.agent == "plan"
    
    def test_keyword_classification_mixed_indicators(self):
        """Тест: сообщение с смешанными индикаторами"""
        classifier = TaskClassifier()
        
        # Сообщение содержит и "create app" (complex) и "fix" (atomic)
        # Complex индикаторы должны иметь приоритет
        classification = classifier._classify_with_keywords(
            "Create app and fix bug in login"
        )
        
        assert classification.is_atomic is False
        assert classification.agent == "plan"


# Фикстуры для тестов
@pytest.fixture
def mock_llm_client():
    """Mock LLM client для тестов"""
    client = AsyncMock()
    return client


@pytest.fixture
def task_classifier(mock_llm_client):
    """TaskClassifier с mock LLM client"""
    classifier = TaskClassifier()
    classifier.llm_client = mock_llm_client
    return classifier
