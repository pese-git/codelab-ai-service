# Диаграммы мультиагентной архитектуры

## 1. Общая архитектура системы

```mermaid
graph TB
    subgraph "IDE Client"
        UI[User Interface]
        WS[WebSocket Client]
    end
    
    subgraph "Gateway Service"
        GW[Gateway API]
        SSE[SSE Handler]
        ToolExec[Tool Executor]
    end
    
    subgraph "Agent Runtime Service"
        API[FastAPI Endpoints]
        MAO[Multi-Agent Orchestrator]
        
        subgraph "Agent Router"
            AR[Agent Router]
            ACM[Agent Context Manager]
        end
        
        subgraph "Agents"
            ORC[Orchestrator Agent]
            COD[Coder Agent]
            ARC[Architect Agent]
            DBG[Debug Agent]
            ASK[Ask Agent]
        end
        
        subgraph "Services"
            LLM[LLM Stream Service]
            SM[Session Manager]
            TR[Tool Registry]
        end
    end
    
    subgraph "LLM Proxy Service"
        LP[LLM Proxy]
        LITELLM[LiteLLM]
    end
    
    UI -->|User Message| WS
    WS -->|WebSocket| GW
    GW -->|SSE Request| API
    API -->|Process| MAO
    MAO -->|Route| AR
    AR -->|Get Agent| ORC
    AR -->|Get Agent| COD
    AR -->|Get Agent| ARC
    AR -->|Get Agent| DBG
    AR -->|Get Agent| ASK
    
    ORC -->|Use| LLM
    COD -->|Use| LLM
    ARC -->|Use| LLM
    DBG -->|Use| LLM
    ASK -->|Use| LLM
    
    LLM -->|Chat Completion| LP
    LP -->|Forward| LITELLM
    
    MAO -->|Tool Call| SSE
    SSE -->|Execute| ToolExec
    ToolExec -->|Result| WS
    WS -->|Display| UI
    
    style ORC fill:#ff9999
    style COD fill:#99ccff
    style ARC fill:#99ff99
    style DBG fill:#ffcc99
    style ASK fill:#cc99ff
```

## 2. Поток обработки сообщения

```mermaid
sequenceDiagram
    participant User
    participant Gateway
    participant API
    participant MAO as Multi-Agent<br/>Orchestrator
    participant AR as Agent Router
    participant ORC as Orchestrator<br/>Agent
    participant COD as Coder<br/>Agent
    participant LLM as LLM Service
    participant IDE
    
    User->>Gateway: Send message
    Gateway->>API: POST /agent/message/stream
    API->>MAO: process_message()
    
    MAO->>AR: get_current_agent()
    AR-->>MAO: Orchestrator Agent
    
    MAO->>ORC: process(message)
    ORC->>LLM: Analyze task type
    LLM-->>ORC: Task classification
    
    alt Task requires Coder
        ORC->>AR: switch_agent(CODER)
        AR-->>ORC: Agent switched
        ORC-->>MAO: switch_agent chunk
        MAO-->>Gateway: agent_switched event
        Gateway-->>User: Show agent switch
        
        MAO->>AR: get_agent(CODER)
        AR-->>MAO: Coder Agent
        MAO->>COD: process(message)
        
        COD->>LLM: Generate response
        LLM-->>COD: Tool call: write_file
        COD-->>MAO: tool_call chunk
        MAO-->>Gateway: tool_call event
        Gateway->>IDE: Execute write_file
        IDE-->>Gateway: Tool result
        Gateway->>API: Send tool_result
        
        API->>MAO: process_message(tool_result)
        MAO->>COD: process(tool_result)
        COD->>LLM: Continue with result
        LLM-->>COD: Final response
        COD-->>MAO: assistant_message chunk
        MAO-->>Gateway: assistant_message
        Gateway-->>User: Display response
    end
```

## 3. Переключение между агентами

