---
typ: projekt
status: aktiv
meeting_key: ACME
start: 2026-08-01
ende: 2026-12-31
---

# Acme Zonenmodell — Hub

Das Feld `meeting_key` oben ist der Anker der ganzen Strecke. Wer auf dem Tablet ein
Dokument `[ACME] Zonenskizze` nennt, landet damit hier.

## Handschriftliche Notizen

Dieser Block sammelt ein, was die Strecke ablegt. Ohne ihn liegt die Notiz zwar
richtig, ist im Hub aber unsichtbar.

```dataview
LIST file.link
FROM "02 Projekte/Acme Zonenmodell/Notizen"
WHERE typ = "artefakt-zeiger"
SORT file.name DESC
```

## Meetings

```dataview
LIST file.link
FROM "02 Projekte/Acme Zonenmodell/Meetings"
SORT file.name DESC
```
