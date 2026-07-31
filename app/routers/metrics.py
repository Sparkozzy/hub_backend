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
    
    query_calls = f"""
    SELECT 
        count(*) as total_calls,
        count(distinct to_number) as unique_leads,
        sum(is_hook) as total_hooks,
        sum(is_conversa) as total_conversas,
        sum(is_interesse) as total_interesse,
        sum(Duracao) as total_duration_seconds,
        avg(Duracao) as avg_duration_seconds,
        avg(densidade_tentativas) as avg_density,
        avg(pressao_recente) as avg_pressure
    FROM calls
    WHERE 1=1 {where_clause}
    """
    
    results = await run_query(query_calls, tuple(params), client_id=active_client)
    
    # Query agendamentos para o período (usando start_date e end_date se informados)
    agendamentos_clauses = []
    agendamentos_params = []
    if start_date and not hasattr(start_date, '__dict__'):
        start_str = str(start_date).strip()
        agendamentos_clauses.append("created_at >= ?")
        agendamentos_params.append(f"{start_str} 00:00:00" if len(start_str) == 10 else start_str)
    if end_date and not hasattr(end_date, '__dict__'):
        end_str = str(end_date).strip()
        agendamentos_clauses.append("created_at <= ?")
        agendamentos_params.append(f"{end_str} 23:59:59" if len(end_str) == 10 else end_str)
        
    agendamentos_where = " AND " + " AND ".join(agendamentos_clauses) if agendamentos_clauses else ""
    query_agendamentos = f"SELECT count(*) as total_agendamentos FROM agendamentos WHERE 1=1 {agendamentos_where}"
    
    res_agendamentos = await run_query(query_agendamentos, tuple(agendamentos_params), client_id=active_client)
    total_agendamentos = res_agendamentos[0]["total_agendamentos"] if res_agendamentos else 0

    if not results or results[0]["total_calls"] == 0:
        return {
            "total_calls": 0,
            "unique_leads": 0,
            "total_hooks": 0,
            "total_conversas": 0,
            "total_interesse": 0,
            "total_agendamentos": total_agendamentos,
            "taxa_agendamento_por_lead": 0.0,
            "minutagem_total": 0.0,
            "minutagem_media": 0.0,
            "minutagem_por_lead": 0.0,
            "avg_ligacoes_por_lead": 0.0,
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
    total_duration_seconds = row["total_duration_seconds"] or 0.0
    avg_duration_seconds = row["avg_duration_seconds"] or 0.0
    avg_density = row["avg_density"] or 0.0
    avg_pressure = row["avg_pressure"] or 0.0
    
    # Conversões para minutos (segundos / 60.0)
    minutagem_total = total_duration_seconds / 60.0
    minutagem_media = avg_duration_seconds / 60.0
    minutagem_por_lead = (total_duration_seconds / unique_leads) / 60.0 if unique_leads > 0 else 0.0
    
    avg_calls_per_lead = total_calls / unique_leads if unique_leads > 0 else 0.0
    interest_rate = (total_interesse / unique_leads) * 100.0 if unique_leads > 0 else 0.0
    
    # Métrica de Taxa de Agendamento por Lead Único
    taxa_agendamento = (total_agendamentos / unique_leads) * 100.0 if unique_leads > 0 else 0.0
    
    return {
        "total_calls": total_calls,
        "unique_leads": unique_leads,
        "total_hooks": total_hooks,
        "total_conversas": total_conversas,
        "total_interesse": total_interesse,
        "total_agendamentos": total_agendamentos,
        "taxa_agendamento_por_lead": round(taxa_agendamento, 2),
        "minutagem_total": round(minutagem_total, 2),
        "minutagem_media": round(minutagem_media, 2),
        "minutagem_por_lead": round(minutagem_por_lead, 2),
        "avg_ligacoes_por_lead": round(avg_calls_per_lead, 2),
        "taxa_interesse_por_lead": round(interest_rate, 2),
        "taxa_tentativa_por_lead": round(avg_calls_per_lead, 2),
        "avg_density": round(avg_density, 3),
        "avg_pressure": round(avg_pressure, 3)
    }
