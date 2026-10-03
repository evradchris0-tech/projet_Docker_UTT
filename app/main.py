"""TODOist — API REST FastAPI + interface web statique.

Routes principales (documentation interactive sur /docs) :
  GET    /api/health                 état de l'app et de la base
  GET    /api/projects               projets + nombre de tâches ouvertes
  POST   /api/projects               créer un projet
  DELETE /api/projects/{id}          supprimer un projet (et ses tâches)
  GET    /api/tasks?view=...         lister (inbox | today | upcoming | all | done)
  POST   /api/tasks                  créer une tâche (champs structurés)
  POST   /api/tasks/parse            analyser une phrase sans l'enregistrer (aperçu)
  POST   /api/tasks/quick            créer une tâche en langage naturel
  PATCH  /api/tasks/{id}             modifier / marquer comme faite
  DELETE /api/tasks/{id}             supprimer
"""
import logging
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import quickadd
from .database import Base, SessionLocal, engine, get_session, wait_for_db
from .models import Project, Task
from .schemas import (ProjectIn, ProjectOut, QuickAddIn, QuickAddPreview, TaskIn, TaskOut,
                      TaskPatch)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
INBOX = "Boîte de réception"
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Au démarrage : attendre MySQL, créer les tables si absentes, créer l'Inbox."""
    wait_for_db()
    Base.metadata.create_all(engine)  # CREATE TABLE IF NOT EXISTS : ne détruit rien
    with SessionLocal() as s:
        if not s.scalar(select(Project).where(Project.name == INBOX)):
            s.add(Project(name=INBOX, color="#246fe0"))
            s.commit()
    yield


app = FastAPI(title="TODOist", version="1.0.0", lifespan=lifespan)


# ------------------------------------------------------------------ helpers
def to_out(t: Task) -> TaskOut:
    return TaskOut(
        id=t.id, title=t.title, description=t.description, due_date=t.due_date,
        priority=t.priority, done=t.done, done_at=t.done_at, created_at=t.created_at,
        project_id=t.project_id, project_name=t.project.name,
        overdue=bool(t.due_date and not t.done and t.due_date < date.today()),
    )


def inbox_id(s: Session) -> int:
    return s.scalar(select(Project.id).where(Project.name == INBOX))


def get_task_or_404(s: Session, task_id: int) -> Task:
    task = s.get(Task, task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tâche introuvable")
    return task


def check_project(s: Session, project_id: int) -> None:
    if s.get(Project, project_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Projet inexistant")


# ------------------------------------------------------------------ santé
@app.get("/api/health")
def health(s: Session = Depends(get_session)):
    s.execute(text("SELECT 1"))
    return {"status": "ok", "database": "up", "tasks": s.scalar(select(func.count(Task.id)))}


# ------------------------------------------------------------------ projets
@app.get("/api/projects", response_model=list[ProjectOut])
def list_projects(s: Session = Depends(get_session)):
    open_count = (select(Task.project_id, func.count(Task.id).label("n"))
                  .where(Task.done.is_(False)).group_by(Task.project_id).subquery())
    rows = s.execute(select(Project, func.coalesce(open_count.c.n, 0))
                     .outerjoin(open_count, open_count.c.project_id == Project.id)
                     .order_by(Project.id)).all()
    return [ProjectOut(id=p.id, name=p.name, color=p.color, open_tasks=n) for p, n in rows]


@app.post("/api/projects", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectIn, s: Session = Depends(get_session)):
    p = Project(name=body.name.strip(), color=body.color)
    s.add(p)
    try:
        s.commit()
    except IntegrityError:
        s.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce projet existe déjà")
    return ProjectOut(id=p.id, name=p.name, color=p.color)


@app.delete("/api/projects/{project_id}", status_code=204)
def delete_project(project_id: int, s: Session = Depends(get_session)):
    p = s.get(Project, project_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Projet introuvable")
    if p.name == INBOX:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La boîte de réception ne peut pas être supprimée")
    s.delete(p)
    s.commit()


# ------------------------------------------------------------------ tâches
View = Literal["inbox", "today", "upcoming", "all", "done"]


@app.get("/api/tasks", response_model=list[TaskOut])
def list_tasks(view: View = "all", project_id: int | None = Query(default=None),
               s: Session = Depends(get_session)):
    q = select(Task).join(Task.project)
    today = date.today()
    if view == "done":
        q = q.where(Task.done.is_(True)).order_by(Task.done_at.desc())
    else:
        q = q.where(Task.done.is_(False))
        if view == "inbox":
            q = q.where(Project.name == INBOX)
        elif view == "today":      # aujourd'hui + en retard, comme Todoist
            q = q.where(Task.due_date <= today)
        elif view == "upcoming":
            q = q.where(Task.due_date > today)
        # tri : échéance (sans date en dernier), puis priorité, puis ancienneté
        q = q.order_by(Task.due_date.is_(None), Task.due_date, Task.priority, Task.id)
    if project_id is not None:
        q = q.where(Task.project_id == project_id)
    return [to_out(t) for t in s.scalars(q)]


@app.post("/api/tasks", response_model=TaskOut, status_code=201)
def create_task(body: TaskIn, s: Session = Depends(get_session)):
    pid = body.project_id or inbox_id(s)
    check_project(s, pid)
    t = Task(title=body.title.strip(), description=body.description, due_date=body.due_date,
             priority=body.priority, project_id=pid)
    s.add(t)
    s.commit()
    return to_out(t)


@app.post("/api/tasks/parse", response_model=QuickAddPreview)
def parse_quick(body: QuickAddIn):
    """Aperçu de l'ajout rapide : l'interface l'appelle pendant la saisie."""
    try:
        r = quickadd.parse(body.text, date.today())
    except ValueError as err:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(err))
    return QuickAddPreview(title=r.title, due_date=r.due_date, priority=r.priority, project=r.project)


@app.post("/api/tasks/quick", response_model=TaskOut, status_code=201)
def quick_add(body: QuickAddIn, s: Session = Depends(get_session)):
    try:
        r = quickadd.parse(body.text, date.today())
    except ValueError as err:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(err))
    if r.project:  # #Projet : réutilisé s'il existe, créé sinon
        project = s.scalar(select(Project).where(Project.name == r.project))
        if project is None:
            project = Project(name=r.project)
            s.add(project)
            s.flush()
        pid = project.id
    else:
        pid = inbox_id(s)
    t = Task(title=r.title, due_date=r.due_date, priority=r.priority, project_id=pid)
    s.add(t)
    s.commit()
    return to_out(t)


@app.patch("/api/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: int, body: TaskPatch, s: Session = Depends(get_session)):
    t = get_task_or_404(s, task_id)
    changes = body.model_dump(exclude_unset=True)
    for champ in ("title", "priority", "done"):  # colonnes NOT NULL : null = « ne pas changer »
        if changes.get(champ, 0) is None:
            del changes[champ]
    if "project_id" in changes:
        changes["project_id"] = changes["project_id"] or inbox_id(s)
        check_project(s, changes["project_id"])
    if "done" in changes:
        t.done_at = datetime.now() if changes["done"] else None
    for field, value in changes.items():
        setattr(t, field, value)
    s.commit()
    return to_out(t)


@app.delete("/api/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, s: Session = Depends(get_session)):
    s.delete(get_task_or_404(s, task_id))
    s.commit()


# ------------------------------------------------------------------ interface web
# Monté en dernier : les routes /api/* ci-dessus restent prioritaires.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
