"""
rastrear.py — Rastreador de editais de concursos públicos.

Saída:
  saida/concursos.json — lista de concursos coletados (id = hash SHA-256 da URL)
  saida/vistos.json    — hashes das URLs já processadas (evita duplicatas)

Regras:
  • robots.txt lido antes de qualquer coleta; URL proibida = não visitada
  • User-Agent: GrNoticias-Bot/1.0
  • Intervalo mínimo de 10 s por domínio, 1 requisição por vez
  • Budget de 15 min por execução
  • Sem segredos, sem tokens, sem dados de candidatos
"""
import hashlib
import json
import logging
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

# Cesgranrio desativado: o servidor retorna HTTP 401/403 para /robots.txt
# quando acessado pelos IPs do GitHub Actions. Python trata 401/403 como
# "disallow all" (RFC 9309 §2.3.1.3). O rastreador respeita esse sinal.
# from collectors.cesgranrio import (
#     LISTING_URL, parse_listing, parse_detalhe,
#     _inscricoes_encerradas, _formatar_data_br,
# )

ROOT        = Path(__file__).parent
SAIDA_DIR   = ROOT / "saida"
VISTOS_PATH = SAIDA_DIR / "vistos.json"
SAIDA_PATH  = SAIDA_DIR / "concursos.json"

_UA           = "GrNoticias-Bot/1.0 (+https://github.com/Gabriel-afk920/gr-rastreador)"
_RATE_LIMIT_S = 10
_BUDGET_S     = 15 * 60

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

_ultimo_req:   dict[str, float]        = {}
_robots_cache: dict[str, RobotFileParser] = {}
_inicio: float = 0.0


# ── robots.txt ────────────────────────────────────────────────────────────────

def _robots(dominio: str) -> RobotFileParser:
    if dominio not in _robots_cache:
        rp = RobotFileParser()
        rp.set_url(f"https://{dominio}/robots.txt")
        try:
            rp.read()
        except Exception:
            pass  # sem robots.txt → permissivo
        _robots_cache[dominio] = rp
    return _robots_cache[dominio]


def _permitido(url: str) -> bool:
    return _robots(urlparse(url).netloc).can_fetch(_UA, url)


# ── Rate limiting e budget ────────────────────────────────────────────────────

def _aguardar(dominio: str) -> None:
    agora  = time.monotonic()
    espera = _RATE_LIMIT_S - (agora - _ultimo_req.get(dominio, 0.0))
    if espera > 0:
        log.info("rate limit: aguardando %.1fs para %s", espera, dominio)
        time.sleep(espera)
    _ultimo_req[dominio] = time.monotonic()


def _dentro_do_budget() -> bool:
    return (time.monotonic() - _inicio) < _BUDGET_S


def _get(url: str) -> str:
    if not _dentro_do_budget():
        raise TimeoutError("budget de 15 min esgotado")
    if not _permitido(url):
        raise PermissionError(f"robots.txt proíbe: {url}")
    dominio = urlparse(url).netloc
    _aguardar(dominio)
    resp = requests.get(url, headers={"User-Agent": _UA}, timeout=30)
    resp.raise_for_status()
    return resp.text


# ── Persistência ──────────────────────────────────────────────────────────────

def _hash_url(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def _ler_vistos() -> set[str]:
    try:
        return set(json.loads(VISTOS_PATH.read_text(encoding="utf-8")))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def _salvar_vistos(vistos: set[str]) -> None:
    SAIDA_DIR.mkdir(parents=True, exist_ok=True)
    VISTOS_PATH.write_text(
        json.dumps(sorted(vistos), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _ler_resultados() -> list[dict]:
    try:
        return json.loads(SAIDA_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _salvar_resultados(resultados: list[dict]) -> None:
    SAIDA_DIR.mkdir(parents=True, exist_ok=True)
    SAIDA_PATH.write_text(
        json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ── Coleta ────────────────────────────────────────────────────────────────────

def coletar() -> list[dict]:
    """
    Retorna lista de novos concursos coletados nesta execução.
    Nenhuma fonte habilitada no momento — ver README.
    """
    global _inicio
    _inicio = time.monotonic()

    log.warning(
        "nenhuma fonte habilitada: Cesgranrio desativada (HTTP 401/403 em robots.txt "
        "nos runners do GitHub Actions — ver README)"
    )
    return []


if __name__ == "__main__":
    import sys
    novos = coletar()
    print(json.dumps(novos, ensure_ascii=False, indent=2))
    sys.exit(0)
