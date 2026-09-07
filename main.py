from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
from pathlib import Path
import sqlite3
import uuid
from datetime import datetime

app = FastAPI(
    title="Vértice CRM",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path("/tmp/vertice_crm.db")


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id TEXT PRIMARY KEY,
            nome TEXT,
            empresa TEXT,
            telefone TEXT,
            email TEXT,
            linkedin TEXT,
            cnpj TEXT,
            status TEXT DEFAULT 'novo',
            segmento TEXT,
            endereco TEXT,
            lat REAL,
            lng REAL,
            score_vertice INTEGER DEFAULT 0,
            ai_priority TEXT,
            website TEXT,
            osm_id TEXT,
            ai_score INTEGER DEFAULT 0,
            pain_point TEXT,
            pitch_hook TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            negocio TEXT,
            whatsapp TEXT,
            segmento TEXT,
            pacote TEXT,
            valor REAL DEFAULT 0,
            status TEXT DEFAULT 'prospect',
            pagamento TEXT DEFAULT 'pendente',
            prazo TEXT,
            obs TEXT,
            cnpj TEXT,
            historico_json TEXT,
            lead_hunter_origin INTEGER DEFAULT 0,
            lead_db_id TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS contatos (
            id TEXT PRIMARY KEY,
            lead_id TEXT,
            canal TEXT,
            resultado TEXT,
            observacao TEXT,
            timestamp TEXT
        )
    """)

    conn.commit()
    conn.close()


init_db()


class LeadCreate(BaseModel):
    nome: Optional[str] = None
    empresa: Optional[str] = None
    telefone: Optional[str] = None
    email: Optional[str] = None
    linkedin: Optional[str] = None
    cnpj: Optional[str] = None
    status: Optional[str] = "novo"
    segmento: Optional[str] = None
    endereco: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    website: Optional[str] = None
    osm_id: Optional[str] = None


class ClienteCreate(BaseModel):
    nome: str
    negocio: Optional[str] = None
    whatsapp: Optional[str] = None
    segmento: Optional[str] = None
    pacote: Optional[str] = None
    valor: Optional[float] = 0
    status: Optional[str] = "prospect"
    pagamento: Optional[str] = "pendente"
    prazo: Optional[str] = None
    obs: Optional[str] = None
    cnpj: Optional[str] = None
    lead_db_id: Optional[str] = None


class StatusUpdate(BaseModel):
    status: str


class ContatoCreate(BaseModel):
    canal: Optional[str] = None
    resultado: Optional[str] = None
    observacao: Optional[str] = None


def row_to_dict(row):
    return dict(row) if row else None


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "app": "vertice-crm",
        "version": "2.0.0",
        "database": "sqlite"
    }


@app.get("/api/stats")
def stats():
    conn = get_db()

    leads = conn.execute(
        "SELECT COUNT(*) AS total FROM leads"
    ).fetchone()["total"]

    clientes = conn.execute(
        "SELECT COUNT(*) AS total FROM clientes"
    ).fetchone()["total"]

    valor = conn.execute(
        "SELECT COALESCE(SUM(valor), 0) AS total FROM clientes"
    ).fetchone()["total"]

    conn.close()

    return {
        "leads": leads,
        "clientes": clientes,
        "valor_total": valor
    }


@app.get("/api/leads")
def listar_leads():
    conn = get_db()

    rows = conn.execute(
        "SELECT * FROM leads ORDER BY created_at DESC"
    ).fetchall()

    conn.close()

    return [dict(row) for row in rows]


@app.post("/api/leads")
def criar_lead(lead: LeadCreate):
    conn = get_db()

    lead_id = str(uuid.uuid4())
    agora = datetime.utcnow().isoformat()

    conn.execute("""
        INSERT INTO leads (
            id,
            nome,
            empresa,
            telefone,
            email,
            linkedin,
            cnpj,
            status,
            segmento,
            endereco,
            lat,
            lng,
            website,
            osm_id,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        lead_id,
        lead.nome,
        lead.empresa,
        lead.telefone,
        lead.email,
        lead.linkedin,
        lead.cnpj,
        lead.status,
        lead.segmento,
        lead.endereco,
        lead.lat,
        lead.lng,
        lead.website,
        lead.osm_id,
        agora,
        agora
    ))

    conn.commit()

    row = conn.execute(
        "SELECT * FROM leads WHERE id = ?",
        (lead_id,)
    ).fetchone()

    conn.close()

    return dict(row)


