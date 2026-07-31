# API Reference — MindFlow Hub Backend (`hub_backend`)

Esta é a documentação de referência completa para todas as rotas e contratos da API REST do **MindFlow Hub Backend**.

---

## 🔑 Autenticação e Multi-Tenancy

A API suporta múltiplos clientes (multi-tenancy) através do cabeçalho HTTP `X-Client-ID` ou do parâmetro de consulta `client_id`.

| Mecanismo | Exemplo | Descrição |
| :--- | :--- | :--- |
| **HTTP Header** | `X-Client-ID: 5` | Identifica o cliente ativo da sessão. |
| **Query Parameter** | `?client_id=5` | Identifica o cliente diretamente na URL. |

> Se nenhum `client_id` for informado (ou for igual a `'2'`), a API operará com o cliente padrão **MindFlow Master**.

---

## 📌 Endpoints

### 1. `GET /metrics` — Indicadores Chave de Desempenho (KPIs)

Retorna métricas consolidadas de ligações, contatos únicos, conversão, custos e médias de pressão de fadiga.

#### Parâmetros de Consulta (Query Params)
- `agent` *(opcional, string)*: Nome amigável do agente SDR.
- `start_date` *(opcional, string)*: Data inicial no formato `YYYY-MM-DD` ou `YYYY-MM-DD HH:MM:SS`.
- `end_date` *(opcional, string)*: Data final no formato `YYYY-MM-DD` ou `YYYY-MM-DD HH:MM:SS`.
- `client_id` *(opcional, string)*: ID do cliente.

#### Exemplo de Resposta (`200 OK`)
```json
{
  "total_calls": 3544,
  "unique_leads": 1250,
  "total_hooks": 890,
  "total_conversas": 420,
  "total_interesse": 185,
  "total_cost": 142.50,
  "avg_ligacoes_por_lead": 2.84,
  "custo_por_lead": 0.11,
  "custo_por_interesse": 0.77,
  "taxa_interesse_por_lead": 14.80,
  "taxa_tentativa_por_lead": 2.84,
  "avg_density": 0.245,
  "avg_pressure": 0.412
}
```

---

### 2. `GET /funnel` — Funil de Conversão SDR

Retorna a quantidade de **Leads Únicos** que atingiram cada um dos 4 estágios do funil.

#### Parâmetros de Consulta (Query Params)
- `agent`, `start_date`, `end_date`, `client_id`

#### Exemplo de Resposta (`200 OK`)
```json
{
  "leads_totais": 1250,
  "leads_iniciados": 1250,
  "hook_15s": 890,
  "conversa_45s": 420,
  "interesse_90s": 185,
  "total_calls_volume": 3544
}
```

---

### 3. `GET /calls` — Auditoria de Ligações (Paginada)

Retorna a lista paginada de chamadas gravadas para exibição em tabela e reprodução no Player de Áudio.

#### Parâmetros de Consulta (Query Params)
- `agent`, `start_date`, `end_date`, `client_id`
- `min_duration` *(opcional, float)*: Duração mínima em segundos.
- `max_duration` *(opcional, float)*: Duração máxima em segundos.
- `page` *(opcional, int, padrão: 1)*: Número da página (ge=1).
- `limit` *(opcional, int, padrão: 20, max: 100)*: Itens por página.

#### Exemplo de Resposta (`200 OK`)
```json
{
  "total": 3544,
  "page": 1,
  "limit": 20,
  "pages": 178,
  "data": [
    {
      "call_id": "call_9a8b7c6d5e4f",
      "to_number": "+5548996027108",
      "Nome": "Carlos Silva",
      "Email": "carlos@exemplo.com",
      "agent_name": "Agente Vendas 01",
      "created_at": "2026-07-31 11:45:00",
      "recording_url": "https://api.retellai.com/recordings/call_9a8b7c6d5e4f.wav",
      "combined_cost": 0.045,
      "Duracao": 125.4,
      "disconnection_category": "Conversa Normal",
      "n_tentativas_anteriores": 2,
      "densidade_tentativas": 0.125,
      "pressao_recente": 0.333
    }
  ]
}
```

---

### 4. `GET /fatigue` — Análise de Fadiga & Pressão

Retorna o impacto do número de tentativas anteriores (`n_tentativas_anteriores`) na taxa de conversão em interesse do lead.

#### Exemplo de Resposta (`200 OK`)
```json
[
  {
    "attempt_bucket": "1ª Ligação",
    "call_count": 1250,
    "interest_count": 95,
    "conversion_rate": 7.60,
    "avg_density": 0.000,
    "avg_pressure": 0.000
  },
  {
    "attempt_bucket": "2ª Ligação",
    "call_count": 820,
    "interest_count": 52,
    "conversion_rate": 6.34,
    "avg_density": 0.180,
    "avg_pressure": 0.350
  }
]
```

---

### 5. `GET /hours` — Horário Nobre de Contato (Fuso BRT)

Retorna o volume de chamadas e a taxa de conversão agrupados por hora do dia (no fuso `America/Sao_Paulo`).

#### Exemplo de Resposta (`200 OK`)
```json
[
  {
    "hour": "09:00",
    "call_count": 320,
    "interest_count": 42,
    "conversion_rate": 13.125
  },
  {
    "hour": "10:00",
    "call_count": 450,
    "interest_count": 68,
    "conversion_rate": 15.11
  }
]
```

---

### 6. `GET /disconnections` — Categoria de Desconexões

Retorna a distribuição percentual das causas de encerramento da chamada.

#### Parâmetros de Consulta (Query Params)
- `detailed` *(opcional, bool, padrão: false)*: Se `true`, retorna os motivos técnicos granulares do Retell.

#### Exemplo de Resposta (`200 OK`)
```json
[
  {
    "category": "Conversa Normal",
    "count": 1850,
    "percentage": 52.20
  },
  {
    "category": "Não Atendeu",
    "count": 1200,
    "percentage": 33.86
  }
]
```

---

### 7. `GET /agents` — Agentes Ativos

Retorna a lista de nomes únicos de agentes SDR que efetuaram chamadas.

#### Exemplo de Resposta (`200 OK`)
```json
[
  "Agente Vendas 01",
  "Agente Vendas 02",
  "Gatekeeper AI"
]
```

---

### 8. `POST /etl/trigger` — Disparo Manual de ETL

Dispara o pipeline de ingestão e pré-processamento em background para o cliente especificado.

#### Exemplo de Resposta (`200 OK`)
```json
{
  "status": "success",
  "message": "ETL pipeline iniciado em background para o cliente 5."
}
```
