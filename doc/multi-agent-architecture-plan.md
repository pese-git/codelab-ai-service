# Архитектура мультиагентной системы для Agent Runtime

## Анализ текущей архитектуры

### Текущее состояние
Agent Runtime сервис имеет следующую структуру:

1. **Основные компоненты:**
   - [`app/main.py`](../agent-runtime/app/main.py) - FastAPI приложение
   - [`app/api/v1/endpoints.py`](../agent-runtime/app/api/v1/endpoints.py) - REST API endpoints
   - [`app/services/llm_stream_service.py`](../agent-runtime/app/services/llm_stream_service.py) - стриминг LLM ответов
   - [`app/services/session_manager.py`](../agent-runtime/app/services/session_manager.py) - управление сессиями
   - [`app/services/tool_registry.py`](../agent-runtime/app/services/tool_registry.py) - реестр инструментов
   - [`app/core/agent/prompts.py`](../agent-runtime/app/core/agent/prompts.py) - системные промпты

2. **Текущий flow:**
   - Пользователь отправляет сообщение через SSE endpoint `/agent/message/stream`
   - Сообщение добавляется в историю сессии
   - LLM генерирует ответ или вызывает инструмент
   - При вызове инструмента - отправляется `tool_call` в Gateway
   - Gateway выполняет инструмент в IDE и возвращает результат
   - Цикл повторяется до получения финального ответа

3. **Проблемы текущей архитектуры:**
   - Один универсальный промпт для всех задач
   - Нет специализации агентов по типам задач
   - Нет оркестрации между разными агентами
   - Нет переключения контекста между режимами работы

## Целевая архитектура: Мультиагентная система

### Список агентов

1. **Orchestrator** - главный координатор
   - Анализирует запрос пользователя
   - Определяет, какой агент должен обработать задачу
   - Координирует работу между агентами
   - Управляет переключением между агентами

2. **Coder** - агент для написания кода
   - Создание новых файлов
   - Модификация существующего кода
   - Рефакторинг
   - Исправление багов
   - Инструменты: `write_file`, `read_file`, `list_files`, `search_in_code`

3. **Architect** - агент для проектирования
   - Планирование архитектуры
   - Создание технических спецификаций
   - Разработка дизайна системы
   - Создание диаграмм и документации
   - Инструменты: `read_file`, `list_files`, `write_file` (только для .md файлов)

4. **Debug** - агент для отладки
   - Анализ ошибок
   - Поиск причин багов
   - Добавление логирования
   - Анализ стек-трейсов
   - Инструменты: `read_file`, `search_in_code`, `execute_command`, `list_files`

5. **Ask** - агент для ответов на вопросы
   - Объяснение концепций
   - Документация
   - Рекомендации
   - Обучение
   - Инструменты: `read_file`, `search_in_code` (только для чтения)

## Архитектура реализации

### 1. Структура директорий

```
app/
├── agents/
│   ├── __init__.py
│   ├── base_agent.py           # Базовый класс агента
│   ├── orchestrator_agent.py   # Orchestrator
│   ├── coder_agent.py          # Coder
│   ├── architect_agent.py      # Architect
│   ├── debug_agent.py          # Debug
│   ├── ask_agent.py            # Ask
│   └── prompts/
│       ├── __init__.py
│       ├── orchestrator.py     # Промпт для Orchestrator
│       ├── coder.py            # Промпт для Coder
│       ├── architect.py        # Промпт для Architect
│       ├── debug.py            # Промпт для Debug
│       └── ask.py              # Промпт для Ask
├── services/
│   ├── agent_router.py         # Маршрутизация между агентами
│   ├── agent_context.py        # Контекст агента (состояние, история)
│   └── multi_agent_orchestrator.py  # Оркестрация мультиагентной системы
└── models/
    └── agent_schemas.py        # Схемы для агентов
```

### 2. Базовый класс агента

