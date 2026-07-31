from typing import Optional
from fastapi import APIRouter, Query, Header, BackgroundTasks, HTTPException
from app.database import run_query
from app.etl import run_etl_pipeline

router = APIRouter()

@router.get("/agents")
async def get_agents(
    client_id: Optional[str] = Query(None),
    x_client_id: Optional[str] = Header(None)
):
    active_client = client_id or x_client_id or "2"
    query = "SELECT DISTINCT agent_name FROM calls WHERE agent_name IS NOT NULL AND agent_name != '' ORDER BY agent_name ASC"
    rows = await run_query(query, client_id=active_client)
    return [r["agent_name"] for r in rows]

@router.post("/etl/trigger")
async def trigger_etl(
    background_tasks: BackgroundTasks,
    client_id: Optional[str] = Query(None),
    x_client_id: Optional[str] = Header(None)
):
    active_client = client_id or x_client_id or "2"
    try:
        background_tasks.add_task(run_etl_pipeline, client_id=active_client)
        return {
            "status": "success",
            "message": f"ETL pipeline iniciado em background para o cliente {active_client}."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha ao agendar ETL: {str(e)}")
