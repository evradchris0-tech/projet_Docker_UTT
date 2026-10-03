"""Tests unitaires du parseur d'ajout rapide (sans base de données).

Lancer :  python -m pytest tests/   (ou  python tests/test_quickadd.py)
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.quickadd import parse  # noqa: E402

JEUDI = date(2026, 9, 24)  # un jeudi


def test_complet():
    r = parse("Réviser Docker demain p1 #UTT", JEUDI)
    assert (r.title, r.due_date, r.priority, r.project) == ("Réviser Docker", date(2026, 9, 25), 1, "UTT")


def test_sans_marqueur():
    r = parse("Acheter du pain", JEUDI)
    assert (r.title, r.due_date, r.priority, r.project) == ("Acheter du pain", None, 4, None)


def test_jour_de_semaine_est_toujours_dans_le_futur():
    assert parse("Sport jeudi", JEUDI).due_date == date(2026, 10, 1)   # pas aujourd'hui
    assert parse("Sport lundi", JEUDI).due_date == date(2026, 9, 28)


def test_date_absolue_passee_bascule_annee_suivante():
    assert parse("Impôts 15/01", JEUDI).due_date == date(2027, 1, 15)
    assert parse("Rendu 30/09/2026", JEUDI).due_date == date(2026, 9, 30)


def test_date_invalide_reste_dans_le_titre():
    r = parse("Vérifier 31/02", JEUDI)
    assert r.due_date is None and r.title == "Vérifier 31/02"


def test_titre_vide_refuse():
    try:
        parse("demain p2 #Perso", JEUDI)
    except ValueError:
        return
    raise AssertionError("un titre vide aurait dû être refusé")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("OK", name)
