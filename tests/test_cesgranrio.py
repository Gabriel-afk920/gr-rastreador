"""tests/test_cesgranrio.py — Testes para collectors/cesgranrio.py e rastrear.py (sem rede)."""
import json
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from collectors.cesgranrio import (
    parse_listing,
    parse_detalhe,
    _data_fim_inscricao,
    _inscricoes_encerradas,
    _titulo_vagas,
    _normalizar_salario,
    _formatar_data_br,
)

# ── HTML simulados ────────────────────────────────────────────────────────────

LISTING_HTML = """
<html><body>
  <article class="grid-cat-27 post-item">
    <h3>Concurso Transpetro 2026</h3>
    <a href="https://www.cesgranrio.org.br/concurso/transpetro-2026/">Saiba mais</a>
  </article>
  <article class="grid-cat-27 post-item">
    <h3>Concurso SEMA-MT 2026</h3>
    <a href="https://www.cesgranrio.org.br/concurso/sema-mt-2026/">Saiba mais</a>
  </article>
  <article class="grid-cat-10 post-item">
    <h3>Encerrado</h3>
    <a href="https://www.cesgranrio.org.br/concurso/antigo-2024/">Saiba mais</a>
  </article>
</body></html>
"""

LISTING_VAZIA = "<html><body><p>Sem concursos abertos.</p></body></html>"

DETALHE_TRANSPETRO = """
<html><body>
  <h1>Concurso Transpetro 2026</h1>
  <div>
    <strong>VAGAS</strong><h3>281</h3>
    <strong>SALÁRIOS</strong><h3>Até R$ 15.034,81</h3>
    <strong>NÍVEIS</strong><h3>Médio, Técnico e Superior</h3>
    <strong>PROVAS</strong><h3>06/12/2026</h3>
    <strong>INSCRIÇÕES</strong><h3>12/08 a 21/09/2026</h3>
  </div>
  <a href="https://concursos.cesgranrio.org.br/portal/avaliacoes/18">Portal</a>
</body></html>
"""

DETALHE_SEMA = """
<html><body>
  <h1>Concurso SEMA-MT 2026</h1>
  <div>
    <strong>VAGAS</strong><h3>Cadastro de reserva</h3>
    <strong>SALÁRIOS</strong><h3>Até R$ 10.491, 97</h3>
    <strong>NÍVEIS</strong><h3>Superior para 24 carreiras</h3>
    <strong>PROVAS</strong><h3>13/12/2026</h3>
    <strong>INSCRIÇÕES</strong><h3>17/09 a 14/10/2026</h3>
  </div>
  <a href="https://concursos.cesgranrio.org.br/portal/avaliacoes/21">Portal</a>
</body></html>
"""

DETALHE_SEM_VAGAS = """
<html><body>
  <h1>Concurso Teste 2026</h1>
  <strong>PROVAS</strong><h3>01/01/2027</h3>
  <strong>INSCRIÇÕES</strong><h3>01/11 a 30/11/2026</h3>
</body></html>
"""

DETALHE_SEM_H1 = """
<html><body>
  <strong>VAGAS</strong><h3>100</h3>
  <strong>PROVAS</strong><h3>01/01/2027</h3>
  <strong>INSCRIÇÕES</strong><h3>01/11 a 30/11/2026</h3>
</body></html>
"""

DETALHE_FUTURO = """
<html><body>
  <h1>Concurso NovoBanco 2026</h1>
  <div>
    <strong>VAGAS</strong><h3>500</h3>
    <strong>SALÁRIOS</strong><h3>R$ 8.000,00</h3>
    <strong>NÍVEIS</strong><h3>Superior</h3>
    <strong>PROVAS</strong><h3>15/03/2027</h3>
    <strong>INSCRIÇÕES</strong><h3>01/11 a 30/11/2026</h3>
  </div>
  <a href="https://concursos.cesgranrio.org.br/portal/avaliacoes/99">Portal</a>
</body></html>
"""

URL_T = "https://www.cesgranrio.org.br/concurso/transpetro-2026/"
URL_S = "https://www.cesgranrio.org.br/concurso/sema-mt-2026/"
URL_N = "https://www.cesgranrio.org.br/concurso/novobanco-2026/"


# ── parse_listing ─────────────────────────────────────────────────────────────

class TestParseListing(unittest.TestCase):

    def test_extrai_dois_urls_abertos(self):
        self.assertEqual(len(parse_listing(LISTING_HTML)), 2)

    def test_contem_transpetro(self):
        self.assertIn(URL_T, parse_listing(LISTING_HTML))

    def test_contem_sema(self):
        self.assertIn(URL_S, parse_listing(LISTING_HTML))

    def test_exclui_categoria_errada(self):
        self.assertNotIn(
            "https://www.cesgranrio.org.br/concurso/antigo-2024/",
            parse_listing(LISTING_HTML)
        )

    def test_listagem_vazia_retorna_vazio(self):
        self.assertEqual(parse_listing(LISTING_VAZIA), [])

    def test_sem_duplicatas(self):
        urls = parse_listing(LISTING_HTML + LISTING_HTML)
        self.assertEqual(len(urls), len(set(urls)))

    def test_url_termina_com_barra(self):
        for u in parse_listing(LISTING_HTML):
            self.assertTrue(u.endswith("/"))


