"""
Sessions роутер.

Предоставляет endpoints для работы с сессиями диалога.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends, Body
from fastapi.responses import JSONResponse

from ..schemas.session_schemas import (
    CreateSessionRequest,
    CreateSessionResponse,
    GetSessionResponse,
    ListSessionsResponse
)
from ....application.commands import CreateSessionCommand, CreateSessionHandler
from ....application.queries import (
    GetSessionQuery,
    GetSessionHandler,
    ListSessionsQuery,
    ListSessionsHandler
)
from ....core.errors import SessionNotFoundError, SessionAlreadyExistsError
from ....core.dependencies_new import (
    get_create_session_handler,
    get_get_session_handler,
    get_list_sessions_handler
)

logger = logging.getLogger("agent-runtime.api.sessions")

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=CreateSessionResponse, status_code=201)
async def create_session(
    request: CreateSessionRequest = Body(default=CreateSessionRequest()),
    handler: CreateSessionHandler = Depends(get_create_session_handler)
) -> CreateSessionResponse:
    """
    Создать новую сессию.
    
    Args:
        request: Запрос на создание сессии
        handler: Command handler (инжектируется)
        
    Returns:
        CreateSessionResponse: Информация о созданной сессии
        
    Raises:
        HTTPException 409: Если сессия с таким ID уже существует
        HTTPException 500: При внутренней ошибке
        
    Пример запроса:
        POST /sessions
        {
            "session_id": "session-123"
        }
        
    Пример ответа:
        {
            "id": "session-123",
            "created_at": "2026-01-18T21:00:00Z",
            "is_active": true,
            "current_agent": "orchestrator"
        }
    """
    try:
        # Создать команду
        command = CreateSessionCommand(session_id=request.session_id)
        
        # Выполнить через handler
        session_dto = await handler.handle(command)
        
        logger.info(f"Created new session: {session_dto.id}")
        
        # Вернуть ответ в формате совместимом с Gateway
        return CreateSessionResponse(
            id=session_dto.id,
            message_count=0,  # Новая сессия всегда имеет 0 сообщений
            created_at=session_dto.created_at,
            is_active=session_dto.is_active,
            current_agent="orchestrator"  # Новые сессии всегда начинают с orchestrator
        )
        
    except SessionAlreadyExistsError as e:
        logger.warning(f"Session already exists: {e.message}")
        raise HTTPException(status_code=409, detail=e.message)
    except Exception as e:
        logger.error(f"Error creating session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{session_id}", response_model=GetSessionResponse)
async def get_session(
    session_id: str,
    include_messages: bool = False,
    handler: GetSessionHandler = Depends(get_get_session_handler)
) -> GetSessionResponse:
    """
    Получить сессию по ID.
    
    Args:
        session_id: ID сессии
        include_messages: Включить ли сообщения в ответ
        handler: Query handler (инжектируется)
        
    Returns:
        GetSessionResponse: Данные сессии
        
    Raises:
        HTTPException 404: Если сессия не найдена
        HTTPException 500: При внутренней ошибке
        
    Пример запроса:
        GET /sessions/session-123?include_messages=true
        
    Пример ответа:
        {
            "session": {
                "id": "session-123",
                "title": "Создание виджета",
                "message_count": 5,
                "messages": [...],
                "is_active": true,
                ...
            }
        }
    """
    try:
        # Создать запрос
        query = GetSessionQuery(
            session_id=session_id,
            include_messages=include_messages
        )
        
        # Выполнить через handler
        session_dto = await handler.handle(query)
        
        if not session_dto:
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found"
            )
        
        logger.debug(f"Retrieved session: {session_id}")
        
        return GetSessionResponse(session=session_dto)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("", response_model=ListSessionsResponse)
async def list_sessions(
    limit: int = 100,
    offset: int = 0,
    active_only: bool = True,
    handler: ListSessionsHandler = Depends(get_list_sessions_handler)
) -> ListSessionsResponse:
    """
    Получить список сессий.
    
    Args:
        limit: Максимальное количество сессий (1-1000)
        offset: Смещение от начала списка
        active_only: Только активные сессии
        handler: Query handler (инжектируется)
        
    Returns:
        ListSessionsResponse: Список сессий
        
    Raises:
        HTTPException 400: Если параметры некорректны
        HTTPException 500: При внутренней ошибке
        
    Пример запроса:
        GET /sessions?limit=10&offset=0&active_only=true
        
    Пример ответа:
        {
            "sessions": [
                {
                    "id": "session-1",
                    "title": "Создание виджета",
                    "message_count": 5,
                    "last_activity": "2026-01-18T21:00:00Z",
                    "is_active": true,
                    "current_agent": "coder"
                },
                ...
            ],
            "total": 25,
            "limit": 10,
            "offset": 0
        }
    """
    try:
        # Валидация параметров
        if limit < 1 or limit > 1000:
            raise HTTPException(
                status_code=400,
                detail="Limit must be between 1 and 1000"
            )
        
        if offset < 0:
            raise HTTPException(
                status_code=400,
                detail="Offset must be >= 0"
            )
        
        # Создать запрос
        query = ListSessionsQuery(
            limit=limit,
            offset=offset,
            active_only=active_only
        )
        
        # Выполнить через handler
        sessions = await handler.handle(query)
        
        logger.debug(f"Listed {len(sessions)} sessions")
        
        return ListSessionsResponse(
            sessions=sessions,
            total=len(sessions),  # TODO: Добавить count query для точного total
            limit=limit,
            offset=offset
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing sessions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{session_id}/history")
async def get_session_history(
    session_id: str,
    handler: GetSessionHandler = Depends(get_get_session_handler)
):
    """
    Получить историю сообщений для сессии.
    
    Этот endpoint позволяет IDE восстановить историю чата после перезапуска.
    
    Args:
        session_id: ID сессии
        handler: Query handler (инжектируется)
        
    Returns:
        История сессии с сообщениями и метаданными
        
    Raises:
        HTTPException 404: Если сессия не найдена
        HTTPException 500: При внутренней ошибке
        
    Пример запроса:
        GET /sessions/session-123/history
        
    Пример ответа:
        {
            "session_id": "session-123",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi!"}
            ],
            "message_count": 2,
            "last_activity": "2026-01-20T04:00:00Z",
            "current_agent": "coder",
            "agent_history": [...]
        }
    """
    logger.debug(f"Getting history for session {session_id}")
    
    try:
        # Использовать GetSessionHandler для загрузки сессии с сообщениями из БД
        query = GetSessionQuery(
            session_id=session_id,
            include_messages=True  # Загрузить сообщения
        )
        
        session_dto = await handler.handle(query)
        
        if not session_dto:
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found"
            )
        
        # Преобразовать сообщения в формат для LLM API
        messages = []
        if session_dto.messages:
            for msg in session_dto.messages:
                message_dict = {
                    "role": msg.role,
                    "content": msg.content
                }
                if msg.name:
                    message_dict["name"] = msg.name
                if msg.tool_call_id:
                    message_dict["tool_call_id"] = msg.tool_call_id
                if msg.tool_calls:
                    message_dict["tool_calls"] = msg.tool_calls
                messages.append(message_dict)
        
        # Получить информацию о текущем агенте из agent_context_manager_adapter
        current_agent = None
        agent_history = []
        try:
            from ....main import agent_context_manager_adapter
            if agent_context_manager_adapter:
                agent_context = agent_context_manager_adapter.get(session_id)
                if agent_context:
                    current_agent = agent_context.current_agent
                    agent_history = agent_context.get_agent_history()
        except Exception as e:
            logger.warning(f"Could not load agent context for {session_id}: {e}")
        
        return {
            "session_id": session_id,
            "messages": messages,
            "message_count": session_dto.message_count,
            "last_activity": session_dto.last_activity.isoformat(),
            "current_agent": current_agent.value if current_agent else None,
            "agent_history": agent_history
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session history for {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{session_id}/pending-approvals")
async def get_pending_approvals(session_id: str):
    """
    Получить все pending approval запросы для сессии.
    
    Этот endpoint используется IDE для восстановления pending approvals
    после перезапуска или переустановки.
    
    Args:
        session_id: ID сессии
        
    Returns:
        Список pending approval запросов с деталями
        
    Raises:
        HTTPException 404: Если сессия не найдена
        HTTPException 500: При внутренней ошибке
        
    Пример запроса:
        GET /sessions/session-123/pending-approvals
        
    Пример ответа:
        {
            "session_id": "session-123",
            "pending_approvals": [
                {
                    "call_id": "call-1",
                    "tool_name": "write_file",
                    "arguments": {"path": "test.py", "content": "..."},
                    "reason": "File modification requires approval",
                    "created_at": "2026-01-20T04:00:00Z"
                }
            ],
            "count": 1
        }
    """
    logger.debug(f"Getting pending approvals for session {session_id}")
    
    try:
        # Получить адаптер из глобального контекста
        from ....main import session_manager_adapter
        from ....services.hitl_manager import hitl_manager
        
        if not session_manager_adapter:
            raise HTTPException(
                status_code=503,
                detail="Session manager not initialized"
            )
        
        # Проверить существование сессии
        if not session_manager_adapter.exists(session_id):
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found"
            )
        
        # Получить pending approvals из HITL manager (загружает из БД)
        pending_approvals = hitl_manager.get_all_pending(session_id)
        
        return {
            "session_id": session_id,
            "pending_approvals": [
                {
                    "call_id": p.call_id,
                    "tool_name": p.tool_name,
                    "arguments": p.arguments,
                    "reason": p.reason,
                    "created_at": p.created_at.isoformat() if p.created_at else None
                }
                for p in pending_approvals
            ],
            "count": len(pending_approvals)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting pending approvals for {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
