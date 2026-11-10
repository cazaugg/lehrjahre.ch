import io
import json
import os
import shutil
import sys
import uuid
import zipfile
from datetime import date, datetime, timezone
from backend.app import create_app
from backend.models import (
    db,
    Company,
    User,
    UserRouting,
    UserRelation,
    Project,
    Participation,
    Eval,
    Grades,
    Documents,
    Knowledge,
)
from backend.auth import hash_password
from backend.storage import get_company_dir, save_text_document
from backend.companies import add_company
from backend import tenants


KNOWLEDGE_TOPICS = [
    {
        "title": "Fertigung & Automatisierung",
        "description": "Zerspanung, Schnittdaten, CNC-Programmierung und SPS-Grundlagen.",
        "intro": r"""# Fertigung & Automatisierung

Von den Grundlagen der Zerspanung über die CNC-Programmierung bis zu Sensoren und SPS in der MEM-Produktion.""",
        "pages": [
            (
                "Drehzahl- und Vorschubberechnung",
                "Formeln für Drehzahl n und Vorschub vf",
                r"""# Drehzahl- und Vorschubberechnung

## 1. Drehzahl $n$ berechnen
Die Spindeldrehzahl berechnet sich aus der Schnittgeschwindigkeit $v_c$ (in m/min) und dem Werkzeug- bzw. Werkstückdurchmesser $d$ (in mm):

```
n = (vc * 1000) / (π * d)
```

## 2. Vorschubgeschwindigkeit $v_f$ beim Fräsen
```
vf = n * fz * z
```
- `n`: Drehzahl [1/min]
- `fz`: Vorschub pro Zahn [mm]
- `z`: Zähnezahl des Fräsers

## 3. Richtwerte für HM-Werkzeuge
- **Baustahl (S235JR):** $v_c = 120 - 180\text{ m/min}$
- **Automatenstahl / Vergütungsstahl:** $v_c = 90 - 140\text{ m/min}$
- **Aluminiumlegierungen:** $v_c = 250 - 500\text{ m/min}$""",
            ),
            (
                "Drehen: Werkzeuge und Schnittwerte",
                "Werkzeugauswahl und Richtwerte für das Längs- und Plandrehen",
                r"""# Drehen: Werkzeuge und Schnittwerte

Beim Drehen rotiert das Werkstück, der Drehmeissel führt die Vorschubbewegung aus.

## Werkzeugauswahl
- **Schruppen:** stabiler Meissel, grosser Eckenradius, hoher Vorschub
- **Schlichten:** kleine Schneidenecke, kleiner Vorschub, hohe Schnittgeschwindigkeit
- **Wendeschneidplatten:** ISO-Bezeichnung, z. B. DCMT 070204

## Richtwerte für Baustahl (S235JR)
| Arbeitsgang | $v_c$ [m/min] | $f$ [mm/U] | $a_p$ [mm] |
|---|---|---|---|
| Schruppen | 120–180 | 0,2–0,4 | 2–4 |
| Schlichten | 180–250 | 0,05–0,15 | 0,2–0,5 |

## Sicherheitshinweise
- Späne nie mit der Hand entfernen, sondern mit Haken oder Bürste.
- Werkstück sicher spannen; bei langen Teilen Reitstock verwenden.
- Schutzbrille und eng anliegende Kleidung tragen.""",
            ),
            (
                "Fräsen: Werkzeuge und Schnittwerte",
                "Umfang- und Stirnfräsen, Schnittgeschwindigkeit und Vorschub",
                r"""# Fräsen: Werkzeuge und Schnittwerte

Beim Fräsen rotiert das Werkzeug, das Werkstück wird auf dem Maschinentisch gespannt und verfahren.

## Umfang- und Stirnfräsen
- **Umfangfräsen:** Fräserachse parallel zur Werkstückoberfläche
- **Stirnfräsen:** Fräserachse senkrecht zur Werkstückoberfläche

## Schnittgeschwindigkeit
$v_c = \frac{\pi \cdot d \cdot n}{1000}$ mit $d$ in mm und $n$ in 1/min.

## Richtwerte für HSS-Werkzeuge
| Werkstoff | $v_c$ [m/min] |
|---|---|
| Baustahl | 25–40 |
| Aluminium | 150–300 |
| Edelstahl | 10–20 |

## Vorschub pro Zahn
$v_f = n \cdot f_z \cdot z$

- `f_z`: Vorschub pro Zahn [mm]
- `z`: Zähnezahl des Fräsers

> Bei CNC-Fräsern werden Schnittwerte aus dem Werkzeugkatalog übernommen und bei Bedarf angepasst.""",
            ),
            (
                "Bohren und Gewindeschneiden",
                "Kernlochbohrungen, Schnittwerte und Gewindetabellen",
                r"""# Bohren und Gewindeschneiden

## Bohren
- **Vorschub:** abhängig von Bohrerø und Werkstoff, bei Baustahl ca. 0,05–0,2 mm/U
- **Drehzahl:** $n = \frac{v_c \cdot 1000}{\pi \cdot d}$
- **Kühlung:** Bohröl oder Emulsion verwenden, besonders bei tiefen Bohrungen
- Bohrer regelmässig ausspannen und auf Verschleiss prüfen.

## Gewindeschneiden von Hand
1. Kernloch nach Tabelle bohren (z. B. M8 → 6,8 mm).
2. Gewindeschneider mit Schneidöl ansetzen und rechtwinklig führen.
3. Nach jeder Vierteldrehung zurückdrehen, um den Span zu brechen.

## Richtwerte metrisches Gewinde
| Gewinde | Kernloch [mm] |
|---|---|
| M3 | 2,5 |
| M4 | 3,3 |
| M5 | 4,2 |
| M6 | 5,0 |
| M8 | 6,8 |
| M10 | 8,5 |
| M12 | 10,2 |

> Bei Sacklöchern die Gewindetiefe mindestens 1,5 × Durchmesser wählen.""",
            ),
            (
                "Aufbau und Koordinatensysteme",
                "Maschinenachsen, Nullpunkte und absolute Koordinaten",
                r"""# Aufbau und Koordinatensysteme einer CNC-Maschine

## Hauptbaugruppen
- Maschinenbett und Führungen
- Hauptspindel mit Werkzeugaufnahme
- Achsantriebe und Messsysteme
- Steuerung mit Bedienpanel
- Werkzeugmagazin und Kühlmittelanlage

## Achsen
- **X:** meist quer zur Spindel
- **Y:** senkrecht zu X und Z
- **Z:** parallel zur Spindelachse
- Drehachsen: A, B, C

## Koordinatensysteme
- **Maschinennullpunkt (M):** fester Bezug der Maschine
- **Werkstücknullpunkt (W):** Bezug auf dem Werkstück
- **Referenzpunkt (R):** Bezugspunkt der Messsysteme

## Absolut und inkrementell
- **G90:** absolute Koordinaten
- **G91:** inkrementelle Koordinaten

> Vor dem Programmstart Werkstücknullpunkt und Werkzeuglängen prüfen.""",
            ),
            (
                "G-Code Grundlagen",
                "Wichtige Befehle und Aufbau eines einfachen Programms",
                r"""# G-Code Grundlagen

G-Code beschreibt Bewegungen, Werkzeuge und Zusatzfunktionen einer CNC-Maschine.

## Wichtige Befehle
| Befehl | Bedeutung |
|---|---|
| G0 | Eilgang |
| G1 | Geradeninterpolation mit Vorschub |
| G2 / G3 | Kreisbogen im bzw. gegen den Uhrzeigersinn |
| G54 | Werkstücknullpunkt anwählen |
| G43 | Werkzeuglängenkorrektur |
| M3 / M4 | Spindel rechts / links |
| M8 / M9 | Kühlmittel ein / aus |

## Beispiel
```gcode
G54 G90 G0 X0 Y0
G43 H1 Z50
M3 S1200
G1 Z-2 F200
G1 X40 F400
G0 Z50
M30
```

## Vorgehen
1. Programm und Werkzeuge prüfen.
2. Trockenlauf ohne Werkstück durchführen.
3. Ersten Satz im Einzelsatz starten.
4. Bei Auffälligkeiten sofort stoppen.

> Programme nie ungeprüft starten und Werkzeugkorrekturen immer kontrollieren.""",
            ),
            (
                "Werkzeugkorrekturen",
                "Längen- und Radiuskorrektur sowie Verschleisskontrolle",
                r"""# Werkzeugkorrekturen

Werkzeugkorrekturen gleichen Länge und Radius des Werkzeugs aus.

## Längenkorrektur
- Werkzeug auf Referenzfläche messen oder Antastfunktion nutzen.
- Wert in die Werkzeugtabelle eintragen.
- Mit `G43 H<nummer>` aktivieren.

## Radiuskorrektur
- Fräserradius in der Werkzeugtabelle hinterlegen.
- **G41:** Korrektur links der Kontur
- **G42:** Korrektur rechts der Kontur
- **G40:** Korrektur aus

## Verschleiss
- Standzeit und Schneidenecken überwachen.
- Verschleisswerte in der Steuerung nachführen.
- Bei Bruch oder Ausbrüchen Werkzeug ersetzen.

## Kontrolle
- Erstes Werkstück nach Korrektur prüfen.
- Masse dokumentieren und bei Abweichungen nachkorrigieren.

> Falsche Korrekturen führen zu Ausschuss und können Kollisionen verursachen.""",
            ),
            (
                "Sensoren und SPS-Grundlagen",
                "Sensorarten, PNP/NPN und der SPS-Zyklus",
                r"""# Sensoren und SPS-Grundlagen

Sensoren erfassen Zustände, die SPS verarbeitet Signale und steuert Aktoren.

## Sensorarten
- **Induktiv:** metallische Werkstücke berührungslos erkennen
- **Kapazitiv:** auch nichtmetallische Stoffe erkennen
- **Optisch:** Lichtschranken und Reflexionssensoren
- **Magnetisch:** Kolbenstellung an Pneumatikzylindern

## Anschaltung
- **PNP:** schaltet Plus an den Eingang
- **NPN:** schaltet Minus an den Eingang
- Signalart und Spannung gemäss Schaltplan prüfen.

## SPS-Zyklus
1. Eingänge einlesen
2. Programm abarbeiten
3. Ausgänge schreiben

## Sicherheit
- Sicherheitsfunktionen gehören in Sicherheitskreise, nicht in die Standard-SPS.
- Not-Halt und Schutztüren nach Herstellerangaben verdrahten.
- Änderungen nur nach Freigabe und mit Dokumentation.

> Bei Störungen zuerst Signale am Sensor und am Eingang der SPS prüfen.""",
            ),
        ],
    },
    {
        "title": "Arbeitssicherheit & SUVA-Regeln",
        "description": "PSA, Not-Halt und lebenswichtige Regeln für die MEM-Branche",
        "intro": r"""# Arbeitssicherheit & SUVA-Regeln

Verbindliche Sicherheitsregeln in den Werkstätten und Labors der Vektorwerk Technik AG.""",
        "pages": [
            (
                "Persönliche Schutzausrüstung (PSA)",
                "Pflichtausrüstung, Kontrolle und Pflege der PSA",
                r"""# Persönliche Schutzausrüstung (PSA)

Die PSA schützt vor Verletzungen und ist vor jedem Arbeitsbeginn zu prüfen.

## Pflichtausrüstung in der Werkstatt
- **Sicherheitsschuhe S3:** Zehenschutz, durchtrittsichere Sohle
- **Schutzbrille:** bei Spanabnahme, Bohren, Schleifen und Arbeiten mit Chemikalien
- **Gehörschutz:** ab 85 dB(A), z. B. beim Schleifen oder an Pressen
- **Handschuhe:** nur bei geeigneten Arbeiten; an rotierenden Maschinen verboten
- **Arbeitskleidung:** eng anliegend, keine offenen Ärmel oder Schmuck

## Kontrolle und Pflege
- Beschädigte PSA sofort ersetzen und dem Berufsbildner melden.
- Schutzbrillen mit Wasser und geeignetem Tuch reinigen.
- Gehörschutz regelmässig prüfen und hygienisch lagern.

> Bei Unsicherheiten gilt: lieber einmal mehr nachfragen als ein Risiko eingehen.""",
            ),
            (
                "Not-Halt und Notausstiege",
                "Not-Halt-Taster, Fluchtwege und Verhalten im Notfall",
                r"""# Not-Halt und Notausstiege

Not-Halt-Einrichtungen stoppen gefährliche Bewegungen sofort und dürfen nie umgangen werden.

## Vor der Arbeit
- Lage der Not-Halt-Taster an jeder Maschine kennen.
- Notausstiege und Fluchtwege freihalten.
- Funktionsprüfung bei Schichtbeginn durchführen.

## Im Notfall
1. Not-Halt-Taster drücken.
2. Maschine stillsetzen und Energie abschalten.
3. Verletzte versorgen und Hilfe holen (144).
4. Vorfall dem Berufsbildner melden und dokumentieren.

## Nach dem Not-Halt
- Ursache klären, bevor die Maschine wieder gestartet wird.
- Freigabe durch eine berechtigte Person einholen.
- Defekte oder blockierte Schalter sofort melden.

> Not-Halt ist keine Betriebsbremse: Der Taster darf nicht zum normalen Stoppen verwendet werden.""",
            ),
            (
                "Gefahrstoffe und Kühlschmierstoffe",
                "Sicherheitsdatenblätter, Hautschutz und richtiger Umgang mit KSS",
                r"""# Gefahrstoffe und Kühlschmierstoffe

Chemikalien und Kühlschmierstoffe können Haut, Atemwege und Augen schädigen.

## Sicherheitsdatenblatt (SDB)
- Für jeden Stoff das aktuelle SDB am Arbeitsplatz bereitstellen.
- Gefahrenpiktogramme, H- und P-Sätze beachten.
- Lagerung und Entsorgung gemäss SDB und Betriebsanweisung.

## Umgang mit Kühlschmierstoffen
- Konzentration und pH-Wert regelmässig prüfen.
- Hautkontakt vermeiden; Schutzhandschuhe und Hautschutzplan nutzen.
- Nebel absaugen und Anlagen geschlossen halten.
- Verbrauchte Emulsion nicht in den Abfluss geben.

## Erste Hilfe
- Augen mit Wasser spülen und Arzt aufsuchen.
- Betroffene Hautstellen reinigen und eincremen.
- Vorfälle dokumentieren und Ursache beheben.""",
            ),
            (
                "Brandschutz und Erste Hilfe",
                "Vorbeugung, Verhalten im Brandfall und lebensrettende Massnahmen",
                r"""# Brandschutz und Erste Hilfe

## Vorbeugung
- Brennbare Materialien von heissen Spänen und Schweissfunken fernhalten.
- Feuerlöscher und Löschdecken nur an gekennzeichneten Plätzen lagern.
- Fluchtwege und Notausgänge dauerhaft freihalten.

## Verhalten im Brandfall
1. Alarm auslösen (interner Alarm, Notruf 118).
2. Menschen in Sicherheit bringen.
3. Nur kleine Entstehungsbrände mit geeignetem Löscher bekämpfen.
4. Gebäude über den nächsten Fluchtweg verlassen und Sammelplatz aufsuchen.

## Erste Hilfe
- **Notruf:** 144
- **Verbrennungen:** kühlen, nicht abdecken mit engem Verband, Arzt rufen.
- **Schnittverletzungen:** Wunde abdecken, Blutung stoppen, Hilfe holen.
- **Augen:** mit Wasser spülen und sofort zum Arzt.

> Nach jedem Einsatz Feuerlöscher prüfen und wieder auffüllen lassen.""",
            ),
        ],
    },
    {
        "title": "Werkstoffkunde",
        "description": "Eisen- und Nichteisenmetalle, Kunststoffe und Wärmebehandlung",
        "intro": r"""# Werkstoffkunde

Werkstoffeigenschaften bestimmen die Auswahl, Bearbeitung und Lebensdauer von Bauteilen.""",
        "pages": [
            (
                "Eisenwerkstoffe und Stahlgruppen",
                "Einteilung, Legierungen und typische Einsatzgebiete",
                r"""# Eisenwerkstoffe und Stahlgruppen

Eisenwerkstoffe sind die wichtigsten Konstruktionswerkstoffe in der MEM-Industrie.

## Einteilung
- **Stahl:** Kohlenstoffgehalt bis ca. 2 %
- **Gusseisen:** Kohlenstoffgehalt über ca. 2 %

## Wichtige Stahlgruppen
| Bezeichnung | Eigenschaft | Einsatz |
|---|---|---|
| S235JR | gut schweissbar, zäh | Rahmen, Bleche |
| C45 | vergütbar, mittelfest | Wellen, Bolzen |
| 42CrMo4 | hochfest, zäh | Getriebeteile |
| X5CrNi18-10 | korrosionsbeständig | Lebensmittel, Medizin |

## Legierungselemente
- **Chrom:** Korrosionsbeständigkeit und Härte
- **Nickel:** Zähigkeit und Korrosionsschutz
- **Molybdän:** Warmfestigkeit
- **Mangan:** Festigkeit und Verschleiss

> Die Werkstoffbezeichnung immer mit dem Lieferanten oder der Zeichnung abgleichen.""",
            ),
            (
                "Nichteisenmetalle",
                "Aluminium, Kupfer, Messing und Bronze in der Fertigung",
                r"""# Nichteisenmetalle

Nichteisenmetalle enthalten kein Eisen und werden für leichte, korrosionsbeständige oder gut leitende Bauteile eingesetzt.

## Aluminium
- Dichte ca. 2,7 g/cm³, gute Korrosionsbeständigkeit
- Gut zerspanbar, hohe Schnittgeschwindigkeiten möglich
- Legierungen z. B. AlMg3, AlCuMgPb

## Kupfer und Kupferlegierungen
- **Kupfer:** sehr gute elektrische und thermische Leitfähigkeit
- **Messing:** Kupfer-Zink-Legierung, gut zerspanbar
- **Bronze:** Kupfer-Zinn-Legierung, verschleissfest

## Bearbeitung
- Scharfe Werkzeuge und grosse Spanräume verwenden.
- Auf Sauberkeit achten, damit sich Späne nicht vermischen.
- Aluminium nicht mit Stahlwerkzeugen bearbeiten, um Korrosion zu vermeiden.""",
            ),
            (
                "Kunststoffe in der MEM-Industrie",
                "Thermoplaste, Duroplaste, Elastomere und ihre Zerspanung",
                r"""# Kunststoffe in der MEM-Industrie

Kunststoffe sind leicht, korrosionsbeständig und elektrisch isolierend.

## Gruppen
- **Thermoplaste:** schmelzbar, z. B. PE, PP, PVC, POM, PA
- **Duroplaste:** nach dem Aushärten nicht mehr schmelzbar, z. B. Epoxidharz
- **Elastomere:** elastisch verformbar, z. B. Gummi

## Zerspanung
- Scharfe Werkzeuge mit grossen Spanwinkeln verwenden.
- Drehzahlen hoch, Vorschübe moderat wählen.
- Wärmeentwicklung begrenzen, sonst schmilzt der Werkstoff.
- Späne absaugen; manche Stäube sind gesundheitsgefährdend.

## Werkstoffauswahl
| Eigenschaft | Geeigneter Kunststoff |
|---|---|
| Gleitlager | POM, PA |
| Chemikalienbehälter | PP, PE |
| Elektrische Isolation | PVC, PA |
| Dichtungen | NBR, EPDM |

> Kunststoffe nie mit offener Flamme bearbeiten und Entsorgungshinweise beachten.""",
            ),
            (
                "Wärmebehandlung von Stahl",
                "Härten, Anlassen, Vergüten und Randschichtverfahren",
                r"""# Wärmebehandlung von Stahl

Durch gezieltes Erwärmen und Abkühlen werden Gefüge und Eigenschaften verändert.

## Verfahren
- **Härten:** Erwärmen auf Härtetemperatur, schnelles Abschrecken in Wasser oder Öl
- **Anlassen:** Nach dem Härten wird die Härte zugunsten von Zähigkeit reduziert
- **Vergüten:** Härten und Anlassen kombiniert
- **Normalisieren:** gleichmässiges Abkühlen an Luft für feines Gefüge
- **Einsatzhärten:** Randschicht aufkohlen und härten
- **Nitrieren:** Stickstoffdiffusion für harte, verschleissfeste Randschicht

## Richtwerte
| Stahl | Härtetemperatur | Anlasstemperatur |
|---|---|---|
| C45 | 820–860 °C | 400–600 °C |
| 42CrMo4 | 840–880 °C | 500–650 °C |

## Verzugsarm arbeiten
- Bauteile langsam und gleichmässig erwärmen.
- Abschreckmedium passend zum Werkstoff wählen.
- Nach dem Härten spannungsarm anlassen.

> Wärmebehandlungen nur nach Freigabe und mit dokumentierten Parametern durchführen.""",
            ),
        ],
    },
    {
        "title": "Technisches Zeichnen & Messtechnik",
        "description": "Toleranzen, Oberflächen, Messmittel und Prüfmittelüberwachung",
        "intro": r"""# Technisches Zeichnen & Messtechnik

Zeichnungen und Messungen sind die Grundlage für masshaltige und prüfbare Bauteile.""",
        "pages": [
            (
                "Toleranzen und Passungen",
                "Grundbegriffe, Passungsarten und Berechnung",
                r"""# Toleranzen und Passungen

Toleranzen legen fest, wie stark ein Nennmass abweichen darf. Passungen beschreiben das Zusammenspiel von Bohrung und Welle.

## Grundbegriffe
- **Nennmass:** theoretisches Mass auf der Zeichnung
- **Höchstmass / Mindestmass:** zulässige Grenzen
- **Toleranz:** Differenz zwischen Höchst- und Mindestmass
- **Passung:** Verhältnis von Bohrung und Welle

## Passungsarten
| Passung | Beispiel | Wirkung |
|---|---|---|
| Spielpassung | H7/g6 | Welle lässt sich leicht drehen |
| Übergangspassung | H7/j6 | Zentriert, montierbar |
| Presspassung | H7/p6 | Kraftschlüssig, kein Spiel |

## Berechnung
- Höchstmass = Nennmass + oberes Abmass
- Mindestmass = Nennmass + unteres Abmass
- Toleranz = Höchstmass − Mindestmass

> Toleranzangaben immer mit der Zeichnung und der Passungstabelle prüfen.""",
            ),
            (
                "Oberflächen und Rauheit",
                "Ra, Rz und typische Oberflächenwerte",
                r"""# Oberflächen und Rauheit

Die Oberflächengüte beeinflusst Dichtheit, Verschleiss und Ermüdung.

## Kenngrössen
- **Ra:** arithmetischer Mittenrauwert
- **Rz:** gemittelte Rautiefe
- **Rmax:** maximale Rautiefe

## Zeichnungsangaben
- Das Oberflächenzeichen steht auf der Werkstückoberfläche.
- Zusätzliche Angaben wie Bearbeitungsverfahren oder Rauheitsklasse beachten.
- `Ra 1,6` bedeutet einen Mittenrauwert von 1,6 µm.

## Typische Werte
| Bearbeitung | Ra [µm] |
|---|---|
| Grob drehen | 6,3–12,5 |
| Schlichten | 1,6–3,2 |
| Schleifen | 0,2–0,8 |
| Läppen | 0,05–0,2 |

> Feine Oberflächen erfordern kleine Vorschübe, scharfe Werkzeuge und stabile Aufspannung.""",
            ),
            (
                "Messmittel im Einsatz",
                "Messschieber, Bügelmessschraube und Grenzlehren",
                r"""# Messmittel im Einsatz

## Messschieber
- Messbereich typisch 0–150 mm, Ablesung 0,02 mm
- Für Aussen-, Innen- und Tiefenmasse
- Vor der Messung Nullstellung prüfen

## Bügelmessschraube
- Ablesung 0,01 mm
- Messflächen reinigen, Werkstück nicht verkanten
- Bei grösseren Serien Messkraftbegrenzung nutzen

## Grenzlehren
- Gut- und Ausschussseite prüfen das Einhalten der Toleranz
- Lehre nie mit Gewalt aufsetzen
- Abnutzung und Kalibrierung beachten

## Messtemperatur
- Referenztemperatur: 20 °C
- Werkstück und Messmittel vor der Messung angleichen lassen.

> Messmittel nach Gebrauch reinigen, trocken lagern und bei Auffälligkeiten melden.""",
            ),
            (
                "Prüfmittelüberwachung",
                "Kalibrierung, Kennzeichnung und rückführbare Messungen",
                r"""# Prüfmittelüberwachung

Nur kalibrierte und freigegebene Prüfmittel dürfen für Prüfungen verwendet werden.

## Kennzeichnung
- Prüfmittel tragen eine eindeutige Nummer und eine Kalibrierplakette.
- Status: gültig, gesperrt oder zur Kalibrierung fällig.
- Abgelaufene Prüfmittel sofort aus dem Verkehr ziehen.

## Kalibrierung
- Kalibrierintervalle gemäss Prüfmittelplan einhalten.
- Rückführbarkeit auf nationale Normale sicherstellen.
- Ergebnisse dokumentieren und Grenzwerte prüfen.

## Umgang
- Prüfmittel nicht als Werkzeug oder Hebel verwenden.
- Stösse, Feuchtigkeit und starke Temperaturschwankungen vermeiden.
- Abweichungen melden und betroffene Messungen bewerten.

> Die Prüfmittelüberwachung ist Teil des Qualitätsmanagements und wird bei Audits geprüft.""",
            ),
        ],
    },
]


