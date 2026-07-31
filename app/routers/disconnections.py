from typing import Optional
from fastapi import APIRouter, Query, Header
from app.database import run_query, build_filter_clauses

router = APIRouter()

@router.get("/disconnections")
async def get_disconnections(
    agent: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    detailed: bool = Query(False),
    client_id: Optional[str] = Query(None),
    x_client_id: Optional[str] = Header(None)
):
    active_client = client_id or x_client_id or "2"
    where_clause, params = build_filter_clauses(agent, start_date, end_date)
    
    if detailed:
        query = f"""
        SELECT 
            disconnection_reason as reason,
            disconnection_category as category,
            count(*) as count
        FROM calls
        WHERE 1=1 {where_clause}
        GROUP BY disconnection_reason, disconnection_category
        ORDER BY count DESC
        """
    else:
        query = f"""
        SELECT 
            disconnection_category,
            count(*) as count
        FROM calls
        WHERE 1=1 {where_clause}
        GROUP BY disconnection_category
        ORDER BY count DESC
        """
        
    rows = await run_query(query, tuple(params), client_id=active_client)
    total = sum(r["count"] for r in rows)
    
    data = []
    for r in rows:
        count = r["count"] or 0
        pct = (count / total) * 100.0 if total > 0 else 0.0
        
        if detailed:
            data.append({
                "reason": r["reason"] or "Não informado / Normal",
                "category": r["category"],
                "count": count,
                "percentage": round(pct, 2)
            })
        else:
            data.append({
                "category": r["disconnection_category"],
                "count": count,
                "percentage": round(pct, 2)
            })
        
    return data