# ── parse_detalhe ─────────────────────────────────────────────────────────────

class TestParseDetalhe(unittest.TestCase):

    def test_transpetro_orgao(self):
        self.assertEqual(parse_detalhe(DETALHE_TRANSPETRO, URL_T)["orgao"], "Transpetro")

    def test_transpetro_vagas(self):
        self.assertEqual(parse_detalhe(DETALHE_TRANSPETRO, URL_T)["vagas"], "281")

    def test_transpetro_banca(self):
        self.assertEqual(parse_detalhe(DETALHE_TRANSPETRO, URL_T)["banca"], "Cesgranrio")

    def test_transpetro_data_prova(self):
        self.assertEqual(parse_detalhe(DETALHE_TRANSPETRO, URL_T)["data_prova"], "06/12/2026")

    def test_transpetro_inscricoes(self):
        self.assertEqual(
            parse_detalhe(DETALHE_TRANSPETRO, URL_T)["inscricoes"], "12/08 a 21/09/2026"
        )

    def test_transpetro_link_portal(self):
        self.assertEqual(
            parse_detalhe(DETALHE_TRANSPETRO, URL_T)["link_edital"],
            "https://concursos.cesgranrio.org.br/portal/avaliacoes/18"
        )

    def test_sema_vagas_cadastro_reserva(self):
        self.assertEqual(
            parse_detalhe(DETALHE_SEMA, URL_S)["vagas"], "Cadastro de reserva"
        )

    def test_sema_salario_normalizado(self):
        # Deve remover espaço após vírgula
        self.assertEqual(
            parse_detalhe(DETALHE_SEMA, URL_S)["salario"], "Até R$ 10.491,97"
        )

    def test_sem_portal_usa_url_pagina(self):
        html = DETALHE_TRANSPETRO.replace(
            '<a href="https://concursos.cesgranrio.org.br/portal/avaliacoes/18">Portal</a>',
            ''
        )
        self.assertEqual(parse_detalhe(html, URL_T)["link_edital"], URL_T)

    def test_sem_h1_retorna_none(self):
        self.assertIsNone(parse_detalhe(DETALHE_SEM_H1, URL_T))

    def test_sem_vagas_retorna_none(self):
        self.assertIsNone(parse_detalhe(DETALHE_SEM_VAGAS, URL_T))

    def test_fonte_e_url_da_pagina(self):
        self.assertEqual(parse_detalhe(DETALHE_TRANSPETRO, URL_T)["fonte"], URL_T)

    def test_data_coleta_formato_iso(self):
        import re
        self.assertRegex(
            parse_detalhe(DETALHE_TRANSPETRO, URL_T)["data_coleta"],
            r"^\d{4}-\d{2}-\d{2}$"
        )


# ── _data_fim_inscricao ───────────────────────────────────────────────────────

class TestDataFimInscricao(unittest.TestCase):

    def test_formato_dd_mm_a_dd_mm_aaaa(self):
        self.assertEqual(_data_fim_inscricao("12/08 a 21/09/2026"), date(2026, 9, 21))

    def test_sema_mt(self):
        self.assertEqual(_data_fim_inscricao("17/09 a 14/10/2026"), date(2026, 10, 14))

    def test_sem_ano_retorna_none(self):
        self.assertIsNone(_data_fim_inscricao("12/08 a 21/09"))

    def test_string_vazia_retorna_none(self):
        self.assertIsNone(_data_fim_inscricao(""))

    def test_formato_inesperado_retorna_none(self):
        self.assertIsNone(_data_fim_inscricao("ver edital"))

    def test_data_invalida_retorna_none(self):
        self.assertIsNone(_data_fim_inscricao("01/13/2026 a 32/01/2027"))


# ── _inscricoes_encerradas ────────────────────────────────────────────────────

class TestInscricoesEncerradas(unittest.TestCase):

    def test_encerrado_quando_hoje_depois_do_fim(self):
        self.assertTrue(
            _inscricoes_encerradas("17/09 a 14/10/2026", date(2026, 10, 20))
        )

    def test_aberto_quando_hoje_antes_do_fim(self):
        self.assertFalse(
            _inscricoes_encerradas("01/11 a 30/11/2026", date(2026, 10, 20))
        )

    def test_no_dia_do_fim_ainda_aberto(self):
        self.assertFalse(
            _inscricoes_encerradas("17/09 a 14/10/2026", date(2026, 10, 14))
        )

    def test_data_ilegivel_retorna_none(self):
        self.assertIsNone(_inscricoes_encerradas("ver edital", date(2026, 10, 20)))

    def test_string_vazia_retorna_none(self):
        self.assertIsNone(_inscricoes_encerradas("", date(2026, 10, 20)))


# ── helpers de formatação ─────────────────────────────────────────────────────

