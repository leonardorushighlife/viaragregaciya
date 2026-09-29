from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from app.core.config import settings
from app.routers.routers import main_router, facade_router, labeling_router, operator_router, notif_router
from app.routers.settings_router import settings_router
from app.routers.today_router import today_router
from app.services.scheduler import start_scheduler, scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    start_scheduler()
    yield
    # Shutdown logic
    scheduler.shutdown()

app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

# Mount Static Files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include Routers
app.include_router(main_router)
app.include_router(facade_router)
app.include_router(labeling_router)
app.include_router(operator_router)
app.include_router(notif_router)
app.include_router(settings_router)
app.include_router(today_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