@app.post("/api/leads/import")
def importar_leads(leads: List[LeadCreate]):
    criados = []

    for lead in leads:
        criados.append(criar_lead(lead))

    return {
        "success": True,
        "total": len(criados),
        "leads": criados
    }


@app.get("/api/leads/{lead_id}")
def obter_lead(lead_id: str):
    conn = get_db()

    row = conn.execute(
        "SELECT * FROM leads WHERE id = ?",
        (lead_id,)
    ).fetchone()

    conn.close()

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Lead não encontrado"
        )

    return dict(row)


@app.put("/api/leads/{lead_id}/status")
def atualizar_status_lead(
    lead_id: str,
    dados: StatusUpdate
):
    conn = get_db()

    agora = datetime.utcnow().isoformat()

    cursor = conn.execute("""
        UPDATE leads
        SET status = ?, updated_at = ?
        WHERE id = ?
    """, (
        dados.status,
        agora,
        lead_id
    ))

    conn.commit()

    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Lead não encontrado"
        )

    row = conn.execute(
        "SELECT * FROM leads WHERE id = ?",
        (lead_id,)
    ).fetchone()

    conn.close()

    return dict(row)


@app.delete("/api/leads/{lead_id}")
def excluir_lead(lead_id: str):
    conn = get_db()

    cursor = conn.execute(
        "DELETE FROM leads WHERE id = ?",
        (lead_id,)
    )

    conn.commit()
    conn.close()

    if cursor.rowcount == 0:
        raise HTTPException(
            status_code=404,
            detail="Lead não encontrado"
        )

    return {
        "success": True
    }


@app.post("/api/leads/{lead_id}/score")
def calcular_score(lead_id: str):
    conn = get_db()

    lead = conn.execute(
        "SELECT * FROM leads WHERE id = ?",
        (lead_id,)
    ).fetchone()

    if not lead:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Lead não encontrado"
        )

    score = 20

    if lead["telefone"]:
        score += 20

    if lead["email"]:
        score += 20

    if lead["website"]:
        score += 15

    if lead["cnpj"]:
        score += 15

    if lead["endereco"]:
        score += 10

    score = min(score, 100)

    if score >= 75:
        prioridade = "alta"
    elif score >= 45:
        prioridade = "media"
    else:
        prioridade = "baixa"

    conn.execute("""
        UPDATE leads
        SET
            ai_score = ?,
            score_vertice = ?,
            ai_priority = ?,
            updated_at = ?
        WHERE id = ?
    """, (
        score,
        score,
        prioridade,
        datetime.utcnow().isoformat(),
        lead_id
    ))

    conn.commit()

    row = conn.execute(
        "SELECT * FROM leads WHERE id = ?",
        (lead_id,)
    ).fetchone()

    conn.close()

    return dict(row)


