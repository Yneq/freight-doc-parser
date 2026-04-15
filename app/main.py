import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routers import documents

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.getLogger(__name__).info("🚀 Freight Doc Parser starting...")
    yield
    logging.getLogger(__name__).info("👋 Shutdown")


app = FastAPI(
    title="Freight Document Parser",
    description="上傳 PDF，自動抽取 MBL、Container No.、Total Amount",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router, prefix="/api")

app.mount("/", StaticFiles(directory="static", html=True), name="static")

'''
### 📁 所有 `__init__.py`

這四個檔案內容都是**空的**，但一定要建：

app/__init__.py
app/routers/__init__.py
app/services/__init__.py
app/schemas/__init__.py
'''