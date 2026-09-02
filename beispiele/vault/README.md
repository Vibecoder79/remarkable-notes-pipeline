# Beispiel-Vault

Ein Minimal-Vault zum Ausprobieren, bevor der echte Bestand drankommt.

```sh
VAULT_DIR="$PWD/beispiele/vault" VAULT_MARKER=.vault \
  python3 src/kuerzel_register.py --register
```

Erwartete Ausgabe:

```
ACME            02 Projekte/Acme Zonenmodell
P-MUSTER-M      10 Personen/Muster Martina
VTR-ACME        09 Vertrieb/2026/Beispiel AG — Vorprojekt
```

Die dritte Zeile ist die interessante: Der Ordner `10 Personen/Muster Martina` existiert
**nicht**. Das Register zeigt auf den künftigen Ort, weil die Kontaktnotiz ihr Kürzel
schon trägt.

Und der Selbsttest, der zeigt, was **nicht** zugeordnet wird:

```sh
VAULT_DIR="$PWD/beispiele/vault" VAULT_MARKER=.vault \
  python3 src/kuerzel_register.py --selbsttest
```