@app.post("/api/leads/{lead_id}/contatos")
def registrar_contato(
    lead_id: str,
    contato: ContatoCreate
):
    conn = get_db()

    lead = conn.execute(
        "SELECT id FROM leads WHERE id = ?",
        (lead_id,)
    ).fetchone()

    if not lead:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Lead não encontrado"
        )

    contato_id = str(uuid.uuid4())

    conn.execute("""
        INSERT INTO contatos (
            id,
            lead_id,
            canal,
            resultado,
            observacao,
            timestamp
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        contato_id,
        lead_id,
        contato.canal,
        contato.resultado,
        contato.observacao,
        datetime.utcnow().isoformat()
    ))

    conn.commit()
    conn.close()

    return {
        "success": True,
        "id": contato_id
    }


@app.get("/api/clientes")
def listar_clientes():
    conn = get_db()

    rows = conn.execute(
        "SELECT * FROM clientes ORDER BY created_at DESC"
    ).fetchall()

    conn.close()

    return [dict(row) for row in rows]


@app.post("/api/clientes")
def criar_cliente(cliente: ClienteCreate):
    conn = get_db()

    cliente_id = str(uuid.uuid4())
    agora = datetime.utcnow().isoformat()

    conn.execute("""
        INSERT INTO clientes (
            id,
            nome,
            negocio,
            whatsapp,
            segmento,
            pacote,
            valor,
            status,
            pagamento,
            prazo,
            obs,
            cnpj,
            lead_db_id,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        cliente_id,
        cliente.nome,
        cliente.negocio,
        cliente.whatsapp,
        cliente.segmento,
        cliente.pacote,
        cliente.valor,
        cliente.status,
        cliente.pagamento,
        cliente.prazo,
        cliente.obs,
        cliente.cnpj,
        cliente.lead_db_id,
        agora,
        agora
    ))

    conn.commit()

    row = conn.execute(
        "SELECT * FROM clientes WHERE id = ?",
        (cliente_id,)
    ).fetchone()

    conn.close()

    return dict(row)


@app.get("/api/clientes/{cliente_id}")
def obter_cliente(cliente_id: str):
    conn = get_db()

    row = conn.execute(
        "SELECT * FROM clientes WHERE id = ?",
        (cliente_id,)
    ).fetchone()

    conn.close()

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Cliente não encontrado"
        )

    return dict(row)


@app.put("/api/clientes/{cliente_id}/status")
def atualizar_status_cliente(
    cliente_id: str,
    dados: StatusUpdate
):
    conn = get_db()

    cursor = conn.execute("""
        UPDATE clientes
        SET status = ?, updated_at = ?
        WHERE id = ?
    """, (
        dados.status,
        datetime.utcnow().isoformat(),
        cliente_id
    ))

    conn.commit()

    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Cliente não encontrado"
        )

    row = conn.execute(
        "SELECT * FROM clientes WHERE id = ?",
        (cliente_id,)
    ).fetchone()

    conn.close()

    return dict(row)


@app.delete("/api/clientes/{cliente_id}")
def excluir_cliente(cliente_id: str):
    conn = get_db()

    cursor = conn.execute(
        "DELETE FROM clientes WHERE id = ?",
        (cliente_id,)
    )

    conn.commit()
    conn.close()

    if cursor.rowcount == 0:
        raise HTTPException(
            status_code=404,
            detail="Cliente não encontrado"
        )

    return {
        "success": True
    }


@app.get("/api/analytics")
def analytics():
    conn = get_db()

    total_clientes = conn.execute(
        "SELECT COUNT(*) AS total FROM clientes"
    ).fetchone()["total"]

    total_leads = conn.execute(
        "SELECT COUNT(*) AS total FROM leads"
    ).fetchone()["total"]

    receita = conn.execute(
        "SELECT COALESCE(SUM(valor), 0) AS total FROM clientes"
    ).fetchone()["total"]

    por_status = conn.execute("""
        SELECT status, COUNT(*) AS total
        FROM clientes
        GROUP BY status
    """).fetchall()

    conn.close()

    return {
        "total_clientes": total_clientes,
        "total_leads": total_leads,
        "receita": receita,
        "clientes_por_status": [
            dict(row) for row in por_status
        ]
    }


@app.get("/")
def home():
    index_file = BASE_DIR / "index.html"

    if index_file.exists():
        return FileResponse(str(index_file))

    return {
        "status": "ok",
        "app": "Vértice CRM"
    }


@app.get("/index.html")
def index():
    index_file = BASE_DIR / "index.html"

    if index_file.exists():
        return FileResponse(str(index_file))

    raise HTTPException(
        status_code=404,
        detail="index.html não encontrado"
    )


@app.get("/lead-hunter.html")
def lead_hunter():
    hunter_file = BASE_DIR / "lead-hunter.html"

    if hunter_file.exists():
        return FileResponse(str(hunter_file))

    raise HTTPException(
        status_code=404,
        detail="lead-hunter.html não encontrado"
    )
