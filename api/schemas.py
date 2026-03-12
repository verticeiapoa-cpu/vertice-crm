import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator

STATUS_OPTIONS = ["Novo", "Contatado", "Qualificado", "Proposta", "Descartado"]


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

    model_config = {"from_attributes": True}


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
