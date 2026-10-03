"""Schémas Pydantic : validation des entrées et forme des réponses de l'API."""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

HEX_COLOR = r"^#[0-9a-fA-F]{6}$"


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    color: str = Field(default="#808080", pattern=HEX_COLOR)


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    color: str
    open_tasks: int = 0


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    due_date: date | None = None
    priority: int = Field(default=4, ge=1, le=4)
    project_id: int | None = None  # None -> Boîte de réception


class TaskPatch(BaseModel):
    """Mise à jour partielle : seuls les champs envoyés sont modifiés."""
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    due_date: date | None = None
    priority: int | None = Field(default=None, ge=1, le=4)
    project_id: int | None = None
    done: bool | None = None


class QuickAddIn(BaseModel):
    text: str = Field(min_length=1, max_length=300)


class QuickAddPreview(BaseModel):
    """Résultat de l'analyse d'une phrase, sans rien enregistrer."""
    title: str
    due_date: date | None
    priority: int
    project: str | None


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: str | None
    due_date: date | None
    priority: int
    done: bool
    done_at: datetime | None
    created_at: datetime
    project_id: int
    project_name: str
    overdue: bool