def save_binary_document(data: bytes, filename: str, company_name: str) -> tuple[str, str]:
    """Save seed-generated binary data under the company's document folder."""
    slug, company_dir = get_company_dir(company_name)
    stored_name = f"{uuid.uuid4().hex[:12]}_{filename}"
    abs_path = os.path.realpath(os.path.join(company_dir, stored_name))
    if not abs_path.startswith(company_dir + os.sep):
        raise ValueError("Invalid destination path")
    with open(abs_path, "wb") as handle:
        handle.write(data)
    return filename, f"{slug}/documents/{stored_name}"


def build_word_preview_docx() -> bytes:
    """Build a small, dependency-free DOCX used to demo the Word preview."""
    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>'''

    root_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>'''

    document_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>'''

    styles = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="22"/></w:rPr></w:rPrDefault>
    <w:pPrDefault><w:pPr><w:spacing w:after="160"/></w:pPr></w:pPrDefault>
  </w:docDefaults>
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:spacing w:before="240" w:after="120"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:sz w:val="36"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:spacing w:before="200" w:after="100"/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/><w:sz w:val="28"/></w:rPr></w:style>
  <w:style w:type="table" w:styleId="TableGrid"><w:name w:val="Table Grid"/><w:tblPr><w:tblBorders>
    <w:top w:val="single" w:sz="4" w:space="0" w:color="auto"/>
    <w:left w:val="single" w:sz="4" w:space="0" w:color="auto"/>
    <w:bottom w:val="single" w:sz="4" w:space="0" w:color="auto"/>
    <w:right w:val="single" w:sz="4" w:space="0" w:color="auto"/>
    <w:insideH w:val="single" w:sz="4" w:space="0" w:color="auto"/>
    <w:insideV w:val="single" w:sz="4" w:space="0" w:color="auto"/>
  </w:tblBorders></w:tblPr></w:style>
</w:styles>'''

    rows = [
        ("Begriff", "Beschreibung"),
        ("Vorschau", "Wird direkt im Browser dargestellt."),
        ("Original", "Kann zusätzlich über «Datei öffnen» heruntergeladen werden."),
    ]
    table_rows = "".join(
        "<w:tr>"
        f'<w:tc><w:tcPr><w:tcW w:w="2800" w:type="dxa"/></w:tcPr><w:p><w:r>{"<w:rPr><w:b/></w:rPr>" if index == 0 else ""}<w:t>{left}</w:t></w:r></w:p></w:tc>'
        f'<w:tc><w:tcPr><w:tcW w:w="5600" w:type="dxa"/></w:tcPr><w:p><w:r><w:t>{right}</w:t></w:r></w:p></w:tc>'
        "</w:tr>"
        for index, (left, right) in enumerate(rows)
    )

    document = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Word-Vorschau Beispiel</w:t></w:r></w:p>
    <w:p><w:r><w:t xml:space="preserve">Dieses Dokument zeigt die </w:t></w:r><w:r><w:rPr><w:b/></w:rPr><w:t>schreibgeschützte Word-Vorschau</w:t></w:r><w:r><w:t xml:space="preserve"> in lehrjahre.ch.</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr><w:r><w:t>Inhalt</w:t></w:r></w:p>
    <w:p><w:r><w:t>• Überschriften und Absätze</w:t></w:r></w:p>
    <w:p><w:r><w:t>• Fett formatierter Text</w:t></w:r></w:p>
    <w:p><w:r><w:t>• Tabellen</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr><w:r><w:t>Beispieltabelle</w:t></w:r></w:p>
    <w:tbl>
      <w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="0" w:type="auto"/></w:tblPr>
      <w:tblGrid><w:gridCol w:w="2800"/><w:gridCol w:w="5600"/></w:tblGrid>
      {table_rows}
    </w:tbl>
    <w:p><w:r><w:t xml:space="preserve">Dieses Beispiel wird durch das Seed-Skript erzeugt und umfasst mehrere Seiten.</w:t></w:r></w:p>
    <w:p><w:r><w:br w:type="page"/></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Seite 2: Hinweise zur Vorschau</w:t></w:r></w:p>
    <w:p><w:r><w:t xml:space="preserve">Word-Dokumente lassen sich direkt im Browser lesen, ohne sie herunterzuladen oder in Word zu öffnen.</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr><w:r><w:t>Was wird dargestellt?</w:t></w:r></w:p>
    <w:p><w:r><w:t>• Überschriften, Absätze und Aufzählungen</w:t></w:r></w:p>
    <w:p><w:r><w:t>• Fett und kursiv formatierter Text</w:t></w:r></w:p>
    <w:p><w:r><w:t>• Tabellen und Seitenumbrüche</w:t></w:r></w:p>
    <w:p><w:r><w:t>• Kopf- und Fusszeilen sowie Bilder</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr><w:r><w:t>Gut zu wissen</w:t></w:r></w:p>
    <w:p><w:r><w:t xml:space="preserve">Die Vorschau ist schreibgeschützt. Das Original bleibt über die Schaltfläche «Datei öffnen» verfügbar.</w:t></w:r></w:p>
    <w:p><w:r><w:t xml:space="preserve">Sehr komplexe Word-Elemente wie Diagramme oder eingebettete Objekte können in der Vorschau abweichen.</w:t></w:r></w:p>
    <w:p><w:r><w:t xml:space="preserve">Diese zweite Seite demonstriert einen expliziten Seitenumbruch im Word-Dokument.</w:t></w:r></w:p>
    <w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr>
  </w:body>
