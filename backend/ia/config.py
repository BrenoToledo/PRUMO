"""Qual IA usar e quanto ela pode gastar, pelas variáveis de ambiente (a chave nunca vai para o banco).

| Escolha no perfil | Modelo | Chave / endereço |
| --- | --- | --- |
| `prumo` (IA do Prumo) | `PRUMO_IA_MODELO` | `PRUMO_IA_CHAVE` |
| `propria` (minha chave de API) | `PRUMO_IA_MODELO_PROPRIO` | `PRUMO_IA_CHAVE_PROPRIA` |
| `local` (modelo local) | `PRUMO_IA_MODELO_LOCAL` | `PRUMO_IA_URL_LOCAL` |

O modelo segue o LiteLLM (`anthropic/claude-haiku-5-5`, `openai/gpt-4o-mini`, `ollama/llama3.2`); `falso` liga o
provedor de demonstração. Sem a chave na variável, o LiteLLM procura a padrão do provedor (`ANTHROPIC_API_KEY`…).
Transcrição de áudio (#27), também pelo LiteLLM: `PRUMO_IA_TRANSCRICAO`, `PRUMO_IA_TRANSCRICAO_PROPRIA` e
`PRUMO_IA_TRANSCRICAO_LOCAL` (ex.: `whisper-1`, `groq/whisper-large-v3`), com a mesma chave e endereço do provedor.
Limites por usuário: `PRUMO_IA_LIMITE_DIARIO` (chamadas) e `PRUMO_IA_LIMITE_MENSAL_USD`.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from .provedores import Provedor, ProvedorFalso, ProvedorLiteLLM

MODELO_FALSO = "falso"
LIMITE_DIARIO_PADRAO = 50
LIMITE_MENSAL_USD_PADRAO = 2.0
ESCOLHAS = {
    "prumo": ("PRUMO_IA_MODELO", "PRUMO_IA_CHAVE", ""),
    "propria": ("PRUMO_IA_MODELO_PROPRIO", "PRUMO_IA_CHAVE_PROPRIA", ""),
    "local": ("PRUMO_IA_MODELO_LOCAL", "", "PRUMO_IA_URL_LOCAL"),
}
TRANSCRICOES = {
    "prumo": "PRUMO_IA_TRANSCRICAO",
    "propria": "PRUMO_IA_TRANSCRICAO_PROPRIA",
    "local": "PRUMO_IA_TRANSCRICAO_LOCAL",
}


@dataclass(frozen=True)
class Config:
    modelos: dict[str, tuple[str, str, str]]  # escolha → (modelo, chave, url)
    limite_diario: int = LIMITE_DIARIO_PADRAO
    limite_mensal_usd: float = LIMITE_MENSAL_USD_PADRAO
    transcricoes: dict[str, str] = field(default_factory=dict)  # escolha → modelo de transcrição

    @classmethod
    def do_ambiente(cls, ambiente: Mapping[str, str] | None = None) -> Config:
        env = os.environ if ambiente is None else ambiente
        modelos = {
            escolha: tuple(env.get(nome, "").strip() if nome else "" for nome in nomes)
            for escolha, nomes in ESCOLHAS.items()
        }
        return cls(
            modelos=modelos,
            transcricoes={escolha: env.get(nome, "").strip() for escolha, nome in TRANSCRICOES.items()},
            limite_diario=int(env.get("PRUMO_IA_LIMITE_DIARIO", "") or LIMITE_DIARIO_PADRAO),
            limite_mensal_usd=float(
                (env.get("PRUMO_IA_LIMITE_MENSAL_USD", "") or str(LIMITE_MENSAL_USD_PADRAO)).replace(",", ".")
            ),
        )

    def opcoes(self) -> dict[str, bool]:
        return {escolha: bool(modelo) for escolha, (modelo, _, _) in self.modelos.items()}

    def provedor(self, escolha: str) -> Provedor | None:
        modelo, chave, url = self.modelos.get(escolha, ("", "", ""))
        if not modelo:
            return None
        if modelo == MODELO_FALSO:
            return ProvedorFalso()
        return ProvedorLiteLLM(modelo, chave=chave, url=url, transcricao=self.transcricoes.get(escolha, ""))
