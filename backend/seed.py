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


def seed_database():
    app = create_app()
    with app.app_context():
        if User.query.first():
            print("Database already contains users. Skipping seed.")
            return

        company = "SwissMEM Technik AG"

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
            company_email="thomas.keller@swissmem-technik.ch",
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
            company_email="sandra.meier@swissmem-technik.ch",
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
            company_email="marco.brunner@swissmem-technik.ch",
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
            company_email="lukas.frei@swissmem-technik.ch",
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
            company_email="elena.schmid@swissmem-technik.ch",
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
            start_date=date(2024, 8, 12),
            due_date=date(2025, 1, 31),
        )
        db.session.add(root_project)
        db.session.flush()

        sub_project1 = Project(
            parent_project=root_project.id,
            title="Teilprojekt: Schraubstock-Spannbacken fräsen",
            description="Herstellung eines Satzes gehärteter Spannbacken auf der konventionellen Universalfräsmaschine inkl. Prüfprotokoll.",
            author=fach_user.id,
            goals=json.dumps(
                [
                    "Winkligkeit und Parallelität innerhalb 0.02 mm einhalten",
                    "Oberflächenrauhigkeit Ra 1.6 erreichen",
                ],
                ensure_ascii=False,
            ),
            start_date=date(2024, 9, 2),
            due_date=date(2024, 10, 18),
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
            start_date=date(2025, 2, 3),
            due_date=date(2025, 7, 18),
        )
        db.session.add_all([sub_project1, sub_project2])
        db.session.flush()

        # 5. Participations (/api/implementation)
        part1 = Participation(
            supervisor=fach_user.id,
            student=student1.id,
            project=sub_project1.id,
            title="Arbeitsbericht: Rohteil zusägen und Grundkörper winklig fräsen",
            text="Rohteil aus 16MnCr5 auf der Bandsäge mit 3 mm Aufmass zugesägt. Anschliessend mit Messerkopf alle 6 Seiten im Schraubstock winklig und parallel vorbearbeitet. Alle Masse im Toleranzfeld.",
            is_done=True,
        )
        part2 = Participation(
            supervisor=admin.id,
            student=student1.id,
            project=sub_project2.id,
            title="CNC-Drehteil 'Antriebswelle' – Programmierung & Einfahren",
            text="ISO-Programm für Schrupp- und Schlichtzyklus geschrieben. Simulation durchgeführt; Einfahren im Einzelsatz steht noch aus.",
            is_done=False,
        )
        db.session.add_all([part1, part2])
        db.session.flush()

        # 6. Evaluations (/api/evaluation)
        eval1 = Eval(
            project=sub_project1.id,
            participation=part1.id,
            goal="Winkligkeit und Parallelität innerhalb 0.02 mm einhalten",
            student=student1.id,
            supervisor=fach_user.id,
            planning_text="Sauberes Entgraten nach jedem Aufspannen und Kontrolle der Auflagefläche mit Messuhr.",
            eval_text="Sehr exakte Arbeitsweise. Prüfprotokoll zeigt Abweichungen von max. 0.01 mm. Ziel vollumfänglich erreicht (A).",
        )
        eval2 = Eval(
            project=sub_project2.id,
            participation=part2.id,
            goal="Nullpunktverschiebung und Werkzeugkorrekturen fehlerfrei einrichten",
            student=student1.id,
            supervisor=admin.id,
            planning_text="Checkliste für Werkzeugvermessung verwenden und Trockenlauf mit Vorschubreduktion durchführen.",
            eval_text="",
        )
        db.session.add_all([eval1, eval2])

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
            "**Lehrbetrieb:** SwissMEM Technik AG, 8404 Winterthur  \n"
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
        k_topic1_md = (
            "# Zerspanungstechnik & Schnittdaten\n\n"
            "Übersicht zu den wichtigsten Formeln und Richtwerten für das Drehen, Fräsen und Bohren in der Lehrwerkstatt."
        )
        kt1_fn, kt1_path = save_text_document(
            k_topic1_md, "Thema_Zerspanungstechnik", company
        )
        doc_kt1 = Documents(
            name="Zerspanungstechnik & Schnittdaten",
            description="Grundlagen der Zerspanung",
            filename=kt1_fn,
            path=kt1_path,
            type="wissen",
            owner=admin.id,
            author=admin.id,
            is_template=False,
            updated_date=datetime.now(timezone.utc),
            is_done=True,
        )
        db.session.add(doc_kt1)
        db.session.flush()

        topic1 = Knowledge(
            parent_id=None,
            title="Zerspanungstechnik & Schnittdaten",
            description="Formeln, Richtwerte und Werkzeugwahl für Drehen, Fräsen und Bohren.",
            document_id=doc_kt1.id,
        )
        db.session.add(topic1)
        db.session.flush()

        k_page1_md = (
            "# Drehzahl- und Vorschubberechnung\n\n"
            "## 1. Drehzahl $n$ berechnen\n"
            "Die Spindeldrehzahl berechnet sich aus der Schnittgeschwindigkeit $v_c$ (in m/min) und dem Werkzeug- bzw. Werkstückdurchmesser $d$ (in mm):\n\n"
            "```\n"
            "n = (vc * 1000) / (π * d)\n"
            "```\n\n"
            "## 2. Vorschubgeschwindigkeit $v_f$ beim Fräsen\n"
            "```\n"
            "vf = n * fz * z\n"
            "```\n"
            "- `n`: Drehzahl [1/min]\n"
            "- `fz`: Vorschub pro Zahn [mm]\n"
            "- `z`: Zähnezahl des Fräsers\n\n"
            "## 3. Richtwerte für HM-Werkzeuge\n"
            "- **Baustahl (S235JR):** $v_c = 120 - 180\\text{ m/min}$\n"
            "- **Automatenstahl / Vergütungsstahl:** $v_c = 90 - 140\\text{ m/min}$\n"
            "- **Aluminiumlegierungen:** $v_c = 250 - 500\\text{ m/min}$\n"
        )
        kp1_fn, kp1_path = save_text_document(
            k_page1_md, "Drehzahl_und_Vorschubberechnung", company
        )
        doc_kp1 = Documents(
            name="Drehzahl- und Vorschubberechnung",
            description="Formeln für Drehzahl n und Vorschub vf",
            filename=kp1_fn,
            path=kp1_path,
            type="wissen",
            owner=admin.id,
            author=admin.id,
            is_template=False,
            updated_date=datetime.now(timezone.utc),
            is_done=True,
        )
        db.session.add(doc_kp1)
        db.session.flush()

        page1 = Knowledge(
            parent_id=topic1.id,
            title="Drehzahl- und Vorschubberechnung",
            description="Wichtige Formeln und Richtwerte für die Werkstatt",
            document_id=doc_kp1.id,
        )

        k_topic2_md = (
            "# Arbeitssicherheit & SUVA-Regeln\n\n"
            "Verbindliche Sicherheitsregeln in den Werkstätten und Labors der SwissMEM Technik AG."
        )
        kt2_fn, kt2_path = save_text_document(
            k_topic2_md, "Arbeitssicherheit_SUVA", company
        )
        doc_kt2 = Documents(
            name="Arbeitssicherheit & SUVA-Regeln",
            description="Sicherheitsvorschriften in der Werkstatt",
            filename=kt2_fn,
            path=kt2_path,
            type="wissen",
            owner=admin.id,
            author=admin.id,
            is_template=False,
            updated_date=datetime.now(timezone.utc),
            is_done=True,
        )
        db.session.add(doc_kt2)
        db.session.flush()

        topic2 = Knowledge(
            parent_id=None,
            title="Arbeitssicherheit & SUVA-Regeln",
            description="PSA, Not-Halt und lebenswichtige Regeln für die MEM-Branche",
            document_id=doc_kt2.id,
        )
        db.session.add_all([page1, topic2])

        db.session.commit()
        print("Database seeded successfully.")


if __name__ == "__main__":
    seed_database()
