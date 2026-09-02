# E-07 — Verknuepfen und melden statt fragen

**Status:** entschieden · **Betrifft:** Sprachnotiz-Zweig — der einzige Modellaufruf

## Die Frage

Eine gesprochene Notiz gehoert zu einer Zeichnung. Liegen mehrere Zeichnungen im
selben Ordner, welche ist gemeint? Und darf ein Sprachmodell das entscheiden?

## Die Entscheidung: eine Leiter, kein Modell als Vorgabe

| Zeichnungen im Ordner | Was passiert | Modell? |
|---|---|---|
| 0 | nichts, naechster Lauf prueft erneut | nein |
| 1 | deterministisch verknuepft | nein |
| 2 oder mehr | Modell waehlt eine — **oder enthaelt sich** | ja |

**Ein Modell dort einzusetzen, wo es nichts zu deuten gibt, heisst raten zu lassen,
wo man vergleichen kann.** Der Ein-Kandidat-Fall braucht kein Modell, und der
Null-Fall erst recht nicht.

## Und dann: verknuepfen, nicht fragen

Das Ergebnis wird **geschrieben und gemeldet**, nicht zur Freigabe vorgelegt. Eine
falsche Verknuepfung ist eine Wikilink-Zeile — in fuenf Sekunden geloescht. Eine
Freigabekarte fuer jede Verknuepfung waere Reibung ohne Schutzwirkung, und Reibung
ohne Wirkung bringt jede Freigabe in Verruf.

## Die vier Verteidigungen

Sie tragen die Entscheidung, nicht das Vertrauen ins Modell:

1. **Index statt Pfad.** Das Modell gibt eine **Nummer** in eine maschinell gebaute
   Kandidatenliste zurueck — keinen Pfad, keinen Dateinamen. Ein Satz im Transkript
   kann so **keinen Schreibort waehlen**. Index ausserhalb des Bereichs = Enthaltung.
2. **Belegpflicht.** Das Modell nennt den Satz aus dem Transkript, der zur Wahl
   fuehrte, **woertlich**; das Programm prueft, ob er dort steht. Kein Beleg, keine
   Verknuepfung. **Das Modell kann nicht assoziieren, es muss zeigen.**
3. **Fremdtext im Zaun.** Transkript und Kontext stehen zwischen Marken
   ([E-04](E-04%20Fremdinhalt%20ist%20Material,%20nie%20Auftrag.md)). Ein «verknuepfe
   mit X» im Diktat ist Inhalt, kein Befehl.
4. **Schreiben eng.** Nur eine Wikilink-Zeile an zwei benannte Dateien anhaengen,
   beidseitig, idempotent. Kein Anlegen, Verschieben, Loeschen.

## Richtungsregel

Mehrere Sprachnotizen duerfen auf **eine** Zeichnung zeigen. Eine Sprachnotiz zeigt
auf **genau eine oder keine**.
