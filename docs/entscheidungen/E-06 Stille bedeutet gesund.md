# E-06 — Stille bedeutet gesund

**Status:** entschieden · **Betrifft:** Waechter, Melder, alle Jobs

## Die Messung, die alles ausloeste

Ein Statusbericht lag als Datei im Vault. Wer die Seite nicht oeffnet, sieht auch ein
rotes Feld nicht — und so waren **vier Routinen sechs Wochen lang tot**, ohne dass es
jemandem auffiel.

Ein Bericht ist eine **Bringschuld des Lesers**. Was fehlte, war eine **Holschuld des
Systems**.

## Die Entscheidung

**Zwei Ebenen der Ueberwachung, bewusst getrennt:**

| Frage | Wer beantwortet sie |
|---|---|
| **Laeuft der Job ueberhaupt?** | Lebenszeichen — jeder Lauf hinterlaesst einen Zeitstempel. Bleibt er aus, meldet der Nachtbericht |
| **Stimmt der Inhalt?** | Der Waechter — er prueft, was ein Lebenszeichen nicht sieht |

Ein Job ohne Lebenszeichen ist ein Job, den man nicht hat.

## Und dann: nicht nach jedem Lauf melden

Der Melder wird **nicht** bei Erfolg aufgerufen. Zehn Jobs mal taeglich waeren ueber
300 Nachrichten im Monat, die alle dasselbe sagen; nach zwei Wochen schaut niemand
mehr hin, und der Kanal ist so tot wie die Statusseite, die er ersetzen sollte.

Gesendet wird **bei Fehlschlag, bei Ueberfaelligkeit — und einmal taeglich die Zeile,
die beweist, dass der Melder selbst noch lebt.**

## Was der Waechter prueft

| Signal | Schwelle | Bedeutung |
|---|---|---|
| Tote `artefakt:`-Links | sofort | Eine Notiz zeigt auf ein Dokument, das nicht mehr da ist |
| «Ohne Zuordnung», veraltet | ab 3 Tagen | Ein Dokument ohne Kuerzel, das niemand repariert hat. Frisch ist normal |
| Stiller Eingang | ab 14 Tagen | Absicht oder Defekt — der Waechter fragt, statt Stille hinzunehmen |

Je Befund hoechstens **eine** Meldung: ein Merker verhindert, dass derselbe tote Link
jede Nacht erneut klingelt.

## Zwei Auflagen an den Kanal

1. **Er haengt nicht an dem, was er ueberwacht.** Kein Vault-Zugriff, kein Git, nur
   ausgehendes HTTPS. Ein Bericht ueber einen kaputten Kanal, der ueber denselben
   Kanal laeuft, ist keine Ueberwachung.
2. **Inhalte gehen nicht hinaus.** Was gesendet wird, sind Kennungen und Fehlerlagen —
   keine Notiztitel, keine Dokumentnamen.
