from fastapi import FastAPI
from app.api.v1.endpoints import router as v1_router
from app.middleware.internal_auth import InternalAuthMiddleware

app = FastAPI(title="Agent Runtime Service")

# Подключение middleware авторизации
app.add_middleware(InternalAuthMiddleware)

# Подключение роутов API v1
app.include_router(v1_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8001, log_level="info", reload=True)
