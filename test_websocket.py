import asyncio
import json
import websockets


async def ws_client():
    session_id = "test123"
    url = f"ws://localhost:8000/ws/{session_id}"

    async with websockets.connect(url) as ws:
        # Отправляем сообщение
        message = {
            "type": "user_message",
            "content": "Hello! Can you stream this message word by word?",
        }
        await ws.send(json.dumps(message))
        print("Sent:", message["content"])

        # Читаем токены
        full_message = ""
        try:
            while True:
                data = await ws.recv()
                msg = json.loads(data)

                if msg.get("type") == "assistant_message":
                    token = msg.get("token", "")
                    is_final = msg.get("is_final", False)
                    full_message += token
                    print(token, end="", flush=True)

                    if is_final:
                        print("\n[Stream complete]")
                        break

                elif msg.get("type") == "error":
                    print("\n[Error]:", msg.get("content"))
                    break

        except websockets.ConnectionClosed:
            print("\nWebSocket disconnected")


asyncio.run(ws_client())
