from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from pathlib import Path

class FootageItem(BaseModel):
    clip_id: str
    url: str
    source: str
    licence: str
    attribution: str
    link: str
    is_ai_generated: bool = False
    aspect_ratio: str = "16:9"
    duration: float = 10.0
    relevance_score: float = 4.0
    tags: List[str] = Field(default_factory=list)
    local_path: Optional[str] = None

class BaseFootageProvider(ABC):
    """Abstract interface for B-roll footage sourcing adapters."""

    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    async def search(
        self,
        query: str,
        duration: float,
        aspect_ratio: str = "16:9",
        avoid: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> List[FootageItem]:
        pass

    @abstractmethod
    async def prepare_clip(self, item: FootageItem, target_dir: Path) -> Path:
        """Ensures the clip is downloaded/generated locally and returns Path."""
        pass
