import math
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Header, Query
from app.database import run_query

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp Metrics"])

@router.get("/metrics")
async def get_whatsapp_metrics(
    start_date: Optional[str] = Query(None, description="Data inicial YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="Data final YYYY-MM-DD"),
    client_id: Optional[str] = Query(None),
    x_client_id: Optional[str] = Header(None, alias="X-Client-ID")
):
    """
    Retorna métricas consolidadas de engajamento do WhatsApp (Sem agendamentos).
    Regras:
    - leads_novos_24h: Criados nas últimas 24h.
    - leads_ativos_24h: Interagiram nas últimas 24h.
    - taxa_resposta: % de leads que responderam (msg type 'human').
    - tempo_medio_atendimento_minutos: Média de (data_ultima_msgm - created_at).
    """
    cid = x_client_id or client_id or "2"
    
    # 1. Leads totais
    query_total = "SELECT COUNT(*) as cnt FROM leads_mindflow"
    res_total = await run_query(query_total, client_id=cid)
    total_leads = res_total[0]["cnt"] if res_total else 0
    
    # 2. Leads novos (24h)
    query_novos = "SELECT COUNT(*) as cnt FROM leads_mindflow WHERE created_at >= datetime('now', '-24 hours')"
    res_novos = await run_query(query_novos, client_id=cid)
    leads_novos_24h = res_novos[0]["cnt"] if res_novos else 0
    
    # 3. Leads ativos (24h)
    query_ativos = "SELECT COUNT(*) as cnt FROM leads_mindflow WHERE data_ultima_msgm >= datetime('now', '-24 hours')"
    res_ativos = await run_query(query_ativos, client_id=cid)
    leads_ativos_24h = res_ativos[0]["cnt"] if res_ativos else 0
    
    # 4. Mensagens em n8n_chat_histories
    query_msgs = """
    SELECT 
        COUNT(*) as total_msgs,
        SUM(CASE WHEN message_type = 'human' THEN 1 ELSE 0 END) as human_msgs,
        SUM(CASE WHEN message_type = 'ai' THEN 1 ELSE 0 END) as ai_msgs,
        COUNT(DISTINCT CASE WHEN message_type = 'human' THEN session_id END) as leads_responderam
    FROM n8n_chat_histories
    """
    res_msgs = await run_query(query_msgs, client_id=cid)
    row_msgs = res_msgs[0] if res_msgs else {}
    
    total_mensagens = row_msgs.get("total_msgs") or 0
    mensagens_lead = row_msgs.get("human_msgs") or 0
    mensagens_ia = row_msgs.get("ai_msgs") or 0
    leads_responderam = row_msgs.get("leads_responderam") or 0
    
    # Taxa de resposta (%)
    taxa_resposta = round((leads_responderam / total_leads * 100.0), 2) if total_leads > 0 else 0.0
    
    # Média de mensagens por lead
    avg_mensagens_por_lead = round((total_mensagens / total_leads), 2) if total_leads > 0 else 0.0
    
    # 5. Tempo Médio de Atendimento (TMA) em minutos
    # Calculado para leads que possuem data_ultima_msgm e created_at válidos
    query_tma = """
    SELECT AVG(
        (julianday(data_ultima_msgm) - julianday(created_at)) * 1440.0
    ) as tma_min
    FROM leads_mindflow
    WHERE data_ultima_msgm IS NOT NULL AND created_at IS NOT NULL
      AND julianday(data_ultima_msgm) >= julianday(created_at)
    """
    res_tma = await run_query(query_tma, client_id=cid)
    tma_raw = res_tma[0]["tma_min"] if res_tma else 0.0
    tempo_medio_atendimento_minutos = round(float(tma_raw or 0.0), 2)
    
    return {
        "total_leads": total_leads,
        "leads_novos_24h": leads_novos_24h,
        "leads_ativos_24h": leads_ativos_24h,
        "taxa_resposta": taxa_resposta,
        "tempo_medio_atendimento_minutos": tempo_medio_atendimento_minutos,
        "total_mensagens": total_mensagens,
        "mensagens_lead": mensagens_lead,
        "mensagens_ia": mensagens_ia,
        "avg_mensagens_por_lead": avg_mensagens_por_lead
    }

@router.get("/funnel")
async def get_whatsapp_funnel(
    client_id: Optional[str] = Query(None),
    x_client_id: Optional[str] = Header(None, alias="X-Client-ID")
):
    """
    Retorna o funil de engajamento do WhatsApp (Sem agendamentos).
    """
    cid = x_client_id or client_id or "2"
    
    query_funnel = """
    SELECT 
        COUNT(*) as total_leads,
        SUM(CASE WHEN created_at >= datetime('now', '-24 hours') THEN 1 ELSE 0 END) as leads_novos_24h,
        SUM(CASE WHEN data_ultima_msgm >= datetime('now', '-24 hours') THEN 1 ELSE 0 END) as leads_ativos_24h
    FROM leads_mindflow
    """
    res = await run_query(query_funnel, client_id=cid)
    row = res[0] if res else {}
    
    query_responderam = "SELECT COUNT(DISTINCT session_id) as cnt FROM n8n_chat_histories WHERE message_type = 'human'"
    res_resp = await run_query(query_responderam, client_id=cid)
    leads_com_resposta = res_resp[0]["cnt"] if res_resp else 0
    
    query_engajadas = """
    SELECT COUNT(*) as cnt FROM (
        SELECT session_id FROM n8n_chat_histories GROUP BY session_id HAVING COUNT(*) > 5
    )
    """
    res_eng = await run_query(query_engajadas, client_id=cid)
    conversas_engajadas = res_eng[0]["cnt"] if res_eng else 0
    
    return {
        "total_leads": row.get("total_leads") or 0,
        "leads_novos_24h": row.get("leads_novos_24h") or 0,
        "leads_ativos_24h": row.get("leads_ativos_24h") or 0,
        "leads_com_resposta": leads_com_resposta,
        "conversas_engajadas_gt5_msgs": conversas_engajadas
    }

@router.get("/chats")
async def get_whatsapp_chats(
    search: Optional[str] = Query(None, description="Busca por nome, e-mail ou número"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    client_id: Optional[str] = Query(None),
    x_client_id: Optional[str] = Header(None, alias="X-Client-ID")
):
    """
    Retorna a lista paginada de conversas com histórico e transcrição resumida.
    """
    cid = x_client_id or client_id or "2"
    offset = (page - 1) * limit
    
    where_clauses = []
    params = []
    
    if search:
        where_clauses.append("(nome LIKE ? OR email LIKE ? OR numero LIKE ?)")
        search_pattern = f"%{search.strip()}%"
        params.extend([search_pattern, search_pattern, search_pattern])
        
    if start_date:
        where_clauses.append("created_at >= ?")
        params.append(f"{start_date.strip()} 00:00:00")
        
    if end_date:
        where_clauses.append("created_at <= ?")
        params.append(f"{end_date.strip()} 23:59:59")
        
    where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
    
    query_count = f"SELECT COUNT(*) as total FROM leads_mindflow {where_sql}"
    res_count = await run_query(query_count, tuple(params), client_id=cid)
    total = res_count[0]["total"] if res_count else 0
    pages = math.ceil(total / limit) if total > 0 else 1
    
    query_data = f"""
    SELECT 
        id,
        numero,
        nome,
        email,
        created_at,
        data_ultima_msgm,
        ultima_msgm_texto,
        etapa_crm,
        reuniao_marcada,
        causa_raiz,
        transcricao,
        ROUND(CAST((julianday(COALESCE(data_ultima_msgm, created_at)) - julianday(created_at)) * 1440.0 AS REAL), 2) as duracao_atendimento_minutos
    FROM leads_mindflow
    {where_sql}
    ORDER BY data_ultima_msgm DESC, created_at DESC
    LIMIT ? OFFSET ?
    """
    params_data = list(params) + [limit, offset]
    rows = await run_query(query_data, tuple(params_data), client_id=cid)
    
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
        "data": rows
    }

@router.get("/chats/{session_id}/messages")
async def get_chat_messages(
    session_id: str,
    client_id: Optional[str] = Query(None),
    x_client_id: Optional[str] = Header(None, alias="X-Client-ID")
):
    """
    Retorna o histórico de mensagens trocadas em uma sessão/telefone específico.
    """
    cid = x_client_id or client_id or "2"
    clean_session = session_id.strip()
    
    query = """
    SELECT id, session_id, message_type, message_content, created_at
    FROM n8n_chat_histories
    WHERE session_id = ?
    ORDER BY id ASC
    """
    messages = await run_query(query, (clean_session,), client_id=cid)
    
    return {
        "session_id": clean_session,
        "total_messages": len(messages),
        "messages": messages
    }

@router.get("/hours")
async def get_whatsapp_hours(
    client_id: Optional[str] = Query(None),
    x_client_id: Optional[str] = Header(None, alias="X-Client-ID")
):
    """
    Retorna a distribuição de mensagens agrupadas por hora do dia.
    """
    cid = x_client_id or client_id or "2"
    
    query = """
    SELECT 
        strftime('%H', created_at) as hora,
        COUNT(*) as total_mensagens,
        SUM(CASE WHEN message_type = 'human' THEN 1 ELSE 0 END) as mensagens_lead,
        SUM(CASE WHEN message_type = 'ai' THEN 1 ELSE 0 END) as mensagens_ia
    FROM n8n_chat_histories
    WHERE created_at IS NOT NULL
    GROUP BY hora
    ORDER BY hora ASC
    """
    rows = await run_query(query, client_id=cid)
    
    return {
        "hours_distribution": rows
    }
