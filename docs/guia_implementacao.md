# Guia de Implementação e Deploy — MindFlow Hub Backend (`hub_backend`)

Este documento orienta o desenvolvedor e o administrador de infraestrutura sobre como implementar, configurar e implantar o microserviço de API **MindFlow Hub Backend (`hub_backend`)** no Easypanel.

---

## 🏗️ 1. Arquitetura da Solução

O **Hub Backend** opera como um microserviço analítico independente em **Python (FastAPI)**, desacoplado da camada de frontend/autenticação em **Node.js (Express)**.

```
┌────────────────────────────────────────────────────────┐
│               Serviço 1: hub-plataformas               │
│               (Node.js / Express - Porta 3000)         │
│  - Autenticação de Usuários via Supabase Auth          │
│  - Sessão Express & Controle de Acessos                │
│  - Proxy/BFF transparente para o Backend Python        │
└───────────────────────────┬────────────────────────────┘
                            │
              Requisição HTTP (Header: X-Client-ID: 5)
                            ▼
┌────────────────────────────────────────────────────────┐
│               Serviço 2: hub_backend                   │
│               (Python / FastAPI - Porta 8000)          │
│  - Multi-Tenancy (Resolução via `client_configurations`)│
│  - ETL diário agendado (3:00 AM BRT via APScheduler)   │
│  - Leitura sub-milissegundo via SQLite por Cliente     │
│  - Conversão estrita de timezone BRT (America/Sao_Paulo)│
└────────────────────────────────────────────────────────┘
```

---

## 🛠️ 2. Estrutura do Repositório

```
hub_backend/
├── app/
│   ├── __init__.py
│   ├── config.py             # Variáveis de ambiente
│   ├── utils.py              # Timezone (BRT), datas e telemetria EDW em Supabase
│   ├── multi_tenant.py       # Resolução dinâmica de clientes (client_configurations)
│   ├── database.py           # Conexões e queries no SQLite por cliente
│   ├── etl.py                # Pipeline de ETL (Extract, Transform BRT, Load)
│   ├── main.py               # Instância FastAPI, CORS e APScheduler (3 AM BRT)
│   └── routers/
│       ├── metrics.py        # /metrics
│       ├── funnel.py         # /funnel
│       ├── calls.py          # /calls
│       ├── fatigue.py        # /fatigue
│       ├── hours.py          # /hours
│       ├── disconnections.py # /disconnections
│       └── agents.py         # /agents & /etl/trigger
├── data/
│   └── clients/              # Guarda bancos SQLite isolados (client_2.db, etc.)
├── Dockerfile                # Image python:3.10-slim para Easypanel
├── .env.example              # Modelo de variáveis de ambiente
└── requirements.txt          # Dependências Python
```

---

## ⚙️ 3. Configuração de Variáveis de Ambiente

No arquivo `.env` (ou no painel do Easypanel), configure as seguintes variáveis:

| Variável | Obrigatória | Exemplo / Valor Padrão | Descrição |
| :--- | :--- | :--- | :--- |
| `SUPABASE_URL` | **Sim** | `https://ghayhpwthdbmnpsptcnb.supabase.co` | URL do Supabase Principal (MindFlow Mestre). |
| `SUPABASE_KEY` | **Sim** | `eyJhbGciOiJIUzI1Ni...` | Chave `service_role` do Supabase Principal para consultar `client_configurations`. |
| `PORT` | Não | `8000` | Porta onde a aplicação FastAPI irá rodar. |
| `TIMEZONE` | Não | `America/Sao_Paulo` | Fuso horário base para agregação e agendamento. |

---

## 🚀 4. Passo a Passo para Deploy no Easypanel

1. **Criar Novo Serviço no Easypanel**:
   - Acesse o painel do Easypanel.
   - Dentro do seu projeto, clique em **+ App** -> selecione **App**.
   - Defina o nome do serviço: `hub-backend` (ou `call-dash-api`).

2. **Configurar Origem do Código (Git)**:
   - **Repository**: `https://github.com/Sparkozzy/hub_backend.git`
   - **Branch**: `main`
   - **Build Method**: Selecione **Dockerfile**.

3. **Configurar Porta e Rede**:
   - Na aba **Port**: Defina a porta de escuta do container como **`8000`**.
   - Defina o domínio público se necessário (ex: `https://hub-api.mindflow-ia.com`) ou utilize a URL interna gerada pelo Easypanel.

4. **Configurar Variáveis de Ambiente**:
   - Acesse a aba **Environment** no Easypanel.
   - Adicione `SUPABASE_URL` e `SUPABASE_KEY` (service_role).

5. **Deploy Inicial**:
   - Clique em **Deploy**.
   - O Easypanel irá construir o container via `Dockerfile` e iniciar a API com o Uvicorn.
   - Acesse `https://sua-url-api/docs` para verificar a interface Swagger do FastAPI.

---

## 🔄 5. Integração com o Serviço de Frontend (`hub-plataformas`)

No serviço do **Frontend (Node.js)** no Easypanel, configure a variável de ambiente:

```bash
DASHBOARD_API_URL=http://hub-backend:8000
```
*(ou a URL externa/interna da API Python).*

No `server.js` do Node.js, ao receber requisições do dashboard (`/metrics`, `/funnel`, etc.), o Express repassa o identificador do cliente no cabeçalho HTTP:

```js
const response = await fetch(`${process.env.DASHBOARD_API_URL}/metrics?${queryParams}`, {
  headers: {
    'X-Client-ID': req.session.user.active_client || '2'
  }
});
```

---

## 📊 6. Manutenção & Agendamento Diário (ETL)

- **Rotina Automática**: O `APScheduler` interno rodando no FastAPI varre todos os clientes ativos diariamente às **3:00 AM (BRT)** e atualiza os arquivos SQLite isolados em `data/clients/client_{id}.db`.
- **Trigger Manual**: É possível forçar a atualização imediata dos dados de qualquer cliente enviando um `POST /etl/trigger` com o header `X-Client-ID`.
