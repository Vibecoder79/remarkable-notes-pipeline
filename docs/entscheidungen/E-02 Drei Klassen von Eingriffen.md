# E-02 — Drei Klassen von Eingriffen

**Status:** entschieden · **Betrifft:** jeden Job der Strecke

## Die Frage

Was darf ein Programm ohne Rueckfrage tun, und wo muss ein Mensch entscheiden?

## Die Entscheidung

Drei Klassen. Der Test lautet: **Braucht es eine Aussage darueber, was ein Dokument
bedeutet?**

| Klasse | Beispiel aus dieser Strecke | Wer entscheidet |
|---|---|---|
| **1 Messen und melden** | Eintraege zaehlen, tote Links suchen, Index erzeugen | Job, autonom |
| **2 Mechanisch reparieren** | Kuerzel im Dateinamen aufloesen, Zeiger-Notiz anlegen, Spalten setzen | Job, autonom — **nur nach abschliessender Positivliste** |
| **3 Inhaltlich entscheiden** | Ein Dokument einem Projekt zuordnen, das kein Kuerzel traegt | Mensch |

**Die Groesse der Aenderung spielt keine Rolle.** Ein einzelnes verschobenes Dokument
ist Klasse 3, hundert reparierte Links sind es nicht.

## Warum das die wichtigste Zeile der Strecke ist

Der Zuordner faellt in Klasse 2, **weil er nicht deutet**. Er vergleicht Zeichen:
Steht `[ACME]` im Dateinamen und ist `ACME` im Register vergeben, ist das Ziel
bestimmt. Steht dort nichts oder etwas Unbekanntes, **haelt er an** — er raet nicht
ueber Aehnlichkeit, nicht ueber Teiltreffer, nicht ueber den Inhalt des Dokuments.

Ein Zuordner, der raet, ist kein besserer Zuordner. Er ist einer, dessen Fehler man
nicht mehr sieht: Eine falsche Zuordnung sieht aus wie eine richtige.

## Was daraus folgt

- Die Positivliste ist **abschliessend**. Was nicht draufsteht, ist Klasse 3, auch
  wenn es mechanisch aussieht.
- Bei Zweifel wird **nicht repariert, sondern gemeldet**.
- Ein Dokument ohne gueltiges Kuerzel bleibt sichtbar liegen, statt irgendwo zu landen.
