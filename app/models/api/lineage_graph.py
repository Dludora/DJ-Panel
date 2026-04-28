from typing import Any, Literal

from pydantic import BaseModel, Field

NodeType = Literal['JOB', 'DATASET']


class Edge(BaseModel):
    origin: str
    destination: str


class Node(BaseModel):
    id: str
    type: NodeType
    data: dict[str, Any]
    in_edges: list[Edge] = Field(default_factory=list, alias='inEdges')
    out_edges: list[Edge] = Field(default_factory=list, alias='outEdges')


class LineageResponse(BaseModel):
    graph: list[Node]
