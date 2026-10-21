# gr-rastreador

Rastreador de editais de concursos públicos com inscrições abertas. Coleta dados de portais de bancas organizadoras e disponibiliza em formato JSON.

## O que faz

- Acessa os portais das bancas habilitadas uma vez por dia
- Extrai dados factuais: órgão, banca, vagas, cargos, salário, inscrições, data da prova e link do edital
- Descarta concursos com inscrições encerradas ou datas ilegíveis
- Salva os resultados em `saida/concursos.json`
- Rastreia URLs já vistas em `saida/vistos.json` para evitar duplicatas

## Fontes habilitadas

| Banca | Portal | Categoria coletada |
|-------|--------|-------------------|
| Cesgranrio | cesgranrio.org.br | Inscrições abertas (grid-cat-27) |

## Fontes fora do escopo

| Banca | Motivo |
|-------|--------|
| FCC | `robots.txt`: `Disallow: /concursos/` |

## Regras de educação do rastreador

- **robots.txt**: lido antes de qualquer requisição; URL proibida = URL não visitada, sem contornar bloqueios
- **User-Agent**: `GrNoticias-Bot/1.0 (+https://github.com/Gabriel-afk920/gr-rastreador)`
- **Intervalo**: mínimo de 10 s entre requisições por domínio, 1 requisição por vez
- **Budget**: máximo de 15 minutos por execução

## O que NÃO coleta

- Dados pessoais ou de candidatos
- Gabaritos, resultados ou convocações
- Conteúdo atrás de autenticação
- Qualquer portal que proíba coleta via `robots.txt` ou termos de uso

## Formato da saída

`saida/concursos.json`:

```json
[
  {
    "id": "d949d2c4673c2ac6",
    "orgao": "SEMA-MT",
    "banca": "Cesgranrio",
    "vagas": "Cadastro de reserva",
    "cargos": "Superior para 24 carreiras",
    "salario": "Até R$ 10.491,97",
    "inscricoes": "17/09 a 14/10/2026",
    "data_prova": "13/12/2026",
    "link_edital": "https://concursos.cesgranrio.org.br/portal/avaliacoes/21",
    "fonte": "https://www.cesgranrio.org.br/concurso/sema-mt-2026/",
    "data_coleta": "20/10/2026",
    "status": "ok"
  }
]
```

## Execução manual

```bash
pip install -r requirements.txt
python rastrear.py
```

## Testes

```bash
python -m pytest tests/ -v
```

Todos os testes usam páginas HTML simuladas — sem acesso à rede.
