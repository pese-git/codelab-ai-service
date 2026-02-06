"""
Mapper для преобразования между Agent Entity и AgentContextModel.

Изолирует доменный слой от деталей персистентности.
Использует новую Agent entity вместо старой AgentContext.
"""

import json
import logging
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ....domain.agent_context.entities import Agent, AgentSwitchRecord
from ....domain.agent_context.value_objects import AgentId, AgentCapabilities, AgentType
from ..models import AgentContextModel, AgentSwitchModel

logger = logging.getLogger("agent-runtime.infrastructure.agent_mapper")


class AgentMapper:
    """
    Mapper между доменной сущностью Agent и моделью БД AgentContextModel.
    
    Отвечает за преобразование данных между доменным слоем
    и слоем персистентности.
    
    Пример:
        >>> mapper = AgentMapper()
        >>> # Entity -> Model
        >>> model = await mapper.to_model(agent, db)
        >>> # Model -> Entity
        >>> entity = await mapper.to_entity(model, db)
    """
    
    async def to_entity(
        self,
        model: AgentContextModel,
        db: AsyncSession,
        load_switches: bool = True
    ) -> Agent:
        """
        Преобразовать модель БД в доменную сущность Agent.
        
        Args:
            model: Модель БД AgentContextModel
            db: Сессия БД для загрузки связанных данных
            load_switches: Загружать ли историю переключений
            
        Returns:
            Доменная сущность Agent
            
        Пример:
            >>> agent = await mapper.to_entity(agent_model, db)
        """
        # Загрузить историю переключений если требуется
        switch_history: List[AgentSwitchRecord] = []
        if load_switches:
            result = await db.execute(
                select(AgentSwitchModel)
                .where(AgentSwitchModel.context_db_id == model.id)
                .order_by(AgentSwitchModel.switched_at.asc())
            )
            switch_models = result.scalars().all()
            
            # Преобразовать модели переключений в сущности
            for switch_model in switch_models:
                # Парсинг metadata из JSON
                metadata = {}
                if switch_model.metadata_json:
                    try:
                        metadata = json.loads(switch_model.metadata_json)
                    except json.JSONDecodeError:
                        logger.warning(
                            f"Failed to parse metadata for switch {switch_model.id}"
                        )
                
                # Преобразовать строки в AgentType
                from_agent = None
                if switch_model.from_agent:
                    try:
                        from_agent = AgentType(switch_model.from_agent)
                    except ValueError:
                        logger.warning(
                            f"Invalid from_agent type: {switch_model.from_agent}"
                        )
                
                try:
                    to_agent = AgentType(switch_model.to_agent)
                except ValueError:
                    logger.warning(
                        f"Invalid to_agent type: {switch_model.to_agent}"
                    )
                    continue
                
                switch_record = AgentSwitchRecord(
                    id=switch_model.id,
                    from_agent=from_agent,
                    to_agent=to_agent,
                    reason=switch_model.reason or "",
                    switched_at=switch_model.switched_at,
                    confidence=metadata.get("confidence")
                )
                switch_history.append(switch_record)
        
        # Парсинг metadata агента
        agent_metadata = {}
        if model.metadata_json:
            try:
                agent_metadata = json.loads(model.metadata_json)
            except json.JSONDecodeError:
                logger.warning(
                    f"Failed to parse metadata for agent {model.id}"
                )
        
        # Преобразовать current_agent в AgentType
        try:
            current_type = AgentType(model.current_agent)
        except ValueError:
            logger.warning(
                f"Invalid current_agent type: {model.current_agent}, defaulting to ORCHESTRATOR"
            )
            current_type = AgentType.ORCHESTRATOR
        
        # Создать AgentCapabilities для текущего типа
        capabilities = AgentCapabilities.for_agent_type(current_type)
        
        # Определить last_switch_at из истории
        last_switch_at = None
        if switch_history:
            last_switch_at = switch_history[-1].switched_at
        
        # Создать доменную сущность
        agent = Agent(
            id=model.id,
            session_id=model.session_db_id,
            capabilities=capabilities,
            switch_history=switch_history,
            metadata=agent_metadata,
            last_switch_at=last_switch_at,
            switch_count=model.switch_count,
            created_at=model.created_at,
            updated_at=model.updated_at
        )
        
        return agent
    
    async def to_model(
        self,
        entity: Agent,
        db: AsyncSession
    ) -> AgentContextModel:
        """
        Преобразовать доменную сущность Agent в модель БД.
        
        Также сохраняет связанную историю переключений.
        
        Args:
            entity: Доменная сущность Agent
            db: Сессия БД
            
        Returns:
            Модель БД AgentContextModel
            
        Пример:
            >>> agent_model = await mapper.to_model(agent, db)
        """
        # Получить существующую модель или создать новую
        result = await db.execute(
            select(AgentContextModel).where(
                AgentContextModel.id == entity.id
            )
        )
        model = result.scalar_one_or_none()
        
        # Сериализовать metadata
        metadata_json = None
        if entity.metadata:
            try:
                metadata_json = json.dumps(entity.metadata)
            except (TypeError, ValueError) as e:
                logger.warning(f"Failed to serialize metadata: {e}")
        
        if not model:
            # Создать новую модель
            model = AgentContextModel(
                id=entity.id,
                session_db_id=entity.session_id,
                current_agent=entity.current_type.value,
                created_at=entity.created_at,
                updated_at=entity.updated_at,
                switch_count=entity.switch_count,
                metadata_json=metadata_json
            )
            db.add(model)
            await db.flush()  # Получить ID
            logger.debug(f"Created new AgentContextModel for {entity.id}")
        else:
            # Обновить существующую модель
            model.current_agent = entity.current_type.value
            model.updated_at = entity.updated_at
            model.switch_count = entity.switch_count
            model.metadata_json = metadata_json
            logger.debug(f"Updated AgentContextModel for {entity.id}")
        
        # Сохранить историю переключений (атомарная замена)
        from sqlalchemy import delete
        await db.execute(
            delete(AgentSwitchModel).where(AgentSwitchModel.context_db_id == model.id)
        )
        
        # Добавить новые записи переключений
        for switch_record in entity.switch_history:
            # Подготовить metadata для переключения
            switch_metadata = {}
            if switch_record.confidence:
                switch_metadata["confidence"] = switch_record.confidence
            
            switch_metadata_json = None
            if switch_metadata:
                try:
                    switch_metadata_json = json.dumps(switch_metadata)
                except (TypeError, ValueError) as e:
                    logger.warning(f"Failed to serialize switch metadata: {e}")
            
            switch_model = AgentSwitchModel(
                id=switch_record.id,
                context_db_id=model.id,
                from_agent=switch_record.from_agent.value if switch_record.from_agent else None,
                to_agent=switch_record.to_agent.value,
                switched_at=switch_record.switched_at,
                reason=switch_record.reason,
                metadata_json=switch_metadata_json
            )
            db.add(switch_model)
        
        return model
