# Usando este repositório como Projeto do Claude

Este guia monta um Projeto no Claude com todo o contexto do Prumo, para você programar um pouco por dia sem precisar reexplicar nada.

## 1. Criar o Projeto

1. No Claude, crie um projeto chamado **Prumo**.
2. Em **Instruções do projeto**, cole o bloco da seção 2.
3. Em **Conhecimento**, adicione os arquivos da seção 3. Se a integração com o GitHub estiver disponível no seu Claude, adicione direto do repositório `BrenoToledo/PRUMO` (fica sincronizado); senão, envie os arquivos baixados.

## 2. Instruções do projeto (copie e cole)

```text
Você é meu par de programação e PO no projeto Prumo, um gerenciador de tarefas e de atenção com IA.
Eu sou o Breno, desenvolvedor Python/Django. Programo um pouco por dia, em sessões de 30 a 60 minutos.

Contexto e regras:
- Leia docs/contexto.md para entender o produto e as decisões já tomadas.
- O plano e a ordem das tarefas estão em docs/plano.md; cada história é uma issue no GitHub (BrenoToledo/PRUMO).
- Siga o CLAUDE.md: português do Brasil no domínio, regras puras em prioridade.py/planejamento.py,
  banco em services.py, views finas, todo estado de tarefa grava EventoTarefa, IA só sugere.
- Interface das releases R1 e R2: Django templates + HTMX (docs/adr/0001).
- Telas de referência pelos códigos M01–M35 e D01–D04 (docs/especificacao.md, seção 8).

Como trabalhar comigo:
- Uma issue por sessão. Se a issue for grande demais para 60 min, proponha como dividir antes de codar.
- Antes de codar, confirme em 3–5 linhas o plano da sessão (arquivos que vou mexer e testes).
- Entregue código completo dos arquivos alterados, com testes pytest.
- Termine sempre com: comandos para rodar os checks, mensagem de commit e o texto do PR com "Closes #N".
- Se eu descobrir algo novo durante o uso, ajude a escrever a issue no formato de história com critérios de aceite.
- Não invente decisões de produto que contradigam docs/contexto.md; se achar que uma deve mudar, diga e explique.
```

## 3. Arquivos de conhecimento

| Arquivo | Por quê |
| --- | --- |
| `docs/contexto.md` | Produto, glossário, decisões, design system |
| `docs/plano.md` | Releases, ordem das issues, Definição de Pronto |
| `CLAUDE.md` | Convenções de código |
| `docs/api.md` | Contrato da API |
| `docs/arquitetura.md` | Camadas e decisões técnicas |
| `docs/adr/0001-interface-web-com-django-templates-e-htmx.md` | Por que a interface começa simples |
| `docs/especificacao.md` | Especificação completa (requisitos, telas, interações) |
| `backend/nucleo/models.py`, `services.py`, `prioridade.py`, `planejamento.py` | O código que as próximas telas reaproveitam |

Atualize o conhecimento do projeto quando esses arquivos mudarem bastante (por exemplo, ao fim de cada release).

## 4. Rotina de cada sessão

**Começo (2 min)** — cole no chat do projeto:

```text
Sessão de hoje: issue #N — <título>.
<cole aqui o corpo da issue>
Tenho <30|60> minutos. Me passe o plano da sessão e depois o código.
```

**Durante:** crie a branch `issue-N-descricao`, aplique o código, rode:

```bash
cd backend
ruff check . && ruff format --check . && python manage.py makemigrations --check --dry-run && pytest
python manage.py runserver   # e abra no celular/desktop
```

**Fim (5 min):** commit, PR com `Closes #N`, CI verde, merge. Se não terminou, comente na issue onde parou: amanhã você cola esse comentário no começo da sessão.

**Toda sexta (10 min):** revise o marco atual no GitHub. O que aprendeu usando o Prumo vira issue nova ou muda a ordem do `docs/plano.md`.

## 5. Alternativa: Claude Code

Se preferir que o Claude edite os arquivos direto, abra o repositório no Claude Code e peça: *"implemente a issue #N seguindo o CLAUDE.md e o docs/plano.md; abra o PR quando os checks passarem"*. O `CLAUDE.md` já carrega as convenções automaticamente.
