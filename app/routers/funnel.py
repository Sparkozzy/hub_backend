from typing import Optional
from fastapi import APIRouter, Query, Header
from app.database import run_query, build_filter_clauses

router = APIRouter()

@router.get("/funnel")
async def get_funnel(
    agent: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    client_id: Optional[str] = Query(None),
    x_client_id: Optional[str] = Header(None)
):
    active_client = client_id or x_client_id or "2"
    where_clause, params = build_filter_clauses(agent, start_date, end_date)
    
    query = f"""
    SELECT 
        count(distinct to_number) as leads_totais,
        count(distinct CASE WHEN call_id IS NOT NULL THEN to_number END) as leads_iniciados,
        count(distinct CASE WHEN is_hook = 1 THEN to_number END) as leads_hook_15s,
        count(distinct CASE WHEN is_conversa = 1 THEN to_number END) as leads_conversa_45s,
        count(distinct CASE WHEN is_interesse = 1 THEN to_number END) as leads_interesse_90s,
        count(*) as total_calls_volume
    FROM calls
    WHERE 1=1 {where_clause}
    """
    
    results = await run_query(query, tuple(params), client_id=active_client)
    if not results:
        return {
            "leads_totais": 0,
            "leads_iniciados": 0,
            "hook_15s": 0,
            "conversa_45s": 0,
            "interesse_90s": 0,
            "total_calls_volume": 0
        }
        
    row = results[0]
    return {
        "leads_totais": row["leads_totais"] or 0,
        "leads_iniciados": row["leads_iniciados"] or 0,
        "hook_15s": row["leads_hook_15s"] or 0,
        "conversa_45s": row["leads_conversa_45s"] or 0,
        "interesse_90s": row["leads_interesse_90s"] or 0,
        "total_calls_volume": row["total_calls_volume"] or 0
    }
