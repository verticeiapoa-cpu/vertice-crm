import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from .database import Base


class Lead(Base):
    __tablename__ = "leads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome = Column(String(255), nullable=False)
    empresa = Column(String(255), nullable=False)
    telefone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    linkedin = Column(String(500), nullable=True)
    cnpj = Column(String(18), nullable=True, unique=True)
    status = Column(String(50), default="Novo", nullable=False)
    ai_priority = Column(Integer, default=0, nullable=False)
    segmento = Column(String(100), nullable=True)
    endereco = Column(Text, nullable=True)
    score_vertice = Column(Integer, default=0, nullable=False)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    website = Column(String(500), nullable=True)
    osm_id = Column(String(50), nullable=True, unique=True)
    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
