import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Boolean
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

    ai_score = Column(Integer, nullable=True)
    pain_point = Column(Text, nullable=True)
    pitch_hook = Column(Text, nullable=True)
    ai_scored_em = Column(DateTime, nullable=True)


class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome = Column(String(255), nullable=False)
    negocio = Column(String(255), nullable=False)
    whatsapp = Column(String(50), nullable=True)
    segmento = Column(String(100), nullable=True)
    pacote = Column(String(200), nullable=True)
    valor = Column(Float, nullable=True)
    status = Column(String(50), default="prospect", nullable=False)
    pagamento = Column(String(20), default="pendente", nullable=False)
    prazo = Column(String(20), nullable=True)
    obs = Column(Text, nullable=True)
    cnpj = Column(String(18), nullable=True)
    lead_hunter_origin = Column(Boolean, default=False, nullable=False)
    lead_db_id = Column(UUID(as_uuid=True), nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status_atualizado_em = Column(DateTime, default=datetime.utcnow)


class ClienteHistorico(Base):
    __tablename__ = "cliente_historico"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cliente_id = Column(UUID(as_uuid=True), nullable=False)
    texto = Column(Text, nullable=False)
    data = Column(String(20), nullable=False)
    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)


class ContatoLog(Base):
    __tablename__ = "contato_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), nullable=True)
    canal = Column(String(50), nullable=False)
    resultado = Column(String(100), nullable=True)
    observacao = Column(Text, nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)
