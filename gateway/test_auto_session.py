#!/usr/bin/env python3
"""
Тестовый скрипт для проверки автоматического создания сессий через Gateway.

Проверяет:
1. Создание новой сессии с временным ID
2. Получение session_info чанка
3. Продолжение диалога с реальным session_id
"""

import asyncio
import json
import sys
from datetime import datetime

import websockets


class Colors:
    """ANSI цвета для вывода."""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_success(msg: str):
    print(f"{Colors.GREEN}✓ {msg}{Colors.RESET}")


def print_info(msg: str):
    print(f"{Colors.BLUE}ℹ {msg}{Colors.RESET}")


def print_warning(msg: str):
    print(f"{Colors.YELLOW}⚠ {msg}{Colors.RESET}")


def print_error(msg: str):
    print(f"{Colors.RED}✗ {msg}{Colors.RESET}")


def print_header(msg: str):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{msg}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.RESET}\n")


async def test_new_session(gateway_url: str):
    """
    Тест 1: Создание новой сессии с временным ID.
    
    Проверяет:
    - WebSocket соединение с временным ID
    - Отправку первого сообщения
    - Получение session_info чанка
    - Отправку второго сообщения
    """
    print_header("Тест 1: Создание новой сессии")
    
    # Генерируем временный session_id
    temp_session_id = f"new_{int(datetime.now().timestamp() * 1000)}"
    print_info(f"Временный session_id: {temp_session_id}")
    
    ws_url = f"{gateway_url}/ws/{temp_session_id}"
    print_info(f"Подключение к: {ws_url}")
    
    try:
        async with websockets.connect(ws_url) as websocket:
            print_success("WebSocket соединение установлено")
            
            # Отправляем первое сообщение
            first_message = {
                "type": "user_message",
                "role": "user",
                "content": "Привет! Это тестовое сообщение для проверки автоматического создания сессии."
            }
            
            print_info("Отправка первого сообщения...")
            await websocket.send(json.dumps(first_message))
            print_success("Первое сообщение отправлено")
            
            # Ожидаем session_info чанк
            print_info("Ожидание session_info чанка...")
            real_session_id = None
            session_info_received = False
            
            # Читаем первые несколько сообщений
            for i in range(10):
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(response)
                    msg_type = data.get('type')
                    
                    print_info(f"Получен чанк: type={msg_type}")
                    
                    if msg_type == "session_info":
                        real_session_id = data.get('session_id')
                        session_info_received = True
                        print_success(f"Получен session_info: {real_session_id}")
                        break
                    
                except asyncio.TimeoutError:
                    print_warning("Таймаут при ожидании сообщения")
                    break
            
            if not session_info_received:
                print_error("session_info чанк НЕ получен!")
                return False
            
            # Отправляем второе сообщение
            print_info("\nОтправка второго сообщения...")
            second_message = {
                "type": "user_message",
                "role": "user",
                "content": "Это второе сообщение в том же диалоге."
            }
            
            await websocket.send(json.dumps(second_message))
            print_success("Второе сообщение отправлено")
            
            # Проверяем, что session_info больше не приходит
            print_info("Проверка отсутствия повторного session_info...")
            session_info_count = 0
            
            for i in range(5):
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    data = json.loads(response)
                    msg_type = data.get('type')
                    
                    if msg_type == "session_info":
                        session_info_count += 1
                        print_warning(f"Получен повторный session_info (неожиданно!)")
                    
                except asyncio.TimeoutError:
                    break
            
            if session_info_count == 0:
                print_success("Повторный session_info НЕ получен (ожидаемо)")
            else:
                print_error(f"Получено {session_info_count} повторных session_info!")
                return False
            
            print_success("\n✓ Тест 1 ПРОЙДЕН")
            return True
            
    except Exception as e:
        print_error(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_existing_session(gateway_url: str, session_id: str):
    """
    Тест 2: Подключение к существующей сессии.
    
    Проверяет:
    - WebSocket соединение с реальным session_id
    - Отправку сообщения
    - Отсутствие session_info чанка
    """
    print_header("Тест 2: Подключение к существующей сессии")
    
    print_info(f"Session ID: {session_id}")
    
    ws_url = f"{gateway_url}/ws/{session_id}"
    print_info(f"Подключение к: {ws_url}")
    
    try:
        async with websockets.connect(ws_url) as websocket:
            print_success("WebSocket соединение установлено")
            
            # Отправляем сообщение
            message = {
                "type": "user_message",
                "role": "user",
                "content": "Продолжаем существующий диалог."
            }
            
            print_info("Отправка сообщения...")
            await websocket.send(json.dumps(message))
            print_success("Сообщение отправлено")
            
            # Проверяем, что session_info НЕ приходит
            print_info("Проверка отсутствия session_info...")
            session_info_received = False
            
            for i in range(5):
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    data = json.loads(response)
                    msg_type = data.get('type')
                    
                    print_info(f"Получен чанк: type={msg_type}")
                    
                    if msg_type == "session_info":
                        session_info_received = True
                        print_error("Получен session_info (неожиданно!)")
                        break
                    
                except asyncio.TimeoutError:
                    break
            
            if not session_info_received:
                print_success("session_info НЕ получен (ожидаемо)")
                print_success("\n✓ Тест 2 ПРОЙДЕН")
                return True
            else:
                print_error("\n✗ Тест 2 ПРОВАЛЕН")
                return False
            
    except Exception as e:
        print_error(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Главная функция."""
    # Параметры подключения
    gateway_url = "ws://localhost:8001/api/v1"
    
    if len(sys.argv) > 1:
        gateway_url = sys.argv[1]
    
    print_header("Тестирование автоматического создания сессий в Gateway")
    print_info(f"Gateway URL: {gateway_url}")
    
    # Тест 1: Создание новой сессии
    test1_passed = await test_new_session(gateway_url)
    
    # Тест 2: Подключение к существующей сессии
    # Используем известный session_id или создаем новый
    if test1_passed:
        # Создаем сессию для теста 2
        temp_id = f"new_{int(datetime.now().timestamp() * 1000)}"
        ws_url = f"{gateway_url}/ws/{temp_id}"
        
        try:
            async with websockets.connect(ws_url) as ws:
                await ws.send(json.dumps({
                    "type": "user_message",
                    "role": "user",
                    "content": "Создание сессии для теста 2"
                }))
                
                # Получаем session_id
                real_session_id = None
                for _ in range(5):
                    try:
                        response = await asyncio.wait_for(ws.recv(), timeout=2.0)
                        data = json.loads(response)
                        if data.get('type') == 'session_info':
                            real_session_id = data.get('session_id')
                            break
                    except asyncio.TimeoutError:
                        break
                
                if real_session_id:
                    test2_passed = await test_existing_session(gateway_url, real_session_id)
                else:
                    print_warning("Не удалось получить session_id для теста 2")
                    test2_passed = False
        except Exception as e:
            print_error(f"Ошибка при подготовке теста 2: {e}")
            test2_passed = False
    else:
        test2_passed = False
    
    # Итоги
    print_header("Результаты тестирования")
    
    if test1_passed:
        print_success("Тест 1 (новая сессия): ПРОЙДЕН")
    else:
        print_error("Тест 1 (новая сессия): ПРОВАЛЕН")
    
    if test2_passed:
        print_success("Тест 2 (существующая сессия): ПРОЙДЕН")
    else:
        print_error("Тест 2 (существующая сессия): ПРОВАЛЕН")
    
    if test1_passed and test2_passed:
        print_success("\n✓ ВСЕ ТЕСТЫ ПРОЙДЕНЫ")
        return 0
    else:
        print_error("\n✗ НЕКОТОРЫЕ ТЕСТЫ ПРОВАЛЕНЫ")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
