from app.domain.recovery import AgentRun
from app.repositories.base import BaseRepository


class AgentRunRepository(BaseRepository[AgentRun]):
    def __init__(self, session):
        super().__init__(AgentRun, session)