```python
# app/agents/base_agent.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from enum import Enum

class AgentType(str, Enum):
    ORCHESTRATOR = "orchestrator"
    CODER = "coder"
    ARCHITECT = "architect"
    DEBUG = "debug"
    ASK = "ask"

class BaseAgent(ABC):
    """Базовый класс для всех агентов"""
    
    def __init__(
        self, 
        agent_type: AgentType,
        system_prompt: str,
        allowed_tools: List[str],
        file_restrictions: Optional[List[str]] = None
    ):
        self.agent_type = agent_type
        self.system_prompt = system_prompt
        self.allowed_tools = allowed_tools
        self.file_restrictions = file_restrictions or []
    
    @abstractmethod
    async def process(
        self, 
        session_id: str,
        message: str,
        context: Dict[str, Any]
    ) -> AsyncGenerator[StreamChunk, None]:
        """Обработка сообщения агентом"""
        pass
    
    def can_use_tool(self, tool_name: str) -> bool:
        """Проверка, может ли агент использовать инструмент"""
        return tool_name in self.allowed_tools
    
    def can_edit_file(self, file_path: str) -> bool:
        """Проверка, может ли агент редактировать файл"""
        if not self.file_restrictions:
            return True
        
        import re
        for pattern in self.file_restrictions:
            if re.match(pattern, file_path):
                return True
        return False
```

### 3. Orchestrator Agent

```python
# app/agents/orchestrator_agent.py
from typing import AsyncGenerator, Dict, Any
from app.agents.base_agent import BaseAgent, AgentType
from app.models.schemas import StreamChunk

class OrchestratorAgent(BaseAgent):
    """
    Главный координатор - анализирует запрос и делегирует задачи
    специализированным агентам
    """
    
    def __init__(self):
        super().__init__(
            agent_type=AgentType.ORCHESTRATOR,
            system_prompt=ORCHESTRATOR_PROMPT,
            allowed_tools=[
                "read_file", 
                "list_files", 
                "search_in_code",
                "switch_agent"  # Специальный инструмент для переключения агентов
            ]
        )
    
    async def process(
        self, 
        session_id: str,
        message: str,
        context: Dict[str, Any]
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Анализирует запрос и определяет, какой агент должен его обработать
        """
        # Логика определения агента на основе анализа запроса
        # Может использовать LLM для классификации задачи
        pass
    
    async def route_to_agent(
        self, 
        task_type: str,
        session_id: str,
        message: str
    ) -> AgentType:
        """Определяет, какому агенту передать задачу"""
        # Логика маршрутизации
        pass
```

### 4. Специализированные агенты

```python
# app/agents/coder_agent.py
class CoderAgent(BaseAgent):
    """Агент для написания и модификации кода"""
    
    def __init__(self):
        super().__init__(
            agent_type=AgentType.CODER,
            system_prompt=CODER_PROMPT,
            allowed_tools=[
                "read_file",
                "write_file",
                "list_files",
                "search_in_code",
                "create_directory",
                "execute_command",
                "attempt_completion",
                "ask_followup_question"
            ]
        )

# app/agents/architect_agent.py
class ArchitectAgent(BaseAgent):
    """Агент для проектирования и планирования"""
    
    def __init__(self):
        super().__init__(
            agent_type=AgentType.ARCHITECT,
            system_prompt=ARCHITECT_PROMPT,
            allowed_tools=[
                "read_file",
                "write_file",  # Только для .md файлов
                "list_files",
                "search_in_code",
                "attempt_completion",
                "ask_followup_question"
            ],
            file_restrictions=[r".*\.md$"]  # Только markdown файлы
        )

# app/agents/debug_agent.py
class DebugAgent(BaseAgent):
    """Агент для отладки и диагностики"""
    
    def __init__(self):
        super().__init__(
            agent_type=AgentType.DEBUG,
            system_prompt=DEBUG_PROMPT,
            allowed_tools=[
                "read_file",
                "list_files",
                "search_in_code",
                "execute_command",
                "attempt_completion",
                "ask_followup_question"
            ]
        )

# app/agents/ask_agent.py
class AskAgent(BaseAgent):
    """Агент для ответов на вопросы и объяснений"""
    
    def __init__(self):
        super().__init__(
            agent_type=AgentType.ASK,
            system_prompt=ASK_PROMPT,
            allowed_tools=[
                "read_file",
                "search_in_code",
                "list_files",
                "attempt_completion"
            ]
        )
```

### 5. Agent Router - маршрутизация между агентами

