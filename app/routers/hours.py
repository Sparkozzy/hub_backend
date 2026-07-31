from typing import Optional
from fastapi import APIRouter, Query, Header
from app.database import run_query, build_filter_clauses

router = APIRouter()

@router.get("/hours")
async def get_hours(
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
        strftime('%H', created_at) as call_hour,
        count(*) as call_count,
        sum(is_interesse) as interest_count
    FROM calls
    WHERE 1=1 {where_clause}
    GROUP BY call_hour
    ORDER BY call_hour ASC
    """
    
    rows = await run_query(query, tuple(params), client_id=active_client)
    
    data = []
    for r in rows:
        call_count = r["call_count"] or 0
        interest_count = r["interest_count"] or 0
        conv_rate = (interest_count / call_count) * 100.0 if call_count > 0 else 0.0
        
        data.append({
            "hour": f"{r['call_hour']}:00",
            "call_count": call_count,
            "interest_count": interest_count,
            "conversion_rate": round(conv_rate, 2)
        })
        
    return data
