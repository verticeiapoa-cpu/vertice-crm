import os
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session

from .database import engine, Base, get_db
from .models import Lead as LeadModel
from .schemas import (
    LeadCreate, LeadResponse,
    HuntRequest, HuntResponse,
    ImportLeadsRequest, ImportResponse,
    UpdateStatusRequest,
)
from .search import hunt_leads

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Vértice CRM API",
    version="2.0.0",
    description="Backend do Vértice CRM — Lead Hunting, PostgreSQL, AI Priority",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", tags=["Sistema"])
def health():
    return {"status": "ok", "version": "2.0.0", "db": "postgresql"}


@app.post("/api/leads/hunt", response_model=HuntResponse, tags=["Lead Hunting"])
async def hunt(req: HuntRequest):
    """
    Busca leads via OpenStreetMap / Overpass API.
    Termo de busca ex: 'Academia em São Paulo', 'Salão de Beleza em Curitiba'.
    Retorna leads qualificados com Score Vértice e AI Priority (0-10).
    """
    try:
        leads = await hunt_leads(req.termo, req.raio, req.score_minimo)
        return {"total": len(leads), "leads": leads}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na busca: {str(e)}")


@app.post("/api/leads/import", response_model=ImportResponse, tags=["Lead Hunting"])
def import_leads(req: ImportLeadsRequest, db: Session = Depends(get_db)):
    """
    Importa lista de leads para o PostgreSQL.
    Deduplicação automática por osm_id, email ou cnpj.
    """
    saved = skipped = 0
    errors = []

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
            saved += 1
        except Exception as e:
            db.rollback()
            errors.append(f"{lead_data.empresa}: {str(e)}")

    msg = f"{saved} leads salvos no PostgreSQL"
    if skipped:
        msg += f", {skipped} duplicata(s) ignorada(s)"
    return {"saved": saved, "skipped": skipped, "errors": errors, "message": msg}


@app.get("/api/leads", response_model=list[LeadResponse], tags=["Leads"])
def list_leads(
    status: Optional[str] = Query(None),
    segmento: Optional[str] = Query(None),
    min_priority: Optional[int] = Query(None, ge=0, le=10),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Lista leads do banco com filtros opcionais."""
    q = db.query(LeadModel)
    if status:
        q = q.filter(LeadModel.status == status)
    if segmento:
        q = q.filter(LeadModel.segmento.ilike(f"%{segmento}%"))
    if min_priority is not None:
        q = q.filter(LeadModel.ai_priority >= min_priority)
    return q.order_by(LeadModel.ai_priority.desc(), LeadModel.criado_em.desc()).offset(offset).limit(limit).all()


@app.get("/api/leads/{lead_id}", response_model=LeadResponse, tags=["Leads"])
def get_lead(lead_id: str, db: Session = Depends(get_db)):
    lead = db.query(LeadModel).filter(LeadModel.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    return lead


@app.put("/api/leads/{lead_id}/status", tags=["Leads"])
def update_status(lead_id: str, req: UpdateStatusRequest, db: Session = Depends(get_db)):
    """Atualiza o status de um lead (Novo → Contatado → Qualificado → Proposta → Descartado)."""
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
    hot = db.query(LeadModel).filter(LeadModel.ai_priority >= 8).count()
    return {
        "total_leads": total,
        "by_status": by_status,
        "avg_ai_priority": round(float(avg_priority), 1),
        "hot_leads": hot,
        "hot_pct": round(hot / total * 100, 1) if total else 0,
    }


if os.path.exists("index.html"):
    app.mount("/", StaticFiles(directory=".", html=True), name="static")
