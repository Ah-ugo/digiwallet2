from fastapi import FastAPI
from routes.auth_routes import router as auth_router
from fastapi.middleware.cors import CORSMiddleware
from routes.banking_routes import router as banking_router

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(banking_router, prefix="/banking", tags=["Banking"])
