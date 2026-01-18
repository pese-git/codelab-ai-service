"""
Agents роутер.

Предоставляет endpoints для работы с агентами.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends

from ..schemas.agent_schemas import (
    SwitchAgentRequest,
    GetAgentContextResponse,
    ListAgentsResponse,
    AgentInfoItem
)
from ....application.commands import SwitchAgentCommand, SwitchAgentHandler
from ....application.queries import GetAgentContextQuery, GetAgentContextHandler
from ....services.agent_router import agent_router
from ....core.errors import AgentSwitchError

logger = logging.getLogger("agent-runtime.api.agents")

router = APIRouter(prefix="/agents", tags=["agents"])


# Временные заглушки для dependencies
async def get_switch_agent_handler():
    """Временная заглушка для SwitchAgentHandler"""
    # TODO: Реализовать через DI в Этапе 5.6
    raise NotImplementedError("DI not configured yet")


async def get_get_agent_context_handler():
    """Временная заглушка для GetAgentContextHandler"""
    # TODO: Реализовать через DI в Этапе 5.6
    raise NotImplementedError("DI not configured yet")


@router.get("", response_model=ListAgentsResponse)
async def list_agents() -> ListAgentsResponse:
    """
    Получить список всех зарегистрированных агентов.
    
    Возвращает информацию о всех доступных агентах,
    их возможностях и ограничениях.
    
    Returns:
        ListAgentsResponse: Список агентов
        
    Пример ответа:
        {
            "agents": [
                {
                    "type": "orchestrator",
                    "name": "Orchestrator Agent",
                    "description": "Routes tasks to specialized agents",
                    "allowed_tools": ["read_file", "list_files", "search_in_code"],
                    "has_file_restrictions": true
                },
                {
                    "type": "coder",
                    "name": "Coder Agent",
                    "description": "Specialized in writing and modifying code",
                    "allowed_tools": ["read_file", "write_file", "execute_command", ...],
                    "has_file_restrictions": false
                },
                ...
            ],
            "total": 5
        }
    """
    logger.debug("Listing all registered agents")
    
    agents_info = []
    for agent_type in agent_router.list_agents():
        agent = agent_router.get_agent(agent_type)
        
        # Извлечь первую строку system prompt как описание
        description = agent.system_prompt.split('\n')[0] if agent.system_prompt else ""
        
        agent_info = AgentInfoItem(
            type=agent.agent_type.value,
            name=f"{agent.agent_type.value.capitalize()} Agent",
            description=description,
            allowed_tools=agent.get_allowed_tools(),
            has_file_restrictions=bool(agent.file_restrictions)
        )
        agents_info.append(agent_info)
    
    logger.info(f"Returning info for {len(agents_info)} agents")
    
    return ListAgentsResponse(
        agents=agents_info,
        total=len(agents_info)
    )


@router.get("/{session_id}/current", response_model=GetAgentContextResponse)
async def get_current_agent(
    session_id: str,
    include_history: bool = False,
    handler: GetAgentContextHandler = Depends(get_get_agent_context_handler)
) -> GetAgentContextResponse:
    """
    Получить текущего агента для сессии.
    
    Args:
        session_id: ID сессии
        include_history: Включить ли историю переключений
        handler: Query handler (инжектируется)
        
    Returns:
        GetAgentContextResponse: Информация о текущем агенте
        
    Raises:
        HTTPException 404: Если сессия не найдена
        HTTPException 500: При внутренней ошибке
        
    Пример запроса:
        GET /agents/session-123/current?include_history=true
        
    Пример ответа:
        {
            "context": {
                "id": "ctx-1",
                "session_id": "session-123",
                "current_agent": "coder",
                "switch_count": 2,
                "switch_history": [...]
            }
        }
    """
    try:
        # Создать запрос
        query = GetAgentContextQuery(
            session_id=session_id,
            include_history=include_history
        )
        
        # Выполнить через handler
        context_dto = await handler.handle(query)
        
        if not context_dto:
            raise HTTPException(
                status_code=404,
                detail=f"Agent context for session {session_id} not found"
            )
        
        logger.debug(f"Retrieved agent context for session: {session_id}")
        
        return GetAgentContextResponse(context=context_dto)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting agent context for {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{session_id}/switch")
async def switch_agent(
    session_id: str,
    request: SwitchAgentRequest,
    handler: SwitchAgentHandler = Depends(get_switch_agent_handler)
):
    """
    Переключить агента для сессии.
    
    Args:
        session_id: ID сессии
        request: Запрос на переключение
        handler: Command handler (инжектируется)
        
    Returns:
        Информация об обновленном контексте
        
    Raises:
        HTTPException 400: Если переключение невозможно
        HTTPException 404: Если сессия не найдена
        HTTPException 500: При внутренней ошибке
        
    Пример запроса:
        POST /agents/session-123/switch
        {
            "target_agent": "coder",
            "reason": "User requested code changes",
            "confidence": "high"
        }
        
    Пример ответа:
        {
            "context": {
                "id": "ctx-1",
                "session_id": "session-123",
                "current_agent": "coder",
                "switch_count": 3,
                ...
            }
        }
    """
    try:
        # Создать команду
        command = SwitchAgentCommand(
            session_id=session_id,
            target_agent=request.target_agent,
            reason=request.reason,
            confidence=request.confidence
        )
        
        # Выполнить через handler
        context_dto = await handler.handle(command)
        
        logger.info(
            f"Switched agent for session {session_id} to {request.target_agent}"
        )
        
        return GetAgentContextResponse(context=context_dto)
        
    except AgentSwitchError as e:
        logger.warning(f"Agent switch failed: {e.message}")
        raise HTTPException(status_code=400, detail=e.message)
    except ValueError as e:
        logger.warning(f"Invalid agent type: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error switching agent for {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
