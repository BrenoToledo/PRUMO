# Prumo

**Proteja sua atenção. Planeje o dia real.**

Prumo é um gerenciador de tarefas e de atenção com IA. Você captura ideias em segundos, a IA ajuda a clarificar, quebrar e priorizar, o dia vira blocos de foco realistas, e o sistema aprende com o que de fato aconteceu para sugerir ajustes.

O ciclo do produto: **capturar → clarificar → priorizar → planejar → executar → revisar e aprender.**

## Estado atual

| Parte | Situação |
| --- | --- |
| Especificação | Documento completo: conceitos, problema, funcionamento, requisitos (RF01–RF40, RNF01–RNF14), fases e rascunho do MVP |
| Design | 39 telas (35 mobile, 4 desktop) e protótipo navegável em [`design/`](design/) |
| Backend | Núcleo do MVP em Django: modelo de dados, motor de prioridade, plano do dia em blocos, modo foco, "meu dia quebrou", revisão diária e API REST, com testes |
| Interface web | **Em andamento: R1 · Uso diário mínimo** (Django templates + HTMX, [ADR 0001](docs/adr/0001-interface-web-com-django-templates-e-htmx.md)) |
| IA, MCP e integrações | Releases R3, R4 e fases seguintes ([plano](docs/plano.md)) |

## Como contribuir (um pouco por dia)

Pegue a próxima issue da tabela do marco atual em [`docs/plano.md`](docs/plano.md), crie uma branch `issue-N-descricao`, implemente, rode os checks e abra o PR com `Closes #N`. Cada issue cabe em 30–60 minutos.

## Estrutura

```text
backend/        API Django + DRF (núcleo do MVP)
  nucleo/
    prioridade.py     motor de prioridade (puro, sem banco)
    planejamento.py   capacidade, plano do dia e replanejamento (puro)
    services.py       regras de negócio que tocam o banco
    models.py         modelo de dados do MVP
    views.py, urls.py API REST
    tests/            testes do motor, do planejamento e da API
frontend/       reservado para um cliente React futuro (ver ADR 0001)
design/         protótipo FigCraft, imagens das telas e o roteiro que gera o arquivo
docs/           contexto, plano, especificação, ADRs, arquitetura, prioridade e API
```

## Rodando o backend

Com Docker:

```bash
cp .env.example .env
docker compose up --build
# API em http://localhost:8000/api/ · admin em http://localhost:8000/admin/
docker compose exec backend python manage.py createsuperuser
```

Sem Docker (usa SQLite):

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
pytest            # testes
ruff check .      # lint
```

## Documentação

- **[Plano de desenvolvimento](docs/plano.md)**: releases, ordem das issues e Definição de Pronto
- **[Contexto do produto](docs/contexto.md)**: resumo, glossário e decisões
- **[Usar como Projeto do Claude](docs/claude-projeto.md)**: instruções e rotina diária
- [Especificação completa](docs/especificacao.md)
- [Arquitetura](docs/arquitetura.md)
- [Motor de prioridade](docs/prioridade.md)
- [API](docs/api.md)
- [Design e protótipo](design/README.md)
