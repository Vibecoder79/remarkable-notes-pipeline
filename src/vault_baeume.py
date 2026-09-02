#!/usr/bin/env python3
"""Was die Programme ueber die Ordnerstruktur des Vaults wissen muessen.

Warum das ein eigenes Modul ist
-------------------------------
Zwei Programme der Strecke — der Zuordner und der Mail-Eingang — legen Notizen ab
und muessen dafuer dieselbe Frage beantworten: Wo genau, und was ist zu tun, wenn der
Zielordner noch gar nicht existiert? Stuende die Antwort in beiden, liefe sie
auseinander, sobald sich die Struktur einmal aendert.

Die Ordnernamen stehen als Konstanten hier oben, nicht im Code verstreut. Wer das
Vault anders schneidet, aendert diese Zeilen und sonst nichts.
"""
import os
import re

# Die Baeume, in denen Kuerzel vergeben werden. Muss zu REGISTER_WURZELN in
# `kuerzel_register.py` passen — dort steht die Begruendung je Baum.
KONTAKTE_ORDNER = os.path.join("09 Vertrieb", "_Kontakte")
PERSONEN_BAUM = "10 Personen"

# Unterordner, in den Zeiger-Notizen geschrieben werden. Bewusst NICHT `Meetings/`:
# eine handschriftliche Skizze ist kein Protokoll.
NOTIZEN_ORDNER = "Notizen"


def materialisiere_personen_ordner(vault, ziel_rel, trockenlauf=False):
    """Erstes Dokument zu einer Person, die bisher nur eine flache Kontakt-Notiz hat:
    der Ordner `10 Personen/<Name>/` entsteht, und die Notiz zieht als Hub um.

    Warum nicht auf Vorrat
    ----------------------
    Ein Ordner je Kontakt waere ein Baum voller leerer Huelsen. Der Ordner entsteht
    beim ERSTEN Inhalt — das Kuerzel dagegen traegt die Kontakt-Notiz von Anfang an,
    damit es sofort benutzbar ist. Das Register loest ein solches Kuerzel bereits auf
    den KUENFTIGEN Ordner auf; diese Funktion holt die Wirklichkeit nach.

    Deterministisch am Kuerzel, keine Bedeutungsentscheidung.

    Gibt `(meldung, pfade)` zurueck. Die Pfade sind vault-relativ und MUESSEN mit
    committet werden: ein halb versionierter Umzug — die Datei am neuen Ort, die
    Loeschung am alten nicht erfasst — blockiert jeden spaeteren Push.
    """
    if os.path.dirname(ziel_rel) != PERSONEN_BAUM:
        return None, []
    name = os.path.basename(ziel_rel)
    hub = os.path.join(vault, ziel_rel, f"{name}.md")
    if os.path.isfile(hub):
        return None, []
    flach_rel = os.path.join(KONTAKTE_ORDNER, f"{name}.md")
    flach = os.path.join(vault, flach_rel)
    if not os.path.isfile(flach):
        # Kein Abbruch: das Dokument wird abgelegt, nur der Hub fehlt. Ein Befund,
        # den ein Mensch aufloest — kein Grund, den Lauf scheitern zu lassen.
        return (f"WARNUNG: weder Hub noch flache Kontakt-Notiz fuer '{name}' — "
                f"Dokument wird abgelegt, aber der Personen-Ordner bleibt ohne Hub"), []
    if trockenlauf:
        return f"wuerde materialisieren: {flach_rel} -> {ziel_rel}/ (Notiz wird Hub)", []
    os.makedirs(os.path.join(vault, ziel_rel), exist_ok=True)
    os.rename(flach, hub)
    return (f"materialisiert: {name}.md -> {ziel_rel}/ (Kontakt-Notiz ist jetzt der Hub)",
            [flach_rel, os.path.join(ziel_rel, f"{name}.md")])


def sichere_dateiname(s, max_len=90):
    """Ein Dateiname, den Dateisystem und SharePoint beide annehmen.

    Die verbotenen Zeichen sind die Schnittmenge aus beiden Welten — wer nur gegen
    das lokale Dateisystem prueft, baut Namen, die beim Hochladen abgelehnt werden.
    """
    s = re.sub(r'[\\/:*?"<>|]', "-", s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return (s[:max_len].rstrip() or "Ohne Titel")
