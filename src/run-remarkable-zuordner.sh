#!/bin/bash
# reMarkable-PDFs aus der Bibliothek zuordnen und Zeiger-Notiz anlegen. E-01.
#
# Wird von Cron ueber heartbeat.sh UND mit-sperre.sh aufgerufen — dieser Job
# SCHREIBT ins Vault, anders als der Abholer:
#   heartbeat.sh remarkable-zuordner -- mit-sperre.sh -- run-remarkable-zuordner.sh
#
# Der Bibliothekszugriff laeuft ueber die Plattform-App (m365.env); das Skript
# liest die Geheimnisse selbst ueber freigabe_gemeinsam.geheimnis().
set -uo pipefail

HIER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT="${VAULT_DIR:-/opt/vault}"

if [ ! -f "$VAULT/${VAULT_MARKER:-CLAUDE.md}" ]; then
    echo "ABBRUCH: '$VAULT' ist keine Vault-Wurzel." >&2
    exit 1
fi

echo "=== reMarkable-Zuordnung $(date -Iseconds) ==="
exec python3 "$HIER/remarkable_zuordner.py" "$@"