```python
# app/services/agent_router.py
from typing import Dict, Optional
from app.agents.base_agent import BaseAgent, AgentType
from app.agents.orchestrator_agent import OrchestratorAgent
from app.agents.coder_agent import CoderAgent
from app.agents.architect_agent import ArchitectAgent
from app.agents.debug_agent import DebugAgent
from app.agents.ask_agent import AskAgent

class AgentRouter:
    """Управляет маршрутизацией между агентами"""
    
    def __init__(self):
        self._agents: Dict[AgentType, BaseAgent] = {
            AgentType.ORCHESTRATOR: OrchestratorAgent(),
            AgentType.CODER: CoderAgent(),
            AgentType.ARCHITECT: ArchitectAgent(),
            AgentType.DEBUG: DebugAgent(),
            AgentType.ASK: AskAgent(),
        }
    
    def get_agent(self, agent_type: AgentType) -> BaseAgent:
        """Получить агента по типу"""
        return self._agents[agent_type]
    
    def get_current_agent(self, session_id: str) -> BaseAgent:
        """Получить текущего активного агента для сессии"""
        # Получить из контекста сессии
        pass
    
    async def switch_agent(
        self, 
        session_id: str, 
        target_agent: AgentType,
        reason: str
    ) -> None:
        """Переключить агента для сессии"""
        # Сохранить в контексте сессии
        # Логировать переключение
        pass

# Singleton instance
agent_router = AgentRouter()
```

### 6. Agent Context - контекст агента

```python
# app/services/agent_context.py
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from app.agents.base_agent import AgentType

class AgentContext(BaseModel):
    """Контекст работы агента в рамках сессии"""
    
    session_id: str
    current_agent: AgentType = Field(default=AgentType.ORCHESTRATOR)
    agent_history: List[Dict[str, Any]] = Field(default_factory=list)
    task_description: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    last_switch_at: Optional[datetime] = None
    
    def switch_agent(self, new_agent: AgentType, reason: str) -> None:
        """Переключить агента"""
        self.agent_history.append({
            "from": self.current_agent,
            "to": new_agent,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        })
        self.current_agent = new_agent
        self.last_switch_at = datetime.now()

class AgentContextManager:
    """Управление контекстами агентов"""
    
    def __init__(self):
        self._contexts: Dict[str, AgentContext] = {}
    
    def get_or_create(self, session_id: str) -> AgentContext:
        """Получить или создать контекст для сессии"""
        if session_id not in self._contexts:
            self._contexts[session_id] = AgentContext(session_id=session_id)
        return self._contexts[session_id]
    
    def get(self, session_id: str) -> Optional[AgentContext]:
        """Получить контекст"""
        return self._contexts.get(session_id)
    
    def delete(self, session_id: str) -> None:
        """Удалить контекст"""
        if session_id in self._contexts:
            del self._contexts[session_id]

# Singleton instance
agent_context_manager = AgentContextManager()
```

### 7. Multi-Agent Orchestrator

```python
# app/services/multi_agent_orchestrator.py
import logging
from typing import AsyncGenerator, Dict, Any
from app.agents.base_agent import AgentType
from app.models.schemas import StreamChunk
from app.services.agent_router import agent_router
from app.services.agent_context import agent_context_manager
from app.services.session_manager import session_manager

logger = logging.getLogger("agent-runtime.multi_agent")

class MultiAgentOrchestrator:
    """Оркестрация мультиагентной системы"""
    
    async def process_message(
        self,
        session_id: str,
        message: str,
        agent_type: Optional[AgentType] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Обработка сообщения через мультиагентную систему
        
        Args:
            session_id: ID сессии
            message: Сообщение пользователя
            agent_type: Явно указанный тип агента (опционально)
        """
        # Получить или создать контекст агента
        context = agent_context_manager.get_or_create(session_id)
        
        # Определить агента
        if agent_type:
            # Явное переключение агента
            if context.current_agent != agent_type:
                context.switch_agent(agent_type, "User requested agent switch")
                logger.info(
                    f"Switched agent for session {session_id}: "
                    f"{context.current_agent} -> {agent_type}"
                )
        else:
            # Автоматическое определение через Orchestrator
            if context.current_agent == AgentType.ORCHESTRATOR:
                # Orchestrator определяет, какой агент нужен
                orchestrator = agent_router.get_agent(AgentType.ORCHESTRATOR)
                target_agent = await orchestrator.route_to_agent(
                    task_type=self._classify_task(message),
                    session_id=session_id,
                    message=message
                )
                
                if target_agent != AgentType.ORCHESTRATOR:
                    context.switch_agent(
                        target_agent, 
                        f"Orchestrator routed to {target_agent}"
                    )
        
        # Получить текущего агента
        current_agent = agent_router.get_agent(context.current_agent)
        
        logger.info(
            f"Processing message with {context.current_agent} agent "
            f"for session {session_id}"
        )
        
        # Обработать сообщение через агента
        async for chunk in current_agent.process(
            session_id=session_id,
            message=message,
            context=context.model_dump()
        ):
            # Проверить, есть ли запрос на переключение агента
            if chunk.type == "switch_agent":
                target_agent = AgentType(chunk.metadata.get("target_agent"))
                reason = chunk.metadata.get("reason", "Agent requested switch")
                context.switch_agent(target_agent, reason)
                
                logger.info(
                    f"Agent switch requested: {context.current_agent} -> {target_agent}"
                )
                
                # Отправить уведомление о переключении
                yield StreamChunk(
                    type="agent_switched",
                    content=f"Switched to {target_agent} agent",
                    metadata={
                        "from_agent": context.current_agent,
                        "to_agent": target_agent,
                        "reason": reason
                    },
                    is_final=False
                )
                
                # Продолжить обработку с новым агентом
                new_agent = agent_router.get_agent(target_agent)
                async for new_chunk in new_agent.process(
                    session_id=session_id,
                    message=message,
                    context=context.model_dump()
                ):
                    yield new_chunk
                
                return
            
            yield chunk
    
    def _classify_task(self, message: str) -> str:
        """Классификация типа задачи на основе сообщения"""
        message_lower = message.lower()
        
        # Простая эвристика (можно заменить на LLM-классификацию)
        if any(word in message_lower for word in ["create", "write", "implement", "add", "fix"]):
            return "coding"
        elif any(word in message_lower for word in ["design", "architecture", "plan", "structure"]):
            return "architecture"
        elif any(word in message_lower for word in ["debug", "error", "bug", "issue", "problem"]):
            return "debugging"
        elif any(word in message_lower for word in ["explain", "what is", "how does", "why"]):
            return "question"
        else:
            return "general"

# Singleton instance
multi_agent_orchestrator = MultiAgentOrchestrator()
```

