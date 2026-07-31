import uuid
import random
import datetime
import zoneinfo
import asyncio
from typing import Callable, Any, Optional, Dict
from app.config import TIMEZONE_STR
from app.multi_tenant import get_supabase_client_for_client_id

BR_TZ = zoneinfo.ZoneInfo(TIMEZONE_STR)

def get_utc_now() -> str:
    """Returns ISO 8601 UTC string for database persistence."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def get_br_now() -> datetime.datetime:
    """Returns datetime in America/Sao_Paulo timezone for internal logic."""
    return datetime.datetime.now(BR_TZ)

def parse_iso_to_br(iso_date: str) -> datetime.datetime:
    """Converts ISO 8601 string of any timezone to America/Sao_Paulo datetime."""
    dt = datetime.datetime.fromisoformat(iso_date)
    return dt.astimezone(BR_TZ)

async def run_in_thread(func: Callable, *args, **kwargs) -> Any:
    """Runs a synchronous function in a separate thread to prevent blocking async loop."""
    return await asyncio.to_thread(func, *args, **kwargs)

async def start_workflow_execution(
    workflow_name: str, 
    input_data: Optional[Dict] = None,
    client_id: str = "2"
) -> str:
    """Registra uma nova execução de workflow em workflow_executions no Supabase do cliente."""
    execution_id = str(uuid.uuid4())
    input_payload = input_data or {}
    now = get_utc_now()
    supabase, _ = get_supabase_client_for_client_id(client_id)
    
    payload = {
        "id": execution_id,
        "workflow_name": workflow_name,
        "status": "PENDING",
        "input_data": input_payload,
        "created_at": now,
        "updated_at": now
    }
    
    try:
        def insert_master():
            return supabase.table("workflow_executions").insert(payload).execute()
        await run_in_thread(insert_master)
    except Exception as e:
        print(f"[Telemetry Warning - Cliente {client_id}] Failed to insert PENDING workflow: {e}")
        return execution_id
        
    try:
        def update_master():
            return supabase.table("workflow_executions").update({
                "status": "RUNNING",
                "started_at": get_utc_now(),
                "updated_at": get_utc_now()
            }).eq("id", execution_id).execute()
        await run_in_thread(update_master)
    except Exception as e:
        print(f"[Telemetry Warning - Cliente {client_id}] Failed to update workflow to RUNNING: {e}")
        
    await asyncio.sleep(0.5)
    return execution_id

async def finish_workflow_execution(
    execution_id: str, 
    status: str, 
    output_data: Optional[Dict] = None, 
    error_details: Optional[str] = None,
    client_id: str = "2"
):
    """Marca uma execução de workflow como FINISHED ou FAILED."""
    supabase, _ = get_supabase_client_for_client_id(client_id)
    payload = {
        "status": status,
        "completed_at": get_utc_now(),
        "updated_at": get_utc_now()
    }
    if output_data is not None:
        payload["output_data"] = output_data
    if error_details is not None:
        payload["error_details"] = error_details
        
    try:
        def update_master():
            return supabase.table("workflow_executions").update(payload).eq("id", execution_id).execute()
        await run_in_thread(update_master)
    except Exception as e:
        print(f"[Telemetry Warning - Cliente {client_id}] Failed to finish workflow ({status}): {e}")

async def run_step_with_retry(
    execution_id: str,
    step_name: str,
    worker_func: Optional[Callable[[], Any]] = None,
    max_retries: int = 3,
    input_data: Optional[Dict] = None,
    client_id: str = "2"
) -> Any:
    """Executa um step com retentativa e grava em workflow_step_executions."""
    supabase, _ = get_supabase_client_for_client_id(client_id)
    input_payload = input_data or {}
    attempt = 0
    last_error = None
    
    while attempt < max_retries:
        attempt += 1
        step_id = str(uuid.uuid4())
        started_at = get_utc_now()
        
        step_init_payload = {
            "id": step_id,
            "execution_id": execution_id,
            "step_name": step_name,
            "status": "RUNNING",
            "attempt": attempt,
            "input_data": input_payload,
            "started_at": started_at,
            "created_at": started_at
        }
        try:
            def log_step_init():
                return supabase.table("workflow_step_executions").insert(step_init_payload).execute()
            await run_in_thread(log_step_init)
        except Exception as e:
            print(f"[Telemetry Warning - Cliente {client_id}] Step init failed ({step_name}): {e}")
        
        try:
            if worker_func:
                if asyncio.iscoroutinefunction(worker_func):
                    result = await worker_func()
                else:
                    result = await run_in_thread(worker_func)
            else:
                result = {"simulated": True}
                
            completed_at = get_utc_now()
            step_success_payload = {
                "status": "SUCCESS",
                "output_data": result if isinstance(result, dict) else {"result": str(result)},
                "completed_at": completed_at
            }
            try:
                def log_step_success():
                    return supabase.table("workflow_step_executions").update(step_success_payload).eq("id", step_id).execute()
                await run_in_thread(log_step_success)
            except Exception as e:
                print(f"[Telemetry Warning - Cliente {client_id}] Step success log failed: {e}")
                
            return result
            
        except Exception as e:
            last_error = str(e)
            completed_at = get_utc_now()
            step_fail_payload = {
                "status": "FAILED",
                "error_details": last_error,
                "completed_at": completed_at
            }
            try:
                def log_step_fail():
                    return supabase.table("workflow_step_executions").update(step_fail_payload).eq("id", step_id).execute()
                await run_in_thread(log_step_fail)
            except Exception as ex:
                print(f"[Telemetry Warning - Cliente {client_id}] Step fail log failed: {ex}")
            
            if attempt < max_retries:
                backoff_time = min(30.0, (2 ** attempt) + random.random())
                await asyncio.sleep(backoff_time)
                
    raise RuntimeError(f"Step {step_name} failed after {max_retries} attempts. Last error: {last_error}")
