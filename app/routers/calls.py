from typing import Optional
from fastapi import APIRouter, Query, Header
from app.database import run_query, build_filter_clauses

router = APIRouter()

@router.get("/calls")
async def get_calls(
    agent: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    startDate: Optional[str] = Query(None),
    endDate: Optional[str] = Query(None),
    min_duration: Optional[float] = Query(None),
    max_duration: Optional[float] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=10000),
    client_id: Optional[str] = Query(None),
    x_client_id: Optional[str] = Header(None)
):
    active_client = client_id or x_client_id or "2"
    effective_start = start_date or startDate
    effective_end = end_date or endDate
    where_clause, params = build_filter_clauses(agent, effective_start, effective_end)
    
    list_params = list(params)
    count_params = list(params)
    
    duration_clauses = []
    if min_duration is not None:
        duration_clauses.append("CAST(Duracao AS REAL) >= ?")
        list_params.append(min_duration)
        count_params.append(min_duration)
    if max_duration is not None:
        duration_clauses.append("CAST(Duracao AS REAL) <= ?")
        list_params.append(max_duration)
        count_params.append(max_duration)
        
    duration_where = " AND " + " AND ".join(duration_clauses) if duration_clauses else ""
    offset = (page - 1) * limit
    
    count_query = f"SELECT count(*) as total FROM calls WHERE 1=1 {where_clause} {duration_where}"
    count_res = await run_query(count_query, tuple(count_params), client_id=active_client)
    total_calls = count_res[0]["total"] if count_res else 0
    
    list_query = f"""
    SELECT 
        call_id, to_number, Nome, Email, agent_name, created_at, 
        recording_url, transcript, Duracao, disconnection_category,
        n_tentativas_anteriores, densidade_tentativas, pressao_recente
    FROM calls
    WHERE 1=1 {where_clause} {duration_where}
    ORDER BY created_at DESC
    LIMIT ? OFFSET ?
    """
    list_params.extend([limit, offset])
    
    calls = await run_query(list_query, tuple(list_params), client_id=active_client)
    
    return {
        "total": total_calls,
        "page": page,
        "limit": limit,
        "pages": (total_calls + limit - 1) // limit if total_calls > 0 else 0,
        "data": calls
    }
