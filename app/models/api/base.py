from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    def to_api_dict(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True)
