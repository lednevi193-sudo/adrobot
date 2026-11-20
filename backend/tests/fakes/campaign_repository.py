"""Репозиторий и транзакция в памяти — с теми же правилами, что у SqlCampaignRepository.

- записи видны после commit, rollback их выбрасывает (как у Session);
- get отдаёт копию: агрегат, изменённый без save, в «базу» не попадает;
- версии и ConcurrencyConflict — как у version_id_col.
"""

from copy import deepcopy
from dataclasses import dataclass, field

from app.application.errors import CampaignAlreadyExists, CampaignNotFound, ConcurrencyConflict
from app.domain.campaigns import Campaign
from app.domain.common.ids import CampaignId


@dataclass
class InMemoryCampaignRepository:
    committed: dict[CampaignId, Campaign] = field(default_factory=dict)
    pending: dict[CampaignId, Campaign] = field(default_factory=dict)

    def get(self, campaign_id: CampaignId) -> Campaign | None:
        return deepcopy(self.pending.get(campaign_id) or self.committed.get(campaign_id))

    def list(self) -> list[Campaign]:
        merged = {**self.committed, **self.pending}
        return [deepcopy(c) for _, c in sorted(merged.items(), reverse=True)]

    def add(self, campaign: Campaign) -> None:
        if campaign.id in self.committed or campaign.id in self.pending:
            raise CampaignAlreadyExists(campaign.id)
        campaign.version = 1
        self.pending[campaign.id] = deepcopy(campaign)

    def save(self, campaign: Campaign) -> None:
        stored = self.pending.get(campaign.id) or self.committed.get(campaign.id)
        if stored is None:
            raise CampaignNotFound(campaign.id)
        if stored.version != campaign.version:
            raise ConcurrencyConflict(campaign.id)
        campaign.version += 1
        self.pending[campaign.id] = deepcopy(campaign)


@dataclass
class FakeUnitOfWork:
    repo: InMemoryCampaignRepository
    commits: int = 0
    rollbacks: int = 0

    def commit(self) -> None:
        self.repo.committed.update(self.repo.pending)
        self.repo.pending.clear()
        self.commits += 1

    def rollback(self) -> None:
        self.repo.pending.clear()
        self.rollbacks += 1