### 8. Обновление API endpoint

```python
# app/api/v1/endpoints.py - обновленный endpoint
@router.post("/agent/message/stream")
async def message_stream_sse(request: AgentStreamRequest):
    """
    SSE streaming endpoint с поддержкой мультиагентной системы
    """
    async def event_generator():
        try:
            logger.info(f"SSE stream started for session: {request.session_id}")
            
            # Получить или создать сессию
            session = session_manager.get_or_create(
                request.session_id,
                system_prompt=""  # Промпт определяется агентом
            )
            
            # Обработать входящее сообщение
            message_type = request.message.get("type", "user_message")
            
            if message_type == "tool_result":
                # Обработка результата инструмента
                call_id = request.message.get("call_id")
                tool_name = request.message.get("tool_name")
                result = request.message.get("result")
                
                result_str = json.dumps(result) if not isinstance(result, str) else result
                session_manager.append_tool_result(
                    request.session_id,
                    call_id=call_id,
                    tool_name=tool_name,
                    result=result_str
                )
                
                # Продолжить с текущим агентом
                context = agent_context_manager.get(request.session_id)
                current_agent = agent_router.get_agent(context.current_agent)
                
                async for chunk in current_agent.process(
                    session_id=request.session_id,
                    message="",  # Пустое сообщение, продолжаем после tool_result
                    context=context.model_dump()
                ):
                    yield {
                        "event": "message",
                        "data": json.dumps(chunk.model_dump(exclude_none=True))
                    }
                    
                    if chunk.is_final:
                        break
            
            elif message_type == "switch_agent":
                # Явное переключение агента
                target_agent = AgentType(request.message.get("agent_type"))
                content = request.message.get("content", "")
                
                async for chunk in multi_agent_orchestrator.process_message(
                    session_id=request.session_id,
                    message=content,
                    agent_type=target_agent
                ):
                    yield {
                        "event": "message",
                        "data": json.dumps(chunk.model_dump(exclude_none=True))
                    }
                    
                    if chunk.is_final:
                        break
            
            else:
                # Обычное сообщение пользователя
                content = request.message.get("content", "")
                session_manager.append_message(
                    request.session_id,
                    role="user",
                    content=content
                )
                
                # Обработать через мультиагентную систему
                async for chunk in multi_agent_orchestrator.process_message(
                    session_id=request.session_id,
                    message=content
                ):
                    yield {
                        "event": "message",
                        "data": json.dumps(chunk.model_dump(exclude_none=True))
                    }
                    
                    if chunk.is_final:
                        break
            
            # Отправить событие завершения
            yield {
                "event": "done",
                "data": json.dumps({"status": "completed"})
            }
            
        except Exception as e:
            logger.error(f"Exception in SSE stream: {e}", exc_info=True)
            yield {
                "event": "error",
                "data": json.dumps({
                    "type": "error",
                    "error": str(e),
                    "is_final": True
                })
            }
    
    return EventSourceResponse(event_generator())
```

