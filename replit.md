# Vértice CRM v2.0

## Visão Geral
CRM completo da Vértice Agência Digital com módulo de Lead Hunting integrado ao PostgreSQL.

## Tecnologias
- **Frontend:** HTML, CSS, JavaScript puro (sem frameworks)
- **Backend:** FastAPI (Python 3.11) — serve estáticos + API REST
- **Banco de Dados:** PostgreSQL (Replit built-in)
- **ORM:** SQLAlchemy
- **Validação:** Pydantic v2
- **Busca de Leads:** OpenStreetMap / Overpass API (gratuito, sem chave)

## Estrutura de Arquivos
```
index.html          — CRM principal (Dashboard, Pipeline Kanban, Clientes, Financeiro)
lead-hunter.html    — Módulo de Lead Hunting (busca OSM + AI Priority)
api/
  main.py           — FastAPI app (endpoints + serve static files)
  models.py         — SQLAlchemy Lead model (PostgreSQL)
  schemas.py        — Pydantic schemas com validação
  search.py         — Engine de busca Overpass + calcAIPriority
  database.py       — Conexão PostgreSQL via SQLAlchemy
```

## API Endpoints
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/health` | Status do servidor |
| GET | `/api/stats` | Estatísticas dos leads no banco |
| POST | `/api/leads/hunt` | Busca leads via OSM (termo livre: "Academia em SP") |
| POST | `/api/leads/import` | Importa leads para PostgreSQL (dedup por osm_id/email/cnpj); retorna `saved_ids` |
| GET | `/api/leads` | Lista leads com filtros (status, segmento, min_priority, scored_only) |
| GET | `/api/leads/{id}` | Detalhe de um lead |
| PUT | `/api/leads/{id}/status` | Atualiza status do lead |
| DELETE | `/api/leads/{id}` | Remove lead |
| **POST** | **`/api/leads/{id}/score`** | **Analisa lead com GPT-5-mini → ai_score, pain_point, pitch_hook** |
| **POST** | **`/api/leads/score-batch`** | **Analisa múltiplos leads com IA (até 50 por vez)** |

## AI Lead Scoring (GPT-5-mini via Replit AI Integrations)
Arquivo: `api/ai_scoring.py`

Analisa cada lead e retorna um JSON com:
- **ai_score** (0-10): fit para a Vértice Agência Digital
- **pain_point**: dor principal identificada em 1 frase (pt-BR)
- **pitch_hook**: frase de abertura personalizada para WhatsApp (pt-BR)

**Fluxo automático:** ao clicar "💾 DB" no Lead Hunter, o lead é salvo e imediatamente analisado pela IA. O modal de resultado abre com o pitch pronto.

**Fluxo manual:** botão "🤖 ANALISAR LEADS NO BANCO" analisa os próximos 10 leads sem ai_score.

## Modelo de Lead (PostgreSQL)
- `id` — UUID primary key
- `nome`, `empresa` — identificação
- `telefone`, `email`, `linkedin` — contato
- `cnpj` — único (deduplicação)
- `status` — Novo / Contatado / Qualificado / Proposta / Descartado
- **`ai_priority`** — 0-10 calculado por nicho + oportunidade digital
- `segmento` — tipo de negócio
- `endereco`, `lat`, `lng` — localização
- `score_vertice` — pontuação de qualificação (0-100)
- `website`, `osm_id` — dados da fonte
- `criado_em`, `atualizado_em` — timestamps

## AI Priority (0-10)
Calculado automaticamente com base no nicho + sinais de oportunidade:
- **9-10**: Salão de Beleza, Barbearia, Estética (core market da Vértice)
- **7-8**: Academia, Dentista, Fisioterapia, Psicologia, Spa
- **5-6**: Restaurante, Padaria, Veterinário, Floricultura
- **2-4**: Imobiliária, Mecânica, Supermercado
- Bônus: Sem site (+2pts), Sem telefone (+1pt), Sem horário (+1pt), Score alto (+1pt)

## Workflow
Rodando FastAPI via uvicorn:
```
uvicorn api.main:app --host 0.0.0.0 --port 5000 --reload
```

## Fluxo Completo
1. Dashboard → botão "▲ Caçar Leads"
2. Lead Hunter: configura cidade/raio/segmento → clica "▲ Caçar Leads"
3. Leads aparecem com Score Vértice e ⚡ AI Priority
4. Opções de exportação:
   - "⟶ CRM" → salva no localStorage + entra no Kanban
   - "💾 DB" → salva no PostgreSQL via API
   - "⟶ ENVIAR TODOS AO CRM" → todos para localStorage
   - "💾 SALVAR TODOS NO BANCO" → todos para PostgreSQL
5. CRM: leads no Kanban com badge "▲ LEAD" e botão WhatsApp rápido

## Configurações de Nicho (Segmentos atendidos)
Clínica de Estética, Salão de Beleza, Barbearia, Esmalteria,
Micropigmentação, Designer de Sobrancelhas, Depilação,
Massoterapia/Spa, Nutrição, Psicologia, Personal Trainer, Outros

## Variáveis de Ambiente
- `DATABASE_URL` — PostgreSQL connection string (automático via Replit)
