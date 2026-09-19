from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import HostCommand
from app.schemas import CommandIn, CommandOut
from app.services.commands import execute_command

router = APIRouter(prefix="/commands", tags=["commands"])


@router.post("", response_model=CommandOut)
def post_command(payload: CommandIn, db: Session = Depends(get_db)) -> CommandOut:
    return execute_command(db, payload)


@router.get("", response_model=list[CommandOut])
def list_commands(db: Session = Depends(get_db)) -> list[CommandOut]:
    return db.query(HostCommand).order_by(HostCommand.created_at.desc()).limit(50).all()
