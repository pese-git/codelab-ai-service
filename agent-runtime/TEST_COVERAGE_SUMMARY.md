# Test Coverage Summary

**Total Coverage: 77%**

## Coverage by Module

| Module | Statements | Missing | Coverage |
|--------|-----------|---------|----------|
| app/__init__.py | 0 | 0 | 100% |
| app/api/v1/endpoints.py | 66 | 21 | 68% |
| app/core/agent/base_agent.py | 10 | 2 | 80% |
| app/core/agent/llm_proxy_agent.py | 48 | 34 | 29% |
| app/core/agent/prompts.py | 1 | 0 | 100% |
| app/core/config.py | 13 | 0 | 100% |
| app/core/dependencies.py | 18 | 6 | 67% |
| app/main.py | 19 | 9 | 53% |
| app/middleware/internal_auth.py | 15 | 0 | 100% |
| app/models/agents.py | 28 | 0 | 100% |
| app/models/schemas.py | 101 | 0 | 100% |
| app/services/chat_service.py | 29 | 17 | 41% |
| app/services/llm_proxy_client.py | 30 | 18 | 40% |
| app/services/llm_stream_service.py | 78 | 5 | 94% |
| app/services/orchestrator.py | 40 | 29 | 28% |
| app/services/session_manager.py | 88 | 0 | 100% |
| app/services/tool_parser.py | 130 | 11 | 92% |
| app/services/tool_registry.py | 38 | 23 | 39% |
| **TOTAL** | **752** | **175** | **77%** |

## Test Results

- **Total Tests**: 90
- **Passed**: 90
- **Failed**: 0
- **Warnings**: 6

## High Coverage Modules (≥90%)

- ✅ app/__init__.py (100%)
- ✅ app/core/agent/prompts.py (100%)
- ✅ app/core/config.py (100%)
- ✅ app/middleware/internal_auth.py (100%)
- ✅ app/models/agents.py (100%)
- ✅ app/models/schemas.py (100%)
- ✅ app/services/session_manager.py (100%)
- ✅ app/services/llm_stream_service.py (94%)
- ✅ app/services/tool_parser.py (92%)

## Modules Needing Improvement (<70%)

- ⚠️ app/api/v1/endpoints.py (68%)
- ⚠️ app/core/dependencies.py (67%)
- ⚠️ app/main.py (53%)
- ⚠️ app/services/chat_service.py (41%)
- ⚠️ app/services/llm_proxy_client.py (40%)
- ⚠️ app/services/tool_registry.py (39%)
- ⚠️ app/core/agent/llm_proxy_agent.py (29%)
- ⚠️ app/services/orchestrator.py (28%)

## Generated

- Date: 2025-12-30
- Test Framework: pytest 9.0.2
- Coverage Tool: pytest-cov 7.0.0
- Python Version: 3.12.2
