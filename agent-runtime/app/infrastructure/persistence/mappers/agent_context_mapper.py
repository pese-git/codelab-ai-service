"""
Маппер для преобразования между AgentContext Entity и AgentContextModel.

Изолирует доменный слой от деталей персистентности.
"""

import json
import logging
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from ....domain.entities.agent_context import AgentContext, AgentType, AgentSwitch
from ..models import AgentContextModel, AgentSwitchModel, SessionModel

logger = logging.getLogger("agent-runtime.infrastructure.agent_context_mapper")


class AgentContextMapper:
    """
    Маппер между доменной сущностью AgentContext и моделью БД AgentContextModel.
    
    Отвечает за преобразование данных между доменным слоем
    и слоем персистентности.
    
    Пример:
        >>> mapper = AgentContextMapper()
        >>> # Entity -> Model
        >>> model = await mapper.to_model(context, db)
        >>> # Model -> Entity
        >>> entity = await mapper.to_entity(model, db)
    """
    
    async def to_entity(
        self,
        model: AgentContextModel,
        db: AsyncSession,
        load_history: bool = True
    ) -> AgentContext:
        """
        Преобразовать модель БД в доменную сущность.
        
        Args:
            model: Модель БД
            db: Сессия БД для загрузки связанных данных
            load_history: Загружать ли историю переключений
            
        Returns:
            Доменная сущность AgentContext
            
        Пример:
            >>> context_entity = await mapper.to_entity(context_model, db)
        """
        # Загрузить историю переключений если требуется
        switch_history: List[AgentSwitch] = []
        last_switch_at = None
        
        if load_history:
            result = await db.execute(
                select(AgentSwitchModel)
                .where(AgentSwitchModel.context_db_id == model.id)
                .order_by(AgentSwitchModel.switched_at.asc())
            )
            switch_models = result.scalars().all()
            
            # Преобразовать модели переключений в сущности
            for switch_model in switch_models:
                # Парсинг metadata из JSON
                switch_metadata = {}
                if switch_model.metadata_json:
                    try:
                        switch_metadata = json.loads(switch_model.metadata_json)
                    except json.JSONDecodeError:
                        logger.warning(
                            f"Failed to parse metadata for switch {switch_model.id}"
                        )
                
                # Преобразовать строки агентов в AgentType
                from_agent = None
                if switch_model.from_agent:
                    try:
                        from_agent = AgentType(switch_model.from_agent)
                    except ValueError:
                        logger.warning(
                            f"Unknown agent type: {switch_model.from_agent}"
                        )
                
                try:
                    to_agent = AgentType(switch_model.to_agent)
                except ValueError:
                    logger.warning(f"Unknown agent type: {switch_model.to_agent}")
                    continue  # Пропустить некорректную запись
                
                switch = AgentSwitch(
                    id=switch_model.id,
                    from_agent=from_agent,
                    to_agent=to_agent,
                    reason=switch_model.reason or "",
                    switched_at=switch_model.switched_at,
                    confidence=switch_metadata.get("confidence"),
                    metadata=switch_metadata,
                    created_at=switch_model.switched_at
                )
                switch_history.append(switch)
                last_switch_at = switch_model.switched_at
        
        # Парсинг metadata контекста из JSON
        context_metadata = {}
        if model.metadata_json:
            try:
                context_metadata = json.loads(model.metadata_json)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse metadata for context {model.id}")
        
        # Преобразовать строку агента в AgentType
        try:
            current_agent = AgentType(model.current_agent)
        except ValueError:
            logger.warning(
                f"Unknown agent type: {model.current_agent}, "
                f"defaulting to ORCHESTRATOR"
            )
            current_agent = AgentType.ORCHESTRATOR
        
        # Получить session_id из связанной сессии
        result = await db.execute(
            select(SessionModel.id).where(SessionModel.id == model.session_db_id)
        )
        session_id = result.scalar_one()
        
        # Создать доменную сущность
        context = AgentContext(
            id=model.id,
            session_id=session_id,
            current_agent=current_agent,
            switch_history=switch_history,
            metadata=context_metadata,
            created_at=model.created_at,
            updated_at=model.updated_at,
            last_switch_at=last_switch_at,
            switch_count=model.switch_count
        )
        
        return context
    
    async def to_model(
        self,
        entity: AgentContext,
        db: AsyncSession
    ) -> AgentContextModel:
        """
        Преобразовать доменную сущность в модель БД.
        
        Также сохраняет историю переключений.
        
        Args:
            entity: Доменная сущность
            db: Сессия БД
            
        Returns:
            Модель БД AgentContextModel
            
        Пример:
            >>> context_model = await mapper.to_model(context_entity, db)
        """
        # Получить ID сессии в БД
        result = await db.execute(
            select(SessionModel).where(
                SessionModel.id == entity.session_id,
                SessionModel.deleted_at.is_(None)
            )
        )
        session_model = result.scalar_one_or_none()
        
        if not session_model:
            raise ValueError(
                f"Session {entity.session_id} not found in database"
            )
        
        # Получить существующую модель или создать новую
        result = await db.execute(
            select(AgentContextModel).where(
                AgentContextModel.session_db_id == session_model.id
            )
        )
        model = result.scalar_one_or_none()
        
        # Сериализация metadata в JSON
        metadata_json = json.dumps(entity.metadata) if entity.metadata else None
        
        if not model:
            # Создать новую модель
            model = AgentContextModel(
                id=entity.id,
                session_db_id=session_model.id,
                current_agent=entity.current_agent.value,
                created_at=entity.created_at,
                updated_at=entity.updated_at or entity.created_at,
                switch_count=entity.switch_count,
                metadata_json=metadata_json
            )
            db.add(model)
            await db.flush()
            logger.debug(f"Created new AgentContextModel for {entity.id}")
        else:
            # Обновить существующую модель
            model.current_agent = entity.current_agent.value
            model.updated_at = entity.updated_at or entity.created_at
            model.switch_count = entity.switch_count
            model.metadata_json = metadata_json
            logger.debug(f"Updated AgentContextModel for {entity.id}")
        
        # Сохранить историю переключений (атомарная замена)
        await db.execute(
            delete(AgentSwitchModel).where(
                AgentSwitchModel.context_db_id == model.id
            )
        )
        
        # Добавить новые записи переключений
        for switch in entity.switch_history:
            switch_metadata_json = json.dumps(switch.metadata) if switch.metadata else None
            
            switch_model = AgentSwitchModel(
                id=switch.id,
                context_db_id=model.id,
                from_agent=switch.from_agent.value if switch.from_agent else None,
                to_agent=switch.to_agent.value,
                switched_at=switch.switched_at,
                reason=switch.reason,
                metadata_json=switch_metadata_json
            )
            db.add(switch_model)
        
        return model