</w:document>'''

    core = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>Word-Vorschau Beispiel</dc:title>
  <dc:creator>lehrjahre.ch</dc:creator>
  <cp:lastModifiedBy>lehrjahre.ch</cp:lastModifiedBy>
</cp:coreProperties>'''

    app_props = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>lehrjahre.ch</Application></Properties>'''

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("word/document.xml", document)
        archive.writestr("word/styles.xml", styles)
        archive.writestr("word/_rels/document.xml.rels", document_rels)
        archive.writestr("docProps/core.xml", core)
        archive.writestr("docProps/app.xml", app_props)
    return buffer.getvalue()


def build_pdf_preview() -> bytes:
    """Build a small, dependency-free two-page PDF used to demo the PDF preview."""

    def escape(value: str) -> str:
        return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    def line(x1, y1, x2, y2, width=0.6):
        return f"{width} w {x1} {y1} m {x2} {y2} l S\n"

    def text(x, y, value, size=12, font="F1"):
        return f"BT /{font} {size} Tf {x} {y} Td ({escape(value)}) Tj ET\n"

    page1 = [text(50, 790, "PDF-Vorschau Beispiel", 24, "F2")]
    page1.append(text(50, 760, "Dieses PDF wird direkt im Browser angezeigt.", 12))
    page1.append(line(50, 745, 545, 745))
    page1.append(text(50, 720, "Inhalt", 16, "F2"))
    for index, item in enumerate(
        [
            "Überschriften und Absätze",
            "Tabellen und Linien",
            "Mehrere Seiten mit Seitenumbruch",
        ]
    ):
        page1.append(text(60, 695 - index * 20, f"- {item}", 12))

    page1.append(text(50, 610, "Beispieltabelle", 16, "F2"))
    table_top = 580
    row_height = 28
    for row in range(4):
        page1.append(line(50, table_top - row * row_height, 545, table_top - row * row_height))
    for column in (50, 200, 545):
        page1.append(line(column, table_top, column, table_top - 3 * row_height))

    rows = [
        ("Begriff", "Beschreibung"),
        ("Vorschau", "Wird direkt im Browser dargestellt."),
        ("Original", "Bleibt über «Datei öffnen» verfügbar."),
    ]
    for index, (left, right) in enumerate(rows):
        y = table_top - index * row_height - 18
        page1.append(text(58, y, left, 11, "F2" if index == 0 else "F1"))
        page1.append(text(208, y, right, 11))
    page1.append(text(50, 520, "Erzeugt durch das Seed-Skript.", 10))
    page1_stream = "".join(page1).encode("latin-1")

    page2 = [text(50, 790, "Seite 2: Hinweise zur Vorschau", 22, "F2")]
    page2.append(text(50, 760, "PDF-Dokumente lassen sich ohne Download im Browser lesen.", 12))
    page2.append(line(50, 745, 545, 745))
    page2.append(text(50, 720, "Was wird dargestellt?", 16, "F2"))
    for index, item in enumerate(
        [
            "Text, Überschriften und Absätze",
            "Tabellen und grafische Linien",
            "Mehrere Seiten und Seitenumbrüche",
        ]
    ):
        page2.append(text(60, 695 - index * 20, f"- {item}", 12))
    page2.append(text(50, 610, "Gut zu wissen", 16, "F2"))
    page2.append(text(50, 585, "Die Vorschau ist schreibgeschützt. Das Original bleibt über", 12))
    page2.append(text(50, 565, "die Schaltfläche «Datei öffnen» verfügbar.", 12))
    page2.append(text(50, 530, "Diese zweite Seite demonstriert einen Seitenumbruch im PDF.", 12))
    page2_stream = "".join(page2).encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R 7 0 R] /Count 2 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
        b"<< /Length %d >>\nstream\n" % len(page1_stream) + page1_stream + b"\nendstream",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 8 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(page2_stream) + page2_stream + b"\nendstream",
    ]

    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += f"{index} 0 obj\n".encode("ascii") + body + b"\nendobj\n"

    xref_offset = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    pdf += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        pdf += f"{offset:010d} 00000 n \n".encode("ascii")
    pdf += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    ).encode("ascii")
    return bytes(pdf)


COMPANY_NAME = "Vektorwerk Technik AG"
COMPANY_DOMAIN = "vektorwerk.ch"
COMPANY_ADDRESS = "Industriestrasse 40, 8404 Winterthur"


def reset_demo_company(company) -> None:
    """Delete a demo company's tenant folder and control-DB registry rows.

    Only meaningful in development (the only place demo seed data lives).
    """
    base_dir = tenants.company_base_dir(company)
    # Drop cached SQLite engines first so no open handle blocks deletion.
    tenants.reset_engine_cache()
    if os.path.isdir(base_dir):
        print(f"Deleting company folder {base_dir}")
        shutil.rmtree(base_dir)
    # Control-DB rows: login routing first, then the company registry.
    deleted_routing = UserRouting.query.filter_by(company_id=company.id).delete()
    print(f"Deleted {deleted_routing} user routing entries.")
    db.session.delete(company)
    db.session.commit()
    print(f"Removed registry entry for {company.name} (@{company.email_domain}).")


def seed_database(force: bool = False):
    app = create_app()
    if not app.config.get("IS_DEV"):
        raise RuntimeError(
            "Seeding demo data is development-only. Set LEHRJAHRE_ENV=development."
        )
    with app.app_context():
        company = Company.query.filter_by(name=COMPANY_NAME).first()
        if force:
            if company is None:
                print(f"No demo company '{COMPANY_NAME}' found; nothing to reset.")
            else:
                reset_demo_company(company)
                company = None
        if not company:
            company = add_company(COMPANY_NAME, COMPANY_DOMAIN, COMPANY_ADDRESS)
        # Provision (idempotent) the company folder: app.db + documents/.
        tenants.create_company_schema(company)
        # All demo data (users incl. credentials, documents, ...) lives in
        # the company database only.
        with tenants.tenant_context(company):
            if User.query.first():
                print(
                    "Database already contains users. Skipping seed "
                    "(reseed with 'npm run seed -- --force')."
                )
                return
            _seed_company_data(company)


def _seed_company_data(company):
    # 1. Trainers (Ausbildner)
    admin = User(
        role="ausbildner",
        name="Thomas",
        surname="Keller",
        company_id=company.id,
        password_hash=hash_password("Lehrjahre2026!"),
        private_address="Bahnhofstrasse 12, 8400 Winterthur",
        private_email="thomas.keller@privat.ch",
        private_phone="+41 79 311 22 33",
        school_address="BBW Berufsbildungsschule Winterthur",
        school_email="sekretariat@bbw.ch",
        school_phone="+41 52 267 81 11",
        company_address="Industriestrasse 40, 8404 Winterthur",
        company_email="thomas.keller@vektorwerk.ch",
        company_phone="+41 52 500 10 01",
        job_title="Berufsbildner",
    )

    # Sandra is the company administrator: user/relationship management is
    # exclusively hers; visibility rules stay the same as a supervisor's.
    hr_user = User(
        role="admin",
        name="Sandra",
        surname="Meier",
        company_id=company.id,
        password_hash=hash_password("Lehrjahre2026!"),
        private_address="Rosenweg 5, 8000 Zürich",
        private_email="s.meier@privat.ch",
        private_phone="+41 78 400 11 22",
        school_address="",
        school_email="",
        school_phone="",
        company_address="Industriestrasse 40, 8404 Winterthur",
        company_email="sandra.meier@vektorwerk.ch",
        company_phone="+41 52 500 10 02",
        job_title="Administrator",
    )

    fach_user = User(
        role="ausbildner",
        name="Marco",
        surname="Brunner",
        company_id=company.id,
        password_hash=hash_password("Lehrjahre2026!"),
        private_address="Lindenstrasse 8, 8400 Winterthur",
        private_email="m.brunner@privat.ch",
        private_phone="+41 76 555 44 33",
        school_address="AZW Ausbildungszentrum Winterthur",
        school_email="info@azw.ch",
        school_phone="+41 52 260 11 11",
        company_address="Werkhalle 2, Industriestrasse 40, 8404 Winterthur",
        company_email="marco.brunner@vektorwerk.ch",
        company_phone="+41 52 500 10 15",
        job_title="Fachvorgesetzter",
    )

    # 2. Apprentices (Lernende) – three Konstrukteur/innen EFZ with
    # staggered Lehrjahre (1st, 2nd and 3rd year of apprenticeship).
    student1 = User(
        role="lernender",
        name="Lea",
        surname="Buchmann",
        company_id=company.id,
        password_hash=hash_password("Lehrjahre2026!"),
        private_address="Wiesenstrasse 19, 8400 Winterthur",
        private_email="lea.buchmann@bluewin.ch",
        private_phone="+41 79 812 34 56",
        school_address="BBW Winterthur, Pionierstrasse 28, 8400 Winterthur",
        school_email="lea.buchmann@stud.bbw.ch",
        school_phone="+41 52 267 81 11",
        company_address="Industriestrasse 40, 8404 Winterthur",
        company_email="lea.buchmann@vektorwerk.ch",
        company_phone="+41 52 500 10 51",
        start_date=date(2026, 8, 10),
        end_date=date(2030, 7, 31),
        job_title="Konstrukteurin / Konstrukteur EFZ",
    )

    student2 = User(
        role="lernender",
        name="Sven",
        surname="Hug",
        company_id=company.id,
        password_hash=hash_password("Lehrjahre2026!"),
        private_address="Seestrasse 44, 8405 Winterthur",
        private_email="sven.hug@gmail.com",
        private_phone="+41 77 901 23 45",
        school_address="BBW Winterthur, Pionierstrasse 28, 8400 Winterthur",
        school_email="sven.hug@stud.bbw.ch",
        school_phone="+41 52 267 81 11",
        company_address="Industriestrasse 40, 8404 Winterthur",
        company_email="sven.hug@vektorwerk.ch",
        company_phone="+41 52 500 10 52",
        start_date=date(2025, 8, 11),
        end_date=date(2029, 7, 31),
        job_title="Konstrukteurin / Konstrukteur EFZ",
    )

    student3 = User(
        role="lernender",
        name="Livia",
        surname="Kälin",
        company_id=company.id,
        password_hash=hash_password("Lehrjahre2026!"),
        private_address="Römerhofstrasse 9, 8406 Winterthur",
        private_email="livia.kaelin@hotmail.com",
        private_phone="+41 76 710 88 42",
        school_address="BBW Winterthur, Pionierstrasse 28, 8400 Winterthur",
        school_email="livia.kaelin@stud.bbw.ch",
        school_phone="+41 52 267 81 11",
        company_address="Industriestrasse 40, 8404 Winterthur",
        company_email="livia.kaelin@vektorwerk.ch",
        company_phone="+41 52 500 10 53",
        start_date=date(2024, 8, 12),
        end_date=date(2028, 7, 31),
        job_title="Konstrukteurin / Konstrukteur EFZ",
    )

    db.session.add_all([admin, hr_user, fach_user, student1, student2, student3])
    db.session.flush()

    # Register the login routing rows in the control database; the full user
    # records live in the company database only.
    db.session.add_all(
        [
            UserRouting(
                id=user.id,
                company_id=company.id,
                company_email=user.company_email,
                private_email=user.private_email or "",
                school_email=user.school_email or "",
            )
            for user in (admin, hr_user, fach_user, student1, student2, student3)
        ]
    )

    # 3. User Relations
    db.session.add_all(
        [
            UserRelation(supervisor=admin.id, student=student1.id),
            UserRelation(supervisor=fach_user.id, student=student1.id),
            UserRelation(supervisor=hr_user.id, student=student1.id),
            UserRelation(supervisor=admin.id, student=student2.id),
            UserRelation(supervisor=fach_user.id, student=student2.id),
            UserRelation(supervisor=hr_user.id, student=student2.id),
            UserRelation(supervisor=admin.id, student=student3.id),
            UserRelation(supervisor=fach_user.id, student=student3.id),
            UserRelation(supervisor=hr_user.id, student=student3.id),
        ]
    )

    # 4. Projects aligned with the Konstrukteur/in EFZ Lehrplan
    # (data/lehrplan/lehrplan_KR.json). Goals are plain Lernziel IDs
    # (LZ_xxxx) as produced by the Lernziel-Picker, so the frontend can
    # resolve them via /api/lehrplan/lz/<id> against the official plan.
    #
    # Einfach (MIT Teilaufgaben): laufendes Projekt für Lea (1. Lehrjahr) –
    # HK 3333 c.01. This is the only demo project with subtasks; all other
    # projects carry their full working steps inside the description.
    p_skizzen = Project(
        parent_project=None,
        title="Normteile skizzieren und Zeichnungen lesen",
        description=(
            "Einstiegsprojekt aus HK 3333 c.01 (Produkte skizzieren). "
            "Ausgangslage: Auf dem Werkbankauftrag liegt die Werkstattzeichnung einer "
            "Grundplatte aus S235JR samt passenden Normteilen.\n\n"
            "**Arbeitsschritte im Überblick:**\n"
            "1. Werkstattzeichnung interpretieren: Ansichten, Schnitte, Werkstoff- und "
            "Oberflächenangaben herauslesen.\n"
            "2. Haupt- und Nebenansichten der Grundplatte als freihändige Skizze in korrekter "
            "Projektionsrichtung anordnen.\n"
            "3. Hauptabmassungen eintragen, Passungen und Form- und Lagetoleranzen gemäss "
            "Vorgabe ergänzen.\n\n"
            "**Abgabe:** Die Skizzen werden nach jeder Aufgabe besprochen und signiert; die "
            "Arbeitssicherheit (LK MEM 11 09) gilt über das ganze Projekt."
        ),
        author=fach_user.id,
        goals=json.dumps(
            ["LZ_7944", "LZ_9011", "LZ_9013"],
            ensure_ascii=False,
        ),
        assigned_students=json.dumps([student1.id]),
        start_date=date(2026, 10, 26),
        due_date=date(2026, 12, 11),
        is_published=True,
        planning_released=True,
        is_completed=False,
    )
    db.session.add(p_skizzen)
    db.session.flush()

    # Mittel (ohne Teilaufgaben): laufendes Projekt für Sven (2. Lehrjahr) –
    # HK 3333 c.02 + c.03; der komplette Arbeitsauftrag steckt in der Beschreibung.
    p_cad = Project(
        parent_project=None,
        title="Haltebolzen mit CAD modellieren und Fertigungsunterlagen erstellen",
        description=(
            "Mittleres Projekt aus den HK 3333 c.02 (CAD-Modellieren) und 3333 c.03 "
            "(Fertigungsunterlagen) – ein durchgehender Auftrag, der ohne vordefinierte "
            "Teilaufgaben eigenständig geplant und abgewickelt wird.\n\n"
            "**Ausgangslage:** Ein Haltebolzen der LED-Beleuchtungseinheit ist als "
            "Ersatzteil nachzuzeichnen. Der Instandhaltungsauftrag verlangt das Modell aus der "
            "parametrisierten CAD-Bibliothek, damit spätere Längen- und Gewindevarianten "
            "ohne neues Modellierarbeiten möglich sind.\n\n"
            "**Vorgehen und Ausführung:**\n"
            "1. *Parametrisiertes 3D-Modell:* Haltebolzen als Volumenmodell aufbauen, "
            "Teil-Länge und Gewinde über eine parametrisierte Tabelle steuern und die "
            "Auswirkung von Werteänderungen auf die Varianten prüfen. **(erledigt)**\n"
            "2. *Passungen und Toleranzen:* Lagersitz und Dichtfläche mit Passung H7/g6 "
            "versehen, Form- und Lagetoleranzen am Modell ergänzen und die Bemassung "
            "fertigungs- und prüfgerecht anordnen. **(erledigt)**\n"
            "3. *Stückliste und Teiledaten:* Teiledaten ermitteln und klassifizieren, dann "
            "die Stückliste mit Positionsnummern, Menge, Einheit, Artikelnummer und "
            "Merkmalen erstellen. **(aktuell offen)**\n\n"
            "**Abgabe:** CAD-Modell samt parametrisierter Tabelle, prüfgerechte Bemassung "
            "und fertigungsfertige Stückliste als eine Unterlagenserie. Ein "
            "Zwischenrückgespräch zu den Passungen hat bereits stattgefunden."
        ),
        author=fach_user.id,
        goals=json.dumps(
            ["LZ_9626", "LZ_9627", "LZ_9544"],
            ensure_ascii=False,
        ),
        assigned_students=json.dumps([student2.id]),
        start_date=date(2026, 9, 7),
        due_date=date(2026, 11, 27),
        is_published=True,
        planning_released=True,
        is_completed=False,
    )
    db.session.add(p_cad)
    db.session.flush()

    # Anspruchsvoll (ohne Teilaufgaben): abgeschlossenes Projekt für Livia
    # (3. Lehrjahr) – HK 3333 b.01 + b.02 + d.04 (Planungsinstrumente);
    # die drei Phasen sind vollständig in der Beschreibung dokumentiert.
    p_haube = Project(
        parent_project=None,
        title="Getriebehaube fertigungs- und werkstoffgerecht konstruieren",
        description=(
            "Anspruchsvolles Projekt aus den HK 3333 b.01 (fertigungsgerechte "
            "Konstruktionen) und 3333 b.02 (spezifische Funktionen) – drei Phasen, "
            "eigenständig geplant, umgesetzt und abgeschlossen.\n\n"
            "**Ausgangslage:** Für das Getriebeprüfaggregat im Lehratelier fehlt ein "
            "Deckelbauteil; es ist eine fertigungsgerechte Getriebehaube zu entwerfen, "
            "die eine Dichtfläche, Lagersitze und einen einfachen Montagezugang enthält.\n\n"
            "**Phase 1 – Anforderungen und Grobentwurf:** Anforderungsliste zur Haube "
            "erfasst, funktionelle Einflussgrössen (Schmierung, Abdichtung, "
            "Wärmeabfuhr, Montagezugang) beurteilt und einen fachgerechten Grobentwurf "
            "mit erster Kostenabschätzung erstellt. **(erledigt)**\n\n"
            "**Phase 2 – CAD-Feinentwurf:** Feinentwurf mit CAD ausgearbeitet, die "
            "gebräuchlichsten Maschinenelemente (Deckel, Lager, Dichtungen, "
            "Befestigung) funktional ausgelegt und die Lagerdichtung vorgezeichnet. "
            "**(erledigt)**\n\n"
            "**Phase 3 – Unterlagen und Bewertung:** Kostenarten der Fertigung bewertet, "
            "Beschichtungsverfahren (Lackierung, Galvanisierung, Eloxal) verglichen und "
            "die finalen Fertigungsunterlagen samt Kontrollliste erstellt. "
            "**(erledigt)**\n\n"
            "**Projektsteuerung:** Der ganze Ablauf wurde mit einem Meilensteinplan und "
            "einer Kontrollliste als Planungsinstrumente begleitet."
        ),
        author=admin.id,
        goals=json.dumps(
            ["LZ_9332", "LZ_9333", "LZ_11278", "LZ_9302"],
            ensure_ascii=False,
        ),
        assigned_students=json.dumps([student3.id]),
        start_date=date(2026, 5, 4),
        due_date=date(2026, 6, 26),
        is_published=True,
        planning_released=True,
        is_completed=True,
        global_eval_text="Livia hat die Getriebehaube fertigungsgerecht ausgearbeitet und die Varianten inklusive Kostenüberblick begründet dokumentiert.",
    )
    db.session.add(p_haube)
    db.session.flush()

    # Entwurf (ohne Teilaufgaben): noch nicht freigegebenes Projekt für alle
    # drei – HK 3333 a.01 + a.03; die Arbeitsphasen stehen in der Beschreibung.
    p_halter = Project(
        parent_project=None,
        title="Messgerätehalter: von der Anforderungsliste zum Grobentwurf",
        description=(
            "Gemeinsames Projekt der drei Konstrukteur/innen aus den HK 3333 a.01 "
            "(Entwicklungen planen) und 3333 a.03 (Grobentwürfe) – noch nicht "
            "veröffentlicht, deshalb erscheint es vorerst ohne Teilaufgaben.\n\n"
            "**Ausgangslage:** Im Messraum der Vektorwerk Werkstatt liegen Messschieber "
            "und Bügelmessschrauben lose auf der Ablage. Ein Halter für zwei Baugrössen "
            "am Werkzeugkarussellwagen soll Ablage- und Wechselzeit reduzieren.\n\n"
            "**Arbeitsschritte im Überblick:**\n"
            "1. Arbeitsauftrag interpretieren, Umgebung und Benutzersituation erfassen "
            "und daraus eine Anforderungsliste (funktional und quantitativ) ableiten.\n"
            "2. Zwei Grobentwurfsvarianten erarbeiten, die funktionellen Einflussgrössen "
            "beurteilen und je Variante die Herstellkosten abschätzen.\n"
            "3. Die Varianten mit einer Vergleichsmatrix gegenüberstellen und die "
            "Entscheidung dokumentiert begründen.\n\n"
            "**Termin:** Bearbeitung im Januar/Februar 2027 nach Rückkehr vom üK; die "
            "Freigabe der Planung erfolgt in der ersten Konstruktionsbesprechung."
        ),
        author=admin.id,
        goals=json.dumps(
            ["LZ_9003", "LZ_9345"],
            ensure_ascii=False,
        ),
        assigned_students=json.dumps([student1.id, student2.id, student3.id]),
        start_date=date(2027, 1, 11),
        due_date=date(2027, 2, 26),
        is_published=False,
        planning_released=False,
        is_completed=False,
    )
    db.session.add(p_halter)
    db.session.flush()

    task_skizzen_ansichten = Project(
        parent_project=p_skizzen.id,
        title="Aufgabe 1: Zeichnung interpretieren und Ansichten skizzieren",
        description="Werkstattzeichnung einer Grundplatte lesen und Haupt- und Nebenansichten als Skizze anordnen.",
        author=fach_user.id,
        goals=json.dumps(["LZ_9471", "LZ_717"], ensure_ascii=False),
        assigned_students=json.dumps([student1.id]),
        start_date=date(2026, 10, 26),
        due_date=date(2026, 11, 6),
        is_published=True,
        planning_released=True,
        is_completed=True,
    )
    task_skizzen_bemassen = Project(
        parent_project=p_skizzen.id,
        title="Aufgabe 2: Skizzen bemassen und Toleranzen ergänzen",
        description="Skizzen bemassen, Passungen und Form- und Lagetoleranzen gemäss Vorgabe ergänzen.",
        author=fach_user.id,
        goals=json.dumps(["LZ_9019", "LZ_9000"], ensure_ascii=False),
        assigned_students=json.dumps([student1.id]),
        start_date=date(2026, 11, 9),
        due_date=date(2026, 12, 11),
        is_published=True,
        planning_released=True,
        is_completed=False,
    )

    db.session.add_all([task_skizzen_ansichten, task_skizzen_bemassen])
    db.session.flush()

    # 5. Participations (/api/implementation). p_skizzen's entries stay on its
    # two subtasks; the subtask-free projects get a single project-level
    # participation each (the UI targets "Projektabgabe" in that case).
    part_skizzen_ansichten = Participation(
        supervisor=fach_user.id,
        student=student1.id,
        project=task_skizzen_ansichten.id,
        title=task_skizzen_ansichten.title,
        text="Werkstattzeichnung der Grundplatte gelesen und drei Ansichten freihändig skizziert. Projektionsrichtungen korrekt gewählt.",
        is_done=True,
    )
    part_skizzen_bemassen = Participation(
        supervisor=fach_user.id,
        student=student1.id,
        project=task_skizzen_bemassen.id,
        title=task_skizzen_bemassen.title,
        text="Hauptabmessungen eingetragen; Passungen besprochen. Ergänzung der Toleranzen folgt nach dem nächsten Gespräch.",
        is_done=False,
    )
    part_cad = Participation(
        supervisor=fach_user.id,
        student=student2.id,
        project=p_cad.id,
        title=p_cad.title,
        text="3D-Modell mit parametrisierter Tabelle erzeugt und die Auswirkung von Werteänderungen auf die Varianten geprüft. Anschliessend Passungen H7/g6 und FL-Toleranzen für Lagersitz und Dichtfläche ergänzt. Stückliste und Teiledaten zur Freigabe noch ausstehend.",
        is_done=False,
    )
    part_haube = Participation(
        supervisor=admin.id,
        student=student3.id,
        project=p_haube.id,
        title=p_haube.title,
        text="Alle drei Phasen abgeschlossen: Grobentwurf mit Kostenüberblick, CAD-Feinentwurf mit Deckel und Befestigung als Maschinenelemente und die finalisierten Fertigungsunterlagen inklusive Beschichtungsvergleich (Lackierung, Galvanisierung, Eloxal).",
        is_done=True,
    )
    db.session.add_all(
        [
            part_skizzen_ansichten,
            part_skizzen_bemassen,
            part_cad,
            part_haube,
        ]
    )
    db.session.flush()

    # 6. Evaluations (/api/evaluation)
    eval_skizzen_task = Eval(
        project=task_skizzen_ansichten.id,
        participation=part_skizzen_ansichten.id,
        target_type="task",
        goal=task_skizzen_ansichten.title,
        student=student1.id,
        supervisor=fach_user.id,
        planning_text="Entwurf vor der Endansicht mit der Berufsbildnerin besprechen.",
        eval_text="Saubere Ansichten mit konsequenter Projektionsrichtung. Lernziel teilweise erreicht (B); Bemassung noch ergänzen.",
        score_type="grade",
        score_value=4.8,
        is_released=True,
        eval_released=True,
    )
    eval_skizzen_goal = Eval(
        project=p_skizzen.id,
        target_type="goal",
        goal="LZ_7944",
        student=student1.id,
        supervisor=fach_user.id,
        eval_text="Schutzbrille konsequent getragen und Zeichnungsunterlagen ordentlich aufbewahrt.",
        is_released=True,
        eval_released=True,
    )
    eval_skizzen_project = Eval(
        project=p_skizzen.id,
        target_type="project",
        goal=p_skizzen.title,
        student=student1.id,
        supervisor=fach_user.id,
        eval_text="Lea arbeitet sorgfältig. Die freie Bemassung ist noch verbesserbar, die Ansichten sind projektionsgerecht.",
        score_type=None,
        score_value=None,
        is_released=False,
        eval_released=False,
    )
    eval_cad_project = Eval(
        project=p_cad.id,
        target_type="project",
        goal=p_cad.title,
        student=student2.id,
        supervisor=fach_user.id,
        eval_text="Zwischenstand: sorgfältig strukturiertes Modell, Parameter sauber verknüpft, Passungen und FL-Toleranzen fertigungs- und prüfgerecht (Ziel A). Die Stückliste inklusive Teiledaten ist noch offen.",
        score_type="grade",
        score_value=5.1,
        is_released=True,
        eval_released=True,
    )
    eval_haube_project = Eval(
        project=p_haube.id,
        target_type="project",
        goal=p_haube.title,
        student=student3.id,
        supervisor=admin.id,
        eval_text="Livia hat das anspruchsvolle Projekt vollumfänglich und selbstständig abgeschlossen. Feinentwurf und Maschinenelemente souverän beurteilt (Ziel A); Varianten, Kostenüberblick und Beschichtungsvergleich sind begründet dokumentiert.",
        score_type="grade",
        score_value=5.4,
        is_released=True,
        eval_released=True,
    )
    eval_haube_goal = Eval(
        project=p_haube.id,
        target_type="goal",
        goal="LZ_9302",
        student=student3.id,
        supervisor=admin.id,
        eval_text="Planungsinstrumente (Meilensteinplan und Kontrollliste) zuverlässig und proaktiv eingesetzt.",
        is_released=True,
        eval_released=True,
    )
    db.session.add_all(
        [
            eval_skizzen_task,
            eval_skizzen_goal,
            eval_skizzen_project,
            eval_cad_project,
            eval_haube_project,
            eval_haube_goal,
        ]
    )
    db.session.flush()

    # 6b. Beispiel-Auswertungsdatei (PDF) an der freigegebenen CAD-Auswertung
    eval_pdf_fn, eval_pdf_path = save_binary_document(
        build_pdf_preview(), "Projektauswertung_CAD_Varianten.pdf", company.name
    )
    doc_eval_pdf = Documents(
        name=f"Projektauswertung: {p_cad.title}",
        description="Beigefügte Auswertungsdatei (PDF / Word)",
        filename=eval_pdf_fn,
        path=eval_pdf_path,
        type="auswertung",
        owner=fach_user.id,
        author=fach_user.id,
        is_template=False,
        updated_date=datetime.now(timezone.utc),
        is_done=True,
    )
    db.session.add(doc_eval_pdf)
    db.session.flush()
    eval_cad_project.document_id = doc_eval_pdf.id

    # 7. Grades (/api/grades)
    db.session.add_all(
        [
            Grades(
                student=student1.id,
                subject="Mathematik",
                date=date(2026, 9, 24),
                grade=4.8,
                title="Prozent-, Dreisatz- und Flächenberechnung",
                comment="Rechenwege nachvollzierbar; Einheiten sauber umgerechnet.",
            ),
            Grades(
                student=student1.id,
                subject="Technisches Zeichnen",
                date=date(2026, 11, 4),
                grade=5.1,
                title="Ansichten, Projektionsrichtung und Bemassung",
                comment="Ansichten normgerecht; bei Hilfslinien noch mehr Ordnung.",
            ),
            Grades(
                student=student1.id,
                subject="Allgemeinbildung (ABU)",
                date=date(2026, 10, 8),
                grade=5.0,
                title="Arbeitswelt & Lehrvertrag",
                comment="",
            ),
            Grades(
                student=student2.id,
                subject="Konstruktionstechnik",
                date=date(2026, 6, 15),
                grade=5.2,
                title="Maschinenelemente: Gewinde, Lager, Dichtungen",
                comment="Funktion und Einsatz sicher erklärt.",
            ),
            Grades(
                student=student2.id,
                subject="CAD / Fertigungsunterlagen",
                date=date(2026, 6, 18),
                grade=5.3,
                title="Parametrisierte Bauteile und Stückliste",
                comment="Teiledaten vollständig; Positionsnummern normgerecht.",
            ),
            Grades(
                student=student2.id,
                subject="Allgemeinbildung (ABU)",
                date=date(2026, 1, 30),
                grade=5.2,
                title="Präsentation Lehrbetrieb",
                comment="Klar strukturierte Präsentation mit guten Fachbezügen.",
            ),
            Grades(
                student=student3.id,
                subject="Konstruktionstechnik",
                date=date(2026, 6, 22),
                grade=5.4,
                title="Getriebenormelemente und Befestigung",
                comment="Varianten mit Kostenargumentation begründet.",
            ),
            Grades(
                student=student3.id,
                subject="Technische Mechanik",
                date=date(2026, 5, 11),
                grade=5.1,
                title="Belastungsarten und einfachere Dimensionierung",
                comment="",
            ),
            Grades(
                student=student3.id,
                subject="Werkstofftechnik",
                date=date(2026, 3, 17),
                grade=4.9,
                title="Oberflächenbehandlung und Korrosionsschutz",
                comment="Beschichtungsverfahren korrekt zugeordnet.",
            ),
        ]
    )

    # 8. Documents & Lernjournal & Templates
    journal_md = (
        "# Lernjournal KW 45 – Normteile skizzieren\n\n"
        "## Ausgeführte Arbeiten\n"
        "- Werkstattzeichnung der Grundplatte interpretiert\n"
        "- Drei Ansichten der Grundplatte freihändig skizziert\n"
        "- Werkstoff und Oberflächenangaben aus der Zeichnung abgeleitet\n\n"
        "## Erkenntnisse & Reflexion\n"
        "Damit die Ansichten projektionsgerecht sind, habe ich zuerst die Blickrichtung festgelegt und die Massstabangaben der Hauptansicht übernommen. Beim nächsten Mal plane ich mehr Zeit für die Kontrollskizze ein.\n"
    )
    j_fn, j_path = save_text_document(
        journal_md, "Lernjournal_KW45", company.name
    )
    doc_journal = Documents(
        name="Lernjournal KW 45 – Normteile skizzieren",
        description="Wochenreflexion Technisches Zeichnen",
        filename=j_fn,
        path=j_path,
        type="lernjournal",
        owner=student1.id,
        author=student1.id,
        is_template=False,
        updated_date=datetime.now(timezone.utc),
        is_done=True,
        feedback="Gute Reflexion zur Projektionsrichtung. Bitte beim nächsten Mal auch die gewählten Werkzeuge (Skizzenpapier, Bleistifte) und die Lernzeit festhalten.",
        feedback_author=admin.id,
    )

    gespraech_md = (
        "# Probezeitgespräch & Bildungsbericht 1. Semester\n\n"
        "**Lernende:** Lea Buchmann  \n"
        "**Berufsbildner:** Thomas Keller  \n"
        "**Beruf:** Konstrukteur/in EFZ  \n"
        "**Datum:** 10.11.2026\n\n"
        "## 1. Fachkompetenz\n"
        "Lea liest Werkstattzeichnungen sicher und skizziert Normteile mit korrekter Projektionsrichtung. Die Bemassung ist noch verbesserbar.\n\n"
        "## 2. Methoden- & Sozialkompetenz\n"
        "Freundliches Auftreten im Team, pünktlich und zuverlässig. Lerndokumentation wird regelmässig geführt.\n\n"
        "## 3. Vereinbarte Ziele für das nächste Semester\n"
        "- Selbstständige Vorbereitung der CAD-Grundübungen\n"
        "- Notenschnitt in der Berufsfachschule über 5.0 halten\n"
    )
    g_fn, g_path = save_text_document(
        gespraech_md, "Probezeitgespraech_Lea_Buchmann", company.name
    )
    doc_gespraech = Documents(
        name="Probezeitgespräch (1. Lehrjahr)",
        description="Abgeschlossenes Probezeitgespräch mit Berufsbildner",
        filename=g_fn,
        path=g_path,
        type="ausbildungsgespraech",
        owner=student1.id,
        author=admin.id,
        is_template=False,
        updated_date=datetime.now(timezone.utc),
        is_done=True,
    )

    # Seed templates for the new "Vorlagen" section. Structure follows the
    # SBFI Bildungsplan 46427 (Automatikmonteur/in EFZ, ab Lehrbeginn 2026):
    # Lerndokumentation (Art. 12), Bildungsbericht (Art. 13) und die
    # Qualifikationsbereiche Planen / Durchfuehren / Auswerten (Art. 18 QV).
    seed_templates = [
        {
            "name": "Vorlage Bildungsbericht",
            "description": "Semesterweiser Bildungsbericht mit Rückmeldungen aus allen Lernorten und vereinbarten Massnahmen (Art. 13 BiVo)",
            "filename": "Vorlage_Bildungsbericht",
            "type": "ausbildungsgespraech",
            "content": (
                "# Bildungsbericht\n\n"
                "**Lernende/r:**  \n"
                "**Berufsbildner/in:**  \n"
                "**Semester:**  \n"
                "**Datum:**  \n\n"
                "## 1. Rückmeldungen aus den Lernorten\n"
                "### 1.1 Ausbildung im Lehrbetrieb\n"
                "- Verlauf und ausgeführte Arbeiten:  \n"
                "- Was ist besonders gut gelungen?  \n"
                "- Wo gab es Herausforderungen?  \n\n"
                "### 1.2 Berufsfachschule\n"
                "- Leistungen / Noten:  \n"
                "- Absenzen / Bemerkungen:  \n\n"
                "### 1.3 Überbetriebliche Kurse (üK)\n"
                "- Kurs(e) / Kompetenznachweise:  \n"
                "- Verlauf und Bemerkungen:  \n\n"
                "## 2. Entwicklungsstand in den Tätigkeitsbereichen\n"
                "| Tätigkeitsbereich | Entwicklungsstand | Bemerkungen |\n"
                "| --- | --- | --- |\n"
                "|  | erreicht / in Entwicklung / nicht erreicht |  |\n"
                "|  | erreicht / in Entwicklung / nicht erreicht |  |\n\n"
                "## 3. Vereinbarte Massnahmen\n"
                "| Massnahme | Ziel | Frist | Verantwortlich |\n"
                "| --- | --- | --- | --- |\n"
                "|  |  |  |  |\n\n"
                "### Überprüfung der Massnahmen aus dem vorigen Bericht\n"
                "- Umsetzung und Wirkung:  \n\n"
                "## 4. Beschluss\n"
                "Der Bildungsbericht wurde mit der lernenden Person besprochen.\n\n"
                "| Lernende/r | Berufsbildner/in | Datum |\n"
                "| --- | --- | --- |\n"
                "|  |  |  |"
            ),
        },
        {
            "name": "Vorlage Lernjournal-Eintrag",
            "description": "Laufende Lerndokumentation mit ausgeführten Arbeiten, Sicherheitsthemen und Reflexion (Art. 12 BiVo)",
            "filename": "Vorlage_Lernjournal",
            "type": "lernjournal",
            "content": (
                "# Lernjournal-Eintrag\n\n"
                "**Datum:**  \n"
                "**Dauer:**  \n"
                "**Arbeitsort / Auftraggeber:**  \n\n"
                "## 1. Ausgeführte Arbeiten\n"
                "1.  \n"
                "2.  \n\n"
                "## 2. Eingesetzte Werkzeuge, Maschinen und Hilfsmittel\n"
                "-  \n\n"
                "## 3. Sicherheit und Prävention\n"
                "- Angewandte Schutzmassnahmen:  \n"
                "- Präventionsthema des Tages:  \n"
                "- Beobachtungen / Auffälligkeiten:  \n\n"
                "## 4. Reflexion\n"
                "- Was ist gut gelungen?  \n"
                "- Was war herausfordernd?  \n"
                "- Was nehme ich mir vor?  \n\n"
                "## 5. Besprechung mit der Berufsbildnerin / dem Berufsbildner\n"
                "- [ ] Eintrag besprochen und kontrolliert\n"
                "- Signum / Datum:  "
            ),
        },
        {
            "name": "Vorlage Projektplanung",
            "description": "Auftragsplanung mit Anforderungen, Zeitplan, Ressourcen und Freigabevermerk",
            "filename": "Vorlage_Projektplanung",
            "type": "projekt",
            "content": (
                "# Projektplanung\n\n"
                "**Projekts-Titel:**  \n"
                "**Kunde / Auslöser des Auftrags:**  \n"
                "**Projektzeitraum:**  \n"
                "**Team / Beteiligte:**  \n\n"
                "## 1. Auftrag und Anforderungen\n"
                "### 1.1 Ausgangslage\n"
                "Beschreibung der Ausgangslage und des Auftrags...  \n\n"
                "### 1.2 Anforderungsliste\n"
                "| Nr. | Anforderung | Priorität | Bemerkungen |\n"
                "| --- | --- | --- | --- |\n"
                "| 1 |  |  |  |\n\n"
                "### 1.3 Rahmenbedingungen und Abgrenzungen\n"
                "-  \n\n"
                "## 2. Zeitplan\n"
                "| Nr. | Arbeitsphase | Start | Ende | Status (geplant) |\n"
                "| --- | --- | --- | --- | --- |\n"
                "| 1 |  |  |  |  |\n\n"
                "**Meilensteine:**  \n"
                "-  \n\n"
                "## 3. Ressourcen und Betriebsmittel\n"
                "- Materialien (Zukauf / Eigenfertigung):  \n"
                "- Maschinen und Werkzeuge:  \n"
                "- Mitarbeitende / Fremdunternehmen:  \n"
                "- Rahmenbudget (optional):  \n\n"
                "## 4. Risiken (optional)\n"
                "| Risiko | Massnahme zur Gegenmassnahme |\n"
                "| --- | --- |\n"
                "|  |  |\n\n"
                "## 5. Freigabe der Planung\n"
                "- [ ] Planung wurde von Auftraggeber/in bzw. Vorgesetzte/n geprüft und freigegeben\n"
                "- Bemerkungen:  \n\n"
                "| Freigabe durch | Datum |\n"
                "| --- | --- |\n"
                "|  |  |"
            ),
        },
        {
            "name": "Vorlage Projektdurchführung",
            "description": "Laufende Fortschrittsberichte mit Abweichungen, Änderungen, Qualitätskontrollen und Abschlussauswertung",
            "filename": "Vorlage_Projektdurchfuehrung",
            "type": "projekt",
            "content": (
                "# Projektdurchführung\n\n"
                "**Projekt:**  \n"
                "**Zeitraum:**  \n"
                "**Verfasser/in:**  \n\n"
                "## 1. Verlaufsberichte\n"
                "### Bericht KW ___ / Datum ___\n"
                "- Fortschritt gegenüber Meilensteinen:  \n"
                "- Ausgeführte Tätigkeiten:  \n"
                "- Abweichungen und Massnahmen:  \n\n"
                "### Bericht KW ___ / Datum ___\n"
                "- Fortschritt gegenüber Meilensteinen:  \n"
                "- Ausgeführte Tätigkeiten:  \n"
                "- Abweichungen und Massnahmen:  \n\n"
                "## 2. Änderungen\n"
                "| Nr. | Änderung | Grund | Auswirkung (Zeit/Kosten) | Datum |\n"
                "| --- | --- | --- | --- | --- |\n"
                "| 1 |  |  |  |  |\n\n"
                "## 3. Qualitätskontrolle und Prüfungen\n"
                "| Prüffeld / Prüfmittel | Kriterium | Soll / Ist | Resultat | Nacharbeit |\n"
                "| --- | --- | --- | --- | --- |\n"
                "|  |  |  |  |  |\n\n"
                "## 4. Abschluss und Auswertung\n"
                "### 4.1 Zielerreichung\n"
                "| Ziel | Erfüllt? | Anmerkung |\n"
                "| --- | --- | --- |\n"
                "|  | ja / teilweise / nein |  |\n\n"
                "### 4.2 Ökologie und Ökonomie\n"
                "- Ressourcen- und Energieeffizienz:  \n"
                "- Kostenblick (Budget vs. effektiv):  \n\n"
                "### 4.3 Reflexion und Erkenntnisse für künftige Projekte\n"
                "-  "
            ),
        },
    ]
    for tpl in seed_templates:
        fn, path = save_text_document(tpl["content"], tpl["filename"], company.name)
        doc = Documents(
            name=tpl["name"],
            description=tpl["description"],
            filename=fn,
            path=path,
            type=tpl["type"],
            owner=admin.id,
            author=admin.id,
            is_template=True,
            updated_date=datetime.now(timezone.utc),
            is_done=True,
        )
        db.session.add(doc)
    db.session.flush()


    vertrag_md = (
        "# Lehrvertrag MEM-Berufe (Auszug)\n\n"
        "**Lehrbetrieb:** Vektorwerk Technik AG, 8404 Winterthur  \n"
        "**Lernende:** Lea Buchmann  \n"
        "**Beruf:** Konstrukteurin EFZ  \n"
        "**Lehrdauer:** 10.08.2026 – 31.07.2030  \n"
        "**Probezeit:** 3 Monate  \n"
        "**Ferienanspruch:** 5 Wochen pro Lehrjahr\n"
    )
    v_fn, v_path = save_text_document(
        vertrag_md, "Lehrvertrag_Lea_Buchmann", company.name
    )
    doc_vertrag = Documents(
        name="Lehrvertrag Konstrukteurin EFZ – Lea Buchmann",
        description="Kantonal genehmigter Lehrvertrag",
        filename=v_fn,
        path=v_path,
        type="vertrag",
        owner=student1.id,
        author=hr_user.id,
        is_template=False,
        updated_date=datetime.now(timezone.utc),
        is_done=True,
    )

    # Beispiel für ein Ausbildungsgespräch als hochgeladene PDF/Word-Datei
    gesp_pdf_fn, gesp_pdf_path = save_binary_document(
        build_pdf_preview(), "Bildungsbericht_Lea_Buchmann.pdf", company.name
    )
    doc_gespraech_pdf = Documents(
        name="Bildungsbericht 1. Semester (PDF)",
        description="Ausgefüllter Bildungsbericht als hochgeladene PDF-Datei",
        filename=gesp_pdf_fn,
        path=gesp_pdf_path,
        type="ausbildungsgespraech",
        owner=student1.id,
        author=admin.id,
        is_template=False,
        updated_date=datetime.now(timezone.utc),
        is_done=True,
    )

    word_fn, word_path = save_binary_document(
        build_word_preview_docx(), "Word_Beispiel.docx", company.name
    )
    doc_word = Documents(
        name="Word-Beispielzeugnis (Vorschau, 2 Seiten)",
        description="Mehrseitiges Beispiel eines Word-Dokuments mit Überschriften, Tabelle und Seitenumbruch",
        filename=word_fn,
        path=word_path,
        type="zeugnis",
        owner=student2.id,
        author=admin.id,
        is_template=False,
        updated_date=datetime.now(timezone.utc),
        is_done=True,
    )

    pdf_fn, pdf_path = save_binary_document(
        build_pdf_preview(), "PDF_Beispiel.pdf", company.name
    )
    doc_pdf = Documents(
        name="PDF-Beispielkursnachweis (Vorschau, 2 Seiten)",
        description="Mehrseitiges Beispiel eines PDF-Dokuments mit Text, Tabelle und Seitenumbruch",
        filename=pdf_fn,
        path=pdf_path,
        type="kursnachweis",
        owner=student3.id,
        author=admin.id,
        is_template=False,
        updated_date=datetime.now(timezone.utc),
        is_done=True,
    )

    db.session.add_all(
        [
            doc_journal,
            doc_gespraech,
            doc_gespraech_pdf,
            doc_vertrag,
            doc_word,
            doc_pdf,
        ]
    )
    db.session.flush()

    # 9. Knowledge Base (Wissen: Thema -> Seite)
    def add_knowledge(title, description, content, parent_id=None, owner_user=admin):
        filename, path = save_text_document(content, title, company.name)
        doc = Documents(
            name=title,
            description=description,
            filename=filename,
            path=path,
            type="wissen",
            owner=owner_user.id,
            author=owner_user.id,
            is_template=False,
            updated_date=datetime.now(timezone.utc),
            is_done=True,
        )
        db.session.add(doc)
        db.session.flush()
        node = Knowledge(
            parent_id=parent_id,
            title=title,
            description=description,
            document_id=doc.id,
        )
        db.session.add(node)
        db.session.flush()
        return node

    knowledge_owners = {
        "Fertigung & Automatisierung": admin,
        "Arbeitssicherheit & SUVA-Regeln": student1,
        "Werkstoffkunde": student2,
        "Technisches Zeichnen & Messtechnik": student3,
    }

    for topic in KNOWLEDGE_TOPICS:
        owner_user = knowledge_owners.get(topic["title"], admin)
        parent = add_knowledge(
            topic["title"],
            topic["description"],
            topic["intro"],
            owner_user=owner_user,
        )
        for title, description, content in topic["pages"]:
            add_knowledge(
                title,
                description,
                content,
                parent_id=parent.id,
                owner_user=owner_user,
            )

    # Eine Wissenseite als hochgeladene PDF/Word-Datei (Statt Markdown-Text)
    pdf_topic = next(
        (
            t
            for t in KNOWLEDGE_TOPICS
            if t["title"] == "Technisches Zeichnen & Messtechnik"
        ),
        None,
    )
    if pdf_topic:
        parent_node = db.session.query(Knowledge).filter_by(title=pdf_topic["title"]).one()
        wissen_pdf_fn, wissen_pdf_path = save_binary_document(
            build_pdf_preview(), "Wissen_Messtechnik_Merkblatt.pdf", company.name
        )
        doc_wissen_pdf = Documents(
            name="Messtechnik-Merkblatt (PDF)",
            description="Praxis-Merkblatt als hochgeladene PDF-Datei",
            filename=wissen_pdf_fn,
            path=wissen_pdf_path,
            type="wissen",
            owner=student3.id,
            author=student3.id,
            is_template=False,
            updated_date=datetime.now(timezone.utc),
            is_done=True,
        )
        db.session.add(doc_wissen_pdf)
        db.session.flush()
        db.session.add(
            Knowledge(
                parent_id=parent_node.id,
                title="Messtechnik-Merkblatt (PDF)",
                description="Praxis-Merkblatt als hochgeladene PDF-Datei",
                document_id=doc_wissen_pdf.id,
            )
        )

    db.session.commit()
    print("Database seeded successfully.")


if __name__ == "__main__":
    seed_database(force="--force" in sys.argv)
