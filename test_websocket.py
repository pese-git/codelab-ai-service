import asyncio
import json
import sys
from websockets import connect, exceptions


async def test_websocket():
    uri = "ws://localhost:8000/ws/test123"
    try:
        async with connect(uri) as websocket:
            # Отправляем тестовое сообщение
            message = {"type": "user_message", "content": "Hello from Docker test!"}
            print(f"Sending message: {message}")
            await websocket.send(json.dumps(message))

            # Получаем ответ
            response = await websocket.recv()
            print(f"Received response: {response}")

    except exceptions.ConnectionClosed:
        print("Connection refused. Make sure the Gateway service is running.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(test_websocket())
