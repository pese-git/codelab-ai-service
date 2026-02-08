"""
Диагностический скрипт для проверки сохранения сообщений в таблицу messages.

Проверяет:
1. Схему таблицы messages
2. Процесс сохранения через ConversationMapper
3. Транзакции и commit
4. Фактическое наличие данных в БД
"""

import asyncio
import logging
import sys
from datetime import datetime, timezone
from sqlalchemy import text, inspect
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Импорты из приложения
sys.path.insert(0, '/Users/sergey/Projects/OpenIdeaLab/codelab-workspace/codelab-ai-service/agent-runtime')

from app.infrastructure.persistence.models import SessionModel, MessageModel, Base
from app.infrastructure.persistence.mappers import ConversationMapper
from app.domain.session_context.entities import Conversation
from app.domain.session_context.value_objects import ConversationId, MessageCollection
from app.domain.entities.message import Message


async def check_database_schema(engine):
    """Проверить схему таблицы messages."""
    logger.info("=" * 80)
    logger.info("ПРОВЕРКА СХЕМЫ ТАБЛИЦЫ MESSAGES")
    logger.info("=" * 80)
    
    async with engine.connect() as conn:
        # Проверить существование таблицы
        result = await conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'messages'
            );
        """))
        exists = result.scalar()
        logger.info(f"Таблица messages существует: {exists}")
        
        if not exists:
            logger.error("❌ КРИТИЧЕСКАЯ ОШИБКА: Таблица messages не существует!")
            return False
        
        # Получить структуру таблицы
        result = await conn.execute(text("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'messages'
            ORDER BY ordinal_position;
        """))
        
        logger.info("\nСтруктура таблицы messages:")
        for row in result:
            logger.info(f"  - {row[0]}: {row[1]} (nullable={row[2]}, default={row[3]})")
        
        # Проверить индексы
        result = await conn.execute(text("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'messages';
        """))
        
        logger.info("\nИндексы таблицы messages:")
        for row in result:
            logger.info(f"  - {row[0]}: {row[1]}")
        
        # Проверить внешние ключи
        result = await conn.execute(text("""
            SELECT
                tc.constraint_name,
                tc.table_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_name = 'messages';
        """))
        
        logger.info("\nВнешние ключи таблицы messages:")
        for row in result:
            logger.info(f"  - {row[0]}: {row[2]} -> {row[3]}.{row[4]}")
        
        return True


async def check_current_data(engine):
    """Проверить текущие данные в таблице."""
    logger.info("\n" + "=" * 80)
    logger.info("ПРОВЕРКА ТЕКУЩИХ ДАННЫХ")
    logger.info("=" * 80)
    
    async with engine.connect() as conn:
        # Количество сессий
        result = await conn.execute(text("SELECT COUNT(*) FROM sessions WHERE deleted_at IS NULL"))
        sessions_count = result.scalar()
        logger.info(f"Активных сессий: {sessions_count}")
        
        # Количество сообщений
        result = await conn.execute(text("SELECT COUNT(*) FROM messages"))
        messages_count = result.scalar()
        logger.info(f"Всего сообщений: {messages_count}")
        
        # Последние 5 сессий
        result = await conn.execute(text("""
            SELECT id, title, created_at, 
                   (SELECT COUNT(*) FROM messages WHERE session_db_id = sessions.id) as msg_count
            FROM sessions 
            WHERE deleted_at IS NULL
            ORDER BY created_at DESC 
            LIMIT 5
        """))
        
        logger.info("\nПоследние 5 сессий:")
        for row in result:
            logger.info(f"  - {row[0][:8]}... | {row[1] or 'No title'} | messages: {row[3]}")
        
        # Последние 10 сообщений
        result = await conn.execute(text("""
            SELECT id, session_db_id, role, 
                   SUBSTRING(content, 1, 50) as content_preview,
                   timestamp
            FROM messages 
            ORDER BY timestamp DESC 
            LIMIT 10
        """))
        
        logger.info("\nПоследние 10 сообщений:")
        for row in result:
            logger.info(f"  - {row[0][:8]}... | session: {row[1][:8]}... | {row[2]} | {row[3] or 'NULL'}")


async def test_save_operation(engine):
    """Тестировать операцию сохранения."""
    logger.info("\n" + "=" * 80)
    logger.info("ТЕСТ СОХРАНЕНИЯ СООБЩЕНИЙ")
    logger.info("=" * 80)
    
    # Создать сессию
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as db:
        try:
            # Создать тестовую conversation
            conv_id = ConversationId(f"test-diag-{datetime.now(timezone.utc).timestamp()}")
            
            messages = [
                Message(
                    id=f"msg-1-{datetime.now(timezone.utc).timestamp()}",
                    role="user",
                    content="Test user message",
                    created_at=datetime.now(timezone.utc)
                ),
                Message(
                    id=f"msg-2-{datetime.now(timezone.utc).timestamp()}",
                    role="assistant",
                    content="Test assistant response",
                    created_at=datetime.now(timezone.utc)
                )
            ]
            
            conversation = Conversation(
                id=conv_id.value,
                conversation_id=conv_id,
                messages=MessageCollection(messages=messages),
                title="Test Diagnostic Session",
                description="Testing message save",
                last_activity=datetime.now(timezone.utc),
                is_active=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                metadata={}
            )
            
            logger.info(f"Создана тестовая conversation: {conv_id.value}")
            logger.info(f"Количество сообщений: {len(messages)}")
            
            # Использовать mapper для сохранения
            mapper = ConversationMapper()
            
            logger.info("\n--- Вызов mapper.to_model() ---")
            model = await mapper.to_model(conversation, db)
            logger.info(f"SessionModel создан: {model.id}")
            
            logger.info("\n--- Вызов db.flush() ---")
            await db.flush()
            logger.info("flush() выполнен")
            
            # Проверить, что данные в сессии
            logger.info("\n--- Проверка данных в текущей транзакции ---")
            result = await db.execute(
                text("SELECT COUNT(*) FROM messages WHERE session_db_id = :session_id"),
                {"session_id": conv_id.value}
            )
            count_before_commit = result.scalar()
            logger.info(f"Сообщений в транзакции (до commit): {count_before_commit}")
            
            logger.info("\n--- Вызов db.commit() ---")
            await db.commit()
            logger.info("commit() выполнен")
            
            # Проверить после commit
            result = await db.execute(
                text("SELECT COUNT(*) FROM messages WHERE session_db_id = :session_id"),
                {"session_id": conv_id.value}
            )
            count_after_commit = result.scalar()
            logger.info(f"Сообщений после commit: {count_after_commit}")
            
            # Детальная проверка сохраненных сообщений
            result = await db.execute(
                text("""
                    SELECT id, role, content, timestamp, tool_calls, metadata_json
                    FROM messages 
                    WHERE session_db_id = :session_id
                    ORDER BY timestamp
                """),
                {"session_id": conv_id.value}
            )
            
            logger.info("\nСохраненные сообщения:")
            for row in result:
                logger.info(f"  - ID: {row[0]}")
                logger.info(f"    Role: {row[1]}")
                logger.info(f"    Content: {row[2][:50] if row[2] else 'NULL'}...")
                logger.info(f"    Timestamp: {row[3]}")
                logger.info(f"    Tool calls: {row[4]}")
                logger.info(f"    Metadata: {row[5]}")
            
            if count_after_commit == len(messages):
                logger.info(f"\n✅ УСПЕХ: Все {len(messages)} сообщения сохранены корректно!")
                return True
            else:
                logger.error(f"\n❌ ОШИБКА: Ожидалось {len(messages)} сообщений, сохранено {count_after_commit}")
                return False
                
        except Exception as e:
            logger.error(f"\n❌ ИСКЛЮЧЕНИЕ при сохранении: {e}", exc_info=True)
            await db.rollback()
            return False


async def main():
    """Главная функция диагностики."""
    logger.info("Начало диагностики сохранения сообщений")
    logger.info("=" * 80)
    
    # Подключение к БД - используем конфигурацию из приложения
    from app.core.config import AppConfig
    DATABASE_URL = AppConfig.DB_URL
    
    # Конвертируем для async
    if DATABASE_URL.startswith("sqlite:///"):
        DATABASE_URL = DATABASE_URL.replace("sqlite:///", "sqlite+aiosqlite:///")
    elif DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    
    logger.info(f"Используется БД: {DATABASE_URL}")
    
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,  # Отключаем SQL echo для чистоты логов
        future=True
    )
    
    try:
        # 1. Проверить схему
        schema_ok = await check_database_schema(engine)
        if not schema_ok:
            logger.error("Проверка схемы не пройдена. Остановка.")
            return
        
        # 2. Проверить текущие данные
        await check_current_data(engine)
        
        # 3. Тестировать сохранение
        save_ok = await test_save_operation(engine)
        
        # Итоговый отчет
        logger.info("\n" + "=" * 80)
        logger.info("ИТОГОВЫЙ ОТЧЕТ")
        logger.info("=" * 80)
        logger.info(f"Схема БД: {'✅ OK' if schema_ok else '❌ FAIL'}")
        logger.info(f"Тест сохранения: {'✅ OK' if save_ok else '❌ FAIL'}")
        
        if not save_ok:
            logger.error("\n⚠️  ОБНАРУЖЕНА ПРОБЛЕМА С СОХРАНЕНИЕМ СООБЩЕНИЙ!")
            logger.error("Рекомендации:")
            logger.error("1. Проверьте логи выше на наличие исключений")
            logger.error("2. Убедитесь, что mapper.to_model() корректно создает MessageModel")
            logger.error("3. Проверьте, что db.flush() и db.commit() вызываются")
            logger.error("4. Проверьте внешние ключи и constraints")
        
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
