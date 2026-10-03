"""Modèle de données (2 tables) : un projet contient des tâches."""
from datetime import date, datetime

from sqlalchemy import (Boolean, Date, DateTime, ForeignKey, SmallInteger, String,
                        Text, func)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    color: Mapped[str] = mapped_column(String(7), default="#808080")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    tasks: Mapped[list["Task"]] = relationship(back_populates="project",
                                               cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    due_date: Mapped[date | None] = mapped_column(Date, default=None, index=True)
    priority: Mapped[int] = mapped_column(SmallInteger, default=4)  # 1 = urgente ... 4 = normale
    done: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    done_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))

    project: Mapped[Project] = relationship(back_populates="tasks")
