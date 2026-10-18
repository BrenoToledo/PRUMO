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
| Frontend (PWA) | Próxima etapa ([`frontend/`](frontend/)) |
| IA, MCP e integrações | Próximas etapas ([roadmap](docs/roadmap.md)) |

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
frontend/       PWA React + TypeScript (próxima etapa)
design/         protótipo FigCraft, imagens das telas e o roteiro que gera o arquivo
docs/           arquitetura, prioridade, API e roadmap
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

- [Arquitetura](docs/arquitetura.md)
- [Motor de prioridade](docs/prioridade.md)
- [API](docs/api.md)
- [Roadmap e próximos passos](docs/roadmap.md)
- [Design e protótipo](design/README.md)
