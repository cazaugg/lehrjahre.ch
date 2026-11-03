import json
from datetime import date, datetime, timezone
from backend.app import create_app
from backend.models import (
    db,
    User,
    UserRelation,
    Project,
    Participation,
    Eval,
    Grades,
    Documents,
    Knowledge,
)
from backend.auth import hash_password
from backend.storage import save_text_document


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


def seed_database():
    app = create_app()
    with app.app_context():
        if User.query.first():
            print("Database already contains users. Skipping seed.")
            return

        company = "Vektorwerk Technik AG"

        # 1. Trainers (Ausbildner)
        admin = User(
            role="ausbildner",
            name="Thomas",
            surname="Keller",
            company=company,
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

        hr_user = User(
            role="ausbildner",
            name="Sandra",
            surname="Meier",
            company=company,
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
            job_title="HR / Rekrutierung",
        )

        fach_user = User(
            role="ausbildner",
            name="Marco",
            surname="Brunner",
            company=company,
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

        # 2. Apprentices (Lernende)
        student1 = User(
            role="lernender",
            name="Lukas",
            surname="Frei",
            company=company,
            password_hash=hash_password("Lehrjahre2026!"),
            private_address="Wiesenstrasse 19, 8400 Winterthur",
            private_email="lukas.frei@bluewin.ch",
            private_phone="+41 79 812 34 56",
            school_address="BBW Winterthur, Pionierstrasse 28, 8400 Winterthur",
            school_email="lukas.frei@stud.bbw.ch",
            school_phone="+41 52 267 81 11",
            company_address="Industriestrasse 40, 8404 Winterthur",
            company_email="lukas.frei@vektorwerk.ch",
            company_phone="+41 52 500 10 51",
            start_date=date(2024, 8, 12),
            end_date=date(2028, 7, 31),
            job_title="Polymechanikerin / Polymechaniker EFZ",
        )

        student2 = User(
            role="lernender",
            name="Elena",
            surname="Schmid",
            company=company,
            password_hash=hash_password("Lehrjahre2026!"),
            private_address="Seestrasse 44, 8405 Winterthur",
            private_email="elena.schmid@gmail.com",
            private_phone="+41 77 901 23 45",
            school_address="BBW Winterthur, Pionierstrasse 28, 8400 Winterthur",
            school_email="elena.schmid@stud.bbw.ch",
            school_phone="+41 52 267 81 11",
            company_address="Industriestrasse 40, 8404 Winterthur",
            company_email="elena.schmid@vektorwerk.ch",
            company_phone="+41 52 500 10 52",
            start_date=date(2025, 8, 11),
            end_date=date(2029, 7, 31),
            job_title="Automatikerin / Automatiker EFZ",
        )

        db.session.add_all([admin, hr_user, fach_user, student1, student2])
        db.session.flush()

        # 3. User Relations
        db.session.add_all(
            [
                UserRelation(supervisor=admin.id, student=student1.id),
                UserRelation(supervisor=fach_user.id, student=student1.id),
                UserRelation(supervisor=hr_user.id, student=student1.id),
                UserRelation(supervisor=admin.id, student=student2.id),
                UserRelation(supervisor=hr_user.id, student=student2.id),
            ]
        )

        # 4. Projects, Topics & Internships
        root_project = Project(
            parent_project=None,
            title="Basisausbildung 1. Lehrjahr – Konventionelle Fertigung",
            description="Grundlagen der spanabhebenden Bearbeitung (Bohren, Drehen, Fräsen) sowie Messtechnik und Arbeitssicherheit nach EKAS.",
            author=admin.id,
            goals=json.dumps(
                [
                    "Arbeitssicherheit und PSA an Dreh- und Fräsmaschinen konsequent anwenden",
                    "Werkstücke nach ISO-Toleranzen fertigen und mit Bügelmessschraube prüfen",
                    "Schnittdaten (vc, n, vf) selbstständig aus Tabellenbuch berechnen",
                ],
                ensure_ascii=False,
            ),
            assigned_students=json.dumps([student1.id, student2.id]),
            start_date=date(2024, 8, 12),
            due_date=date(2025, 1, 31),
            is_published=True,
            is_completed=False,
            global_eval_text="Beide Lernenden haben sich rasch an die Sicherheitsregeln in der Werkstatt gewöhnt.",
        )
        db.session.add(root_project)
        db.session.flush()

        sub_project1 = Project(
            parent_project=root_project.id,
            title="Aufgabe 1: Schraubstock-Spannbacken fräsen",
            description="Herstellung eines Satzes gehärteter Spannbacken auf der konventionellen Universalfräsmaschine inkl. Prüfprotokoll.",
            author=fach_user.id,
            goals=json.dumps(
                [
                    "Winkligkeit und Parallelität innerhalb 0.02 mm einhalten",
                    "Oberflächenrauhigkeit Ra 1.6 erreichen",
                ],
                ensure_ascii=False,
            ),
            assigned_students=json.dumps([student1.id, student2.id]),
            start_date=date(2024, 9, 2),
            due_date=date(2024, 10, 18),
            is_published=True,
            is_completed=False,
        )

        sub_project1b = Project(
            parent_project=root_project.id,
            title="Aufgabe 2: Passbolzen drehen & Messprotokoll",
            description="Fertigung eines gestuften Passbolzens mit Passung g6 auf der Leit- und Zugspindeldrehmaschine.",
            author=fach_user.id,
            goals=json.dumps([]),
            assigned_students=json.dumps([student1.id, student2.id]),
            start_date=date(2024, 10, 21),
            due_date=date(2024, 11, 29),
            is_published=True,
            is_completed=False,
        )

        sub_project2 = Project(
            parent_project=None,
            title="Schwerpunktausbildung – CNC-Drehen & CAM-Grundlagen",
            description="Programmierung nach ISO-Code, Werkzeugvermessung, Einrichten von Spannmitteln und Serienüberwachung.",
            author=admin.id,
            goals=json.dumps(
                [
                    "Nullpunktverschiebung und Werkzeugkorrekturen fehlerfrei einrichten",
                    "Erstmusterprüfung im Messraum dokumentieren",
                ],
                ensure_ascii=False,
            ),
            assigned_students=json.dumps([student1.id]),
            start_date=date(2025, 2, 3),
            due_date=date(2025, 7, 18),
            is_published=True,
            is_completed=False,
        )
        db.session.add_all([sub_project1, sub_project1b, sub_project2])
        db.session.flush()

        # 4b. Additional projects with different students and difficulty levels
        # (einfach -> mittel -> anspruchsvoll)

        # Einfach: abgeschlossenes Projekt für Elena
        p_pneumatik = Project(
            parent_project=None,
            title="Pneumatik-Hubvorrichtung montieren",
            description="Einfaches Einstiegsprojekt: Eine pneumatische Hubvorrichtung nach Plan aufbauen, verdrahten und auf Dichtheit prüfen.",
            author=fach_user.id,
            goals=json.dumps(
                [
                    "Pneumatikplan lesen und Bauteile korrekt zuordnen",
                    "Zylinder, Ventile und Drosseln normgerecht montieren",
                    "Dichtheit und Endlagen mit Lecksuchspray und Manometer prüfen",
                ],
                ensure_ascii=False,
            ),
            assigned_students=json.dumps([student2.id]),
            start_date=date(2025, 9, 15),
            due_date=date(2025, 10, 10),
            is_published=True,
            is_completed=True,
            global_eval_text="Elena hat die Hubvorrichtung selbstständig und sauber montiert. Die Funktionsprüfung war vollständig dokumentiert.",
        )
        db.session.add(p_pneumatik)
        db.session.flush()

        task_pneumatik_plan = Project(
            parent_project=p_pneumatik.id,
            title="Aufgabe 1: Pneumatikplan lesen und Bauteile bereitstellen",
            description="Stückliste und Pneumatikplan vergleichen, benötigte Ventile, Zylinder und Fittings bereitstellen.",
            author=fach_user.id,
            goals=json.dumps(["Stückliste mit Plan abgleichen"], ensure_ascii=False),
            assigned_students=json.dumps([student2.id]),
            start_date=date(2025, 9, 15),
            due_date=date(2025, 9, 26),
            is_published=True,
            is_completed=True,
        )
        task_pneumatik_montage = Project(
            parent_project=p_pneumatik.id,
            title="Aufgabe 2: Hubvorrichtung montieren und Dichtheit prüfen",
            description="Zylinder, Ventile und Drosseln montieren, Verschraubungen anziehen und die Anlage auf Dichtheit prüfen.",
            author=fach_user.id,
            goals=json.dumps(
                ["Alle Verschraubungen mit korrektem Drehmoment anziehen"],
                ensure_ascii=False,
            ),
            assigned_students=json.dumps([student2.id]),
            start_date=date(2025, 9, 29),
            due_date=date(2025, 10, 10),
            is_published=True,
            is_completed=True,
        )

        # Einfach: abgeschlossenes Projekt für Lukas
        p_werkzeug = Project(
            parent_project=None,
            title="Werkzeugkunde: Schneidwerkzeuge instand halten",
            description="Einfaches Projekt zur Pflege und Beurteilung von Bohrern, Gewindebohrern und Fräsern inkl. Schleif- und Prüfprotokoll.",
            author=admin.id,
            goals=json.dumps(
                [
                    "Schneidwerkzeuge nach Verschleissbild beurteilen",
                    "Bohrer mit der Schleifvorrichtung korrekt anschleifen",
                    "Werkzeugausgabe und Prüfprotokoll nachführen",
                ],
                ensure_ascii=False,
            ),
            assigned_students=json.dumps([student1.id]),
            start_date=date(2025, 9, 1),
            due_date=date(2025, 9, 19),
            is_published=True,
            is_completed=True,
            global_eval_text="Lukas beurteilt Verschleissbilder zuverlässig und arbeitet beim Anschleifen sehr genau.",
        )
        db.session.add(p_werkzeug)
        db.session.flush()

        task_werkzeug_schleifen = Project(
            parent_project=p_werkzeug.id,
            title="Aufgabe 1: Bohrersatz prüfen und anschleifen",
            description="Verschlissene Bohrer aussortieren, mit der Schleifvorrichtung anschleifen und die Schneidengeometrie prüfen.",
            author=admin.id,
            goals=json.dumps(["Freiwinkel und Spitzenwinkel kontrollieren"], ensure_ascii=False),
            assigned_students=json.dumps([student1.id]),
            start_date=date(2025, 9, 1),
            due_date=date(2025, 9, 12),
            is_published=True,
            is_completed=True,
        )
        task_werkzeug_inventar = Project(
            parent_project=p_werkzeug.id,
            title="Aufgabe 2: Werkzeugausgabe inventarisieren",
            description="Werkzeugbestand aufnehmen, beschädigte Werkzeuge kennzeichnen und fehlende Positionen nachbestellen.",
            author=admin.id,
            goals=json.dumps(["Inventarliste vollständig und nachvollziehbar führen"], ensure_ascii=False),
            assigned_students=json.dumps([student1.id]),
            start_date=date(2025, 9, 15),
            due_date=date(2025, 9, 19),
            is_published=True,
            is_completed=True,
        )

        # Mittel: laufendes Projekt für Elena
        p_schaltung = Project(
            parent_project=None,
            title="Motorsteuerung mit Schützschaltung aufbauen",
            description="Mittleres Projekt: Steuerung eines Drehstrommotors mit Schützen, Tastern und Selbsthaltung nach Schaltplan aufbauen und prüfen.",
            author=fach_user.id,
            goals=json.dumps(
                [
                    "Schaltplan in eine sichere Verdrahtung umsetzen",
                    "Selbsthaltung und Verriegelung funktional testen",
                    "Messwerte mit Multimeter und Stromzange dokumentieren",
                ],
                ensure_ascii=False,
            ),
            assigned_students=json.dumps([student2.id]),
            start_date=date(2025, 11, 3),
            due_date=date(2025, 12, 12),
            is_published=True,
            is_completed=False,
        )
        db.session.add(p_schaltung)
        db.session.flush()

        task_schaltung_plan = Project(
            parent_project=p_schaltung.id,
            title="Aufgabe 1: Schaltplan analysieren und Material bereitstellen",
            description="Schaltplan lesen, benötigte Schütze, Taster und Leiterquerschnitte bestimmen und Material bereitstellen.",
            author=fach_user.id,
            goals=json.dumps(["Benötigte Betriebsmittel korrekt bestimmen"], ensure_ascii=False),
            assigned_students=json.dumps([student2.id]),
            start_date=date(2025, 11, 3),
            due_date=date(2025, 11, 14),
            is_published=True,
            is_completed=True,
        )
        task_schaltung_verdrahten = Project(
            parent_project=p_schaltung.id,
            title="Aufgabe 2: Schaltung verdrahten und messtechnisch prüfen",
            description="Schaltung nach Plan verdrahten, Funktion der Selbsthaltung testen und Spannungen sowie Ströme messen.",
            author=fach_user.id,
            goals=json.dumps(
                ["Spannungs- und Strommessungen nachvollziehbar protokollieren"],
                ensure_ascii=False,
            ),
            assigned_students=json.dumps([student2.id]),
            start_date=date(2025, 11, 17),
            due_date=date(2025, 12, 12),
            is_published=True,
            is_completed=False,
        )

        # Mittel: laufendes Projekt für Lukas
        p_getriebe = Project(
            parent_project=None,
            title="Getriebemontage nach technischer Zeichnung",
            description="Mittleres Projekt: Ein zweistufiges Stirnradgetriebe nach Zeichnung montieren, ausrichten und die Endkontrolle dokumentieren.",
            author=admin.id,
            goals=json.dumps(
                [
                    "Montagereihenfolge anhand der Zeichnung festlegen",
                    "Lager und Wellen beschädigungsfrei montieren",
                    "Zahnflankenspiel und Leichtlauf prüfen",
                ],
                ensure_ascii=False,
            ),
            assigned_students=json.dumps([student1.id]),
            start_date=date(2026, 1, 12),
            due_date=date(2026, 2, 27),
            is_published=True,
            is_completed=False,
        )
        db.session.add(p_getriebe)
        db.session.flush()

        task_getriebe_vorbereiten = Project(
            parent_project=p_getriebe.id,
            title="Aufgabe 1: Bauteile prüfen und Montagereihenfolge festlegen",
            description="Alle Bauteile auf Vollständigkeit und Beschädigungen prüfen, Reinigung durchführen und die Montagereihenfolge dokumentieren.",
            author=admin.id,
            goals=json.dumps(["Montageanleitung und Zeichnung konsistent umsetzen"], ensure_ascii=False),
            assigned_students=json.dumps([student1.id]),
            start_date=date(2026, 1, 12),
            due_date=date(2026, 1, 23),
            is_published=True,
            is_completed=True,
        )
        task_getriebe_montieren = Project(
            parent_project=p_getriebe.id,
            title="Aufgabe 2: Getriebe montieren, ausrichten und Endkontrolle",
            description="Wellen und Lager montieren, Gehäuse ausrichten, Zahnflankenspiel messen und die Endkontrolle durchführen.",
            author=admin.id,
            goals=json.dumps(
                ["Zahnflankenspiel innerhalb der Zeichnungsvorgabe einstellen"],
                ensure_ascii=False,
            ),
            assigned_students=json.dumps([student1.id]),
            start_date=date(2026, 1, 26),
            due_date=date(2026, 2, 27),
            is_published=True,
            is_completed=False,
        )

        # Anspruchsvoll: laufendes Projekt für Elena
        p_sps = Project(
            parent_project=None,
            title="SPS-gesteuerte Sortieranlage in Betrieb nehmen",
            description="Anspruchsvolles Projekt: Sensorik, Aktorik und SPS-Programm einer Sortieranlage zusammenführen, simulieren und in Betrieb nehmen.",
            author=admin.id,
            goals=json.dumps(
                [
                    "Sensorik und Aktorik nach Stromlaufplan verdrahten",
                    "SPS-Programm strukturiert erstellen und simulieren",
                    "Anlage sicher einrichten, testen und dokumentieren",
                ],
                ensure_ascii=False,
            ),
            assigned_students=json.dumps([student2.id]),
            start_date=date(2026, 3, 16),
            due_date=date(2026, 6, 26),
            is_published=True,
            is_completed=False,
        )
        db.session.add(p_sps)
        db.session.flush()

        task_sps_verdrahten = Project(
            parent_project=p_sps.id,
            title="Aufgabe 1: Sensorik und Aktorik am Prüfstand verdrahten",
            description="Induktive, optische und kapazitive Sensoren sowie Ventile und Motoren nach Stromlaufplan anschliessen.",
            author=admin.id,
            goals=json.dumps(["Alle Signal- und Versorgungsleitungen korrekt auflegen"], ensure_ascii=False),
            assigned_students=json.dumps([student2.id]),
            start_date=date(2026, 3, 16),
            due_date=date(2026, 4, 10),
            is_published=True,
            is_completed=True,
        )
        task_sps_programm = Project(
            parent_project=p_sps.id,
            title="Aufgabe 2: SPS-Programm erstellen und simulieren",
            description="Ablaufsteuerung mit Schritten und Verzweigungen programmieren, Variablen benennen und die Simulation testen.",
            author=admin.id,
            goals=json.dumps(["Programm lesbar strukturieren und kommentieren"], ensure_ascii=False),
            assigned_students=json.dumps([student2.id]),
            start_date=date(2026, 4, 13),
            due_date=date(2026, 5, 22),
            is_published=True,
            is_completed=False,
        )
        task_sps_inbetriebnahme = Project(
            parent_project=p_sps.id,
            title="Aufgabe 3: Anlage einrichten, testen und dokumentieren",
            description="Anlage im Einzelsatz und Automatikbetrieb testen, Störungen beheben und die Inbetriebnahme dokumentieren.",
            author=admin.id,
            goals=json.dumps(["Inbetriebnahmeprotokoll vollständig führen"], ensure_ascii=False),
            assigned_students=json.dumps([student2.id]),
            start_date=date(2026, 5, 26),
            due_date=date(2026, 6, 26),
            is_published=True,
            is_completed=False,
        )

        # Anspruchsvoll: Entwurf für beide Lernenden
        p_bildverarbeitung = Project(
            parent_project=None,
            title="Bildverarbeitung: automatische Qualitätsprüfung",
            description="Anspruchsvolles Projekt: Eine kamerabasierte Qualitätsprüfung mit Roboterübergabe konzipieren, aufbauen und auswerten.",
            author=admin.id,
            goals=json.dumps(
                [
                    "Prüfmerkmale und Beleuchtung definieren",
                    "Kamerasystem kalibrieren und Prüfprogramm erstellen",
                    "Ausschussquoten auswerten und Verbesserungen ableiten",
                ],
                ensure_ascii=False,
            ),
            assigned_students=json.dumps([student1.id, student2.id]),
            start_date=date(2026, 8, 17),
            due_date=date(2026, 12, 18),
            is_published=False,
            is_completed=False,
        )
        db.session.add(p_bildverarbeitung)
        db.session.flush()

        task_bild_pruefkonzept = Project(
            parent_project=p_bildverarbeitung.id,
            title="Aufgabe 1: Prüfkonzept und Beleuchtung definieren",
            description="Zu prüfende Merkmale festlegen, Beleuchtungsszenarien vergleichen und das Prüfkonzept dokumentieren.",
            author=admin.id,
            goals=json.dumps(["Prüfmerkmale messbar beschreiben"], ensure_ascii=False),
            assigned_students=json.dumps([student1.id, student2.id]),
            start_date=date(2026, 8, 17),
            due_date=date(2026, 9, 11),
            is_published=False,
            is_completed=False,
        )
        task_bild_kalibrieren = Project(
            parent_project=p_bildverarbeitung.id,
            title="Aufgabe 2: Kamerasystem kalibrieren und Prüfprogramm erstellen",
            description="Kamera und Beleuchtung einrichten, Kalibrierung durchführen und ein Prüfprogramm mit Toleranzgrenzen erstellen.",
            author=admin.id,
            goals=json.dumps(["Kalibrierung reproduzierbar dokumentieren"], ensure_ascii=False),
            assigned_students=json.dumps([student1.id, student2.id]),
            start_date=date(2026, 9, 14),
            due_date=date(2026, 11, 6),
            is_published=False,
            is_completed=False,
        )
        task_bild_auswerten = Project(
            parent_project=p_bildverarbeitung.id,
            title="Aufgabe 3: Testreihe auswerten und dokumentieren",
            description="Testreihe mit Gut- und Schlechtteilen durchführen, Ausschussquote berechnen und Verbesserungen vorschlagen.",
            author=admin.id,
            goals=json.dumps(["Auswertung mit Kennzahlen und Massnahmen belegen"], ensure_ascii=False),
            assigned_students=json.dumps([student1.id, student2.id]),
            start_date=date(2026, 11, 9),
            due_date=date(2026, 12, 18),
            is_published=False,
            is_completed=False,
        )

        db.session.add_all(
            [
                task_pneumatik_plan,
                task_pneumatik_montage,
                task_werkzeug_schleifen,
                task_werkzeug_inventar,
                task_schaltung_plan,
                task_schaltung_verdrahten,
                task_getriebe_vorbereiten,
                task_getriebe_montieren,
                task_sps_verdrahten,
                task_sps_programm,
                task_sps_inbetriebnahme,
                task_bild_pruefkonzept,
                task_bild_kalibrieren,
                task_bild_auswerten,
            ]
        )
        db.session.flush()

        # 5. Participations (/api/implementation)
        part1 = Participation(
            supervisor=fach_user.id,
            student=student1.id,
            project=sub_project1.id,
            title=sub_project1.title,
            text="Rohteil aus 16MnCr5 auf der Bandsäge mit 3 mm Aufmass zugesägt. Anschliessend mit Messerkopf alle 6 Seiten im Schraubstock winklig und parallel vorbearbeitet. Alle Masse im Toleranzfeld.",
            is_done=True,
        )
        part2 = Participation(
            supervisor=admin.id,
            student=student1.id,
            project=sub_project2.id,
            title=sub_project2.title,
            text="ISO-Programm für Schrupp- und Schlichtzyklus geschrieben. Simulation durchgeführt; Einfahren im Einzelsatz steht noch aus.",
            is_done=False,
        )
        part_pneumatik_plan = Participation(
            supervisor=fach_user.id,
            student=student2.id,
            project=task_pneumatik_plan.id,
            title=task_pneumatik_plan.title,
            text="Stückliste mit dem Pneumatikplan abgeglichen. Alle Ventile, Zylinder und Fittings waren vorhanden; zwei Dichtringe wurden ersetzt.",
            is_done=True,
        )
        part_pneumatik_montage = Participation(
            supervisor=fach_user.id,
            student=student2.id,
            project=task_pneumatik_montage.id,
            title=task_pneumatik_montage.title,
            text="Hubvorrichtung montiert und alle Verschraubungen mit dem Drehmomentschlüssel angezogen. Dichtheitsprüfung mit Lecksuchspray ohne Befund.",
            is_done=True,
        )
        part_werkzeug_schleifen = Participation(
            supervisor=admin.id,
            student=student1.id,
            project=task_werkzeug_schleifen.id,
            title=task_werkzeug_schleifen.title,
            text="Acht Bohrer geprüft, vier als verschlissen aussortiert und die übrigen mit der Schleifvorrichtung neu angeschliffen. Spitzenwinkel kontrolliert.",
            is_done=True,
        )
        part_schaltung_plan = Participation(
            supervisor=fach_user.id,
            student=student2.id,
            project=task_schaltung_plan.id,
            title=task_schaltung_plan.title,
            text="Schaltplan analysiert und die benötigten Schütze, Taster sowie Leiterquerschnitte bestimmt. Material vollständig bereitgestellt.",
            is_done=True,
        )
        part_getriebe_vorbereiten = Participation(
            supervisor=admin.id,
            student=student1.id,
            project=task_getriebe_vorbereiten.id,
            title=task_getriebe_vorbereiten.title,
            text="Alle Bauteile gereinigt und auf Beschädigungen geprüft. Montagereihenfolge anhand der Zeichnung festgelegt und dokumentiert.",
            is_done=True,
        )
        part_sps_verdrahten = Participation(
            supervisor=admin.id,
            student=student2.id,
            project=task_sps_verdrahten.id,
            title=task_sps_verdrahten.title,
            text="Sensoren und Aktoren am Prüfstand nach Stromlaufplan verdrahtet. Alle Signal- und Versorgungsleitungen mit Kabelbindern sauber geführt.",
            is_done=True,
        )
        db.session.add_all(
            [
                part1,
                part2,
                part_pneumatik_plan,
                part_pneumatik_montage,
                part_werkzeug_schleifen,
                part_schaltung_plan,
                part_getriebe_vorbereiten,
                part_sps_verdrahten,
            ]
        )
        db.session.flush()

        # 6. Evaluations (/api/evaluation)
        eval_proj = Eval(
            project=root_project.id,
            target_type="project",
            goal=root_project.title,
            student=student1.id,
            supervisor=admin.id,
            eval_text="Lukas arbeitet sehr sorgfältig und strukturiert an den konventionellen Maschinen.",
            score_type="grade",
            score_value=5.4,
            is_released=True,
        )
        eval1 = Eval(
            project=sub_project1.id,
            participation=part1.id,
            target_type="task",
            goal=sub_project1.title,
            student=student1.id,
            supervisor=fach_user.id,
            eval_text="Sehr exakte Arbeitsweise. Prüfprotokoll zeigt Abweichungen von max. 0.01 mm.",
            score_type="grade",
            score_value=5.5,
            is_released=True,
        )
        eval_goal1 = Eval(
            project=root_project.id,
            target_type="goal",
            goal="Arbeitssicherheit und PSA an Dreh- und Fräsmaschinen konsequent anwenden",
            student=student1.id,
            supervisor=admin.id,
            eval_text="Vorbildliche Einhaltung der SUVA-Regeln (Schutzbrille, Spänehaken).",
            is_released=True,
        )
        eval_pneumatik_project = Eval(
            project=p_pneumatik.id,
            target_type="project",
            goal=p_pneumatik.title,
            student=student2.id,
            supervisor=fach_user.id,
            eval_text="Elena hat das Einstiegsprojekt selbstständig umgesetzt und die Dichtheitsprüfung sauber dokumentiert.",
            score_type="grade",
            score_value=5.3,
            is_released=True,
        )
        eval_pneumatik_task = Eval(
            project=task_pneumatik_montage.id,
            participation=part_pneumatik_montage.id,
            target_type="task",
            goal=task_pneumatik_montage.title,
            student=student2.id,
            supervisor=fach_user.id,
            eval_text="Sorgfältige Montage, korrekte Drehmomente und eine vollständige Funktionsprüfung.",
            score_type="grade",
            score_value=5.4,
            is_released=True,
        )
        eval_werkzeug_project = Eval(
            project=p_werkzeug.id,
            target_type="project",
            goal=p_werkzeug.title,
            student=student1.id,
            supervisor=admin.id,
            eval_text="Lukas beurteilt den Werkzeugverschleiss sicher und führt das Inventar zuverlässig nach.",
            score_type="grade",
            score_value=5.0,
            is_released=True,
        )
        eval_getriebe_task = Eval(
            project=task_getriebe_vorbereiten.id,
            participation=part_getriebe_vorbereiten.id,
            target_type="task",
            goal=task_getriebe_vorbereiten.title,
            student=student1.id,
            supervisor=admin.id,
            eval_text="Bauteile vollständig geprüft und die Montagereihenfolge nachvollziehbar hergeleitet.",
            score_type="grade",
            score_value=5.1,
            is_released=True,
        )
        eval_sps_project = Eval(
            project=p_sps.id,
            target_type="project",
            goal=p_sps.title,
            student=student2.id,
            supervisor=admin.id,
            eval_text="Elena arbeitet sehr strukturiert an der Verdrahtung. Die Inbetriebnahme ist noch nicht abgeschlossen.",
            score_type=None,
            score_value=None,
            is_released=False,
        )
        db.session.add_all(
            [
                eval_proj,
                eval1,
                eval_goal1,
                eval_pneumatik_project,
                eval_pneumatik_task,
                eval_werkzeug_project,
                eval_getriebe_task,
                eval_sps_project,
            ]
        )

        # 7. Grades (/api/grades)
        db.session.add_all(
            [
                Grades(
                    student=student1.id,
                    subject="Technische Grundlagen (Mathematik & Physik)",
                    date=date(2025, 10, 15),
                    grade=5.2,
                    title="Kräfteberechnung & Drehmoment",
                    comment="Sehr gute Herleitung der Gleichgewichtsbedingungen.",
                ),
                Grades(
                    student=student1.id,
                    subject="Werkstoff- und Fertigungstechnik",
                    date=date(2025, 11, 20),
                    grade=5.5,
                    title="Eisen-Kohlenstoff-Diagramm & Wärmebehandlung",
                    comment="Härteverfahren sicher beherrscht.",
                ),
                Grades(
                    student=student1.id,
                    subject="Zeichnungstechnik / CAD",
                    date=date(2025, 12, 10),
                    grade=4.8,
                    title="Baugruppenzeichnung & Form- und Lagetoleranzen",
                    comment="Schnittdarstellung korrekt, Oberflächensymbole beachten.",
                ),
                Grades(
                    student=student1.id,
                    subject="Allgemeinbildung (ABU)",
                    date=date(2026, 1, 22),
                    grade=5.0,
                    title="Recht & Obligationenrecht (Lehrvertrag)",
                    comment="",
                ),
                Grades(
                    student=student2.id,
                    subject="Montagetechnik",
                    date=date(2025, 10, 24),
                    grade=5.3,
                    title="Pneumatik-Hubvorrichtung montieren",
                    comment="Saubere Montage und vollständige Dichtheitsprüfung.",
                ),
                Grades(
                    student=student2.id,
                    subject="Elektrotechnik",
                    date=date(2025, 12, 19),
                    grade=5.0,
                    title="Motorsteuerung mit Schützschaltung",
                    comment="Schaltung korrekt verdrahtet, Messprotokoll nachvollziehbar.",
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
                    student=student2.id,
                    subject="Steuerungstechnik",
                    date=date(2026, 4, 17),
                    grade=4.8,
                    title="SPS-Grundlagen: Ablaufsteuerung",
                    comment="Programm funktioniert; Struktur und Kommentierung noch verbesserbar.",
                ),
            ]
        )

        # 8. Documents & Lernjournal & Templates
        journal_md = (
            "# Lernjournal KW 44 – Konventionelles Fräsen\n\n"
            "## Ausgeführte Arbeiten\n"
            "- Passfedernut 8H7 auf Universalfräsmaschine hergestellt\n"
            "- Zweischneider-Schaftfräser eingespannt und angetastet\n\n"
            "## Erkenntnisse & Reflexion\n"
            "Beim Fräsen einer Passung muss zuerst mit Untermasfräser vorgefräst und danach die Breite mit Endmassen kontrolliert werden, bevor die Fertigmass-Zustellung erfolgt.\n"
        )
        j_fn, j_path = save_text_document(journal_md, "Lernjournal_KW44", company)
        doc_journal = Documents(
            name="Lernjournal KW 44 – Passfedernut fräsen",
            description="Wochenreflexion Fertigungstechnik",
            filename=j_fn,
            path=j_path,
            type="lernjournal",
            owner=student1.id,
            author=student1.id,
            is_template=False,
            updated_date=datetime.now(timezone.utc),
            is_done=True,
        )

        gespraech_md = (
            "# Probezeitgespräch & Bildungsbericht 1. Semester\n\n"
            "**Lernender:** Lukas Frei  \n"
            "**Berufsbildner:** Thomas Keller  \n"
            "**Datum:** 15.11.2024\n\n"
            "## 1. Fachkompetenz\n"
            "Lukas arbeitet sehr sorgfältig an den konventionellen Maschinen und hält die Sicherheitsvorschriften vorbildlich ein.\n\n"
            "## 2. Methoden- & Sozialkompetenz\n"
            "Freundliches Auftreten im Team, pünktlich und zuverlässig. Lerndokumentation wird regelmässig geführt.\n\n"
            "## 3. Vereinbarte Ziele für das nächste Semester\n"
            "- Selbstständige Vorbereitung der CNC-Grundübungen\n"
            "- Notenschnitt in der Berufsfachschule über 5.0 halten\n"
        )
        g_fn, g_path = save_text_document(
            gespraech_md, "Probezeitgespraech_Lukas_Frei", company
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

        tpl_gespraech_md = (
            "# Vorlage: Halbjahres-Ausbildungsgespräch (Bildungsbericht)\n\n"
            "**Lernende/r:**  \n"
            "**Berufsbildner/in:**  \n"
            "**Semester:**  \n\n"
            "## 1. Rückblick auf das vergangene Semester\n"
            "- Was ist besonders gut gelungen?\n"
            "- Wo gab es Herausforderungen?\n\n"
            "## 2. Beurteilung der Kompetenzen (A–D)\n"
            "- **Fachkompetenz:** \n"
            "- **Methodenkompetenz:** \n"
            "- **Sozial- und Selbstkompetenz:** \n\n"
            "## 3. Schulische Leistungen & ÜK\n"
            "- Berufsfachschule / BM:\n"
            "- Überbetriebliche Kurse:\n\n"
            "## 4. Ziele für das nächste Semester\n"
            "1. \n"
            "2. \n"
        )
        t_fn, t_path = save_text_document(
            tpl_gespraech_md, "Vorlage_Ausbildungsgespraech", company
        )
        doc_tpl = Documents(
            name="Vorlage Bildungsbericht / Ausbildungsgespräch",
            description="Offizielle Vorlage für Semester- und Probezeitgespräche",
            filename=t_fn,
            path=t_path,
            type="ausbildungsgespraech",
            owner=admin.id,
            author=admin.id,
            is_template=True,
            updated_date=datetime.now(timezone.utc),
            is_done=True,
        )

        vertrag_md = (
            "# Lehrvertrag MEM-Berufe (Auszug)\n\n"
            "**Lehrbetrieb:** Vektorwerk Technik AG, 8404 Winterthur  \n"
            "**Lernender:** Lukas Frei  \n"
            "**Beruf:** Polymechaniker EFZ  \n"
            "**Lehrdauer:** 12.08.2024 – 31.07.2028  \n"
            "**Probezeit:** 3 Monate  \n"
            "**Ferienanspruch:** 5 Wochen pro Lehrjahr\n"
        )
        v_fn, v_path = save_text_document(
            vertrag_md, "Lehrvertrag_Lukas_Frei", company
        )
        doc_vertrag = Documents(
            name="Lehrvertrag Polymechaniker EFZ – Lukas Frei",
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

        db.session.add_all([doc_journal, doc_gespraech, doc_tpl, doc_vertrag])
        db.session.flush()

        # 9. Knowledge Base (Wissen: Thema -> Seite)
        def add_knowledge(title, description, content, parent_id=None, owner_user=admin):
            filename, path = save_text_document(content, title, company)
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
            "Technisches Zeichnen & Messtechnik": student1,
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

        db.session.commit()
        print("Database seeded successfully.")


if __name__ == "__main__":
    seed_database()