```mermaid
stateDiagram-v2
    [*] --> Orchestrator: Initial request
    
    Orchestrator --> Coder: Coding task
    Orchestrator --> Architect: Design task
    Orchestrator --> Debug: Debug task
    Orchestrator --> Ask: Question
    
    Coder --> Orchestrator: Task complete
    Architect --> Orchestrator: Task complete
    Debug --> Orchestrator: Task complete
    Ask --> Orchestrator: Task complete
    
    Coder --> Debug: Found bug
    Debug --> Coder: Fix needed
    
    Architect --> Coder: Implementation needed
    Coder --> Architect: Design clarification
    
    Orchestrator --> [*]: Session end
    
    note right of Orchestrator
        Main coordinator
        Routes to specialists
    end note
    
    note right of Coder
        Write/modify code
        Create files
        Refactor
    end note
    
    note right of Architect
        Design systems
        Plan architecture
        Create specs
    end note
    
    note right of Debug
        Investigate errors
        Find root causes
        Add logging
    end note
    
    note right of Ask
        Answer questions
        Explain concepts
        Provide docs
    end note
```

## 4. Структура классов агентов

```mermaid
classDiagram
    class BaseAgent {
        <<abstract>>
        +AgentType agent_type
        +str system_prompt
        +List~str~ allowed_tools
        +List~str~ file_restrictions
        +process(session_id, message, context)* AsyncGenerator
        +can_use_tool(tool_name) bool
        +can_edit_file(file_path) bool
    }
    
    class OrchestratorAgent {
        +process() AsyncGenerator
        +route_to_agent() AgentType
        +analyze_task() str
    }
    
    class CoderAgent {
        +process() AsyncGenerator
        +validate_code_change() bool
    }
    
    class ArchitectAgent {
        +process() AsyncGenerator
        +validate_file_type() bool
    }
    
    class DebugAgent {
        +process() AsyncGenerator
        +analyze_error() Dict
    }
    
    class AskAgent {
        +process() AsyncGenerator
        +format_explanation() str
    }
    
    class AgentRouter {
        -Dict~AgentType, BaseAgent~ _agents
        +get_agent(agent_type) BaseAgent
        +get_current_agent(session_id) BaseAgent
        +switch_agent(session_id, target_agent, reason)
    }
    
    class AgentContext {
        +str session_id
        +AgentType current_agent
        +List agent_history
        +str task_description
        +Dict metadata
        +switch_agent(new_agent, reason)
    }
    
    class MultiAgentOrchestrator {
        +process_message(session_id, message, agent_type) AsyncGenerator
        -_classify_task(message) str
    }
    
    BaseAgent <|-- OrchestratorAgent
    BaseAgent <|-- CoderAgent
    BaseAgent <|-- ArchitectAgent
    BaseAgent <|-- DebugAgent
    BaseAgent <|-- AskAgent
    
    AgentRouter --> BaseAgent: manages
    AgentRouter --> AgentContext: uses
    MultiAgentOrchestrator --> AgentRouter: uses
    MultiAgentOrchestrator --> AgentContext: uses
```

## 5. Поток данных в сессии

```mermaid
graph LR
    subgraph "Session State"
        MSG[Messages History]
        CTX[Agent Context]
        TOOLS[Pending Tool Calls]
    end
    
    subgraph "Agent Processing"
        A1[Agent 1: Orchestrator]
        A2[Agent 2: Coder]
        A3[Agent 3: Debug]
    end
    
    subgraph "LLM Interaction"
        PROMPT[System Prompt]
        HIST[Message History]
        RESP[LLM Response]
    end
    
    MSG -->|Read| A1
    CTX -->|Current Agent| A1
    A1 -->|Switch| A2
    
    A2 -->|Build Context| PROMPT
    MSG -->|Add to| HIST
    PROMPT -->|Combine| HIST
    HIST -->|Send| RESP
    
    RESP -->|Tool Call| TOOLS
    TOOLS -->|Execute| MSG
    MSG -->|Update| A2
    
    A2 -->|Switch| A3
    A3 -->|Process| MSG
    
    style A1 fill:#ff9999
    style A2 fill:#99ccff
    style A3 fill:#ffcc99
```

## 6. Инструменты по агентам

