# E-03 — Zwei Fehlerklassen und die Reihenfolge

**Status:** entschieden · **Betrifft:** `graph_basis.py`, jeden Job

## Die Frage

Ein Job scheitert. Soll der naechste Lauf es erneut versuchen?

## Die Entscheidung

**Jeder Fehler traegt eine Klasse, und die Klasse entscheidet — nicht der Fehlertext.**

```
VORUEBERGEHEND  Netz weg, 5xx, Drosselung, Zeitueberschreitung
                -> nichts tun. Der naechste Lauf holt es nach. Selbstheilend.  rc 69

DAUERHAFT       401, 403, 404, falsch konfigurierte Bibliothek
                -> erneut versuchen hilft NIE. Sofort melden.                  rc 77
```

Ohne diese Unterscheidung laeuft ein Konfigurationsfehler endlos im Kreis, oder ein
Netzhaenger loest einen Alarm aus. Ein Job, der beides gleich behandelt, ist entweder
laut oder blind.

## Die zweite Haelfte: die Reihenfolge ist die Idempotenz

Der Abholer arbeitet je Mail in dieser Folge:

```
1. pruefen      DMARC-Gate
2. kappen       Rumpf auf 4'000 Zeichen
3. hochladen    Anhang + alle Spalten in EINEM Zug
4. wegraeumen   Mail nach `verarbeitet` — ERST nach Schritt 3
```

**Bricht der Lauf zwischen 3 und 4 ab, wiederholt der naechste — statt zu verlieren.**
Waere die Reihenfolge umgekehrt, waere die Mail weg und das Dokument nicht da.

Die Wiederholung ist gefahrlos, weil Namensgleichheit geprueft wird: gleicher Name mit
gleichem `Eingang` ist derselbe Vorgang (ersetzen), mit anderem `Eingang` ein anderes
Dokument (die Uhrzeit kommt in den Namen). **Namensgleichheit allein ist kein Beweis
fuer Identitaet.**

## Was daraus folgt

- Nach Schritt 3 haengt nichts mehr an der Mail. Die Bibliothek ist **selbsttragend**,
  und deshalb kann ein Dokument Tage spaeter noch zugeordnet werden.
- Kein stiller Fallback. Fehlt ein Geheimnis, bricht der Lauf ab, **bevor** er
  irgendetwas geschrieben hat.
