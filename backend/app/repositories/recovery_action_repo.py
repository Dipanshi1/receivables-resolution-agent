from app.domain.recovery import RecoveryAction
from app.repositories.base import BaseRepository


class RecoveryActionRepository(BaseRepository[RecoveryAction]):
    def __init__(self, session):
        super().__init__(RecoveryAction, session)
