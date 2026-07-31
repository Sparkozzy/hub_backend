from typing import Optional
from fastapi import APIRouter, Query, Header
from app.database import run_query, build_filter_clauses

router = APIRouter()

@router.get("/metrics")
async def get_metrics(
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
        count(*) as total_calls,
        count(distinct to_number) as unique_leads,
        sum(is_hook) as total_hooks,
        sum(is_conversa) as total_conversas,
        sum(is_interesse) as total_interesse,
        sum(combined_cost) as total_cost,
        avg(densidade_tentativas) as avg_density,
        avg(pressao_recente) as avg_pressure
    FROM calls
    WHERE 1=1 {where_clause}
    """
    
    results = await run_query(query, tuple(params), client_id=active_client)
    if not results or results[0]["total_calls"] == 0:
        return {
            "total_calls": 0,
            "unique_leads": 0,
            "total_hooks": 0,
            "total_conversas": 0,
            "total_interesse": 0,
            "total_cost": 0.0,
            "avg_ligacoes_por_lead": 0.0,
            "custo_por_lead": 0.0,
            "custo_por_interesse": 0.0,
            "taxa_interesse_por_lead": 0.0,
            "taxa_tentativa_por_lead": 0.0,
            "avg_density": 0.0,
            "avg_pressure": 0.0
        }
        
    row = results[0]
    total_calls = row["total_calls"] or 0
    unique_leads = row["unique_leads"] or 0
    total_hooks = row["total_hooks"] or 0
    total_conversas = row["total_conversas"] or 0
    total_interesse = row["total_interesse"] or 0
    total_cost = row["total_cost"] or 0.0
    avg_density = row["avg_density"] or 0.0
    avg_pressure = row["avg_pressure"] or 0.0
    
    avg_calls_per_lead = total_calls / unique_leads if unique_leads > 0 else 0.0
    cost_per_lead = total_cost / unique_leads if unique_leads > 0 else 0.0
    cost_per_interest = total_cost / total_interesse if total_interesse > 0 else 0.0
    interest_rate = (total_interesse / unique_leads) * 100.0 if unique_leads > 0 else 0.0
    
    return {
        "total_calls": total_calls,
        "unique_leads": unique_leads,
        "total_hooks": total_hooks,
        "total_conversas": total_conversas,
        "total_interesse": total_interesse,
        "total_cost": round(total_cost, 2),
        "avg_ligacoes_por_lead": round(avg_calls_per_lead, 2),
        "custo_por_lead": round(cost_per_lead, 2),
        "custo_por_interesse": round(cost_per_interest, 2),
        "taxa_interesse_por_lead": round(interest_rate, 2),
        "taxa_tentativa_por_lead": round(avg_calls_per_lead, 2),
        "avg_density": round(avg_density, 3),
        "avg_pressure": round(avg_pressure, 3)
    }
