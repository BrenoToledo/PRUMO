"""Harness de IA do Prumo (R3): interface única para qualquer provedor, sem Django.

- `ia.provedores`: `ProvedorLiteLLM` (Anthropic, OpenAI, DeepSeek, Ollama… pelo LiteLLM) e `ProvedorFalso`.
- `ia.config`: qual provedor e quais limites, lidos das variáveis de ambiente `PRUMO_IA_*`.
- `ia.tarefas`: os prompts de cada sugestão e a leitura (com limpeza) do JSON que volta.

A IA só sugere: quem grava `SugestaoIA` e registra o uso (`ChamadaIA`) é `nucleo.services`.
"""
