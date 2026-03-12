import os
import uuid as uuid_mod
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, text
from sqlalchemy.orm import Session
import httpx

from .database import engine, Base, get_db
from .models import Lead as LeadModel, Cliente as ClienteModel, ClienteHistorico, ContatoLog
from .schemas import (
    LeadCreate, LeadResponse,
    HuntRequest, HuntResponse,
    ImportLeadsRequest, ImportResponse,
    UpdateStatusRequest,
    AIScoreResponse, BatchScoreRequest,
    ClienteCreate, ClienteUpdate, ClienteResponse,
    UpdateClienteStatusRequest,
    ContatoLogCreate, ContatoLogResponse,
    AnalyticsResponse,
)
from .search import hunt_leads
from .ai_scoring import score_lead


def run_migrations():
    with engine.connect() as conn:
        migrations = [
            # Leads table
            "ALTER TABLE leads ADD COLUMN IF NOT EXISTS ai_score INTEGER",
            "ALTER TABLE leads ADD COLUMN IF NOT EXISTS pain_point TEXT",
            "ALTER TABLE leads ADD COLUMN IF NOT EXISTS pitch_hook TEXT",
            "ALTER TABLE leads ADD COLUMN IF NOT EXISTS ai_scored_em TIMESTAMP",
            # Clientes table (new)
            """CREATE TABLE IF NOT EXISTS clientes (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                nome VARCHAR(255) NOT NULL,
                negocio VARCHAR(255) NOT NULL,
                whatsapp VARCHAR(50),
                segmento VARCHAR(100),
                pacote VARCHAR(200),
                valor FLOAT,
                status VARCHAR(50) NOT NULL DEFAULT 'prospect',
                pagamento VARCHAR(20) NOT NULL DEFAULT 'pendente',
                prazo VARCHAR(20),
                obs TEXT,
                cnpj VARCHAR(18),
                lead_hunter_origin BOOLEAN NOT NULL DEFAULT FALSE,
                lead_db_id UUID,
                criado_em TIMESTAMP NOT NULL DEFAULT NOW(),
                atualizado_em TIMESTAMP DEFAULT NOW(),
                status_atualizado_em TIMESTAMP DEFAULT NOW()
            )""",
            # Cliente historico table (new)
            """CREATE TABLE IF NOT EXISTS cliente_historico (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                cliente_id UUID NOT NULL,
                texto TEXT NOT NULL,
                data VARCHAR(20) NOT NULL,
                criado_em TIMESTAMP NOT NULL DEFAULT NOW()
            )""",
            # Contato log table (new)
            """CREATE TABLE IF NOT EXISTS contato_log (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                lead_id UUID,
                canal VARCHAR(50) NOT NULL,
                resultado VARCHAR(100),
                observacao TEXT,
                criado_em TIMESTAMP NOT NULL DEFAULT NOW()
            )""",
        ]
        for sql in migrations:
            try:
                conn.execute(text(sql))
            except Exception:
                pass
        conn.commit()


Base.metadata.create_all(bind=engine)
run_migrations()

