"""
Sessions роутер.

Предоставляет endpoints для работы с сессиями диалога.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends
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

logger = logging.getLogger("agent-runtime.api.sessions")

router = APIRouter(prefix="/sessions", tags=["sessions"])


# Временные заглушки для dependencies (будут заменены в Этапе 5.6)
async def get_create_session_handler():
    """Временная заглушка для CreateSessionHandler"""
    # TODO: Реализовать через DI в Этапе 5.6
    raise NotImplementedError("DI not configured yet")


async def get_get_session_handler():
    """Временная заглушка для GetSessionHandler"""
    # TODO: Реализовать через DI в Этапе 5.6
    raise NotImplementedError("DI not configured yet")


async def get_list_sessions_handler():
    """Временная заглушка для ListSessionsHandler"""
    # TODO: Реализовать через DI в Этапе 5.6
    raise NotImplementedError("DI not configured yet")


@router.post("", response_model=CreateSessionResponse, status_code=201)
async def create_session(
    request: CreateSessionRequest,
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
            "session_id": "session-123",
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
        
        # Вернуть ответ
        return CreateSessionResponse(
            session_id=session_dto.id,
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
