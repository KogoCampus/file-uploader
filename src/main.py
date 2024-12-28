from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import images

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
app.include_router(images.router)

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "File Upload API is running",
        "docs": "/docs",
        "redoc": "/redoc"
    } 