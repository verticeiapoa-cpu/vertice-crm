import os
from datetime import datetime
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, Query, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from .database import engine, Base, get_db
from .models import Lead as LeadModel
from .schemas import (
    LeadCreate, LeadResponse,
    HuntRequest, HuntResponse,
    ImportLeadsRequest, ImportResponse,
    UpdateStatusRequest,
    AIScoreResponse, BatchScoreRequest,
)
from .search import hunt_leads
from .ai_scoring import score_lead


def run_migrations():
    with engine.connect() as conn:
        migrations = [
            "ALTER TABLE leads ADD COLUMN IF NOT EXISTS ai_score INTEGER",
            "ALTER TABLE leads ADD COLUMN IF NOT EXISTS pain_point TEXT",
            "ALTER TABLE leads ADD COLUMN IF NOT EXISTS pitch_hook TEXT",
            "ALTER TABLE leads ADD COLUMN IF NOT EXISTS ai_scored_em TIMESTAMP",
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
    version="3.0.0",
    description="Backend do Vértice CRM — Lead Hunting, PostgreSQL, AI Priority, AI Lead Scoring",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", tags=["Sistema"])
def health():
    return {"status": "ok", "version": "3.0.0", "db": "postgresql", "ai": "openai/gpt-5-mini"}


@app.post("/api/leads/hunt", response_model=HuntResponse, tags=["Lead Hunting"])
async def hunt(req: HuntRequest):
    """Busca leads via OpenStreetMap / Overpass API."""
    try:
        leads = await hunt_leads(req.termo, req.raio, req.score_minimo)
        return {"total": len(leads), "leads": leads}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na busca: {str(e)}")


@app.post("/api/leads/import", response_model=ImportResponse, tags=["Lead Hunting"])
def import_leads(req: ImportLeadsRequest, db: Session = Depends(get_db)):
    """Importa leads para PostgreSQL com deduplicação automática."""
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


@app.post("/api/leads/{lead_id}/score", response_model=AIScoreResponse, tags=["AI Scoring"])
def score_single_lead(lead_id: str, db: Session = Depends(get_db)):
    """
    Analisa um lead com GPT-5-mini e retorna:
    - ai_score (0-10): fit para a Vértice
    - pain_point: dor principal identificada
    - pitch_hook: frase de abertura para WhatsApp
    Atualiza o banco automaticamente.
    """
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
    """
    Pontua múltiplos leads com IA em sequência.
    Se lead_ids for omitido, pontua os N leads mais antigos ainda sem ai_score.
    Retorna resultados de cada lead pontuado.
    """
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
                "id": str(lead.id),
                "empresa": lead.empresa,
                "ai_score": result["score"],
                "pain_point": result["pain_point"],
                "pitch_hook": result["pitch_hook"],
            })
        except Exception as e:
            erros.append({"id": str(lead.id), "empresa": lead.empresa, "erro": str(e)})

    return {
        "pontuados": len(resultados),
        "erros": len(erros),
        "resultados": resultados,
        "message": f"{len(resultados)} leads analisados pela IA"
    }


@app.get("/api/leads", response_model=list[LeadResponse], tags=["Leads"])
def list_leads(
    status: Optional[str] = Query(None),
    segmento: Optional[str] = Query(None),
    min_priority: Optional[int] = Query(None, ge=0, le=10),
    scored_only: bool = Query(False, description="Apenas leads já pontuados pela IA"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Lista leads com filtros opcionais."""
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
def update_status(lead_id: str, req: UpdateStatusRequest, db: Session = Depends(get_db)):
    """Atualiza o status de um lead."""
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


@app.get("/api/stats", tags=["Sistema"])
def get_stats(db: Session = Depends(get_db)):
    """Estatísticas dos leads no banco."""
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


if os.path.exists("index.html"):
    app.mount("/", StaticFiles(directory=".", html=True), name="static")
