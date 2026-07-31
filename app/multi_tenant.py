from typing import Tuple, Dict, Any, Optional
from supabase import create_client, Client
from app.config import DEFAULT_SUPABASE_URL, DEFAULT_SUPABASE_KEY

# Cache de clientes Supabase em memória para reutilização de conexões
_supabase_clients_cache: Dict[str, Client] = {}

def get_master_supabase_client() -> Client:
    """Retorna o cliente Supabase principal do sistema (MindFlow)."""
    cache_key = "master"
    if cache_key not in _supabase_clients_cache:
        _supabase_clients_cache[cache_key] = create_client(DEFAULT_SUPABASE_URL, DEFAULT_SUPABASE_KEY)
    return _supabase_clients_cache[cache_key]

def get_supabase_client_for_client_id(client_id: Optional[str] = None) -> Tuple[Client, str]:
    """
    Resolve as credenciais e retorna o cliente Supabase correto baseado no client_id.
    Retorna uma tupla: (SupabaseClient, client_id_normalizado)
    """
    # Se for o cliente padrão (ou não especificado)
    if not client_id or str(client_id).strip() == "2":
        return get_master_supabase_client(), "2"

    cid_str = str(client_id).strip()
    if cid_str in _supabase_clients_cache:
        return _supabase_clients_cache[cid_str], cid_str

    master = get_master_supabase_client()
    try:
        # Consulta client_configurations no Supabase mestre
        response = master.table("client_configurations")\
            .select("client_id, client_name, supabase_url, supabase_service_key, supabase_anon_key")\
            .eq("client_id", cid_str)\
            .maybe_single()\
            .execute()
        
        if response.data:
            cfg = response.data
            url = cfg.get("supabase_url") or DEFAULT_SUPABASE_URL
            # Preferência para service_key para rotas administrativas do backend, depois anon_key
            key = cfg.get("supabase_service_key") or cfg.get("supabase_anon_key") or DEFAULT_SUPABASE_KEY
            
            client = create_client(url, key)
            _supabase_clients_cache[cid_str] = client
            return client, cid_str
    except Exception as e:
        print(f"[MultiTenant Warning] Falha ao resolver client_id '{cid_str}': {e}. Usando cliente padrão.")

    return master, "2"
