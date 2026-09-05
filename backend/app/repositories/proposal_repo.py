from app.domain.recovery import ResolutionProposal
from app.repositories.base import BaseRepository


class ProposalRepository(BaseRepository[ResolutionProposal]):
    def __init__(self, session):
        super().__init__(ResolutionProposal, session)
