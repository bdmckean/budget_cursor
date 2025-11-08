# Data models for the budget planner application
from pydantic import BaseModel
from typing import Dict, List, Optional

class RowMapping(BaseModel):
    row_index: int
    original_data: Dict[str, str]
    category: Optional[str] = None
    mapped: bool = False

class MappingRequest(BaseModel):
    row_index: int
    category: str

class ProgressResponse(BaseModel):
    rows: List[RowMapping]
    total_rows: int
    mapped_count: int

