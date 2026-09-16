"""Models SQLAlchemy e helpers de acesso ao banco (SQLite)."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    func,
)
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker

from config import settings

Base = declarative_base()


class Oferta(Base):
    """Uma linha por produto (identificado pela URL). Atualizada a cada nova captura."""

    __tablename__ = "ofertas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String, nullable=False)
    preco = Column(Float, nullable=False)
    preco_anterior = Column(Float)
    desconto = Column(Float)
    loja = Column(String)
    categoria = Column(String)
    url = Column(String, unique=True, index=True)
    imagem = Column(String)
    sku = Column(String)
    capturado_em = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    envios = relationship("Envio", back_populates="oferta")


class Envio(Base):
    """Registro de cada envio efetivo para o WhatsApp (permite mais de um por oferta)."""

    __tablename__ = "envios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    oferta_id = Column(Integer, ForeignKey("ofertas.id"))
    enviado_em = Column(DateTime, default=datetime.now)
    grupo = Column(String)
    mensagem = Column(Text)
    preco_enviado = Column(Float)
    status = Column(String)

    oferta = relationship("Oferta", back_populates="envios")


_engine = create_engine(settings.database_url, echo=False, future=True)
_SessionFactory = sessionmaker(bind=_engine, expire_on_commit=False, future=True)


def init_db() -> None:
    Base.metadata.create_all(_engine)


@contextmanager
def get_session() -> Session:
    session = _SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def upsert_oferta(session: Session, dados: dict) -> Oferta:
    """Cria ou atualiza a oferta. Prefere SKU+loja (estável); fallback pela URL."""
    oferta = None
    sku = dados.get("sku")
    loja = dados.get("loja")
    if sku:
        # Pode haver duplicatas antigas no SQLite — pega a mais recente.
        oferta = (
            session.query(Oferta)
            .filter_by(sku=sku, loja=loja)
            .order_by(Oferta.id.desc())
            .first()
        )
    if oferta is None:
        oferta = session.query(Oferta).filter_by(url=dados["url"]).one_or_none()

    if oferta is None:
        oferta = Oferta(**dados)
        session.add(oferta)
    else:
        if oferta.preco != dados["preco"]:
            oferta.preco_anterior = oferta.preco
        oferta.nome = dados["nome"]
        oferta.preco = dados["preco"]
        oferta.desconto = dados.get("desconto")
        oferta.loja = dados.get("loja")
        oferta.categoria = dados.get("categoria")
        # Só atualiza URL se não conflitar com outra linha (unique).
        if oferta.url != dados["url"]:
            conflito = session.query(Oferta).filter_by(url=dados["url"]).first()
            if conflito is None or conflito.id == oferta.id:
                oferta.url = dados["url"]
        oferta.imagem = dados.get("imagem")
        oferta.sku = dados.get("sku") or oferta.sku
        oferta.capturado_em = datetime.now()
    session.flush()
    return oferta


def ultimo_envio(session: Session, oferta_id: int) -> Envio | None:
    """Último envio com sucesso no WhatsApp (falha de rede não bloqueia retry)."""
    return (
        session.query(Envio)
        .filter_by(oferta_id=oferta_id, status="sucesso")
        .order_by(Envio.enviado_em.desc())
        .first()
    )


def ja_conhecida(session: Session, oferta_id: int) -> bool:
    """True se a oferta já foi vista no baseline ou enviada com sucesso."""
    return (
        session.query(Envio.id)
        .filter(
            Envio.oferta_id == oferta_id,
            Envio.status.in_(("sucesso", "visto")),
        )
        .first()
        is not None
    )


def registrar_visto(session: Session, oferta_id: int, preco: float) -> Envio:
    """Marca a oferta como já existente na partida do bot (sem WhatsApp)."""
    return registrar_envio(
        session,
        oferta_id=oferta_id,
        grupo="",
        mensagem="",
        preco=preco,
        status="visto",
    )


def registrar_envio(session: Session, oferta_id: int, grupo: str, mensagem: str, preco: float, status: str) -> Envio:
    envio = Envio(
        oferta_id=oferta_id,
        grupo=grupo,
        mensagem=mensagem,
        preco_enviado=preco,
        status=status,
    )
    session.add(envio)
    session.flush()
    return envio


def contar_envios_desde(session: Session, desde: datetime) -> int:
    return (
        session.query(func.count(Envio.id))
        .filter(Envio.enviado_em >= desde, Envio.status == "sucesso")
        .scalar()
        or 0
    )


def contar_envios_ultima_hora(session: Session) -> int:
    return contar_envios_desde(session, datetime.now() - timedelta(hours=1))


def contar_envios_hoje(session: Session) -> int:
    inicio_do_dia = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return contar_envios_desde(session, inicio_do_dia)


def minutos_desde_ultimo_envio(session: Session) -> float | None:
    """Minutos desde o último envio com sucesso. None se nunca enviou."""
    ultimo = (
        session.query(Envio.enviado_em)
        .filter(Envio.status == "sucesso")
        .order_by(Envio.enviado_em.desc())
        .first()
    )
    if not ultimo or not ultimo[0]:
        return None
    return (datetime.now() - ultimo[0]).total_seconds() / 60.0


def sku_ja_enviado(
    session: Session,
    sku: str,
    loja: str | None = None,
    exceto_oferta_id: int | None = None,
) -> bool:
    """True se algum envio com sucesso já usou este SKU (mesmo produto, outra URL)."""
    q = (
        session.query(Envio.id)
        .join(Oferta, Oferta.id == Envio.oferta_id)
        .filter(Envio.status == "sucesso", Oferta.sku == sku)
    )
    if loja:
        q = q.filter(Oferta.loja == loja)
    if exceto_oferta_id is not None:
        q = q.filter(Oferta.id != exceto_oferta_id)
    return q.first() is not None


def nomes_precos_enviados_recentes(session: Session, dias: int = 30) -> list[tuple[str, float]]:
    """Nome + preço das ofertas já enviadas com sucesso no período."""
    desde = datetime.now() - timedelta(days=dias)
    rows = (
        session.query(Oferta.nome, Envio.preco_enviado)
        .join(Envio, Envio.oferta_id == Oferta.id)
        .filter(Envio.status == "sucesso", Envio.enviado_em >= desde)
        .all()
    )
    return [(n or "", float(p) if p is not None else 0.0) for n, p in rows]
