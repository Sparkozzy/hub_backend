import os
import sqlite3
import asyncio
from typing import List, Dict, Any, Tuple, Optional

def get_db_path_for_client(client_id: str = "2") -> str:
    """Retorna o caminho do banco SQLite isolado para um cliente."""
    clean_id = str(client_id).strip() or "2"
    base_dir = os.path.join("data", "clients")
    os.makedirs(base_dir, exist_ok=True)
    return os.path.join(base_dir, f"client_{clean_id}.db")

def init_db_for_client(client_id: str = "2"):
    """Garante que a tabela calls e seus índices existam para o cliente."""
    db_path = get_db_path_for_client(client_id)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS calls (
        call_id TEXT PRIMARY KEY,
        to_number TEXT,
        Nome TEXT,
        Email TEXT,
        agent_name TEXT,
        created_at TEXT,
        recording_url TEXT,
        combined_cost REAL,
        Duracao REAL,
        disconnection_reason TEXT,
        disconnection_category TEXT,
        is_ligacao INTEGER,
        is_hook INTEGER,
        is_conversa INTEGER,
        is_interesse INTEGER,
        n_tentativas_anteriores INTEGER,
        horas_desde_primeiro_contato REAL,
        horas_desde_ultimo_contato REAL,
        densidade_tentativas REAL,
        pressao_recente REAL
    )
    """)
    
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_calls_call_id ON calls(call_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_calls_to_number ON calls(to_number)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_calls_agent_name ON calls(agent_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_calls_created_at ON calls(created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_calls_duration ON calls(Duracao)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_calls_disconnection_category ON calls(disconnection_category)")
    
    conn.commit()
    conn.close()

async def run_query(query: str, params: tuple = (), client_id: str = "2") -> List[Dict[str, Any]]:
    """Executa uma query no banco SQLite do cliente assincronamente sem bloquear a thread principal."""
    db_path = get_db_path_for_client(client_id)
    if not os.path.exists(db_path):
        init_db_for_client(client_id)

    def sync_query():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    return await asyncio.to_thread(sync_query)

def build_filter_clauses(
    agent: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Tuple[str, List[Any]]:
    """Helper para construir cláusulas WHERE dinâmicas em SQL."""
    clauses = []
    params = []

    if agent:
        clauses.append("agent_name = ?")
        params.append(agent)

    if start_date:
        if len(start_date) == 10:
            clauses.append("created_at >= ?")
            params.append(f"{start_date} 00:00:00")
        else:
            clauses.append("created_at >= ?")
            params.append(start_date)

    if end_date:
        if len(end_date) == 10:
            clauses.append("created_at <= ?")
            params.append(f"{end_date} 23:59:59")
        else:
            clauses.append("created_at <= ?")
            params.append(end_date)

    where_clause = " AND " + " AND ".join(clauses) if clauses else ""
    return where_clause, params
