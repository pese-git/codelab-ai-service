"""
Ручное тестирование retry механизма.

Запуск: uv run python test_retry_manual.py
"""
import asyncio
import logging
from datetime import datetime
import httpx

# Настройка логирования для видимости retry попыток
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from app.services.retry_service import (
    RetryableError,
    NonRetryableError,
    call_with_retry,
    llm_retry
)


# Тест 1: Успешный вызов после нескольких попыток
print("\n" + "="*70)
print("ТЕСТ 1: Успешный вызов после 2 неудачных попыток")
print("="*70)

attempt_count = 0

@llm_retry
async def test_success_after_retries():
    global attempt_count
    attempt_count += 1
    print(f"  → Попытка #{attempt_count} в {datetime.now().strftime('%H:%M:%S')}")
    
    if attempt_count < 3:
        print(f"  ✗ Попытка #{attempt_count} не удалась (timeout)")
        raise RetryableError("Simulated timeout")
    
    print(f"  ✓ Попытка #{attempt_count} успешна!")
    return "Success!"


async def run_test_1():
    global attempt_count
    attempt_count = 0
    
    try:
        result = await test_success_after_retries()
        print(f"\n✅ Результат: {result}")
        print(f"   Всего попыток: {attempt_count}")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")


# Тест 2: Все попытки неудачны
print("\n" + "="*70)
print("ТЕСТ 2: Все 3 попытки неудачны (превышен лимит)")
print("="*70)

attempt_count_2 = 0

@llm_retry
async def test_all_retries_fail():
    global attempt_count_2
    attempt_count_2 += 1
    print(f"  → Попытка #{attempt_count_2} в {datetime.now().strftime('%H:%M:%S')}")
    print(f"  ✗ Попытка #{attempt_count_2} не удалась (timeout)")
    raise RetryableError("Always fails")


async def run_test_2():
    global attempt_count_2
    attempt_count_2 = 0
    
    try:
        result = await test_all_retries_fail()
        print(f"\n✅ Результат: {result}")
    except Exception as e:
        print(f"\n❌ Все попытки исчерпаны после {attempt_count_2} попыток")
        print(f"   Тип ошибки: {type(e).__name__}")


# Тест 3: Не-retry ошибка (немедленный отказ)
print("\n" + "="*70)
print("ТЕСТ 3: Не-retry ошибка (400 Bad Request)")
print("="*70)

attempt_count_3 = 0

async def test_non_retryable():
    global attempt_count_3
    attempt_count_3 += 1
    print(f"  → Попытка #{attempt_count_3} в {datetime.now().strftime('%H:%M:%S')}")
    print(f"  ✗ Ошибка 400 - не подлежит retry")
    
    # Симуляция 400 ошибки
    response = httpx.Response(400, request=httpx.Request("POST", "http://test"))
    raise httpx.HTTPStatusError("Bad request", request=response.request, response=response)


async def run_test_3():
    global attempt_count_3
    attempt_count_3 = 0
    
    try:
        result = await call_with_retry(test_non_retryable, max_attempts=3)
        print(f"\n✅ Результат: {result}")
    except NonRetryableError as e:
        print(f"\n❌ Не-retry ошибка после {attempt_count_3} попытки (как и ожидалось)")
        print(f"   Сообщение: {str(e)[:100]}")


# Тест 4: Разные типы retry ошибок
print("\n" + "="*70)
print("ТЕСТ 4: Различные типы retry ошибок")
print("="*70)

async def test_different_errors():
    errors = [
        ("Timeout", httpx.TimeoutException("Request timeout")),
        ("Rate Limit (429)", httpx.HTTPStatusError(
            "Rate limited",
            request=httpx.Request("POST", "http://test"),
            response=httpx.Response(429, request=httpx.Request("POST", "http://test"))
        )),
        ("Service Unavailable (503)", httpx.HTTPStatusError(
            "Service unavailable",
            request=httpx.Request("POST", "http://test"),
            response=httpx.Response(503, request=httpx.Request("POST", "http://test"))
        )),
    ]
    
    for error_name, error in errors:
        attempt = 0
        
        async def failing_func():
            nonlocal attempt
            attempt += 1
            if attempt < 2:
                print(f"  → {error_name}: попытка #{attempt} не удалась")
                raise error
            print(f"  → {error_name}: попытка #{attempt} успешна!")
            return f"Success after {attempt} attempts"
        
        try:
            result = await call_with_retry(failing_func, max_attempts=3)
            print(f"  ✓ {error_name}: {result}")
        except Exception as e:
            print(f"  ✗ {error_name}: failed - {type(e).__name__}")


# Запуск всех тестов
async def main():
    print("\n" + "="*70)
    print("РУЧНОЕ ТЕСТИРОВАНИЕ RETRY МЕХАНИЗМА")
    print("="*70)
    print("\nОбратите внимание на:")
    print("  • Количество попыток")
    print("  • Задержки между попытками (exponential backoff: 2s, 4s, 8s)")
    print("  • Логи WARNING от retry_service")
    
    await run_test_1()
    
    await asyncio.sleep(1)
    await run_test_2()
    
    await asyncio.sleep(1)
    await run_test_3()
    
    await asyncio.sleep(1)
    await test_different_errors()
    
    print("\n" + "="*70)
    print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(main())
