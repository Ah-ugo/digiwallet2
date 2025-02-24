from fastapi import FastAPI
from routes.auth_routes import router as auth_router
from routes.banking_routes import router as banking_router

app = FastAPI()

app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(banking_router, prefix="/banking", tags=["Banking"])
