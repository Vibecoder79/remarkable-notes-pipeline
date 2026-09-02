#!/bin/bash
# reMarkable-Post abholen. E-01.
#
# Wird von Cron ueber heartbeat.sh aufgerufen:
#   heartbeat.sh remarkable -- run-remarkable.sh
#
# BEWUSST ohne mit-sperre.sh: dieser Job schreibt nur in Postfach und
# SharePoint-Bibliothek, nie ins Vault. Die Vault-Sperre kommt mit dem
# Zuordner, sobald hier Notizen entstehen.
#
# Die Geheimnisse (remarkable.env, m365.env) liest das Python-Skript selbst
# ueber freigabe_gemeinsam.geheimnis() — sie landen nie in der Shell-Umgebung
# und damit in keiner Prozessliste und keinem Log.
set -uo pipefail

HIER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCHLUESSELDATEI="${REMARKABLE_ENV:-/etc/notizen-strecke/remarkable.env}"

if [ ! -r "$SCHLUESSELDATEI" ]; then
    echo "ABBRUCH: '$SCHLUESSELDATEI' fehlt oder ist nicht lesbar." >&2
    exit 2
fi

echo "=== reMarkable-Abholung $(date -Iseconds) ==="
exec python3 "$HIER/remarkable_abholer.py" "$@"
