from enum import Enum

from pydantic import BaseModel


class IngestionStatus(str, Enum):
    ACCEPTED = 'accepted'


class IngestionResult(BaseModel):
    projected: bool


class IngestionResponse(BaseModel):
    status: IngestionStatus = IngestionStatus.ACCEPTED
    projected: bool
