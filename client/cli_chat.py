# client/cli_chat.py
import asyncio
import json
import sys
import websockets

GATEWAY_WS = "ws://localhost:8000/ws/cli-session"


async def ws_reader(websocket, queue):
    """
    Читает ответы ассистента из WebSocket, обрабатывает и tool_call, и обычные сообщения.
    """
    while True:
        try:
            data = await websocket.recv()
            msg = json.loads(data)
            if msg.get("type") == "assistant_message":
                token = msg.get("token", "")
                if token:
                    print(token, end="", flush=True)
                if msg.get("is_final"):
                    print()
                    print("═════════════════════════════════════")
                    print("You: ", end="", flush=True)
            elif msg.get("type") == "tool_call":
                # Обнаружен инструмент! Спрашиваем пользователя/эмулируем результат
                meta = msg.get("metadata", {})
                tool = meta.get("tool_call", {})
                call_id = tool.get("id")
                tool_name = tool.get("tool_name")
                arguments = tool.get("arguments", {})
                print(f"\n[ToolCall] {tool_name} (id={call_id}) с аргументами: {arguments}")
                # Простая эмуляция: спрашиваем у пользователя результат:
                fake_result = None
                try:
                    print(f"Введите результат для инструмента '{tool_name}' (оставьте пустым для demo): ", end="", flush=True)
                    fake_result = sys.stdin.readline().strip() or f"Executed {tool_name}"
                except Exception:
                    fake_result = f"Executed {tool_name}"  # fallback
                # Собираем и отправляем tool_result обратно в Gateway через WS
                tool_result_msg = {
                    "type": "tool_result",
                    "call_id": call_id,
                    "result": {"response": fake_result},
                }
                await websocket.send(json.dumps(tool_result_msg))
                print(f"[Отправлен tool_result для {tool_name} / {call_id}]")
                print("You: ", end="", flush=True)
            elif msg.get("type") == "error":
                print(f"\n[Error]: {msg.get('content')}")
                print("You: ", end="", flush=True)
        except websockets.ConnectionClosed:
            await queue.put("__ws_closed__")
            break


async def stdin_reader(queue):
    """
    Асинхронно читает пользовательский ввод и кладёт его в очередь.
    """
    loop = asyncio.get_event_loop()
    while True:
        print("You: ", end="", flush=True)
        user_input = await loop.run_in_executor(None, sys.stdin.readline)
        user_input = user_input.strip()
        await queue.put(user_input)


async def main():
    queue = asyncio.Queue()
    print("🚀 Connected to Gateway (WebSocket). Type 'exit' to quit")
    async with websockets.connect(GATEWAY_WS) as ws:
        # Запускаем reader'ы: ассистент/ввод отдельно
        tasks = [
            asyncio.create_task(ws_reader(ws, queue)),
            asyncio.create_task(stdin_reader(queue)),
        ]
        try:
            while True:
                user_input = await queue.get()
                if user_input == "__ws_closed__":
                    print("\n[!!] WebSocket closed by server. Exiting.")
                    break
                if user_input.lower() in ("exit", "quit"):
                    print("👋 Bye!")
                    break
                if not user_input:
                    continue
                msg = {"type": "user_message", "content": user_input}
                await ws.send(json.dumps(msg))
        except KeyboardInterrupt:
            print("\n👋 Bye!")
        finally:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\n👋 Bye (exit on Ctrl+C)!")
