# E-12 — Jeder Modellaufruf nennt sein Modell

**Status:** entschieden · **Betrifft:** `modell.py`, Sprachnotiz-Zweig

## Die Messung, die alles ausloeste

Ein Job rief eine Kommandozeilen-KI ohne `--model` auf. Damit lief er auf der
**Sitzungseinstellung dessen, der die CLI zuletzt konfiguriert hat** — und die aendert
sich, ohne dass es jemand merkt.

Gemessen ueber einen Zeitraum: **35 Laeufe auf einem grossen Modell, 9 auf einem
kleineren — ohne dass das je jemand entschieden haette.** Gleiche Eingabe, anderes
Ergebnis, andere Kosten, kein Eintrag irgendwo.

## Die Entscheidung

**Jede Stelle, die ein Sprachmodell startet, nennt ihr Modell ausdruecklich.**

Fehlt die Angabe, ist das ein **Befund und kein Vorgabewert**: `modell.py` bricht ab,
statt eines zu waehlen.

```python
if not gewaehlt:
    return {"ok": False, "klasse": "dauerhaft",
            "grund": "kein Modell benannt — es wird keines geraten."}
```

## Zwei weitere Auflagen an denselben Aufruf

1. **Kein Werkzeugzugriff.** Alles, was gebraucht wird, steht im Prompt. Damit haengt
   das Ergebnis nur an dem, was das Programm nachweislich beigelegt hat — sonst waere
   jede Zusicherung ueber die Eingabe wertlos, weil sich das Modell den Rest
   danebenher selbst zusammensuchen koennte.
2. **Leeres Arbeitsverzeichnis.** Keine gefundene Konfigurationsdatei, kein
   Projektkontext von der Seite. Gleiche Eingabe, gleiche Grundlage.

## Der Rueckgabewert beweist nichts

Eine CLI kann mit `rc=0` enden und «Unknown command» ausgegeben haben. Geprueft wird
deshalb **das Ergebnis**, nicht der Rueckgabewert — und die Unterscheidung traegt die
Fehlerklasse: ein angenommener Aufruf ohne Ergebnis wiederholt sich morgen genauso
(**dauerhaft**), ein abgestuerzter Prozess darf wiederholt werden (**voruebergehend**).
