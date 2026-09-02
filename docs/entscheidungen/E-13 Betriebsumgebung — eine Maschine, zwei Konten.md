# E-13 — Betriebsumgebung: eine Maschine, zwei Konten, eine Sperre

**Status:** entschieden · **Betrifft:** Betrieb, `mit-sperre.sh`, `heartbeat.sh`

## Die Ausgangslage

Die Jobs laufen ohne Menschen davor, im Minuten- bis Tagesrhythmus, auf einer
kleinen Maschine. Mehrere schreiben in dasselbe Vault.

## Drei Festlegungen

### 1. Zwei Konten, nach Bedarf getrennt

Ein Dienstkonto faehrt alles, was nur Netz und Vault braucht. Ein zweites Konto
faehrt, was an ein Benutzerprofil gebunden ist — in dieser Strecke der eine
Modellaufruf, weil die CLI dort ihre Anmeldung hat.

Das Dienstkonto braucht kein Heimatverzeichnis mit Anmeldedaten. Ein Konto, das nur
liest und ausfuehrt, ist ein kleineres Ziel.

### 2. Eine Sperre um alles, was viele Dateien anfasst

Zwei Prozesse, die gleichzeitig ins Vault schreiben, erzeugen einen Zwischenstand, den
der eine als den eigenen einliest. Dagegen steht eine Dateisperre mit Wartezeit.

**Die Grenze:** *Startest du ein Programm, das viele Dateien anfasst?* Ja heisst
Sperre. **Eine einzelne Dateibearbeitung braucht keine** — die Sperre minutenlang zu
halten, waehrend jemand eine Notiz schreibt, legt alle Jobs still.

### 3. Ein Commit gehoert einem Lauf

Wer die Ergebnisse versioniert, committet **nur die Pfade des eigenen Laufs** — nie
pauschal alles, was gerade offen ist.

```sh
git commit -m "…" -- "Pfad/aus/diesem/Lauf.md"   # richtig
git commit -m "…"                                 # falsch
```

**Gemessen:** Ein gezieltes Hinzufuegen von drei Dateien, gefolgt von einem Commit
**ohne** Pfadangabe, ergab einen Commit mit **323 Dateien** — die uebrigen 320 stammten
aus der parallel laufenden Arbeit einer anderen Sitzung und stehen seither unter einer
fremden Commit-Nachricht.

Inhaltlich ging nichts verloren. Trotzdem ist es ein Schaden: **Ein Rueckbau ist dann
eine Suche und kein Befehl.**

## Was daraus folgt fuer einen Nachbau

Nichts davon ist an eine bestimmte Maschine gebunden. Wer die Strecke anderswo
aufsetzt, braucht: einen Zeitplaner, ein Verzeichnis fuer Geheimnisse mit engen
Rechten, eine Sperrdatei — und die Bereitschaft, den Commit-Umfang ernst zu nehmen.
