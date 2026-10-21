"""
collectors/cesgranrio.py — Extração de editais do portal Cesgranrio.

Funções de parsing puras (sem I/O, sem rede):

  parse_listing(html)              → list[str]   URLs dos concursos abertos
  parse_detalhe(html, url)         → dict | None campos extraídos; None se incompleto
  _data_fim_inscricao(inscricoes)  → date | None data de encerramento; None se ilegível
  _inscricoes_encerradas(s, hoje)  → bool | None True=encerrado; None=data ilegível
  _titulo_vagas(vagas)             → str         "281 vagas" ou "Cadastro de reserva"
  _normalizar_salario(s)           → str         remove espaço após vírgula
  _formatar_data_br(data_iso)      → str         "2026-10-20" → "20/10/2026"

Fonte: https://www.cesgranrio.org.br/concursos/?ucat=27
Categoria 27 = inscrições abertas.
"""
import re
from datetime import date, datetime, timezone, timedelta

_BRT = timezone(timedelta(hours=-3))

LISTING_URL = "https://www.cesgranrio.org.br/concursos/?ucat=27"


def parse_listing(html: str) -> list[str]:
    """
    Extrai URLs dos concursos com inscrições abertas (classe CSS grid-cat-27).
    Cada ocorrência da classe delimita um card; o href está no trecho seguinte,
    até o próximo card (próxima ocorrência de grid-cat-N).
    """
    urls: list[str] = []
    for m in re.finditer(r'\bgrid-cat-27\b', html, re.IGNORECASE):
        prox   = re.search(r'\bgrid-cat-\d+\b', html[m.end():], re.IGNORECASE)
        fim    = m.end() + (prox.start() if prox else 1500)
        trecho = html[m.end() : fim]
        lm = re.search(
            r'href="(https?://www\.cesgranrio\.org\.br/concurso/[^"]+)"', trecho
        )
        if lm:
            u = lm.group(1).rstrip("/") + "/"
            if u not in urls:
                urls.append(u)
    return urls


def parse_detalhe(html: str, url: str) -> dict | None:
    """
    Parseia a página de detalhe de um concurso Cesgranrio.
    Retorna dict com os campos ou None se algum campo obrigatório estiver ausente.

    Campos obrigatórios: orgao, vagas, inscricoes, data_prova, link_edital.
    Campos opcionais:    cargos, salario (preenchidos com "—" / "a definir").
    """
    # Título H1: "Concurso <Órgão> <Ano>"
    h1_m = re.search(r'<h1[^>]*>([\s\S]*?)</h1>', html, re.IGNORECASE)
    if not h1_m:
        return None
    titulo = re.sub(r'<[^>]+>', '', h1_m.group(1)).strip()
    orgao  = re.sub(r'^Concurso\s+', '', titulo, flags=re.IGNORECASE)
    orgao  = re.sub(r'\s+\d{4}\s*$', '', orgao).strip()

    # Pares <strong>LABEL</strong> … <h2|h3>VALOR</h2|h3>
    campos: dict[str, str] = {}
    for m in re.finditer(
        r'<strong>([^<]+)</strong>[\s\S]{0,600}?<h[23][^>]*>([\s\S]*?)</h[23]>',
        html, re.IGNORECASE
    ):
        label = m.group(1).strip().upper()
        valor = re.sub(r'<[^>]+>', '', m.group(2)).strip()
        valor = re.sub(r'\s+', ' ', valor)
        campos[label] = valor

    # Link do portal (edital)
    portal_m    = re.search(
        r'href="(https://concursos\.cesgranrio\.org\.br/portal/avaliacoes/\d+)"', html
    )
    link_edital = portal_m.group(1) if portal_m else url

    vagas      = campos.get("VAGAS") or campos.get("NÚMERO DE VAGAS") or ""
    salario    = campos.get("SALÁRIOS") or campos.get("SALÁRIO") or ""
    cargos     = (campos.get("NÍVEIS") or campos.get("NÍVEL")
                  or campos.get("CARGOS") or "")
    inscricoes = campos.get("INSCRIÇÕES") or campos.get("INSCRIÇÃO") or ""
    data_prova = campos.get("PROVAS") or campos.get("PROVA") or ""

    obrigatorios = {
        "orgao": orgao, "vagas": vagas,
        "inscricoes": inscricoes, "data_prova": data_prova,
        "link_edital": link_edital,
    }
    for campo, val in obrigatorios.items():
        if not val:
            return None

    return {
        "orgao":       orgao,
        "banca":       "Cesgranrio",
        "vagas":       vagas,
        "cargos":      cargos or "—",
        "salario":     _normalizar_salario(salario) if salario else "a definir",
        "inscricoes":  inscricoes,
        "data_prova":  data_prova,
        "link_edital": link_edital,
        "fonte":       url,
        "data_coleta": date.today().isoformat(),
        "status":      "ok",
    }


def _data_fim_inscricao(inscricoes: str) -> date | None:
    """
    Extrai a data de fim de inscrição.
    Aceita: "DD/MM a DD/MM/YYYY" e "DD/MM/YYYY a DD/MM/YYYY".
    Retorna None se a data não puder ser lida.
    """
    m = re.search(r'a\s+(\d{1,2})/(\d{1,2})/(\d{4})', inscricoes)
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def _inscricoes_encerradas(inscricoes: str, hoje: date | None = None) -> bool | None:
    """
    Compara hoje BRT com a data de fim de inscrição.
    Retorna True (encerradas), False (abertas) ou None (data ilegível).
    """
    fim = _data_fim_inscricao(inscricoes)
    if fim is None:
        return None
    if hoje is None:
        hoje = datetime.now(_BRT).date()
    return hoje > fim


def _titulo_vagas(vagas: str) -> str:
    """'281' → '281 vagas'; texto não numérico → retorna sem alteração."""
    return f"{vagas} vagas" if re.match(r'^\d+$', vagas.strip()) else vagas


def _normalizar_salario(salario: str) -> str:
    """Remove espaço após vírgula em valores monetários: '10.491, 97' → '10.491,97'."""
    return re.sub(r',\s+(\d)', r',\1', salario)


def _formatar_data_br(data_iso: str) -> str:
    """'2026-10-20' → '20/10/2026'; retorna a string original em caso de erro."""
    try:
        d = date.fromisoformat(data_iso)
        return d.strftime("%d/%m/%Y")
    except ValueError:
        return data_iso
