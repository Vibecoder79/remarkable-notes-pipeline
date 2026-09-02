# E-09 — Zwei App-Registrierungen statt einer

**Status:** entschieden · **Betrifft:** Microsoft-365-Einrichtung

## Die Frage

Ein Schluessel fuer alles waere einfacher zu verwalten. Warum zwei?

## Die Entscheidung

**Zwei getrennte App-Registrierungen im selben Mandanten, mit sich nicht
ueberschneidenden Reichweiten:**

| App | Geheimnis | Recht | Reichweite |
|---|---|---|---|
| **Bibliotheks-App** | `m365.env` | `Sites.Selected` | genau **eine** SharePoint-Site |
| **Postfach-App** | `postfach.env` | `Mail.ReadWrite`, `Mail.Send` | genau **ein** Dienstpostfach |

## Warum das keine Formsache ist

Die Postfach-App braucht `Mail.Send`, damit die Sammelmeldung aus dem Dienstpostfach
hinausgeht. Eine mandantenweite `Mail.Send`-Erteilung hiesse: **dieser Schluessel kann
als jede Person im Haus senden.** Wer ihn von der Maschine holt, schreibt Mails im
Namen der Geschaeftsfuehrung.

Die Application Access Policy schnuert die App auf **ein** Postfach ein. Das ist eine
**physische Grenze, keine Regel** — sie haengt nicht daran, dass sich ein Programm
korrekt verhaelt.

**Gemessen, in beide Richtungen:**

```
Postfach-App    -> Dienstpostfach      200 OK
Postfach-App    -> Postfach des Eigners  403 ErrorAccessDenied
Bibliotheks-App -> Dienstpostfach      403 (durch die Policy ausgeschlossen)
```

Die Eingrenzung ist damit **gemessen und nicht geglaubt**. Faellt sie weg, hat eine
Kennung auf derselben Maschine Sende-Recht auf jedes Postfach.

## Was daraus folgt

- Wer eine Rolle eintraegt, die ueber das Dienstpostfach hinausreicht, hebelt die
  Trennung aus. **Im Zweifel: nicht eintragen, sondern fragen.**
- Die Reihenfolge bei der Einrichtung ist zwingend: **erst die Policy, dann das
  Recht.** Umgekehrt gaebe es ein Zeitfenster — mitunter Stunden lang —, in dem die
  App mandantenweiten Postfachzugriff haette.
- Beide Richtungen werden nach jeder Aenderung **per Graph gegengemessen**, nicht nur
  per Test-Cmdlet. Das Cmdlet sagt laengst das Richtige, wenn der echte Aufruf noch
  scheitert.
