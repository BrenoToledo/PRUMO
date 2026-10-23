# Servidor MCP do Prumo

Com o servidor MCP você usa o Prumo de dentro do Claude (Desktop ou Code) ou de outro assistente compatível: capturar enquanto conversa, ver o dia, gerar o plano e fechar um bloco de foco. Ele roda no mesmo código do backend e chama os mesmos serviços da interface web; o contrato está em [contratos.md](contratos.md#servidor-mcp-p12-r4).

## Ferramentas

| Ferramenta | Para quê |
| --- | --- |
| `capturar(texto)` | Guarda um item na caixa de entrada, com origem "Assistente (MCP)". A clarificação continua no Prumo |
| `caixa_de_entrada()` | Lista os itens que esperam clarificação, mais novos primeiro |
| `ver_hoje(dia?)` | O plano do dia (o mesmo JSON de `GET /api/hoje/`) |
| `gerar_plano(dia?)` | Refaz os blocos ainda não iniciados e devolve o dia replanejado |
| `concluir_bloco(bloco, resultado, blocos_restantes?, nova_proxima_acao?)` | Fecha o bloco em foco com `concluiu`, `avancou` ou `nao_avancou` |

Cada ferramenta só vê os dados do dono do token. Um erro (texto vazio, bloco de outra pessoa, bloco que não está em foco) volta para o assistente como mensagem, sem gravar nada.

## 1. Gere um token

No Prumo, abra **Perfil → Tokens da API**, crie um token com o nome "Claude" e copie a chave (`prumo_…`). Ela só aparece uma vez. Para cortar o acesso, revogue o token na mesma tela.

## 2. Configure o assistente

O servidor fala por **stdio**: o assistente abre o comando abaixo e conversa com ele pela entrada e saída padrão. O token vai na variável `PRUMO_TOKEN`; sem token válido o comando para antes de abrir o servidor.

```bash
python manage.py servidor_mcp
```

### Prumo no homelab (Docker), Claude no seu computador

O assistente abre o comando no servidor por SSH. Use uma chave SSH sem senha interativa (o assistente não consegue digitar). No Claude Desktop, edite `claude_desktop_config.json` (Configurações → Desenvolvedor → Editar configuração):

```json
{
  "mcpServers": {
    "prumo": {
      "command": "ssh",
      "args": [
        "usuario@servidor",
        "cd ~/PRUMO/deploy && docker compose exec -T -e PRUMO_TOKEN=prumo_SUA_CHAVE backend python manage.py servidor_mcp"
      ]
    }
  }
}
```

O `-T` é obrigatório: sem ele o Docker abre um terminal e mistura caracteres de controle na conversa. Reinicie o Claude Desktop; as ferramentas do Prumo aparecem no ícone de ferramentas.

No Claude Code:

```bash
claude mcp add prumo -- ssh usuario@servidor \
  "cd ~/PRUMO/deploy && docker compose exec -T -e PRUMO_TOKEN=prumo_SUA_CHAVE backend python manage.py servidor_mcp"
```

### Prumo rodando na mesma máquina (desenvolvimento)

```json
{
  "mcpServers": {
    "prumo": {
      "command": "python",
      "args": ["manage.py", "servidor_mcp"],
      "cwd": "/caminho/para/PRUMO/backend",
      "env": {"PRUMO_TOKEN": "prumo_SUA_CHAVE"}
    }
  }
}
```

Use o `python` do ambiente virtual do backend (com `requirements.txt` instalado), e não esqueça das variáveis do banco (`DATABASE_URL`) se não usar o SQLite padrão.

## 3. Teste

Peça ao Claude: "anota no Prumo: ligar para o seguro amanhã" e depois "o que tenho hoje no Prumo?". O item aparece na caixa de entrada com a origem do assistente.

## Problemas comuns

| Sintoma | Causa |
| --- | --- |
| `defina PRUMO_TOKEN` | A variável não chegou ao comando: confira o `-e PRUMO_TOKEN=…` ou o bloco `env` |
| `token inválido ou revogado` | Chave copiada errada ou revogada: gere outra em Perfil → Tokens da API |
| `os tokens da API (#30) ainda não estão neste backend` | O backend é anterior à página de tokens; atualize |
| O assistente não lista as ferramentas | O comando falhou ao abrir: rode o mesmo comando num terminal para ver o erro |

## Segurança

O token dá ao assistente o mesmo acesso que você tem na API. O banco guarda só o hash dele; a chave em texto fica apenas na configuração do assistente, no seu computador. Use um token por assistente, para revogar um sem afetar os outros. O transporte por HTTP (para usar o Prumo pelo Claude no navegador ou no celular) fica para uma próxima história.
