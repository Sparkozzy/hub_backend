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

Retorna métricas consolidadas de ligações, contatos únicos, conversão, minutagem e **métricas de agendamentos (`total_agendamentos` e `taxa_agendamento_por_lead`)**.

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
  "total_agendamentos": 85,
  "taxa_agendamento_por_lead": 6.80,
  "minutagem_total": 485.50,
  "minutagem_media": 1.35,
  "minutagem_por_lead": 0.39,
  "avg_ligacoes_por_lead": 2.84,
  "taxa_interesse_por_lead": 14.80,
  "taxa_tentativa_por_lead": 2.84,
  "avg_density": 0.245,
  "avg_pressure": 0.412
}
```

---

### 2. `GET /agendamentos` — Detalhamento Paginado de Agendamentos (Novo)

Retorna a lista paginada e detalhada de agendamentos registrados no banco local do cliente.

#### Parâmetros de Consulta (Query Params)
- `status` *(opcional, string)*: Filtrar por status (`agendado`, `realizado`, `cancelado`).
- `canal` *(opcional, string)*: Filtrar por canal (`ligacao`, `whatsapp`).
- `search` *(opcional, string)*: Busca parcial por Nome, E-mail ou Telefone.
- `start_date`, `end_date`, `client_id`
- `page` *(opcional, int, padrão: 1)*: Número da página (ge=1).
- `limit` *(opcional, int, padrão: 20, max: 100)*: Itens por página.

#### Exemplo de Resposta (`200 OK`)
```json
{
  "total": 85,
  "page": 1,
  "limit": 20,
  "pages": 5,
  "data": [
    {
      "id": "85a572c0-4f3b-4912-a58a-8e41ec8c95ad",
      "created_at": "2026-07-16 15:05:41",
      "nome": "RYAN FELIPE FERRARI",
      "email": "ryanferrari@iatize-ia.com",
      "numero": "+5548996027108",
      "canal": "ligacao",
      "data_agendamento": "2026-07-17 17:00:00",
      "status": "agendado",
      "detalhes": "Envio de material de indicadores + abertura de relacionamento",
      "google_event_id": "nb56e584ep30akoskbfe3e33rc",
      "calendar_id": "c_0c05c1269e9b6880ecd85c1083e3ff63c6632b53e8d0e72e55db17baec6e8291@group.calendar.google.com",
      "execution_id": "c2ec3a88-7d2f-4784-b4b9-9b99df59fdff",
      "agent_id": "Agente_Gatekeeper_Mindflow_Trafego"
    }
  ]
}
```

---

### 3. `GET /funnel` — Funil de Conversão SDR

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

### 4. `GET /calls` — Auditoria de Ligações (Paginada com Transcrição)

Retorna a lista paginada de chamadas para exibição em tabela, player de áudio e **transcrição textual da conversa (`transcript`)**.

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
      "transcript": "Agente: Olá Carlos, tudo bem?\nLead: Tudo ótimo! Gostaria de saber mais sobre a plataforma.",
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

### 5. `GET /fatigue` — Análise de Fadiga & Pressão

Retorna o impacto do número de tentativas anteriores (`n_tentativas_anteriores`) na taxa de conversão em interesse do lead.

---

### 6. `GET /hours` — Horário Nobre de Contato (Fuso BRT)

Retorna o volume de chamadas e a taxa de conversão agrupados por hora do dia (no fuso `America/Sao_Paulo`).

---

### 7. `GET /disconnections` — Categoria de Desconexões

Retorna a distribuição percentual das causas de encerramento da chamada.

---

### 8. `GET /agents` — Agentes Ativos

Retorna a lista de nomes únicos de agentes SDR que efetuaram chamadas.

---

### 9. `POST /etl/trigger` — Disparo Manual de ETL

Dispara o pipeline de ingestão e pré-processamento em background (Calls + Agendamentos) para o cliente especificado.
