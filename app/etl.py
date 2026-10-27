import os
import json
import sqlite3
import pandas as pd
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timezone
from app.multi_tenant import get_supabase_client_for_client_id
from app.database import get_db_path_for_client, init_db_for_client
from app.utils import (
    start_workflow_execution,
    finish_workflow_execution,
    run_step_with_retry,
    BR_TZ
)

# ============================================================
# HELPER DE DATA LOCAL NO SQLITE
# ============================================================
def get_last_created_at_local(table_name: str = "calls", client_id: str = "2") -> Optional[str]:
    """Retorna a última data registrada no SQLite do cliente em formato UTC ISO 8601."""
    db_path = get_db_path_for_client(client_id)
    if not os.path.exists(db_path):
        return None
        
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"SELECT MAX(created_at) FROM {table_name}")
        row = cursor.fetchone()
        conn.close()
        
        if row and row[0]:
            last_created_str = row[0]
            dt_local = datetime.strptime(last_created_str, '%Y-%m-%d %H:%M:%S')
            dt_local_with_tz = dt_local.replace(tzinfo=BR_TZ)
            dt_utc = dt_local_with_tz.astimezone(timezone.utc)
            return dt_utc.isoformat()
    except Exception as e:
        print(f"[ETL Warning] Erro ao consultar estado local ({table_name}) do cliente {client_id}: {e}")
        
    return None

# ============================================================
# INGESTÃO E PROCESSAMENTO DE LIGAÇÕES (calls)
# ============================================================
def extract_supabase_calls(client_id: str = "2", last_created_at_utc: Optional[str] = None) -> List[Dict[str, Any]]:
    """Extrai chamadas do Supabase do cliente com paginação de 1.000 em 1.000."""
    supabase_client, _ = get_supabase_client_for_client_id(client_id)
    
    if last_created_at_utc:
        print(f"[ETL Extract - Calls - Cliente {client_id}] Ingestão INCREMENTAL desde {last_created_at_utc}...")
    else:
        print(f"[ETL Extract - Calls - Cliente {client_id}] Ingestão FULL SYNC...")
        
    all_data = []
    batch_size = 1000
    start = 0
    columns = "id, call_id, to_number, Nome, Email, agent_name, created_at, recording_url, transcript, Duracao, disconnection_reason"
    
    while True:
        query = supabase_client.table("Retell_calls_Mindflow").select(columns)
        if last_created_at_utc:
            query = query.gt("created_at", last_created_at_utc)
            
        response = query.range(start, start + batch_size - 1).execute()
        if not response.data:
            break
            
        all_data.extend(response.data)
        print(f"[ETL Extract - Calls - Cliente {client_id}] Lote de {len(response.data)} registros (Total: {len(all_data)})")
        
        if len(response.data) < batch_size:
            break
        start += batch_size
        
    return all_data

