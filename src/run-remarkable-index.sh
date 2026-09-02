#!/bin/bash
# Kuerzel-Index erzeugen und in die Bibliothek 'an-remarkable' legen.
#
# Wird von Cron ueber heartbeat.sh aufgerufen:
#   heartbeat.sh remarkable-index -- run-remarkable-index.sh
#
# BEWUSST ohne mit-sperre.sh: dieser Job LIEST nur das Vault (das Register der
# Kuerzel) und schreibt nach SharePoint — nie ins Vault. Die Sperre schuetzt
# Schreibzugriffe auf die Arbeitskopie, und davon gibt es hier keine.
#
# Die Geheimnisse (m365.env) liest das Python-Skript selbst ueber
# freigabe_gemeinsam.geheimnis() — sie landen nie in der Shell-Umgebung.
set -uo pipefail

HIER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCHLUESSELDATEI="${M365_ENV:-/etc/notizen-strecke/m365.env}"

if [ ! -r "$SCHLUESSELDATEI" ]; then
    echo "ABBRUCH: '$SCHLUESSELDATEI' fehlt oder ist nicht lesbar." >&2
    exit 2
fi

echo "=== Kuerzel-Index $(date -Iseconds) ==="
exec python3 "$HIER/remarkable_index.py" "$@"
