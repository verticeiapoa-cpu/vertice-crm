import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator

STATUS_OPTIONS = ["Novo", "Contatado", "Qualificado", "Proposta", "Descartado"]
CLIENTE_STATUS = ["prospect", "proposta", "fechado", "entregue", "cancelado"]
PAGAMENTO_STATUS = ["pendente", "parcial", "pago"]


class LeadBase(BaseModel):
    nome: str = Field(..., min_length=1, max_length=255)
    empresa: str = Field(..., min_length=1, max_length=255)
    telefone: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=255)
    linkedin: Optional[str] = Field(None, max_length=500)
    cnpj: Optional[str] = Field(None, max_length=18)
    status: str = Field("Novo")
    ai_priority: int = Field(0, ge=0, le=10)
    segmento: Optional[str] = Field(None, max_length=100)
    endereco: Optional[str] = None
    score_vertice: int = Field(0, ge=0, le=100)
    lat: Optional[float] = None
    lng: Optional[float] = None
    website: Optional[str] = Field(None, max_length=500)
    osm_id: Optional[str] = Field(None, max_length=50)

    @field_validator("status")
    @classmethod
    def status_must_be_valid(cls, v: str) -> str:
        if v not in STATUS_OPTIONS:
            raise ValueError(f"Status deve ser um de: {', '.join(STATUS_OPTIONS)}")
        return v

    @field_validator("ai_priority")
    @classmethod
    def priority_in_range(cls, v: int) -> int:
        if not 0 <= v <= 10:
            raise ValueError("ai_priority deve estar entre 0 e 10")
        return v


class LeadCreate(LeadBase):
    pass


class LeadResponse(LeadBase):
    id: uuid.UUID
    criado_em: datetime
    ai_score: Optional[int] = None
    pain_point: Optional[str] = None
    pitch_hook: Optional[str] = None
    ai_scored_em: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AIScoreResponse(BaseModel):
    id: uuid.UUID
    empresa: str
    ai_score: int
    pain_point: str
    pitch_hook: str
    ai_scored_em: datetime


class HuntRequest(BaseModel):
    termo: str = Field(..., min_length=3, description="Ex: 'Academia em São Paulo'")
    raio: int = Field(3000, ge=500, le=10000, description="Raio de busca em metros")
    score_minimo: int = Field(30, ge=10, le=80)


class ImportLeadsRequest(BaseModel):
    leads: List[LeadCreate]


class UpdateStatusRequest(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def status_must_be_valid(cls, v: str) -> str:
        if v not in STATUS_OPTIONS:
            raise ValueError(f"Status inválido. Use: {', '.join(STATUS_OPTIONS)}")
        return v


class HuntResponse(BaseModel):
    total: int
    leads: List[LeadCreate]


class ImportResponse(BaseModel):
    saved: int
    skipped: int
    errors: List[str]
    message: str
    saved_ids: List[str] = []


class BatchScoreRequest(BaseModel):
    lead_ids: Optional[List[str]] = Field(None)
    limit: int = Field(10, ge=1, le=50)


# ── CLIENTES ──────────────────────────────────────────────────

class HistoricoItem(BaseModel):
    texto: str
    data: str


class ClienteCreate(BaseModel):
    nome: str = Field(..., min_length=1, max_length=255)
    negocio: str = Field(..., min_length=1, max_length=255)
    whatsapp: Optional[str] = Field(None, max_length=50)
    segmento: Optional[str] = Field(None, max_length=100)
    pacote: Optional[str] = Field(None, max_length=200)
    valor: Optional[float] = Field(None, ge=0)
    status: str = Field("prospect")
    pagamento: str = Field("pendente")
    prazo: Optional[str] = None
    obs: Optional[str] = None
    cnpj: Optional[str] = Field(None, max_length=18)
    lead_hunter_origin: bool = False
    lead_db_id: Optional[str] = None
    historico: List[HistoricoItem] = []


class ClienteUpdate(BaseModel):
    nome: Optional[str] = Field(None, max_length=255)
    negocio: Optional[str] = Field(None, max_length=255)
    whatsapp: Optional[str] = Field(None, max_length=50)
    segmento: Optional[str] = Field(None, max_length=100)
    pacote: Optional[str] = Field(None, max_length=200)
    valor: Optional[float] = Field(None, ge=0)
    status: Optional[str] = None
    pagamento: Optional[str] = None
    prazo: Optional[str] = None
    obs: Optional[str] = None
    cnpj: Optional[str] = Field(None, max_length=18)


class ClienteHistoricoResponse(BaseModel):
    id: uuid.UUID
    texto: str
    data: str
    criado_em: datetime

    model_config = {"from_attributes": True}


class ClienteResponse(BaseModel):
    id: uuid.UUID
    nome: str
    negocio: str
    whatsapp: Optional[str] = None
    segmento: Optional[str] = None
    pacote: Optional[str] = None
    valor: Optional[float] = None
    status: str
    pagamento: str
    prazo: Optional[str] = None
    obs: Optional[str] = None
    cnpj: Optional[str] = None
    lead_hunter_origin: bool
    criado_em: datetime
    atualizado_em: Optional[datetime] = None
    status_atualizado_em: Optional[datetime] = None
    historico: List[ClienteHistoricoResponse] = []

    model_config = {"from_attributes": True}


class UpdateClienteStatusRequest(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def status_must_be_valid(cls, v: str) -> str:
        if v not in CLIENTE_STATUS:
            raise ValueError(f"Status inválido. Use: {', '.join(CLIENTE_STATUS)}")
        return v


# ── CONTATO LOG ───────────────────────────────────────────────

class ContatoLogCreate(BaseModel):
    lead_id: str
    canal: str = Field(..., description="whatsapp | ligacao | email | outro")
    resultado: Optional[str] = Field(None, description="interesse | sem_interesse | sem_resposta | agendado")
    observacao: Optional[str] = None


class ContatoLogResponse(BaseModel):
    id: uuid.UUID
    lead_id: Optional[uuid.UUID] = None
    canal: str
    resultado: Optional[str] = None
    observacao: Optional[str] = None
    criado_em: datetime

    model_config = {"from_attributes": True}


# ── ANALYTICS ─────────────────────────────────────────────────

class AnalyticsResponse(BaseModel):
    total_leads_db: int
    total_clientes: int
    clientes_de_leads: int
    taxa_conversao_pct: float
    receita_total: float
    receita_pendente: float
    pipeline_valor: float
    ticket_medio: float
    receita_por_segmento: dict
    distribuicao_status: dict
    leads_sem_scoring: int
    top_leads: list
