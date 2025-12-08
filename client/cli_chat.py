# cli_chat.py
import asyncio
import json
import websockets

GATEWAY_WS = "ws://localhost:8000/ws/cli-session"


async def chat_loop():
    async with websockets.connect(GATEWAY_WS) as ws:
        print(
            "🚀 Connected to Gateway (WebSocket).\nType your message (or 'exit' to quit):"
        )
        while True:
            user_input = input("You: ")
            if user_input.lower() in ("exit", "quit"):
                print("👋 Bye!")
                break

            msg = {"type": "user_message", "content": user_input}
            await ws.send(json.dumps(msg))

            full_answer = ""
            print("Assistant: ", end="", flush=True)
            while True:
                data = await ws.recv()
                msg = json.loads(data)
                if msg.get("type") == "assistant_message":
                    token = msg.get("token", "")
                    print(token, end="", flush=True)
                    full_answer += token
                    if msg.get("is_final"):
                        print()
                        break
                elif msg.get("type") == "error":
                    print("\n[Error]:", msg.get("content"))
                    break


if __name__ == "__main__":
    try:
        asyncio.run(chat_loop())
    except KeyboardInterrupt:
        print("\n👋 Bye!")
