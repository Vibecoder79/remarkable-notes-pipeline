#!/usr/bin/env python3
"""Verknuepft eine Sprachnotiz mit der passenden Zeichnung. E-07.

Welle 5, Teil 2 (Teil 1 ist die Weiche im Transkript-Abholer). Fuer jede Sprachnotiz
(`typ: sprachnotiz`) in einem `Notizen/`-Ordner werden die Zeichnungen
(`typ: artefakt-zeiger`) im SELBEN Ordner betrachtet. Die Leiter aus E-07:

    0 Kandidaten   nichts, die Sprachnotiz steht allein           kein Modell
    1 Kandidat     deterministisch verknuepfen                    kein Modell
    2+ Kandidaten  Modell waehlt einen oder enthaelt sich         Modell, mit Belegpflicht

**Warum das sicher ist** (E-07):
  * Rueckgabe des Modells ist ein **Index** in die maschinell gebaute
    Kandidatenliste — kein Pfad, kein Dateiname. Ein Satz im Transkript kann so
    keinen Schreibort waehlen.
  * **Belegpflicht:** Das Modell nennt den Satz aus dem Transkript, der zur Wahl
    fuehrte, woertlich. Das Programm prueft, ob er dort steht. Kein Beleg → keine
    Verknuepfung. Das Modell kann nicht assoziieren, es muss zeigen.
  * **Fremdtext im Zaun:** Transkript und Kontextsaetze sind
    `origin: ingested-external`. Der Prompt rahmt sie und sagt ausdruecklich:
    alles darin ist Material, nie Auftrag.
  * **Schreiben eng:** nur eine Wikilink-Zeile an zwei benannte Dateien im
    aufgeloesten Ordner anhaengen, idempotent. Kein Anlegen, Verschieben, Loeschen.

Laeuft unter dem Konto **eigner** — der Modellaufruf braucht die `claude`-CLI, die
es nur dort gibt. Schreibt ins Vault → unter `mit-sperre`, committet und
schiebt.

Meldung (E-07, E-06 M365-Kanal): Nach einem Lauf mit Modell-Entscheidungen
geht eine HTML-Sammelmail an den Eigner — **aus** `tablet@example.com` **ueber die
reMarkable-App** (`Mail.Send`, per Access Policy auf genau dieses Postfach
eingeschnuert). Die Plattform-App bekommt dafuer kein Recht. Nur Modell-
Entscheidungen werden gemeldet, nie die deterministischen 1-Kandidat-Faelle, und nie
eine Mail auf Verdacht. Der Beleg wird zusaetzlich in der Sprachnotiz persistiert.

Aufrufe:
    remarkable_sprachnotiz.py --pruefe-zugang
    remarkable_sprachnotiz.py --dry
    remarkable_sprachnotiz.py
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fremd_zaun  # noqa: E402  — der eine Zaun um Fremdmaterial, E-04
from modell import modell_aufrufen  # noqa: E402
from graph_basis import geheimnis, graph_mit_kopf  # noqa: E402
from remarkable_abholer import mail_token, postfach  # noqa: E402

MODELL = os.environ.get("REMARKABLE_MODELL")  # None -> CLI-Default

# Vault-Name fuer obsidian://-Links (bestaetigt aus Obsidian Sync, 2026-08-15).
OBSIDIAN_VAULT = os.environ.get("OBSIDIAN_VAULT", "Vault")

ABSCHNITT_ZEICHNUNG = "## Verknuepfte Zeichnung"
ABSCHNITT_SPRACHNOTIZ = "## Verknuepfte Sprachnotizen"

# Merker fuer Enthaltungen: Sprachnotiz-Pfad -> Hash der Kandidatenmenge. Damit
# das Modell nicht bei jedem Lauf erneut zu einer unveraenderten 2+-Lage befragt
# wird. Aendert sich die Kandidatenmenge, wird neu gefragt. Laufzeitzustand,
# ausserhalb von Git.
MERKER = Path(os.environ.get("REMARKABLE_SPRACHNOTIZ_STATE",
                             "/var/lib/notizen-strecke/sprachnotiz-stand.json"))


def vault_wurzel():
    return os.environ.get("VAULT_DIR", "/opt/vault")


# --------------------------------------------------------------------------
# Vault lesen
# --------------------------------------------------------------------------

def _frontmatter_und_koerper(text):
    if text.startswith("---"):
        ende = text.find("\n---", 3)
        if ende != -1:
            return text[:ende], text[ende + 4:]
    return "", text


def sprachnotizen(vault):
    """Alle Notizen mit `typ: sprachnotiz` in einem `Notizen/`-Ordner."""
    treffer = []
    for baum in ("02 Projekte", "09 Vertrieb", "10 Personen"):
        wurzel = os.path.join(vault, baum)
        if not os.path.isdir(wurzel):
            continue
        for r, dirs, fs in os.walk(wurzel):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            if os.path.basename(r) != "Notizen":
                continue
            for f in fs:
                if not f.endswith(".md"):
                    continue
                p = os.path.join(r, f)
                try:
                    kopf = open(p, encoding="utf-8").read(2048)
                except OSError:
                    continue
                if re.search(r"^typ:\s*sprachnotiz\s*$", kopf, re.M):
                    treffer.append(p)
    return sorted(treffer)


def kandidaten(notizen_ordner):
    """Zeichnungen (`typ: artefakt-zeiger`) im selben Ordner, deterministisch
    sortiert (nach Dateiname), damit der Index stabil ist. Gibt Liste von
    {pfad, dateiname, thema, kontext}."""
    liste = []
    for f in sorted(os.listdir(notizen_ordner)):
        if not f.endswith(".md"):
            continue
        p = os.path.join(notizen_ordner, f)
        try:
            text = open(p, encoding="utf-8").read()
        except OSError:
            continue
        fm, koerper = _frontmatter_und_koerper(text)
        if not re.search(r"^typ:\s*artefakt-zeiger\s*$", fm, re.M):
            continue
        thema = ""
        mh = re.search(r"^#\s+(.+)$", koerper, re.M)
        if mh:
            thema = mh.group(1).strip()
        # Kontext aus dem Zitatblock des Zuordners.
        kontext_zeilen = []
        for zeile in koerper.splitlines():
            if zeile.startswith("> ") and "[!quote]" not in zeile:
                kontext_zeilen.append(zeile[2:].strip())
        liste.append({"pfad": p, "dateiname": f, "thema": thema,
                      "kontext": " ".join(kontext_zeilen).strip()})
    return liste


def transkript(sprachnotiz_pfad):
    """Der gesprochene Text der Sprachnotiz — ohne Frontmatter und ohne den
    maschinellen `## Herkunft`-Block. Grundlage fuer Modell-Eingabe und
    Belegpruefung."""
    text = open(sprachnotiz_pfad, encoding="utf-8").read()
    _, koerper = _frontmatter_und_koerper(text)
    schnitt = koerper.find("## Herkunft")
    if schnitt != -1:
        koerper = koerper[:schnitt]
    # H1 (Titel) entfernen, der Rest ist der gesprochene Inhalt.
    koerper = re.sub(r"^#\s+.+$", "", koerper, count=1, flags=re.M)
    return koerper.strip()


def schon_verknuepft(pfad):
    try:
        return ABSCHNITT_ZEICHNUNG in open(pfad, encoding="utf-8").read()
    except OSError:
        return False


# --------------------------------------------------------------------------
# Belegpruefung — das Programm rechnet nach, es glaubt dem Modell nicht
# --------------------------------------------------------------------------

def _norm(s):
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def beleg_gueltig(beleg, quelle, mindestlaenge=15):
    """Steht der Beleg woertlich in der Quelle? Whitespace normalisiert,
    Gross/Klein egal (Spracherkennung ist da unzuverlaessig), aber der Kern muss
    zeichengenau vorkommen. Zu kurze Belege zaehlen nicht — ein Fuellwort belegt
    nichts. Dieselbe Hausregel wie in meeting_ableitung.py."""
    b = _norm(beleg)
    if len(b) < mindestlaenge:
        return False
    return b in _norm(quelle)


# --------------------------------------------------------------------------
# Der Modellaufruf — so eng wie moeglich
# --------------------------------------------------------------------------

def frage_modell(text, kand):
    """Gibt (index, beleg, roh) zurueck. index = -1 heisst Enthaltung.
    Der Prompt gibt dem Modell NUR Text, keine Werkzeuge; die Rueckgabe ist ein
    Index in `kand`, kein Pfad."""
    zeilen = [
        "Du ordnest eine gesprochene Notiz genau EINER von mehreren handschriftlichen",
        "Zeichnungen zu — oder keiner. Du waehlst nur aus, du benennst nichts.",
        "",
        fremd_zaun.regel(),
        "",
        fremd_zaun.eingezaeunt("SPRACHNOTIZ", text),
        "",
        "Kandidaten (Zeichnungen im selben Ordner):",
    ]
    for i, k in enumerate(kand):
        zeilen.append(f"[{i}] {k['thema'] or k['dateiname']}"
                      + (f" — Kontext: {k['kontext']}" if k["kontext"] else ""))
    zeilen += [
        "",
        "Antworte mit GENAU EINEM JSON-Objekt, sonst nichts:",
        '{"index": <Nummer eines Kandidaten oder -1 fuer keine Zuordnung>,',
        ' "beleg": "<woertlicher Satz aus der Sprachnotiz, der die Wahl traegt>"}',
        "",
        "Regeln:",
        "- Bei Unsicherheit waehle -1. Enthaltung ist eine vollwertige Antwort.",
        "- Der Beleg MUSS woertlich in der Sprachnotiz oben stehen. Erfinde nichts.",
        "- Waehle nur, wenn die Sprachnotiz erkennbar von dieser Zeichnung spricht.",
    ]
    prompt = "\n".join(zeilen)

    antwort = modell_aufrufen(prompt, MODELL, zeitgrenze=300, job="remarkable-sprachnotiz")
    if not antwort.get("ok"):
        raise RuntimeError(f"Modellaufruf fehlgeschlagen: {antwort.get('grund')}")
    # Der Beleg fuer `modell-drift`: Dieser Job schreibt keine eigene Datei mit
    # Frontmatter, nur Verweise in bestehende Notizen. Die Zeile im Log ist deshalb die
    # einzige Spur, welches Modell wirklich lief — dieselbe Form wie in run-skill.sh.
    print(f"  Modell gelaufen: modelle={','.join(antwort.get('modelle') or []) or 'unbekannt'}")
    roh = antwort["text"]
    m = re.search(r"\{.*\}", roh, re.S)
    if not m:
        raise RuntimeError(f"keine JSON-Antwort: {roh[:200]}")
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        raise RuntimeError(f"JSON nicht lesbar: {m.group(0)[:200]}")
    try:
        idx = int(d.get("index", -1))
    except (TypeError, ValueError):
        idx = -1
    if idx < 0 or idx >= len(kand):
        idx = -1
    return idx, (d.get("beleg") or ""), roh


# --------------------------------------------------------------------------
# Schreiben — nur anhaengen, idempotent
# --------------------------------------------------------------------------

def _anhaengen(pfad, abschnitt, wikilink_ziel):
    """Haengt unter `abschnitt` eine Wikilink-Zeile an. Idempotent: existiert die
    Zeile schon, passiert nichts. Handarbeit wird nie ueberschrieben."""
    zeile = f"- [[{wikilink_ziel}]]"
    text = open(pfad, encoding="utf-8").read()
    if zeile in text:
        return False
    if abschnitt in text:
        # Zeile ans Ende des vorhandenen Abschnitts haengen.
        stelle = text.index(abschnitt) + len(abschnitt)
        neu = text[:stelle] + "\n" + zeile + text[stelle:]
    else:
        neu = text.rstrip() + f"\n\n{abschnitt}\n\n{zeile}\n"
    with open(pfad, "w", encoding="utf-8") as f:
        f.write(neu)
    return True


def _wikilink_name(pfad):
    """Obsidian-Wikilink-Ziel: Dateiname ohne Endung (das Vault nutzt kurze
    Namen; bei Kollision faellt Obsidian auf den Pfad zurueck)."""
    return os.path.splitext(os.path.basename(pfad))[0]


def verknuepfe(sprachnotiz, zeichnung, vault, beleg=None):
    """Beidseitiger Wikilink. Gibt die geaenderten vault-relativen Pfade zurueck.
    Bei einer Modell-Entscheidung wird der Beleg zusaetzlich in der Sprachnotiz
    persistiert — auditierbar, damit sichtbar bleibt, worauf die Wahl beruhte."""
    rel_sn = os.path.relpath(sprachnotiz, vault)
    geaendert = []
    if _anhaengen(sprachnotiz, ABSCHNITT_ZEICHNUNG, _wikilink_name(zeichnung)):
        geaendert.append(rel_sn)
    if beleg:
        txt = open(sprachnotiz, encoding="utf-8").read()
        if "Beleg (Modell-Entscheidung)" not in txt:
            with open(sprachnotiz, "a", encoding="utf-8") as f:
                f.write(f"\n> [!quote] Beleg (Modell-Entscheidung)\n> {beleg.strip()}\n")
            if rel_sn not in geaendert:
                geaendert.append(rel_sn)
    if _anhaengen(zeichnung, ABSCHNITT_SPRACHNOTIZ, _wikilink_name(sprachnotiz)):
        geaendert.append(os.path.relpath(zeichnung, vault))
    return geaendert


# --------------------------------------------------------------------------

def merker_lesen():
    try:
        return json.loads(MERKER.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def merker_schreiben(d):
    neben = MERKER.with_suffix(".neu")
    neben.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(neben, MERKER)


def kandidaten_hash(kand):
    return hashlib.sha1(
        "|".join(sorted(k["dateiname"] for k in kand)).encode()).hexdigest()[:12]


# --------------------------------------------------------------------------
# Die Sammelmail — HTML, aus remarkable@ ueber die reMarkable-App (E-06/032)
# --------------------------------------------------------------------------

def _feld(pfad, name):
    txt = open(pfad, encoding="utf-8").read(2000)
    m = re.search(rf"^{name}:\s*(.+)$", txt, re.M)
    return m.group(1).strip() if m else ""


def _thema(pfad):
    txt = open(pfad, encoding="utf-8").read()
    m = re.search(r"^#\s+(.+)$", txt, re.M)
    s = m.group(1).strip() if m else os.path.basename(pfad)
    return re.sub(r"^\[[A-Z0-9-]+\]\s*", "", s)   # Kuerzel-Praefix weg fuers Auge


def _obsidian(pfad, vault):
    rel = os.path.relpath(pfad, vault)
    return (f"obsidian://open?vault={urllib.parse.quote(OBSIDIAN_VAULT)}&file="
            + urllib.parse.quote(rel[:-3] if rel.endswith(".md") else rel))


def digest_zeile(entscheidung, vault):
    """Die maschinellen Fakten einer Zuordnung fuer die Mail. hrefs kommen aus dem
    Frontmatter (maschinell), Themen und Beleg sind Fremdtext (werden escaped)."""
    sn, zn = entscheidung["sprachnotiz"], entscheidung["zeichnung"]
    return {
        "kuerzel": _feld(zn, "project"),
        "sprach_thema": _thema(sn), "zeich_thema": _thema(zn),
        "beleg": entscheidung.get("beleg", ""),
        "sharepoint": _feld(zn, "artefakt"), "transkript": _feld(sn, "transkript_url"),
        "obs_sn": _obsidian(sn, vault), "obs_zn": _obsidian(zn, vault),
    }


def digest_html(zeilen):
    """Reine HTML-Erzeugung. Fremdtext (Themen, Beleg) escaped; hrefs sind
    maschinell und werden fuer das Attribut ebenfalls escaped."""
    e = html.escape
    knopf = ("display:inline-block;margin:2px 10px 2px 0;padding:6px 12px;"
             "background:#eef1f6;border-radius:6px;text-decoration:none;"
             "color:#2657c9;font-size:13px;font-weight:600;")
    karten = []
    for z in zeilen:
        karten.append(
            '<table role="presentation" style="width:100%;border-collapse:separate;'
            'border-spacing:0;background:#f7f8fa;border:1px solid #e6e8ec;'
            'border-radius:10px;margin:0 0 12px;"><tr><td style="padding:16px 18px;">'
            f'<div style="font-size:11px;color:#8a8f98;text-transform:uppercase;'
            f'letter-spacing:.05em;margin-bottom:10px;">Kuerzel {e(z["kuerzel"])}</div>'
            '<table role="presentation" style="border-collapse:collapse;font-size:15px;">'
            f'<tr><td style="padding:2px 10px 2px 0;color:#8a8f98;">Sprachnotiz</td>'
            f'<td style="padding:2px 0;font-weight:600;">{e(z["sprach_thema"])}</td></tr>'
            f'<tr><td style="padding:2px 10px 2px 0;color:#8a8f98;">Zeichnung</td>'
            f'<td style="padding:2px 0;font-weight:600;">{e(z["zeich_thema"])}</td></tr>'
            '</table>'
            + (f'<blockquote style="margin:12px 0;padding:8px 14px;border-left:3px '
               f'solid #c7ccd4;color:#4a4f57;font-size:13.5px;font-style:italic;">'
               f'{e(z["beleg"])}</blockquote>' if z["beleg"] else '')
            + '<div style="margin-top:6px;">'
            f'<a href="{e(z["sharepoint"])}" style="{knopf}">📄 Zeichnung (SharePoint)</a>'
            f'<a href="{e(z["transkript"])}" style="{knopf}">🎙 der Transkript-Dienst-Protokoll</a>'
            f'<a href="{e(z["obs_zn"])}" style="{knopf}">📝 Zeiger-Notiz</a>'
            f'<a href="{e(z["obs_sn"])}" style="{knopf}">🗣 Sprachnotiz</a>'
            '</div></td></tr></table>')
    n = len(zeilen)
    wort = "Sprachnotiz" if n == 1 else "Sprachnotizen"
    return (
        '<div style="font-family:-apple-system,\'Segoe UI\',Arial,sans-serif;'
        'color:#1b1b1f;max-width:600px;line-height:1.5;">'
        f'<p style="font-size:15px;margin:0 0 4px;">Heute wurde{"n" if n != 1 else ""} '
        f'<b>{n} {wort}</b> automatisch mit einer Zeichnung verknuepft.</p>'
        '<p style="font-size:13px;color:#666;margin:0 0 18px;">Jede Zuordnung ist '
        'durch einen woertlichen Satz aus deinem Diktat belegt.</p>'
        + "".join(karten)
        + '<p style="font-size:12.5px;color:#8a8f98;margin-top:16px;">Falsch '
        'zugeordnet? Sprachnotiz oeffnen und die Wikilink-Zeile loeschen — fuenf '
        'Sekunden, kein Prozess.</p></div>')


def sende_digest(entscheidungen, vault):
    """Baut den HTML-Digest und sendet ihn aus remarkable@ ueber die reMarkable-App.
    Nur Modell-Entscheidungen; kein Vorgang -> keine Mail (der Aufrufer prueft das)."""
    zeilen = [digest_zeile(e, vault) for e in entscheidungen]
    n = len(zeilen)
    wort = "Sprachnotiz" if n == 1 else "Sprachnotizen"
    empfaenger = geheimnis("m365.env", "M365_POSTFACH") or "eigner@example.com"
    nachricht = {
        "message": {
            "subject": f"Vault · {n} {wort} verknuepft · "
                       f"{datetime.now().strftime('%Y-%m-%d')}",
            "body": {"contentType": "HTML", "content": digest_html(zeilen)},
            "toRecipients": [{"emailAddress": {"address": empfaenger}}],
        },
        "saveToSentItems": True,
    }
    graph_mit_kopf(mail_token(), "POST", f"/users/{postfach()}/sendMail",
                   rumpf=nachricht)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pruefe-zugang", action="store_true",
                    help="nur pruefen, ob die claude-CLI da ist")
    ap.add_argument("--dry", action="store_true", help="nichts schreiben")
    a = ap.parse_args()

    import shutil
    if a.pruefe_zugang:
        if shutil.which("claude"):
            print("claude-CLI im PATH — Verknuepfer lauffaehig.")
            return 0
        print("ABBRUCH: claude-CLI fehlt. Dieser Job gehoert auf das Konto eigner.",
              file=sys.stderr)
        return 2
    if not shutil.which("claude"):
        print("ABBRUCH: claude-CLI fehlt (Konto eigner noetig).", file=sys.stderr)
        return 2

    vault = vault_wurzel()
    if not os.path.isfile(os.path.join(vault, os.environ.get("VAULT_MARKER", "CLAUDE.md"))):
        print(f"ABBRUCH: '{vault}' ist keine Vault-Wurzel.", file=sys.stderr)
        return 1

    merker = merker_lesen()
    zaehler = {"leer": 0, "eins": 0, "modell": 0, "enthalten": 0, "schon": 0}
    entscheidungen = []
    geschrieben = []

    for sn in sprachnotizen(vault):
        if schon_verknuepft(sn):
            zaehler["schon"] += 1
            continue
        ordner = os.path.dirname(sn)
        kand = [k for k in kandidaten(ordner) if k["pfad"] != sn]
        rel = os.path.relpath(sn, vault)

        if len(kand) == 0:
            zaehler["leer"] += 1
            continue

        if len(kand) == 1:
            # Deterministisch, kein Modell, keine Meldung.
            print(f"  [1 KANDIDAT] {rel} -> {kand[0]['dateiname']}")
            if not a.dry:
                geschrieben += verknuepfe(sn, kand[0]["pfad"], vault)
            zaehler["eins"] += 1
            continue

        # 2+ Kandidaten: Modell — aber nicht erneut, wenn dieselbe Lage schon
        # zur Enthaltung fuehrte.
        h = kandidaten_hash(kand)
        if merker.get(rel) == h:
            print(f"  [UEBERSPRUNGEN] {rel} — {len(kand)} Kandidaten, "
                  f"unveraendert seit letzter Enthaltung")
            zaehler["enthalten"] += 1
            continue

        print(f"  [MODELL] {rel} — {len(kand)} Kandidaten")
        if a.dry:
            print("           (dry: kein Modellaufruf)")
            continue
        try:
            idx, beleg, roh = frage_modell(transkript(sn), kand)
        except RuntimeError as e:
            print(f"           FEHLER: {e}", file=sys.stderr)
            continue

        if idx < 0:
            print("           Enthaltung (index -1)")
            merker[rel] = h
            zaehler["enthalten"] += 1
            continue
        if not beleg_gueltig(beleg, transkript(sn)):
            print(f"           Beleg NICHT in der Sprachnotiz — keine Zuordnung. "
                  f"Beleg: {beleg[:80]!r}", file=sys.stderr)
            merker[rel] = h
            zaehler["enthalten"] += 1
            continue

        gewaehlt = kand[idx]
        print(f"           -> {gewaehlt['dateiname']} (Beleg belegt)")
        geschrieben += verknuepfe(sn, gewaehlt["pfad"], vault, beleg=beleg)
        merker.pop(rel, None)
        entscheidungen.append({"sprachnotiz": sn, "zeichnung": gewaehlt["pfad"],
                               "beleg": beleg})
        zaehler["modell"] += 1

    print(f"\nLeer: {zaehler['leer']}, deterministisch: {zaehler['eins']}, "
          f"per Modell: {zaehler['modell']}, Enthaltungen: {zaehler['enthalten']}, "
          f"schon verknuepft: {zaehler['schon']}.")

    if a.dry:
        print("Dry-Lauf — nichts geschrieben.")
        return 0

    merker_schreiben(merker)

    # Sammelmail nur bei Modell-Entscheidungen (E-07). Der Versand darf den Job
    # nicht scheitern lassen — die Verknuepfung steht schon sichtbar im Vault.
    if entscheidungen:
        try:
            sende_digest(entscheidungen, vault)
            print(f"Digest gesendet aus {postfach()} "
                  f"({len(entscheidungen)} Modell-Zuordnung(en)).")
        except Exception as fehler:
            print(f"WARNUNG: Digest-Versand fehlgeschlagen ({str(fehler)[:150]}). "
                  f"Verknuepfung steht im Vault, Meldung nachholbar.", file=sys.stderr)

    return veroeffentliche(vault, geschrieben)


def veroeffentliche(vault, pfade):
    if not pfade:
        print("Nichts verknuepft, kein Commit.")
        return 0
    pfade = sorted(set(pfade))

    def git(*args):
        return subprocess.run(["git", "-C", vault, *args], capture_output=True, text=True)

    if git("pull", "--ff-only", "origin", "main").returncode != 0:
        print("WARNUNG: pull --ff-only fehlgeschlagen.", file=sys.stderr)
        return 1
    git("add", "--", *pfade)
    n = len(pfade)
    if git("commit", "-q", "-m", f"chore(remarkable): {n} Sprachnotiz-Verknuepfung(en)",
           "-m", "\n".join(f"- {p}" for p in pfade)).returncode != 0:
        print("Nichts zu committen.")
        return 0
    if git("push", "-q", "origin", "main").returncode != 0:
        print("WARNUNG: Push fehlgeschlagen.", file=sys.stderr)
        return 1
    print(f"Veroeffentlicht: {git('rev-parse', '--short', 'HEAD').stdout.strip()} ({n})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
