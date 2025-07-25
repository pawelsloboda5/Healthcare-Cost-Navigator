#!/usr/bin/env python3
"""
Healthcare Cost Navigator - FastAPI Application
Enhanced with RAG-powered AI assistant and comprehensive provider search
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.database import init_db
from .core.config import settings
from .api.routes import router

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI app with enhanced configuration
app = FastAPI(
    title=settings.API_TITLE,
    description=settings.API_DESCRIPTION,
    version=settings.API_VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api/v1")

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Healthcare Cost Navigator API",
        "version": settings.API_VERSION,
        "status": "healthy",
        "features": [
            "RAG-enhanced natural language queries",
            "Template-based SQL matching",
            "Comprehensive safety validation",
            "Advanced provider search",
            "Cost analysis and comparisons"
        ],
        "endpoints": {
            "docs": "/docs",
            "health": "/api/v1/health",
            "ask_ai": "/api/v1/ask",
            "search_providers": "/api/v1/providers/search",
            "legacy_search": "/api/v1/providers"
        }
    }

@app.get("/health")
async def health_check():
    """Global health check endpoint"""
    return {
        "status": "healthy",
        "service": "Healthcare Cost Navigator API",
        "version": settings.API_VERSION
    }

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    logger.info(f"Starting {settings.API_TITLE} v{settings.API_VERSION}")
    logger.info("Initializing database connection...")
    
    try:
        await init_db()
        logger.info("Database initialized successfully")
        
        # Verify OpenAI connection
        if settings.OPENAI_API_KEY:
            logger.info("OpenAI API key configured")
        else:
            logger.warning("OpenAI API key not configured - AI features may not work")
            
        logger.info("Healthcare Cost Navigator API started successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown"""
    logger.info("Shutting down Healthcare Cost Navigator API")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=settings.LOG_LEVEL.lower()
    ) 