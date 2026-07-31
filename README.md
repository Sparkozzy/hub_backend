# MindFlow Hub Backend — API REST Multi-Tenant (Python FastAPI)

API REST Backend de alta performance construída em **Python (FastAPI)** com processamento analítico via **Pandas**, suporte a **Multi-Tenancy (`client_configurations`)**, bancos de dados **SQLite isolados por cliente** e fuso horário estrito de Brasília (`America/Sao_Paulo`).

---

## 🎯 Funcionalidades

- **Multi-Tenancy Dinâmico**: Resolve o Supabase correto do cliente consultando a tabela `client_configurations` com base no header `X-Client-ID` ou parâmetro `client_id`.
- **Isolamento de Dados**: Cada cliente possui seu próprio banco SQLite em `data/clients/client_{id}.db`.
- **ETL com Fuso BRT**: Trata fusos UTC do Supabase convertendo rigorosamente para `America/Sao_Paulo` antes dos cálculos de horários nobres e fadiga.
- **Respostas de Alta Performance**: Agregações e consultas de auditoria paginadas executadas em sub-milissegundos via SQLite local.
- **Agendador Diário (APScheduler)**: Executa o ETL diário para todos os clientes ativos às 3:00 AM (BRT).

---

## 🚀 Endpoints da API

| Método | Rota | Descrição |
| :--- | :--- | :--- |
| `GET` | `/metrics` | Agregados globais de volume, custos (CPL), interesse e médias de pressão. |
| `GET` | `/funnel` | Leads únicos por estágio do funil (Iniciados, Hook, Conversa, Interesse). |
| `GET` | `/calls` | Tabela paginada para audit de chamadas e player de áudio. |
| `GET` | `/fatigue` | Correlação entre buckets de tentativas e taxa de conversão do lead. |
| `GET` | `/hours` | Distribuição de chamadas e conversão por hora do dia (fuso BRT). |
| `GET` | `/disconnections` | Distribuição de categorias de desconexão (Conversa Normal, Não Atendeu, etc.). |
| `GET` | `/agents` | Lista de agentes únicos com chamadas realizadas. |
| `POST` | `/etl/trigger` | Dispara o pipeline de ETL sob demanda em background para um cliente. |

---

## 📦 Como Rodar Localmente

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Configurar variáveis de ambiente
cp .env.example .env

# 3. Iniciar o servidor de desenvolvimento
python -m uvicorn app.main:app --port 8000 --reload
```

Acesse a documentação interativa Swagger em `http://localhost:8000/docs`.

---

## 🐳 Deploy no Easypanel

O repositório inclui um `Dockerfile` otimizado em `python:3.10-slim`.

- **Build Method**: Dockerfile
- **Porta Exposta**: `8000`
- **Variáveis de Ambiente**: Configurar `SUPABASE_URL` e `SUPABASE_KEY` no painel do Easypanel.
