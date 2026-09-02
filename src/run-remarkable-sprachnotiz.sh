#!/bin/bash
# Sprachnotizen mit Zeichnungen verknuepfen — der einzige Modellaufruf.
#
# Wird ueber heartbeat.sh und mit-sperre.sh aufgerufen:
#   heartbeat.sh remarkable-sprachnotiz -- mit-sperre.sh -- run-remarkable-sprachnotiz.sh
#
# MIT Sperre, weil dieses Programm ins Vault schreibt und committet.
#
# MODELL_NAME ist PFLICHT (siehe docs/entscheidungen/E-12). Ohne die Angabe
# liefe der Aufruf auf der Sitzungseinstellung dessen, der die CLI zuletzt
# konfiguriert hat — und die aendert sich, ohne dass es jemand merkt.
set -uo pipefail

HIER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCHLUESSELDATEI="${REMARKABLE_ENV:-${SECRETS_DIR:-/etc/notizen-strecke}/remarkable.env}"

if [ ! -r "$SCHLUESSELDATEI" ]; then
    echo "ABBRUCH: '$SCHLUESSELDATEI' fehlt oder ist nicht lesbar." >&2
    exit 78
fi

if [ -z "${MODELL_NAME:-}" ]; then
    echo "ABBRUCH: MODELL_NAME ist nicht gesetzt. Es wird kein Modell geraten (E-12)." >&2
    exit 78
fi

echo "=== Sprachnotiz-Verknuepfung $(date -Iseconds), Modell ${MODELL_NAME} ==="
exec python3 "$HIER/remarkable_sprachnotiz.py" "$@"
