#!/bin/bash
# Notizen aus dem Postfach notizen@example.com abholen und in Notizen/ ablegen.
#
# Wird von Cron ueber heartbeat.sh UND mit-sperre.sh aufgerufen — dieser Job
# SCHREIBT ins Vault:
#   heartbeat.sh notiz-eingang -- mit-sperre.sh -- run-notiz-eingang.sh
#
# Die Geheimnisse (postfach.env) liest das Python-Skript selbst ueber
# freigabe_gemeinsam.geheimnis() — sie landen nie in der Shell-Umgebung und
# damit in keiner Prozessliste und keinem Log.
set -uo pipefail

HIER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT="${VAULT_DIR:-/opt/vault}"
SCHLUESSELDATEI="${NOTIZEN_ENV:-/etc/notizen-strecke/postfach.env}"

if [ ! -f "$VAULT/${VAULT_MARKER:-CLAUDE.md}" ]; then
    echo "ABBRUCH: '$VAULT' ist keine Vault-Wurzel." >&2
    exit 1
fi
if [ ! -r "$SCHLUESSELDATEI" ]; then
    echo "ABBRUCH: '$SCHLUESSELDATEI' fehlt oder ist nicht lesbar (Einrichtung, Schritt 1)." >&2
    exit 2
fi

echo "=== Notizen-Eingang $(date -Iseconds) ==="
exec python3 "$HIER/notiz_abholer.py" "$@"
