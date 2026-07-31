from typing import Optional
from fastapi import APIRouter, Query, Header
from app.database import run_query, build_filter_clauses

router = APIRouter()

@router.get("/fatigue")
async def get_fatigue(
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
        CASE 
            WHEN n_tentativas_anteriores = 0 THEN '1ª Ligação'
            WHEN n_tentativas_anteriores = 1 THEN '2ª Ligação'
            WHEN n_tentativas_anteriores = 2 THEN '3ª Ligação'
            WHEN n_tentativas_anteriores BETWEEN 3 AND 4 THEN '4-5 Ligações'
            WHEN n_tentativas_anteriores BETWEEN 5 AND 9 THEN '6-10 Ligações'
            ELSE '11+ Ligações'
        END as attempt_bucket,
        n_tentativas_anteriores as attempt_order,
        count(*) as call_count,
        sum(is_interesse) as interest_count,
        avg(densidade_tentativas) as avg_density,
        avg(pressao_recente) as avg_pressure
    FROM calls
    WHERE 1=1 {where_clause}
    GROUP BY attempt_bucket
    ORDER BY MIN(n_tentativas_anteriores) ASC
    """
    
    rows = await run_query(query, tuple(params), client_id=active_client)
    
    data = []
    for r in rows:
        call_count = r["call_count"] or 0
        interest_count = r["interest_count"] or 0
        conv_rate = (interest_count / call_count) * 100.0 if call_count > 0 else 0.0
        
        data.append({
            "attempt_bucket": r["attempt_bucket"],
            "call_count": call_count,
            "interest_count": interest_count,
            "conversion_rate": round(conv_rate, 2),
            "avg_density": round(r["avg_density"] or 0.0, 3),
            "avg_pressure": round(r["avg_pressure"] or 0.0, 3)
        })
        
    return data