def transform_call_data(raw_calls: List[Dict[str, Any]], client_id: str = "2", is_incremental: bool = False) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Processa e calcula variáveis de fadiga e fuso horário de Brasília."""
    if not raw_calls:
        raise ValueError("Nenhum registro extraído do Supabase.")
        
    df_new = pd.DataFrame(raw_calls)
    df_new['created_at'] = pd.to_datetime(df_new['created_at'], format='ISO8601', utc=True).dt.tz_convert('America/Sao_Paulo')
    def clean_duration(val: Any) -> float:
        if pd.isna(val) or val is None or val == "":
            return 0.0
        val_str = str(val).strip()
        try:
            val_float = float(val_str)
        except (ValueError, TypeError):
            return 0.0

        if val_float <= 0:
            return 0.0

        # Se for inteiro (ex: '996', '14971' vindo de duration_ms da Retell) ou valor >= 1000 ms:
        if val_str.isdigit() or val_float >= 1000.0:
            return round(val_float / 1000.0, 3)

        # Já está em segundos (ex: '3.769', '11.272')
        return round(val_float, 3)

    df_new['Duracao'] = df_new['Duracao'].apply(clean_duration)
    df_new['transcript'] = df_new['transcript'].fillna("")
    
    def map_disconnection_reason(reason: Any, duration_sec: float) -> str:
        if pd.isna(reason) or not reason:
            return "Conversa Normal" if duration_sec > 15.0 else "Não Atendeu"
        reason_str = str(reason).lower().strip()
        
        if reason_str in ["agent_hangup", "user_hangup", "inactivity", "max_duration_reached", "call_transfer"]:
            return "Conversa Normal"
        elif reason_str in ["dial_no_answer", "no-answer", "voicemail_reached"]:
            return "Não Atendeu"
        elif reason_str in ["user_declined", "invalid_destination"]:
            return "Bloqueado"
        elif reason_str in ["dial_busy", "ivr_reached"]:
            return "Ocupado"
        elif reason_str.startswith("telephony_provider_") or reason_str in ["error_asr", "error_retell", "dial_failed"]:
            return "Erro Técnico"
        else:
            return "Conversa Normal" if duration_sec > 15.0 else "Não Atendeu"
            
    df_new['disconnection_category'] = df_new.apply(lambda row: map_disconnection_reason(row['disconnection_reason'], row['Duracao']), axis=1)
    df_new['is_ligacao'] = (df_new['Duracao'] > 0.0).astype(int)
    df_new['is_hook'] = (df_new['Duracao'] > 15.0).astype(int)
    df_new['is_conversa'] = (df_new['Duracao'] > 45.0).astype(int)
    df_new['is_interesse'] = (df_new['Duracao'] > 90.0).astype(int)
    
    if is_incremental:
        active_leads = df_new['to_number'].dropna().unique()
        db_path = get_db_path_for_client(client_id)
        if os.path.exists(db_path) and len(active_leads) > 0:
            try:
                conn = sqlite3.connect(db_path)
                placeholders = ",".join(["?"] * len(active_leads))
                query = f"SELECT * FROM calls WHERE to_number IN ({placeholders})"
                df_old = pd.read_sql_query(query, conn, params=list(active_leads))
                conn.close()
                
                if not df_old.empty:
                    df_old['created_at'] = pd.to_datetime(df_old['created_at'], format='ISO8601').dt.tz_localize('America/Sao_Paulo')
                    df_old['Duracao'] = pd.to_numeric(df_old['Duracao'], errors='coerce').fillna(0.0)
                    if 'transcript' not in df_old.columns:
                        df_old['transcript'] = ""
                    df_old['transcript'] = df_old['transcript'].fillna("")
                    df = pd.concat([df_old, df_new], ignore_index=True)
                else:
                    df = df_new
            except Exception as e:
                print(f"[ETL Warning] Falha ao carregar histórico local: {e}. Usando dados novos.")
                df = df_new
        else:
            df = df_new
    else:
        df = df_new
        
    df = df.sort_values('created_at')
    initial_len = len(df)
    if 'call_id' in df.columns and df['call_id'].notna().any():
        # Usa call_id onde disponível, e id onde call_id for nulo
        df['dedup_key'] = df['call_id'].fillna(df['id'].astype(str))
        df = df.drop_duplicates(subset=['dedup_key'], keep='last').drop(columns=['dedup_key'])
    else:
        df = df.drop_duplicates(subset=['id'], keep='last')
    deduped_len = len(df)
    
    df = df.sort_values(['to_number', 'created_at']).reset_index(drop=True)
    df['n_tentativas_anteriores'] = df.groupby('to_number').cumcount()
    
    first_contact = df.groupby('to_number')['created_at'].transform('min')
    df['horas_desde_primeiro_contato'] = (df['created_at'] - first_contact).dt.total_seconds() / 3600.0
    
    last_contact = df.groupby('to_number')['created_at'].shift(1)
    df['horas_desde_ultimo_contato'] = (df['created_at'] - last_contact).dt.total_seconds() / 3600.0
    df['horas_desde_ultimo_contato'] = df['horas_desde_ultimo_contato'].fillna(0.0)
    
    df['densidade_tentativas'] = df['n_tentativas_anteriores'] / (df['horas_desde_primeiro_contato'] + 1.0)
    df['pressao_recente'] = df['n_tentativas_anteriores'] / (df['horas_desde_ultimo_contato'] + 1.0)
    
    df = df.sort_values('created_at', ascending=False).reset_index(drop=True)
    
    metadata = {
        "initial_record_count": initial_len,
        "deduped_record_count": deduped_len,
        "unique_leads": df['to_number'].nunique(),
        "total_ligacoes": int(df['is_ligacao'].sum()),
        "total_hooks": int(df['is_hook'].sum()),
        "total_conversas": int(df['is_conversa'].sum()),
        "total_interesse": int(df['is_interesse'].sum())
    }
    return df, metadata

def load_data_to_sqlite(df: pd.DataFrame, client_id: str = "2", is_incremental: bool = False) -> Dict[str, Any]:
    """Salva os dados transformados de chamadas na base SQLite do cliente."""
    init_db_for_client(client_id)
    db_path = get_db_path_for_client(client_id)
    
    df_db = df.copy()
    df_db['created_at'] = pd.to_datetime(df_db['created_at']).dt.strftime('%Y-%m-%d %H:%M:%S')
    
    conn = sqlite3.connect(db_path)
    try:
        if is_incremental:
            active_leads = df['to_number'].dropna().unique()
            cursor = conn.cursor()
            placeholders = ",".join(["?"] * len(active_leads))
            cursor.execute(f"DELETE FROM calls WHERE to_number IN ({placeholders})", list(active_leads))
            conn.commit()
            df_db.to_sql("calls", conn, if_exists="append", index=False)
        else:
            df_db.to_sql("calls", conn, if_exists="replace", index=False)
            init_db_for_client(client_id)
            
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM calls")
        saved_count = cursor.fetchone()[0]
    finally:
        conn.close()
        
    return {"saved_count": saved_count, "db_path": db_path}

# ============================================================
# INGESTÃO E PROCESSAMENTO DE AGENDAMENTOS (agendamentos)
# ============================================================
def extract_supabase_agendamentos(client_id: str = "2", last_created_at_utc: Optional[str] = None) -> List[Dict[str, Any]]:
    """Extrai novos agendamentos da tabela agendamentos no Supabase do cliente."""
    supabase_client, _ = get_supabase_client_for_client_id(client_id)
    
    if last_created_at_utc:
        print(f"[ETL Extract - Agendamentos - Cliente {client_id}] Ingestão INCREMENTAL desde {last_created_at_utc}...")
    else:
        print(f"[ETL Extract - Agendamentos - Cliente {client_id}] Ingestão FULL SYNC...")
        
    all_data = []
    batch_size = 1000
    start = 0
    columns = "id, created_at, nome, email, numero, canal, data_agendamento, status, detalhes, google_event_id, calendar_id, execution_id, agent_id"
    
    try:
        while True:
            query = supabase_client.table("agendamentos").select(columns)
            if last_created_at_utc:
                query = query.gt("created_at", last_created_at_utc)
                
            response = query.range(start, start + batch_size - 1).execute()
            if not response.data:
                break
                
            all_data.extend(response.data)
            print(f"[ETL Extract - Agendamentos - Cliente {client_id}] Lote de {len(response.data)} agendamentos (Total: {len(all_data)})")
            
            if len(response.data) < batch_size:
                break
            start += batch_size
    except Exception as e:
        print(f"[ETL Warning - Cliente {client_id}] Tabela agendamentos não acessível ou sem dados: {e}")
        
    return all_data

def transform_and_load_agendamentos(raw_agendamentos: List[Dict[str, Any]], client_id: str = "2", is_incremental: bool = False) -> int:
    """Transforma datas para BRT e carrega na tabela agendamentos do SQLite."""
    if not raw_agendamentos:
        return 0
        
    df = pd.DataFrame(raw_agendamentos)
    
    # Converter created_at e data_agendamento para Brasília
    if 'created_at' in df.columns:
        df['created_at'] = pd.to_datetime(df['created_at']).dt.tz_convert('America/Sao_Paulo').dt.strftime('%Y-%m-%d %H:%M:%S')
    if 'data_agendamento' in df.columns:
        df['data_agendamento'] = pd.to_datetime(df['data_agendamento'], errors='coerce').dt.tz_convert('America/Sao_Paulo').dt.strftime('%Y-%m-%d %H:%M:%S')
        
    init_db_for_client(client_id)
    db_path = get_db_path_for_client(client_id)
    
    conn = sqlite3.connect(db_path)
    try:
        if is_incremental:
            cursor = conn.cursor()
            existing_ids = df['id'].dropna().tolist()
            if existing_ids:
                placeholders = ",".join(["?"] * len(existing_ids))
                cursor.execute(f"DELETE FROM agendamentos WHERE id IN ({placeholders})", existing_ids)
                conn.commit()
            df.to_sql("agendamentos", conn, if_exists="append", index=False)
        else:
            df.to_sql("agendamentos", conn, if_exists="replace", index=False)
            init_db_for_client(client_id)
            
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM agendamentos")
        saved_count = cursor.fetchone()[0]
    finally:
        conn.close()
        
    return saved_count

# ============================================================
# INGESTÃO E PROCESSAMENTO DE WHATSAPP (leads_mindflow & n8n_chat_histories)
# ============================================================
def extract_supabase_whatsapp_leads(client_id: str = "2") -> List[Dict[str, Any]]:
    """Extrai leads da tabela Leads_Mindflow no Supabase."""
    supabase_client, _ = get_supabase_client_for_client_id(client_id)
    all_data = []
    batch_size = 1000
    start = 0
    
    try:
        while True:
            response = supabase_client.table("Leads_Mindflow").select("*").range(start, start + batch_size - 1).execute()
            if not response.data:
                break
            all_data.extend(response.data)
            if len(response.data) < batch_size:
                break
            start += batch_size
    except Exception as e:
        print(f"[ETL Warning - Cliente {client_id}] Tabela Leads_Mindflow erro: {e}")
        
    return all_data

def extract_supabase_n8n_chat_histories(client_id: str = "2") -> List[Dict[str, Any]]:
    """Extrai histórico de chats da tabela n8n_chat_histories no Supabase."""
    supabase_client, _ = get_supabase_client_for_client_id(client_id)
    all_data = []
    batch_size = 1000
    start = 0
    
    try:
        while True:
            response = supabase_client.table("n8n_chat_histories").select("id, session_id, message, created_at").range(start, start + batch_size - 1).execute()
            if not response.data:
                break
            all_data.extend(response.data)
            if len(response.data) < batch_size:
                break
            start += batch_size
    except Exception as e:
        print(f"[ETL Warning - Cliente {client_id}] Tabela n8n_chat_histories erro: {e}")
        
    return all_data

def transform_and_load_whatsapp_data(raw_leads: List[Dict[str, Any]], raw_chats: List[Dict[str, Any]], client_id: str = "2") -> Dict[str, int]:
    """Carrega dados de WhatsApp no SQLite local do cliente."""
    init_db_for_client(client_id)
    db_path = get_db_path_for_client(client_id)
    conn = sqlite3.connect(db_path)
    
    saved_leads = 0
    saved_chats = 0
    
    try:
        if raw_leads:
            df_leads = pd.DataFrame(raw_leads)
            # Mapear nomes de colunas do Supabase para o SQLite local
            rename_map = {
                "id": "id",
                "Número": "numero",
                "Nome": "nome",
                "Email": "email",
                "created_at": "created_at",
                "data ultima msgm": "data_ultima_msgm",
                "Ultima msgm (texto)": "ultima_msgm_texto",
                "Etapa CRM": "etapa_crm",
                "Reunião Marcada": "reuniao_marcada",
                "causa_raiz": "causa_raiz",
                "transcricao": "transcricao"
            }
            # Manter apenas colunas mapeadas que existem no DataFrame
            cols_to_keep = [col for col in rename_map.keys() if col in df_leads.columns]
            df_leads_clean = df_leads[cols_to_keep].rename(columns=rename_map)
            
            # Garantir deduplicação por número
            if "numero" in df_leads_clean.columns:
                df_leads_clean = df_leads_clean.drop_duplicates(subset=["numero"], keep="last")
                
            df_leads_clean.to_sql("leads_mindflow", conn, if_exists="replace", index=False)
            cursor = conn.cursor()
            cursor.execute("SELECT count(*) FROM leads_mindflow")
            saved_leads = cursor.fetchone()[0]

        if raw_chats:
            formatted_chats = []
            for item in raw_chats:
                msg_obj = item.get("message") or {}
                if isinstance(msg_obj, str):
                    try:
                        msg_obj = json.loads(msg_obj)
                    except Exception:
                        msg_obj = {}
                
                formatted_chats.append({
                    "id": item.get("id"),
                    "session_id": str(item.get("session_id") or ""),
                    "message_type": msg_obj.get("type", "unknown") if isinstance(msg_obj, dict) else "unknown",
                    "message_content": str(msg_obj.get("content", "")) if isinstance(msg_obj, dict) else str(msg_obj),
                    "created_at": item.get("created_at")
                })
                
            df_chats = pd.DataFrame(formatted_chats)
            df_chats.to_sql("n8n_chat_histories", conn, if_exists="replace", index=False)
            cursor = conn.cursor()
            cursor.execute("SELECT count(*) FROM n8n_chat_histories")
            saved_chats = cursor.fetchone()[0]

    except Exception as exc:
        import traceback
        print(f"[ETL Error transform_and_load_whatsapp_data]: {exc}")
        traceback.print_exc()
        raise exc
    finally:
        conn.close()
        
    return {"saved_leads": saved_leads, "saved_chats": saved_chats}

# ============================================================
# ORQUESTRADOR PRINCIPAL DO PIPELINE
# ============================================================
async def run_etl_pipeline(client_id: str = "2") -> Dict[str, Any]:
    """Orquestrador completo de ETL (Chamadas + Agendamentos + WhatsApp) por cliente."""
    execution_id = await start_workflow_execution(
        workflow_name=f"dashboard_etl_client_{client_id}",
        input_data={"trigger": "manual_or_scheduler", "client_id": client_id},
        client_id=client_id
    )
    
    last_created_at_utc = get_last_created_at_local("calls", client_id)
    is_incremental = last_created_at_utc is not None
    raw_calls = []
    raw_agendamentos = []
    raw_wa_leads = []
    raw_wa_chats = []
    df_transformed = None
    
    try:
        # Step 1: Extract Calls, Agendamentos & WhatsApp
        async def extract_worker():
            nonlocal raw_calls, raw_agendamentos, raw_wa_leads, raw_wa_chats
            raw_calls = extract_supabase_calls(client_id, last_created_at_utc)
            
            last_agendamento_utc = get_last_created_at_local("agendamentos", client_id)
            raw_agendamentos = extract_supabase_agendamentos(client_id, last_agendamento_utc)

            raw_wa_leads = extract_supabase_whatsapp_leads(client_id)
            raw_wa_chats = extract_supabase_n8n_chat_histories(client_id)
            return {
                "calls_count": len(raw_calls),
                "agendamentos_count": len(raw_agendamentos),
                "wa_leads_count": len(raw_wa_leads),
                "wa_chats_count": len(raw_wa_chats)
            }
            
        await run_step_with_retry(
            execution_id=execution_id,
            step_name="dashboard_etl_extract",
            worker_func=extract_worker,
            client_id=client_id
        )
        
        # Step 2: Transform & Load Agendamentos & WhatsApp
        def extra_data_worker():
            try:
                out = {}
                if raw_agendamentos:
                    ag_last = get_last_created_at_local("agendamentos", client_id)
                    out["saved_agendamentos"] = transform_and_load_agendamentos(raw_agendamentos, client_id, is_incremental=ag_last is not None)
                if raw_wa_leads or raw_wa_chats:
                    wa_out = transform_and_load_whatsapp_data(raw_wa_leads, raw_wa_chats, client_id)
                    out.update(wa_out)
                return out
            except Exception as e:
                import traceback
                print(f"[EXTRA DATA WORKER EXCEPTION]: {e}", flush=True)
                traceback.print_exc()
                raise e
            
        await run_step_with_retry(
            execution_id=execution_id,
            step_name="dashboard_etl_extra_data",
            worker_func=extra_data_worker,
            client_id=client_id
        )

        if is_incremental and len(raw_calls) == 0:
            summary = {
                "status": "SUCCESS (Sem novas chamadas)",
                "agendamentos_loaded": len(raw_agendamentos),
                "wa_leads_loaded": len(raw_wa_leads),
                "wa_chats_loaded": len(raw_wa_chats),
                "client_id": client_id
            }
            await finish_workflow_execution(execution_id, "FINISHED", summary, client_id=client_id)
            return summary
            
        # Step 3: Transform Calls
        async def transform_worker():
            nonlocal df_transformed
            df_transformed, meta = transform_call_data(raw_calls, client_id, is_incremental)
            return meta
            
        await run_step_with_retry(
            execution_id=execution_id,
            step_name="dashboard_etl_transform",
            worker_func=transform_worker,
            client_id=client_id
        )
        
        # Step 4: Load Calls
        async def load_worker():
            return load_data_to_sqlite(df_transformed, client_id, is_incremental)
            
        load_out = await run_step_with_retry(
            execution_id=execution_id,
            step_name="dashboard_etl_load",
            worker_func=load_worker,
            client_id=client_id
        )
        
        summary = {
            "status": "FINISHED",
            "calls_extracted": len(raw_calls),
            "calls_loaded": load_out["saved_count"],
            "agendamentos_extracted": len(raw_agendamentos),
            "wa_leads_extracted": len(raw_wa_leads),
            "wa_chats_extracted": len(raw_wa_chats),
            "client_id": client_id
        }
        await finish_workflow_execution(execution_id, "FINISHED", summary, client_id=client_id)
        return summary
        
    except Exception as e:
        await finish_workflow_execution(execution_id, "FAILED", error_details=str(e), client_id=client_id)
        raise e

