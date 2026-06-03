from fastapi import FastAPI
from app.api.admin import router as admin_router
import uvicorn

app = FastAPI(title="Video Editor Admin API")
app.include_router(admin_router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