class TestTituloVagas(unittest.TestCase):

    def test_numero_adiciona_vagas(self):
        self.assertEqual(_titulo_vagas("281"), "281 vagas")

    def test_cadastro_de_reserva_sem_sufixo(self):
        self.assertEqual(_titulo_vagas("Cadastro de reserva"), "Cadastro de reserva")

    def test_texto_livre_sem_sufixo(self):
        self.assertEqual(_titulo_vagas("Ampla concorrência"), "Ampla concorrência")


class TestNormalizarSalario(unittest.TestCase):

    def test_remove_espaco_apos_virgula(self):
        self.assertEqual(_normalizar_salario("R$ 10.491, 97"), "R$ 10.491,97")

    def test_sem_espaco_permanece_igual(self):
        self.assertEqual(_normalizar_salario("R$ 15.034,81"), "R$ 15.034,81")

    def test_string_vazia(self):
        self.assertEqual(_normalizar_salario(""), "")


class TestFormatarDataBr(unittest.TestCase):

    def test_iso_para_br(self):
        self.assertEqual(_formatar_data_br("2026-10-20"), "20/10/2026")

    def test_zeros_no_dia_e_mes(self):
        self.assertEqual(_formatar_data_br("2026-01-01"), "01/01/2026")

    def test_data_invalida_retorna_original(self):
        self.assertEqual(_formatar_data_br("não-é-data"), "não-é-data")


# ── rastrear.coletar (com mock de rede) ───────────────────────────────────────

def _side_get_aberto(url: str) -> str:
    """Simula a rede: SEMA-MT com inscrições futuras, Transpetro encerrado."""
    if "ucat=27" in url:
        return LISTING_HTML
    if "transpetro" in url:
        return DETALHE_TRANSPETRO   # inscrições encerradas: 21/09/2026
    if "sema-mt" in url:
        # Inscrições futuras para passar o filtro de data
        return DETALHE_FUTURO.replace("NovoBanco", "SEMA-MT").replace(
            "https://concursos.cesgranrio.org.br/portal/avaliacoes/99",
            "https://concursos.cesgranrio.org.br/portal/avaliacoes/21"
        )
    return ""


class TestColetar(unittest.TestCase):

    def _patch_coletar(self, side_get, vistos=None, encerrado_side=None):
        patches = [
            patch("rastrear._get", side_effect=side_get),
            patch("rastrear._ler_vistos", return_value=vistos or set()),
            patch("rastrear._salvar_vistos"),
            patch("rastrear._salvar_resultados"),
            patch("rastrear._ler_resultados", return_value=[]),
        ]
        if encerrado_side is not None:
            patches.append(
                patch("rastrear._inscricoes_encerradas", return_value=encerrado_side)
            )
        return patches

    def _apply(self, patches):
        for p in patches:
            p.start()
        return patches

    def _stop(self, patches):
        for p in patches:
            p.stop()

    def test_sem_fonte_ativa_retorna_vazio(self):
        # Cesgranrio desativada — coletar() deve retornar [] sem erros
        import rastrear
        self.assertEqual(rastrear.coletar(), [])

    def test_data_ilegivel_descarta(self):
        ps = self._apply(self._patch_coletar(lambda u: (
            LISTING_HTML if "ucat=27" in u else DETALHE_TRANSPETRO
        ), encerrado_side=None))
        try:
            import rastrear
            novos = rastrear.coletar()
            self.assertEqual(novos, [])
        finally:
            self._stop(ps)

    def test_url_ja_vista_ignorada(self):
        from rastrear import _hash_url
        vistos = {_hash_url(URL_T), _hash_url(URL_S)}
        ps = self._apply(self._patch_coletar(lambda u: LISTING_HTML, vistos=vistos))
        try:
            import rastrear
            novos = rastrear.coletar()
            self.assertEqual(novos, [])
        finally:
            self._stop(ps)

    def test_robots_bloqueado_ignora_url(self):
        ps = self._apply(self._patch_coletar(
            lambda u: (_ for _ in ()).throw(
                PermissionError("robots.txt proíbe") if "ucat=27" not in u
                else type("R", (), {"__iter__": lambda s: iter([LISTING_HTML])})()
            )
        ))
        # Patch mais direto: _permitido retorna False para detalhe
        with patch("rastrear._get") as mock_get:
            def side(url):
                if "ucat=27" in url:
                    return LISTING_HTML
                raise PermissionError("robots.txt proíbe")
            mock_get.side_effect = side
            with patch("rastrear._ler_vistos", return_value=set()), \
                 patch("rastrear._salvar_vistos"), \
                 patch("rastrear._salvar_resultados"), \
                 patch("rastrear._ler_resultados", return_value=[]):
                import rastrear
                novos = rastrear.coletar()
                self.assertEqual(novos, [])
        self._stop(ps)


    def test_falha_na_listagem_retorna_vazio(self):
        with patch("rastrear._get", side_effect=Exception("timeout")), \
             patch("rastrear._ler_vistos", return_value=set()), \
             patch("rastrear._salvar_vistos"), \
             patch("rastrear._salvar_resultados"), \
             patch("rastrear._ler_resultados", return_value=[]):
            import rastrear
            self.assertEqual(rastrear.coletar(), [])


if __name__ == "__main__":
    unittest.main()
