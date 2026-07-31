from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.config import TIMEZONE_STR, PORT
from app.utils import BR_TZ
from app.etl import run_etl_pipeline
from app.multi_tenant import get_master_supabase_client
from app.routers import (
    metrics,
    funnel,
    calls,
    fatigue,
    hours,
    disconnections,
    agents,
    agendamentos
)

scheduler = AsyncIOScheduler()

async def run_daily_multi_tenant_etl():
    """Roda o ETL para o cliente master e todos os clientes cadastrados em client_configurations."""
    print("[Lifespan Scheduler] Iniciando ETL diário automático às 3:00 AM (BRT)...")
    try:
        await run_etl_pipeline("2")
    except Exception as e:
        print(f"[Lifespan Scheduler Error] Falha no ETL do cliente master: {e}")
        
    try:
        master = get_master_supabase_client()
        res = master.table("client_configurations").select("client_id").execute()
        if res.data:
            for row in res.data:
                cid = str(row["client_id"])
                if cid != "2":
                    try:
                        await run_etl_pipeline(cid)
                    except Exception as ex:
                        print(f"[Lifespan Scheduler Error] Falha no ETL do cliente {cid}: {ex}")
    except Exception as e:
        print(f"[Lifespan Scheduler Error] Falha ao listar clientes para ETL: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(
        run_daily_multi_tenant_etl,
        'cron',
        hour=3,
        minute=0,
        timezone=BR_TZ,
        id='daily_multi_tenant_etl',
        replace_existing=True
    )
    scheduler.start()
    print(f"[Lifespan] Servidor FastAPI iniciado na porta {PORT}. Agendador diário ativo (3:00 AM BRT).")
    yield
    scheduler.shutdown()
    print("[Lifespan] Agendador finalizado.")

app = FastAPI(
    title="MindFlow Call Analytics API (Multi-Tenant)",
    description="API REST Backend em Python para o Hub de Plataformas com suporte a Multi-Tenancy e fuso BRT.",
    version="2.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar Routers
app.include_router(metrics.router)
app.include_router(funnel.router)
app.include_router(calls.router)
app.include_router(fatigue.router)
app.include_router(hours.router)
app.include_router(disconnections.router)
app.include_router(agents.router)
app.include_router(agendamentos.router)

@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "MindFlow Call Analytics API (Multi-Tenant)",
        "version": "2.1.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=PORT, reload=True)