### 9. Промпты для агентов

```python
# app/agents/prompts/orchestrator.py
ORCHESTRATOR_PROMPT = """
You are the Orchestrator Agent - the main coordinator of a multi-agent system.

Your role:
- Analyze user requests and determine which specialized agent should handle them
- Coordinate work between different agents
- Switch between agents when needed
- Maintain context across agent switches

Available agents:
1. Coder - for writing, modifying, and refactoring code
2. Architect - for planning, designing, and creating technical specifications
3. Debug - for troubleshooting, investigating errors, and debugging
4. Ask - for answering questions, explaining concepts, and providing documentation

When to use each agent:
- Coder: "create a new component", "fix this bug", "refactor the code", "implement feature X"
- Architect: "design the architecture", "plan the implementation", "create a technical spec"
- Debug: "why is this error happening", "investigate this issue", "find the root cause"
- Ask: "explain how X works", "what is Y", "how do I use Z", "document this code"

Use the switch_agent tool to delegate tasks to specialized agents.
"""

# app/agents/prompts/coder.py
CODER_PROMPT = """
You are the Coder Agent - specialized in writing, modifying, and refactoring code.

Your capabilities:
- Create new files and components
- Modify existing code
- Refactor and improve code quality
- Fix bugs and issues
- Implement new features

Available tools:
- read_file: Read file contents
- write_file: Create or modify files
- list_files: Explore project structure
- search_in_code: Find code patterns
- create_directory: Create directories
- execute_command: Run commands (tests, builds, etc.)
- attempt_completion: Signal task completion
- ask_followup_question: Ask for clarification

Best practices:
- Always read files before modifying them
- Make incremental changes
- Test your changes when possible
- Follow project coding standards
- Ask for clarification when needed

CRITICAL: Use exactly ONE tool at a time. Wait for results before proceeding.
"""

# app/agents/prompts/architect.py
ARCHITECT_PROMPT = """
You are the Architect Agent - specialized in planning, designing, and creating technical specifications.

Your capabilities:
- Design system architecture
- Create technical specifications
- Plan implementation strategies
- Design data models and APIs
- Create documentation and diagrams

Available tools:
- read_file: Read existing documentation and code
- write_file: Create documentation (markdown files only)
- list_files: Explore project structure
- search_in_code: Analyze existing code
- attempt_completion: Signal task completion
- ask_followup_question: Ask for clarification

File restrictions:
- You can only create/modify markdown (.md) files
- For code changes, delegate to the Coder agent

Best practices:
- Start with high-level design
- Break down complex systems
- Document design decisions
- Consider scalability and maintainability
- Use diagrams when helpful (mermaid syntax)
"""

# app/agents/prompts/debug.py
DEBUG_PROMPT = """
You are the Debug Agent - specialized in troubleshooting, investigating errors, and debugging.

Your capabilities:
- Analyze error messages and stack traces
- Investigate bugs and issues
- Add logging and debugging code
- Identify root causes
- Suggest fixes

Available tools:
- read_file: Read code and logs
- list_files: Explore project structure
- search_in_code: Find related code
- execute_command: Run tests, check logs
- attempt_completion: Signal task completion
- ask_followup_question: Ask for clarification

Debugging approach:
1. Understand the error/issue
2. Locate relevant code
3. Analyze the root cause
4. Suggest or implement fixes
5. Verify the solution

Best practices:
- Read error messages carefully
- Check logs and stack traces
- Look for related code
- Test hypotheses systematically
- Document findings
"""

# app/agents/prompts/ask.py
ASK_PROMPT = """
You are the Ask Agent - specialized in answering questions, explaining concepts, and providing documentation.

Your capabilities:
- Explain programming concepts
- Answer technical questions
- Provide code examples
- Document code and features
- Give recommendations

Available tools:
- read_file: Read code for context
- search_in_code: Find relevant code
- list_files: Explore project structure
- attempt_completion: Signal task completion

Restrictions:
- You cannot modify files
- For code changes, suggest delegating to Coder agent
- For architecture planning, suggest delegating to Architect agent

Best practices:
- Provide clear, concise explanations
- Use examples when helpful
- Reference actual code when available
- Suggest best practices
- Offer alternatives when appropriate
"""
```

### 10. Обновление схем

