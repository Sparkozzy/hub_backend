from typing import Optional
from fastapi import APIRouter, Query, Header
from app.database import run_query

router = APIRouter()

@router.get("/agendamentos")
async def get_agendamentos(
    status: Optional[str] = Query(None),
    canal: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    client_id: Optional[str] = Query(None),
    x_client_id: Optional[str] = Header(None)
):
    """
    Retorna uma lista paginada e detalhada de agendamentos salvos no banco SQLite local do cliente.
    Filtra por período, status, canal ou termo de busca textual (nome/email/número).
    """
    active_client = client_id or x_client_id or "2"
    clauses = []
    params = []

    if status:
        clauses.append("status = ?")
        params.append(status)

    if canal:
        clauses.append("canal = ?")
        params.append(canal)

    if search:
        search_pattern = f"%{search.strip()}%"
        clauses.append("(nome LIKE ? OR email LIKE ? OR numero LIKE ?)")
        params.extend([search_pattern, search_pattern, search_pattern])

    if start_date:
        clauses.append("created_at >= ?")
        params.append(f"{start_date} 00:00:00" if len(start_date) == 10 else start_date)

    if end_date:
        clauses.append("created_at <= ?")
        params.append(f"{end_date} 23:59:59" if len(end_date) == 10 else end_date)

    where_clause = " AND " + " AND ".join(clauses) if clauses else ""
    offset = (page - 1) * limit

    # Query total de contagem
    count_query = f"SELECT count(*) as total FROM agendamentos WHERE 1=1 {where_clause}"
    count_res = await run_query(count_query, tuple(params), client_id=active_client)
    total = count_res[0]["total"] if count_res else 0

    # Query lista de agendamentos
    list_query = f"""
    SELECT 
        id, created_at, nome, email, numero, canal, 
        data_agendamento, status, detalhes, google_event_id, 
        calendar_id, execution_id, agent_id
    FROM agendamentos
    WHERE 1=1 {where_clause}
    ORDER BY created_at DESC
    LIMIT ? OFFSET ?
    """
    list_params = list(params)
    list_params.extend([limit, offset])

    agendamentos = await run_query(list_query, tuple(list_params), client_id=active_client)

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit if total > 0 else 0,
        "data": agendamentos
    }
