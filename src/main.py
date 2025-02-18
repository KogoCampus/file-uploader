from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import files
from .routes import stale
from .backend.s3 import scheduler as s3_scheduler

app = FastAPI(
    title="File Upload API",
    description="API for handling file uploads to S3",
    version="1.0.0"
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(files.file_router)
app.include_router(stale.stale_router)

# Start scheduler
@app.on_event("startup")
async def startup_event():
    s3_scheduler.start()

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "File Upload API is running",
        "docs": "/docs",
        "redoc": "/redoc"
    } 