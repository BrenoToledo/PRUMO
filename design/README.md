# Design

- **`prumo-prototipo-mvp.figcraft`**: as 39 telas, os componentes (com estados Hover e Pressionado), 48 variáveis de cor com modos Claro e Escuro, 9 estilos de texto e 178 ligações de protótipo. Abra no [FigCraft](https://github.com/storytold/figcraft) e use **Apresentar** a partir de um dos fluxos: Dia a dia (M01), Primeiro uso (M29) ou Desktop (D01). Em M33 Configurações, o alternador "Tema escuro" troca o tema durante a apresentação.
- **`telas/`**: uma imagem por seção (A a J).
- **`figcraft/`**: o roteiro em Python que gera o arquivo do zero pelo servidor MCP do FigCraft. Para regenerar:

```bash
# com o figcraft-cli no PATH (ou FIGCRAFT_CLI=/caminho/figcraft-cli)
cd design/figcraft
python3 build.py          # todas as seções
python3 build.py A B      # só algumas
```

| Seção | Telas |
| --- | --- |
| A · Hoje e captura | M01–M03 |
| B · Tarefa e prioridade | M04–M06 |
| C · Foco | M07–M12 |
| D · Meu dia quebrou | M13–M14 |
| E · Caixa de entrada | M15–M17 |
| F · Projetos e rotinas | M18–M21 |
| G · Pessoas e follow-up | M22–M24 |
| H · Revisão e planejamento | M25–M28 |
| I · Conta e configurações | M29–M35 |
| J · Desktop | D01–D04 |
