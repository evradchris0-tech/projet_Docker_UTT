"""Ajout rapide « à la Todoist » : une phrase -> une tâche structurée.

    "Réviser Docker demain p1 #UTT"
      -> titre="Réviser Docker", échéance=demain, priorité=1, projet="UTT"

Fonction pure (aucun accès base ni horloge cachée : la date du jour est un
paramètre), donc facile à tester unitairement.
"""
import re
from dataclasses import dataclass
from datetime import date, timedelta

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
RE_PRIORITE = re.compile(r"^p([1-4])$", re.IGNORECASE)
RE_PROJET = re.compile(r"^#([\w-]{1,60})$", re.UNICODE)
RE_DATE = re.compile(r"^(\d{1,2})/(\d{1,2})(?:/(\d{4}))?$")


@dataclass
class QuickAddResult:
    title: str
    due_date: date | None = None
    priority: int = 4
    project: str | None = None


def _date_absolue(jour: int, mois: int, annee: int | None, today: date) -> date | None:
    try:
        d = date(annee or today.year, mois, jour)
    except ValueError:
        return None  # ex. 31/02 : on laisse le mot dans le titre
    if annee is None and d < today:
        d = d.replace(year=d.year + 1)  # "05/01" en décembre -> janvier prochain
    return d


def _mot_vers_date(mot: str, today: date) -> date | None:
    m = mot.lower()
    if m in ("aujourd'hui", "aujourdhui", "auj"):
        return today
    if m == "demain":
        return today + timedelta(days=1)
    if m in ("après-demain", "apres-demain"):
        return today + timedelta(days=2)
    if m in JOURS:  # prochain jour de ce nom, strictement après aujourd'hui
        ecart = (JOURS.index(m) - today.weekday()) % 7 or 7
        return today + timedelta(days=ecart)
    if (r := RE_DATE.match(m)):
        return _date_absolue(int(r[1]), int(r[2]), int(r[3]) if r[3] else None, today)
    return None


def parse(texte: str, today: date) -> QuickAddResult:
    titre: list[str] = []
    res = QuickAddResult(title="")
    for mot in texte.split():
        if (m := RE_PRIORITE.match(mot)):
            res.priority = int(m[1])
        elif (m := RE_PROJET.match(mot)):
            res.project = m[1]
        elif res.due_date is None and (d := _mot_vers_date(mot, today)):
            res.due_date = d
        else:
            titre.append(mot)
    res.title = " ".join(titre).strip()
    if not res.title:
        raise ValueError("Le titre de la tâche est vide après analyse")
    return res
