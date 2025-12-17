import logging
import pprint
from typing import List, Optional

import httpx

from app.core.config import AppConfig

logger = logging.getLogger("agent-runtime.llm_proxy_client")


class LLMProxyClient:
    """
    Инкапсулирует общение с LLM Proxy (через REST API).
    """

    def __init__(self, api_url: Optional[str] = None, api_key: Optional[str] = None):
        self.api_url = api_url or AppConfig.LLM_PROXY_URL
        self.api_key = api_key or AppConfig.INTERNAL_API_KEY

    async def chat_completion(
        self,
        model: str,
        messages: List[dict],
        tools: Optional[list] = None,
        stream: bool = False,
        extra_payload: Optional[dict] = None,
    ) -> dict:
        """
        Отправляет запрос на chat/completions и возвращает decoded результат.
        extra_payload — любые дополнительные поля в raw запрос.
        """
        payload = {"model": model, "messages": messages, "stream": stream}
        if tools:
            payload["tools"] = tools
        if extra_payload:
            payload.update(extra_payload)

        logger.info(f"[LLMProxyClient] POST {self.api_url}/v1/chat/completions stream={stream}")
        logger.debug("[LLMProxyClient] Payload:\n" + pprint.pformat(payload, indent=2, width=120))

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/v1/chat/completions",
                    json=payload,
                    headers={"X-Internal-Auth": self.api_key},
                    timeout=360.0,
                )
            response.raise_for_status()
            logger.debug(
                f"[LLMProxyClient] Response {response.status_code}, head: {str(response.text)[:256]}"
            )
            logger.debug(
                "[LLMProxyClient] Response JSON:\n" + pprint.pformat(response.json(), indent=2, width=120)
            )
            return response.json()
        except Exception as e:
            logger.error(f"[LLMProxyClient] Exception in chat_completion: {e}", exc_info=True)
            logger.error("[LLMProxyClient] Locals at exception:\n" + pprint.pformat(locals(), indent=2, width=120))
            raise


# Singleton для всего проекта (можно замокать при необходимости)
llm_proxy_client = LLMProxyClient()
