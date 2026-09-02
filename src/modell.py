#!/usr/bin/env python3
"""Der eine Ort, an dem diese Strecke ein Sprachmodell aufruft.

Wo ein Modell vorkommt — und wo bewusst nicht
----------------------------------------------
Die ganze Strecke ist deterministisch: Zeichenvergleich, HTTP, Dateien. Ein Modell
kommt an genau EINER Stelle ins Spiel, im Sprachnotiz-Zweig, und auch dort erst ab
zwei Kandidaten. Bei null Kandidaten passiert nichts, bei einem entscheidet der Code.

Das ist kein Zufall, sondern die Auslegung: Ein Modell dort einzusetzen, wo es nichts
zu deuten gibt, heisst raten zu lassen, wo man vergleichen kann — teurer, langsamer
und nicht nachvollziehbar.

Drei Auflagen bei diesem Aufruf
-------------------------------
1. **Kein Werkzeugzugriff.** Alles, was gebraucht wird, steht im Prompt. Damit haengt
   das Ergebnis nur an dem, was dieses Programm nachweislich beigelegt hat.
2. **Leeres Arbeitsverzeichnis.** Kein Projektkontext von der Seite, keine
   gefundene Konfigurationsdatei. Gleiche Eingabe, gleiche Grundlage.
3. **Das Modell wird benannt, nie geerbt.** Ohne ausdrueckliche Angabe liefe der Job
   auf der Voreinstellung dessen, der die CLI zuletzt eingestellt hat — und die
   aendert sich, ohne dass es jemand merkt. Siehe
   `docs/entscheidungen/E-12 Jeder Modellaufruf nennt sein Modell.md`.

Der Rueckgabewert traegt eine Fehlerklasse wie alles in dieser Strecke, damit der
Aufrufer weiss, ob Wiederholen hilft.
"""
import os
import subprocess
import tempfile

# Die CLI, die den Aufruf ausfuehrt, und das Modell. BEIDE ohne stillen Vorgabewert
# fuer das Modell: fehlt es, ist das ein Befund und kein Default.
CLI = os.environ.get("MODELL_CLI", "claude")
MODELL = os.environ.get("MODELL_NAME")

# Werkzeuge, die dem Modell entzogen werden. Die Liste ist eine Positivliste des
# Entzugs — was eine kuenftige CLI-Fassung dazu erfindet, ist NICHT automatisch
# gesperrt. Wer die CLI wechselt, prueft diese Zeile.
WERKZEUGE_AUS = ["Bash", "Edit", "Write", "Read", "Glob", "Grep",
                 "WebFetch", "WebSearch", "Task", "NotebookEdit"]


def modell_aufrufen(prompt: str, modell: str | None = None,
                    zeitgrenze: int = 900) -> dict:
    """Einen Durchlauf ausfuehren und das ERGEBNIS pruefen, nicht den Rueckgabewert.

    Der Rueckgabewert einer CLI beweist wenig: Sie kann mit rc=0 enden und dabei
    «Unknown command» ausgegeben haben. Geprueft wird deshalb, ob Text ankam.

    Rueckgabe:
        {"ok": True, "text": "…"}
        {"ok": False, "klasse": "voruebergehend"|"dauerhaft", "grund": "…"}
    """
    gewaehlt = modell or MODELL
    if not gewaehlt:
        return {"ok": False, "klasse": "dauerhaft",
                "grund": "kein Modell benannt — weder Parameter noch MODELL_NAME. "
                         "Es wird keines geraten (siehe E-12)."}

    befehl = [CLI, "-p", "--model", gewaehlt]
    if WERKZEUGE_AUS:
        befehl += ["--disallowedTools", ",".join(WERKZEUGE_AUS)]

    with tempfile.TemporaryDirectory() as leeres_verzeichnis:
        try:
            lauf = subprocess.run(befehl, input=prompt, capture_output=True,
                                  text=True, timeout=zeitgrenze,
                                  cwd=leeres_verzeichnis)
        except subprocess.TimeoutExpired:
            return {"ok": False, "klasse": "voruebergehend",
                    "grund": f"Zeitgrenze von {zeitgrenze} s ueberschritten"}
        except FileNotFoundError:
            return {"ok": False, "klasse": "dauerhaft",
                    "grund": f"`{befehl[0]}` ist nicht im PATH"}

    ergebnis = (lauf.stdout or "").strip()
    if not ergebnis:
        # Ein angenommener Aufruf, der nichts geliefert hat, wiederholt sich morgen
        # genauso — das ist dauerhaft. Ein abgestuerzter Prozess darf wiederholt
        # werden.
        klasse = "voruebergehend" if lauf.returncode != 0 else "dauerhaft"
        return {"ok": False, "klasse": klasse,
                "grund": f"leeres Ergebnis (rc={lauf.returncode}): "
                         f"{(lauf.stderr or '').strip()[:200]}"}
    return {"ok": True, "text": ergebnis, "modell": gewaehlt}
