#!/bin/bash
# Backup diário do PostgreSQL (#9). Roda no contêiner "backup" do deploy/docker-compose.yml.
#   bash backup.sh         espera BACKUP_HORA, faz o dump e repete todo dia
#   bash backup.sh agora   faz um dump agora e sai
# Conexão pelas variáveis padrão do libpq: PGHOST, PGUSER, PGPASSWORD, PGDATABASE.
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups}"
BACKUP_HORA="${BACKUP_HORA:-03:00}"
BACKUP_RETENCAO_DIAS="${BACKUP_RETENCAO_DIAS:-7}"

fazer_backup() {
    local arquivo
    mkdir -p "$BACKUP_DIR"
    arquivo="$BACKUP_DIR/prumo-$(date +%Y-%m-%d_%H%M%S).dump"
    # Grava num arquivo parcial e só renomeia no fim: um dump interrompido nunca parece válido.
    if ! pg_dump --format=custom --no-owner --file="$arquivo.parcial"; then
        rm -f "$arquivo.parcial"
        echo "backup: pg_dump falhou" >&2
        return 1
    fi
    mv "$arquivo.parcial" "$arquivo"
    echo "backup: $arquivo"
    # Guarda BACKUP_RETENCAO_DIAS dias: apaga só os próprios dumps (prumo-*.dump) mais velhos que isso.
    find "$BACKUP_DIR" -maxdepth 1 -name 'prumo-*.dump' -mtime +"$((BACKUP_RETENCAO_DIAS - 1))" -print -delete
    return 0
}

segundos_ate_a_hora() {
    local agora alvo
    agora=$(date +%s)
    alvo=$(date -d "$BACKUP_HORA" +%s)
    if [[ "$alvo" -le "$agora" ]]; then
        alvo=$(date -d "tomorrow $BACKUP_HORA" +%s)
    fi
    echo "$((alvo - agora))"
    return 0
}

if [[ "${1:-}" == "agora" ]]; then
    fazer_backup
    exit "$?"
fi

echo "backup: diário às $BACKUP_HORA, guardando $BACKUP_RETENCAO_DIAS dias em $BACKUP_DIR"
while true; do
    sleep "$(segundos_ate_a_hora)"
    fazer_backup || echo "backup: tentará de novo amanhã" >&2
    sleep 60
done