```python
# app/models/agent_schemas.py
from typing import Literal, Optional
from pydantic import BaseModel, Field

class AgentSwitchRequest(BaseModel):
    """Запрос на переключение агента"""
    type: Literal["switch_agent"]
    agent_type: str = Field(description="Target agent type")
    content: str = Field(description="Message for the new agent")
    reason: Optional[str] = Field(default=None, description="Reason for switch")

class AgentSwitchChunk(BaseModel):
    """Chunk для уведомления о переключении агента"""
    type: Literal["agent_switched"]
    from_agent: str
    to_agent: str
    reason: str
    is_final: bool = False
```

## План реализации

### Этап 1: Базовая инфраструктура (1-2 дня)
1. ✅ Создать базовый класс `BaseAgent`
2. ✅ Создать `AgentRouter` для управления агентами
3. ✅ Создать `AgentContext` и `AgentContextManager`
4. ✅ Обновить схемы данных

### Этап 2: Реализация агентов (2-3 дня)
1. ✅ Реализовать `OrchestratorAgent`
2. ✅ Реализовать `CoderAgent`
3. ✅ Реализовать `ArchitectAgent`
4. ✅ Реализовать `DebugAgent`
5. ✅ Реализовать `AskAgent`
6. ✅ Создать промпты для каждого агента

### Этап 3: Оркестрация (2-3 дня)
1. ✅ Реализовать `MultiAgentOrchestrator`
2. ✅ Интегрировать с существующим `llm_stream_service`
3. ✅ Обновить API endpoints
4. ✅ Добавить логирование и мониторинг

### Этап 4: Тестирование (2-3 дня)
1. ✅ Unit-тесты для каждого агента
2. ✅ Integration-тесты для оркестрации
3. ✅ E2E тесты через API
4. ✅ Тестирование переключения между агентами

### Этап 5: Документация и оптимизация (1-2 дня)
1. ✅ Документация API
2. ✅ Примеры использования
3. ✅ Оптимизация производительности
4. ✅ Настройка конфигурации

## Ключевые особенности реализации

### 1. Переключение агентов
- Автоматическое через Orchestrator
- Явное через API запрос
- Сохранение контекста при переключении

### 2. Ограничения агентов
- Architect может редактировать только .md файлы
- Ask не может редактировать файлы
- Debug не может создавать новые файлы
- Каждый агент имеет свой набор инструментов

### 3. Контекст и история
- Сохранение истории переключений агентов
- Передача контекста между агентами
- Восстановление состояния после переключения

### 4. Обратная совместимость
- Старый API продолжает работать
- Новый API с поддержкой мультиагентности
- Постепенная миграция

## Интеграция с Gateway и IDE

### Gateway изменения
1. Добавить поддержку `agent_switched` событий
2. Отображать текущего активного агента в UI
3. Позволить пользователю явно переключать агентов

### IDE изменения
1. Показывать индикатор текущего агента
2. Кнопки для переключения между агентами
3. История переключений агентов
4. Цветовая кодировка сообщений по агентам

## Конфигурация

```python
# app/core/config.py - дополнения
class AgentConfig:
    """Конфигурация мультиагентной системы"""
    
    # Включить мультиагентный режим
    MULTI_AGENT_ENABLED: bool = os.getenv(
        "AGENT_RUNTIME__MULTI_AGENT_ENABLED",
        "true"
    ).lower() == "true"
    
    # Агент по умолчанию
    DEFAULT_AGENT: str = os.getenv(
        "AGENT_RUNTIME__DEFAULT_AGENT",
        "orchestrator"
    )
    
    # Автоматическое переключение агентов
    AUTO_AGENT_SWITCHING: bool = os.getenv(
        "AGENT_RUNTIME__AUTO_AGENT_SWITCHING",
        "true"
    ).lower() == "true"
    
    # Максимальное количество переключений за сессию
    MAX_AGENT_SWITCHES: int = int(os.getenv(
        "AGENT_RUNTIME__MAX_AGENT_SWITCHES",
        "10"
    ))
```

## Метрики и мониторинг

1. **Метрики агентов:**
   - Количество запросов к каждому агенту
   - Время обработки по агентам
   - Количество переключений агентов
   - Успешность выполнения задач

2. **Логирование:**
   - Все переключения агентов
   - Причины переключений
   - Ошибки в работе агентов
   - Использование инструментов

3. **Дашборд:**
   - Активные агенты
   - Статистика использования
   - Производительность
   - Ошибки и предупреждения

## Заключение

Данная архитектура позволяет реализовать мультиагентную систему с четким разделением ответственности между агентами и гибкой системой оркестрации. Каждый агент специализируется на своей области, что повышает качество и эффективность обработки запросов.