```mermaid
graph TB
    subgraph "Orchestrator Tools"
        O1[read_file]
        O2[list_files]
        O3[search_in_code]
        O4[switch_agent]
    end
    
    subgraph "Coder Tools"
        C1[read_file]
        C2[write_file]
        C3[list_files]
        C4[search_in_code]
        C5[create_directory]
        C6[execute_command]
        C7[attempt_completion]
        C8[ask_followup_question]
    end
    
    subgraph "Architect Tools"
        A1[read_file]
        A2[write_file<br/>*.md only]
        A3[list_files]
        A4[search_in_code]
        A5[attempt_completion]
        A6[ask_followup_question]
    end
    
    subgraph "Debug Tools"
        D1[read_file]
        D2[list_files]
        D3[search_in_code]
        D4[execute_command]
        D5[attempt_completion]
        D6[ask_followup_question]
    end
    
    subgraph "Ask Tools"
        K1[read_file<br/>read-only]
        K2[search_in_code<br/>read-only]
        K3[list_files<br/>read-only]
        K4[attempt_completion]
    end
    
    style O4 fill:#ffcccc
    style C2 fill:#ffcccc
    style A2 fill:#ffcccc
    style C6 fill:#ffcccc
    style D4 fill:#ffcccc
```

## 7. Жизненный цикл сессии

```mermaid
sequenceDiagram
    participant User
    participant Gateway
    participant SessionManager
    participant AgentContextManager
    participant MultiAgentOrchestrator
    participant Agent
    
    User->>Gateway: Start conversation
    Gateway->>SessionManager: get_or_create(session_id)
    SessionManager-->>Gateway: Session created
    
    Gateway->>AgentContextManager: get_or_create(session_id)
    AgentContextManager-->>Gateway: Context created<br/>(default: Orchestrator)
    
    loop Message Processing
        User->>Gateway: Send message
        Gateway->>MultiAgentOrchestrator: process_message()
        MultiAgentOrchestrator->>AgentContextManager: get_context()
        AgentContextManager-->>MultiAgentOrchestrator: Current context
        
        MultiAgentOrchestrator->>Agent: process()
        Agent-->>MultiAgentOrchestrator: Stream chunks
        MultiAgentOrchestrator-->>Gateway: Forward chunks
        Gateway-->>User: Display response
        
        opt Agent Switch
            Agent->>AgentContextManager: switch_agent()
            AgentContextManager-->>Agent: Context updated
            Agent-->>User: Notify agent switch
        end
        
        opt Tool Execution
            Agent-->>Gateway: tool_call
            Gateway->>User: Execute tool
            User-->>Gateway: tool_result
            Gateway->>Agent: Continue with result
        end
    end
    
    User->>Gateway: End conversation
    Gateway->>SessionManager: delete(session_id)
    Gateway->>AgentContextManager: delete(session_id)
```

## 8. Конфигурация и расширяемость

```mermaid
graph TB
    subgraph "Configuration"
        ENV[Environment Variables]
        CONFIG[AppConfig]
        AGENT_CONFIG[AgentConfig]
    end
    
    subgraph "Agent Registry"
        REG[Agent Registry]
        FACTORY[Agent Factory]
    end
    
    subgraph "Custom Agents"
        CUSTOM1[Custom Agent 1]
        CUSTOM2[Custom Agent 2]
    end
    
    subgraph "Tool Registry"
        TOOLS[Tool Specifications]
        LOCAL[Local Tools]
        REMOTE[Remote Tools]
    end
    
    ENV -->|Load| CONFIG
    CONFIG -->|Configure| AGENT_CONFIG
    AGENT_CONFIG -->|Initialize| REG
    
    REG -->|Register| FACTORY
    FACTORY -->|Create| CUSTOM1
    FACTORY -->|Create| CUSTOM2
    
    CUSTOM1 -->|Use| TOOLS
    CUSTOM2 -->|Use| TOOLS
    
    TOOLS -->|Define| LOCAL
    TOOLS -->|Define| REMOTE
    
    style CUSTOM1 fill:#e6e6fa
    style CUSTOM2 fill:#e6e6fa
```

## Ключевые преимущества архитектуры

### 1. Модульность
- Каждый агент - независимый модуль
- Легко добавлять новых агентов
- Четкое разделение ответственности

### 2. Гибкость
- Динамическое переключение агентов
- Настраиваемые ограничения
- Расширяемый набор инструментов

### 3. Масштабируемость
- Агенты могут работать параллельно
- Кэширование контекстов
- Оптимизация LLM запросов

### 4. Безопасность
- Ограничения по файлам
- Валидация инструментов
- Контроль доступа

### 5. Наблюдаемость
- Логирование всех переключений
- Метрики по агентам
- Трассировка запросов