app = FastAPI(
    title="Vértice CRM API",
    version="4.0.0",
    description="Vértice CRM — Lead Hunting, AI Scoring, PostgreSQL CRM, Analytics",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── SISTEMA ───────────────────────────────────────────────────

@app.get("/api/health", tags=["Sistema"])
def health():
    return {"status": "ok", "version": "4.0.0", "db": "postgresql", "ai": "openai/gpt-5-mini"}


@app.get("/api/stats", tags=["Sistema"])
def get_stats(db: Session = Depends(get_db)):
    total = db.query(LeadModel).count()
    by_status = {
        s: db.query(LeadModel).filter(LeadModel.status == s).count()
        for s in ["Novo", "Contatado", "Qualificado", "Proposta", "Descartado"]
    }
    avg_priority = db.query(func.avg(LeadModel.ai_priority)).scalar() or 0
    avg_ai_score = db.query(func.avg(LeadModel.ai_score)).scalar() or 0
    hot = db.query(LeadModel).filter(LeadModel.ai_priority >= 8).count()
    scored = db.query(LeadModel).filter(LeadModel.ai_score.isnot(None)).count()
    return {
        "total_leads": total,
        "by_status": by_status,
        "avg_ai_priority": round(float(avg_priority), 1),
        "avg_ai_score": round(float(avg_ai_score), 1),
        "hot_leads": hot,
        "hot_pct": round(hot / total * 100, 1) if total else 0,
        "scored_leads": scored,
    }


# ── ANALYTICS ─────────────────────────────────────────────────

@app.get("/api/analytics", tags=["Analytics"])
def get_analytics(db: Session = Depends(get_db)):
    total_leads = db.query(LeadModel).count()
    total_clientes = db.query(ClienteModel).count()
    clientes_de_leads = db.query(ClienteModel).filter(ClienteModel.lead_hunter_origin == True).count()
    taxa_conversao = round(clientes_de_leads / total_leads * 100, 1) if total_leads else 0.0

    pagos = db.query(ClienteModel).filter(
        ClienteModel.pagamento == "pago", ClienteModel.valor.isnot(None)
    ).all()
    pendentes = db.query(ClienteModel).filter(
        ClienteModel.pagamento != "pago", ClienteModel.valor.isnot(None)
    ).all()
    pipeline_ativos = db.query(ClienteModel).filter(
        ClienteModel.status.in_(["prospect", "proposta"]),
        ClienteModel.valor.isnot(None)
    ).all()

    receita_total = sum(c.valor for c in pagos)
    receita_pendente = sum(c.valor for c in pendentes)
    pipeline_valor = sum(c.valor for c in pipeline_ativos)

    todos_com_valor = db.query(ClienteModel).filter(ClienteModel.valor.isnot(None)).all()
    ticket_medio = (sum(c.valor for c in todos_com_valor) / len(todos_com_valor)) if todos_com_valor else 0

    # Receita por segmento
    receita_seg: dict = {}
    for c in db.query(ClienteModel).filter(ClienteModel.valor.isnot(None)).all():
        seg = c.segmento or "Outros"
        receita_seg[seg] = receita_seg.get(seg, 0) + c.valor

    # Distribuição de status
    dist_status: dict = {}
    for s in ["prospect", "proposta", "fechado", "entregue", "cancelado"]:
        dist_status[s] = db.query(ClienteModel).filter(ClienteModel.status == s).count()

    # Leads sem scoring
    sem_scoring = db.query(LeadModel).filter(LeadModel.ai_score.is_(None)).count()

    # Top 5 leads por ai_score
    top = db.query(LeadModel).filter(
        LeadModel.ai_score.isnot(None)
    ).order_by(LeadModel.ai_score.desc()).limit(5).all()
    top_leads = [
        {"id": str(l.id), "empresa": l.empresa, "ai_score": l.ai_score,
         "pain_point": l.pain_point, "segmento": l.segmento}
        for l in top
    ]

    return {
        "total_leads_db": total_leads,
        "total_clientes": total_clientes,
        "clientes_de_leads": clientes_de_leads,
        "taxa_conversao_pct": taxa_conversao,
        "receita_total": receita_total,
        "receita_pendente": receita_pendente,
        "pipeline_valor": pipeline_valor,
        "ticket_medio": round(ticket_medio, 2),
        "receita_por_segmento": receita_seg,
        "distribuicao_status": dist_status,
        "leads_sem_scoring": sem_scoring,
        "top_leads": top_leads,
    }


# ── CNPJ LOOKUP ───────────────────────────────────────────────

@app.get("/api/cnpj/{cnpj}", tags=["Utilidades"])
async def lookup_cnpj(cnpj: str):
    clean = "".join(c for c in cnpj if c.isdigit())
    if len(clean) != 14:
        raise HTTPException(status_code=400, detail="CNPJ deve ter 14 dígitos")
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.get(f"https://brasilapi.com.br/api/cnpj/v1/{clean}")
            if r.status_code == 200:
                d = r.json()
                return {
                    "cnpj": d.get("cnpj", clean),
                    "razao_social": d.get("razao_social", ""),
                    "nome_fantasia": d.get("nome_fantasia", ""),
                    "situacao": d.get("descricao_situacao_cadastral", ""),
                    "data_abertura": d.get("data_inicio_atividade", ""),
                    "natureza_juridica": d.get("natureza_juridica", ""),
                    "atividade_principal": d.get("cnae_fiscal_descricao", ""),
                    "logradouro": d.get("logradouro", ""),
                    "municipio": d.get("municipio", ""),
                    "uf": d.get("uf", ""),
                    "telefone": d.get("ddd_telefone_1", ""),
                    "email": d.get("email", ""),
                    "porte": d.get("porte", ""),
                }
            raise HTTPException(status_code=404, detail="CNPJ não encontrado")
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Timeout na consulta do CNPJ")


# ── LEAD HUNTING ──────────────────────────────────────────────

@app.post("/api/leads/hunt", response_model=HuntResponse, tags=["Lead Hunting"])
async def hunt(req: HuntRequest):
    try:
        leads = await hunt_leads(req.termo, req.raio, req.score_minimo)
        return {"total": len(leads), "leads": leads}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na busca: {str(e)}")


@app.post("/api/leads/import", response_model=ImportResponse, tags=["Lead Hunting"])
def import_leads(req: ImportLeadsRequest, db: Session = Depends(get_db)):
    saved = skipped = 0
    errors = []
    saved_ids = []

    for lead_data in req.leads:
        try:
            exists = None
            if lead_data.osm_id:
                exists = db.query(LeadModel).filter(LeadModel.osm_id == lead_data.osm_id).first()
            if not exists and lead_data.email:
                exists = db.query(LeadModel).filter(LeadModel.email == lead_data.email).first()
            if not exists and lead_data.cnpj:
                exists = db.query(LeadModel).filter(LeadModel.cnpj == lead_data.cnpj).first()

            if exists:
                skipped += 1
                continue

            db_lead = LeadModel(**lead_data.model_dump())
            db.add(db_lead)
            db.commit()
            db.refresh(db_lead)
            saved += 1
            saved_ids.append(str(db_lead.id))
        except Exception as e:
            db.rollback()
            errors.append(f"{lead_data.empresa}: {str(e)}")

    msg = f"{saved} leads salvos no PostgreSQL"
    if skipped:
        msg += f", {skipped} duplicata(s) ignorada(s)"
    return {"saved": saved, "skipped": skipped, "errors": errors, "message": msg, "saved_ids": saved_ids}


# ── AI SCORING ────────────────────────────────────────────────

@app.post("/api/leads/{lead_id}/score", response_model=AIScoreResponse, tags=["AI Scoring"])
def score_single_lead(lead_id: str, db: Session = Depends(get_db)):
    lead = db.query(LeadModel).filter(LeadModel.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    try:
        result = score_lead(
            empresa=lead.empresa,
            segmento=lead.segmento or "",
            tem_site=bool(lead.website),
            tem_telefone=bool(lead.telefone),
            endereco=lead.endereco or "",
            score_vertice=lead.score_vertice or 0,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na análise de IA: {str(e)}")

    lead.ai_score = result["score"]
    lead.pain_point = result["pain_point"]
    lead.pitch_hook = result["pitch_hook"]
    lead.ai_scored_em = datetime.utcnow()
    db.commit()
    db.refresh(lead)

    return AIScoreResponse(
        id=lead.id,
        empresa=lead.empresa,
        ai_score=lead.ai_score,
        pain_point=lead.pain_point,
        pitch_hook=lead.pitch_hook,
        ai_scored_em=lead.ai_scored_em,
    )


@app.post("/api/leads/score-batch", tags=["AI Scoring"])
def score_batch(req: BatchScoreRequest, db: Session = Depends(get_db)):
    if req.lead_ids:
        leads = db.query(LeadModel).filter(LeadModel.id.in_(req.lead_ids)).all()
    else:
        leads = (
            db.query(LeadModel)
            .filter(LeadModel.ai_score.is_(None))
            .order_by(LeadModel.ai_priority.desc())
            .limit(req.limit)
            .all()
        )

    if not leads:
        return {"pontuados": 0, "resultados": [], "message": "Nenhum lead para pontuar"}

    resultados = []
    erros = []
    for lead in leads:
        try:
            result = score_lead(
                empresa=lead.empresa,
                segmento=lead.segmento or "",
                tem_site=bool(lead.website),
                tem_telefone=bool(lead.telefone),
                endereco=lead.endereco or "",
                score_vertice=lead.score_vertice or 0,
            )
            lead.ai_score = result["score"]
            lead.pain_point = result["pain_point"]
            lead.pitch_hook = result["pitch_hook"]
            lead.ai_scored_em = datetime.utcnow()
            db.commit()
            resultados.append({
                "id": str(lead.id), "empresa": lead.empresa,
                "ai_score": result["score"],
                "pain_point": result["pain_point"],
                "pitch_hook": result["pitch_hook"],
            })
        except Exception as e:
            erros.append({"id": str(lead.id), "empresa": lead.empresa, "erro": str(e)})

    return {"pontuados": len(resultados), "erros": len(erros),
            "resultados": resultados, "message": f"{len(resultados)} leads analisados pela IA"}


# ── CONTATO LOG ───────────────────────────────────────────────

@app.post("/api/leads/{lead_id}/contatos", response_model=ContatoLogResponse, tags=["Contato Log"])
def add_contato(lead_id: str, req: ContatoLogCreate, db: Session = Depends(get_db)):
    lead = db.query(LeadModel).filter(LeadModel.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    log = ContatoLog(
        lead_id=uuid_mod.UUID(lead_id),
        canal=req.canal,
        resultado=req.resultado,
        observacao=req.observacao,
    )
    db.add(log)
    lead.status = "Contatado"
    lead.atualizado_em = datetime.utcnow()
    db.commit()
    db.refresh(log)
    return log


@app.get("/api/leads/{lead_id}/contatos", response_model=List[ContatoLogResponse], tags=["Contato Log"])
def list_contatos(lead_id: str, db: Session = Depends(get_db)):
    return db.query(ContatoLog).filter(
        ContatoLog.lead_id == lead_id
    ).order_by(ContatoLog.criado_em.desc()).all()


# ── LEADS CRUD ────────────────────────────────────────────────

@app.get("/api/leads", response_model=list[LeadResponse], tags=["Leads"])
def list_leads(
    status: Optional[str] = Query(None),
    segmento: Optional[str] = Query(None),
    min_priority: Optional[int] = Query(None, ge=0, le=10),
    scored_only: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    q = db.query(LeadModel)
    if status:
        q = q.filter(LeadModel.status == status)
    if segmento:
        q = q.filter(LeadModel.segmento.ilike(f"%{segmento}%"))
    if min_priority is not None:
        q = q.filter(LeadModel.ai_priority >= min_priority)
    if scored_only:
        q = q.filter(LeadModel.ai_score.isnot(None))
    return q.order_by(LeadModel.ai_priority.desc(), LeadModel.criado_em.desc()).offset(offset).limit(limit).all()


@app.get("/api/leads/{lead_id}", response_model=LeadResponse, tags=["Leads"])
def get_lead(lead_id: str, db: Session = Depends(get_db)):
    lead = db.query(LeadModel).filter(LeadModel.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    return lead


@app.put("/api/leads/{lead_id}/status", tags=["Leads"])
def update_lead_status(lead_id: str, req: UpdateStatusRequest, db: Session = Depends(get_db)):
    lead = db.query(LeadModel).filter(LeadModel.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    lead.status = req.status
    db.commit()
    return {"message": "Status atualizado", "id": str(lead_id), "status": req.status}


@app.delete("/api/leads/{lead_id}", tags=["Leads"])
def delete_lead(lead_id: str, db: Session = Depends(get_db)):
    lead = db.query(LeadModel).filter(LeadModel.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    db.delete(lead)
    db.commit()
    return {"message": "Lead excluído", "id": str(lead_id)}


# ── CLIENTES CRM ──────────────────────────────────────────────

def _build_cliente_response(c: ClienteModel, db: Session) -> dict:
    hist = db.query(ClienteHistorico).filter(
        ClienteHistorico.cliente_id == c.id
    ).order_by(ClienteHistorico.criado_em.asc()).all()
    return {
        "id": str(c.id),
        "nome": c.nome,
        "negocio": c.negocio,
        "whatsapp": c.whatsapp,
        "segmento": c.segmento,
        "pacote": c.pacote,
        "valor": c.valor,
        "status": c.status,
        "pagamento": c.pagamento,
        "prazo": c.prazo,
        "obs": c.obs,
        "cnpj": c.cnpj,
        "lead_hunter_origin": c.lead_hunter_origin,
        "criado_em": c.criado_em.isoformat(),
        "atualizado_em": c.atualizado_em.isoformat() if c.atualizado_em else None,
        "status_atualizado_em": c.status_atualizado_em.isoformat() if c.status_atualizado_em else None,
        "historico": [{"id": str(h.id), "texto": h.texto, "data": h.data,
                        "criado_em": h.criado_em.isoformat()} for h in hist],
    }


@app.get("/api/clientes", tags=["CRM Clientes"])
def list_clientes(
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(ClienteModel)
    if status and status != "todos":
        q = q.filter(ClienteModel.status == status)
    if search:
        like = f"%{search}%"
        q = q.filter(
            (ClienteModel.nome.ilike(like)) | (ClienteModel.negocio.ilike(like))
        )
    clientes = q.order_by(ClienteModel.criado_em.desc()).all()
    return [_build_cliente_response(c, db) for c in clientes]


@app.post("/api/clientes", tags=["CRM Clientes"])
def create_cliente(req: ClienteCreate, db: Session = Depends(get_db)):
    lead_db_uuid = None
    if req.lead_db_id:
        try:
            lead_db_uuid = uuid_mod.UUID(req.lead_db_id)
        except Exception:
            pass

    c = ClienteModel(
        nome=req.nome,
        negocio=req.negocio,
        whatsapp=req.whatsapp,
        segmento=req.segmento,
        pacote=req.pacote,
        valor=req.valor,
        status=req.status,
        pagamento=req.pagamento,
        prazo=req.prazo,
        obs=req.obs,
        cnpj=req.cnpj,
        lead_hunter_origin=req.lead_hunter_origin,
        lead_db_id=lead_db_uuid,
    )
    db.add(c)
    db.commit()
    db.refresh(c)

    for h in req.historico:
        hist = ClienteHistorico(cliente_id=c.id, texto=h.texto, data=h.data)
        db.add(hist)
    db.commit()

    return _build_cliente_response(c, db)


@app.get("/api/clientes/{cliente_id}", tags=["CRM Clientes"])
def get_cliente(cliente_id: str, db: Session = Depends(get_db)):
    c = db.query(ClienteModel).filter(ClienteModel.id == cliente_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return _build_cliente_response(c, db)


@app.put("/api/clientes/{cliente_id}", tags=["CRM Clientes"])
def update_cliente(cliente_id: str, req: ClienteUpdate, db: Session = Depends(get_db)):
    c = db.query(ClienteModel).filter(ClienteModel.id == cliente_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    old_status = c.status
    for field, value in req.model_dump(exclude_none=True).items():
        setattr(c, field, value)

    c.atualizado_em = datetime.utcnow()
    if req.status and req.status != old_status:
        c.status_atualizado_em = datetime.utcnow()

    db.commit()
    return _build_cliente_response(c, db)


@app.put("/api/clientes/{cliente_id}/status", tags=["CRM Clientes"])
def update_cliente_status(cliente_id: str, req: UpdateClienteStatusRequest, db: Session = Depends(get_db)):
    c = db.query(ClienteModel).filter(ClienteModel.id == cliente_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    old_status = c.status
    c.status = req.status
    c.atualizado_em = datetime.utcnow()
    c.status_atualizado_em = datetime.utcnow()
    db.commit()

    labels = {"prospect": "Prospect", "proposta": "Proposta enviada",
              "fechado": "Projeto fechado", "entregue": "Entregue", "cancelado": "Cancelado"}
    hist = ClienteHistorico(
        cliente_id=c.id,
        texto=f"Status: {labels.get(old_status, old_status)} → {labels.get(req.status, req.status)}",
        data=datetime.now().strftime("%d/%m/%Y"),
    )
    db.add(hist)
    db.commit()
    return _build_cliente_response(c, db)


@app.post("/api/clientes/{cliente_id}/historico", tags=["CRM Clientes"])
def add_historico(cliente_id: str, texto: str, db: Session = Depends(get_db)):
    c = db.query(ClienteModel).filter(ClienteModel.id == cliente_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    hist = ClienteHistorico(
        cliente_id=c.id,
        texto=texto,
        data=datetime.now().strftime("%d/%m/%Y"),
    )
    db.add(hist)
    db.commit()
    db.refresh(hist)
    return {"id": str(hist.id), "texto": hist.texto, "data": hist.data}


@app.delete("/api/clientes/{cliente_id}", tags=["CRM Clientes"])
def delete_cliente(cliente_id: str, db: Session = Depends(get_db)):
    c = db.query(ClienteModel).filter(ClienteModel.id == cliente_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    db.query(ClienteHistorico).filter(ClienteHistorico.cliente_id == cliente_id).delete()
    db.delete(c)
    db.commit()
    return {"message": "Cliente excluído", "id": cliente_id}


@app.post("/api/clientes/migrate", tags=["CRM Clientes"])
def migrate_from_localstorage(clients_data: list, db: Session = Depends(get_db)):
    """Recebe array de clientes do localStorage e migra para PostgreSQL."""
    saved = 0
    for old in clients_data:
        try:
            c = ClienteModel(
                nome=old.get("nome", ""),
                negocio=old.get("negocio", ""),
                whatsapp=old.get("whatsapp"),
                segmento=old.get("segmento"),
                pacote=old.get("pacote"),
                valor=old.get("valor"),
                status=old.get("status", "prospect"),
                pagamento=old.get("pagamento", "pendente"),
                prazo=old.get("prazo"),
                obs=old.get("obs"),
                cnpj=old.get("cnpj"),
                lead_hunter_origin=any(
                    "Lead Hunter" in (h.get("texto", "") or "")
                    for h in old.get("historico", [])
                ),
            )
            db.add(c)
            db.commit()
            db.refresh(c)

            for h in old.get("historico", []):
                hist = ClienteHistorico(
                    cliente_id=c.id,
                    texto=h.get("texto", ""),
                    data=h.get("data", datetime.now().strftime("%d/%m/%Y")),
                )
                db.add(hist)
            db.commit()
            saved += 1
        except Exception:
            db.rollback()

    return {"migrados": saved, "message": f"{saved} clientes migrados do localStorage"}


if os.path.exists("index.html"):
    app.mount("/", StaticFiles(directory=".", html=True), name="static")
