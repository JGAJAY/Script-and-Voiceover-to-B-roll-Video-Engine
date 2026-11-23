import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import logging

from src.config import settings
from src.api.schemas import SceneInput

logger = logging.getLogger(__name__)

# Double meaning keyword mappings (contextual disambiguation)
DISAMBIGUATION_MAP = {
    "value": {
        "metaphor": "pile of cash",  # MUST AVOID
        "recommended": "graph showing business value and upward growth",
        "category": "abstract_business"
    },
    "bank": {
        "financial": "modern architectural banking building and digital finance interface",
        "river": "peaceful flowing river bank with lush greenery",
        "category": "finance_or_nature"
    },
    "cloud": {
        "computing": "high-tech server room with blinking led lights and fiber optics",
        "weather": "blue sky with gentle white cumulus clouds",
        "category": "tech_infrastructure"
    },
    "mouse": {
        "computer": "ergonomic optical computer mouse on desk beside keyboard",
        "animal": "small rodent in natural wild habitat",
        "category": "hardware"
    },
    "python": {
        "programming": "developer writing clean code in IDE on laptop monitor",
        "reptile": "wild green serpent moving in jungle foliage",
        "category": "software"
    }
}

SENSITIVE_KEYWORDS = {
    "died", "death", "tragedy", "funeral", "accident", "mourn", "casualty", "grief",
    "crisis", "victim", "disaster", "war", "devastation", "passed away", "loss"
}

ABSTRACT_PATTERNS = [
    r"trust\s+is\s+earned",
    r"success\s+comes",
    r"patience\s+and",
    r"mindset",
    r"philosophy",
    r"belief",
    r"journey\s+of",
    r"wisdom",
    r"vision\s+for"
]

STATISTICS_PATTERNS = [
    r"\d+%",
    r"sales\s+grew",
    r"revenue\s+increased",
    r"in\s+202[0-9]",
    r"\$\d+",
    r"\d+\s+billion",
    r"\d+\s+million",
    r"growth\s+rate"
]

@dataclass
class SegmentedScene:
    scene_index: int
    text: str
    start_time: float
    end_time: float
    duration: float
    visual_hint: Optional[str] = None
    is_abstract: bool = False
    has_statistics: bool = False
    is_sensitive: bool = False
    has_named_entity: bool = False
    disambiguated_concept: Optional[str] = None
    tags: List[str] = field(default_factory=list)

class SceneSegmenter:
    """Segments narration words and texts into semantic scenes respecting duration and voice boundaries."""

    def segment(
        self,
        words: List[Dict[str, Any]],
        total_duration: float,
        predefined_scenes: Optional[List[SceneInput]] = None
    ) -> List[SegmentedScene]:
        """Segments speech into scenes. Predefined scenes take precedence for boundaries if provided."""
        if predefined_scenes and len(predefined_scenes) > 0:
            return self._segment_from_predefined_scenes(words, total_duration, predefined_scenes)
        
        return self._segment_from_words(words, total_duration)

    def _segment_from_predefined_scenes(
        self,
        words: List[Dict[str, Any]],
        total_duration: float,
        predefined_scenes: List[SceneInput]
    ) -> List[SegmentedScene]:
        """Splits the audio duration proportionately or via word alignment across the IncuBrix scene list."""
        n = len(predefined_scenes)
        if n == 0:
            return []

        # Find matching word ranges for each scene's text
        scenes = []
        cur_word_idx = 0
        total_words = len(words)

        for i, scene_input in enumerate(predefined_scenes):
            target_words = scene_input.text.strip().split()
            target_count = max(1, len(target_words))

            # Approximate time range based on word count fraction
            if total_words > 0 and cur_word_idx < total_words:
                start_time = words[cur_word_idx]["start"]
                end_word_idx = min(total_words - 1, cur_word_idx + target_count - 1)
                if i == n - 1:  # Last scene covers to end
                    end_time = total_duration
                else:
                    end_time = words[end_word_idx]["end"]
                cur_word_idx = end_word_idx + 1
            else:
                start_time = (i / n) * total_duration
                end_time = ((i + 1) / n) * total_duration

            # Ensure strict non-overlapping contiguous boundaries
            if i > 0:
                start_time = scenes[i - 1].end_time
            if i == n - 1:
                end_time = total_duration

            dur = max(0.1, end_time - start_time)
            seg = self._analyze_and_create_scene(
                index=i,
                text=scene_input.text,
                start=round(start_time, 2),
                end=round(end_time, 2),
                duration=round(dur, 2),
                visual_hint=scene_input.visual_hint
            )
            scenes.append(seg)

        return scenes

    def _segment_from_words(
        self,
        words: List[Dict[str, Any]],
        total_duration: float
    ) -> List[SegmentedScene]:
        """Segments words into scenes by natural punctuation/sentence boundaries enforcing sensible pacing."""
        if not words:
            # Fallback single scene
            return [self._analyze_and_create_scene(0, "Narration", 0.0, total_duration, total_duration)]

        min_dur = settings.MIN_SCENE_DURATION_SECONDS  # 2.0s
        max_dur = settings.MAX_SCENE_DURATION_SECONDS  # 6.5s

        raw_scenes = []
        current_chunk_words = []
        chunk_start = 0.0

        for idx, w in enumerate(words):
            word_str = w["word"]
            current_chunk_words.append(word_str)
            w_end = w["end"]
            chunk_duration = w_end - chunk_start

            # Check sentence or major punctuation boundary
            is_sentence_boundary = bool(re.search(r"[\.\!\?]$", word_str))
            is_phrase_boundary = bool(re.search(r"[\;\:]$", word_str))
            is_comma_boundary = bool(re.search(r"[\,]$", word_str))
            is_last_word = (idx == len(words) - 1)

            should_split = False
            if is_last_word:
                should_split = True
            elif chunk_duration >= min_dur and is_sentence_boundary:
                should_split = True
            elif chunk_duration >= (min_dur + 2.5) and is_phrase_boundary:
                should_split = True
            elif chunk_duration >= (max_dur - 1.0) and is_comma_boundary:
                should_split = True
            elif chunk_duration >= max_dur:
                should_split = True

            if should_split and current_chunk_words:
                text_block = " ".join(current_chunk_words)
                chunk_end = total_duration if is_last_word else w_end
                raw_scenes.append({
                    "text": text_block,
                    "start": round(chunk_start, 2),
                    "end": round(chunk_end, 2),
                    "duration": round(chunk_end - chunk_start, 2)
                })
                current_chunk_words = []
                chunk_start = chunk_end

        # Enforce sensible pacing: merge any trailing slivers (< 1.5s) into previous scene
        merged = []
        for s in raw_scenes:
            if merged and s["duration"] < 1.8:
                merged[-1]["end"] = s["end"]
                merged[-1]["duration"] = round(merged[-1]["end"] - merged[-1]["start"], 2)
                merged[-1]["text"] += " " + s["text"]
            else:
                merged.append(s)

        # Build final SegmentedScene list
        result = []
        for i, s in enumerate(merged):
            # Guarantee continuous coverage
            if i == 0:
                s["start"] = 0.0
            if i > 0:
                s["start"] = result[i - 1].end_time
            if i == len(merged) - 1:
                s["end"] = total_duration
            s["duration"] = round(s["end"] - s["start"], 2)

            seg = self._analyze_and_create_scene(
                index=i,
                text=s["text"],
                start=s["start"],
                end=s["end"],
                duration=s["duration"],
                visual_hint=None
            )
            result.append(seg)

        return result

    def _analyze_and_create_scene(
        self,
        index: int,
        text: str,
        start: float,
        end: float,
        duration: float,
        visual_hint: Optional[str] = None
    ) -> SegmentedScene:
        """Analyzes text for abstractness, statistics, sensitive topics, and double meanings."""
        text_lower = text.lower()
        tags = []

        # Check abstractness
        is_abstract = any(re.search(pat, text_lower) for pat in ABSTRACT_PATTERNS)
        if "abstract" in text_lower or "concept" in text_lower or "philosophy" in text_lower:
            is_abstract = True
        if is_abstract:
            tags.append("abstract")

        # Check statistics / numbers
        has_stats = any(re.search(pat, text_lower) for pat in STATISTICS_PATTERNS)
        if has_stats:
            tags.append("statistics")

        # Check sensitive / sad content
        is_sensitive = any(w in text_lower.split() for w in SENSITIVE_KEYWORDS)
        if is_sensitive:
            tags.append("sensitive")

        # Check double meanings
        disambiguated = None
        for key, disambig in DISAMBIGUATION_MAP.items():
            if re.search(r"\b" + key + r"\b", text_lower):
                if key == "value":
                    disambiguated = disambig["recommended"]
                    tags.append("semantic_disambiguation_value")
                elif key == "cloud":
                    # Weather if explicit rain, storm, sky or airplane
                    if any(t in text_lower for t in ["rain", "storm", "sky", "weather", "wind", "airplane", "flying", "cumulus", "sunshine"]):
                        disambiguated = disambig["weather"]
                    else:
                        disambiguated = disambig["computing"]
                    tags.append("semantic_disambiguation_cloud")
                elif key == "bank":
                    # River/nature if water, river, stream, shore, lake
                    if any(t in text_lower for t in ["river", "stream", "water", "lake", "shore", "beach", "greenery", "swimming", "fish"]):
                        disambiguated = disambig["river"]
                    else:
                        disambiguated = disambig["financial"]
                    tags.append("semantic_disambiguation_bank")
                elif key == "python":
                    # Reptile ONLY if explicit snake, venom, zoo, jungle, wild animal
                    if any(t in text_lower for t in ["snake", "serpent", "reptile", "zoo", "jungle", "wildlife", "species", "venom", "bite"]):
                        disambiguated = disambig["reptile"]
                    else:
                        disambiguated = disambig["programming"]
                    tags.append("semantic_disambiguation_python")

        # Check named entities or brands
        has_named_entity = bool(re.search(r"\b(Elon Musk|Apple|Google|Microsoft|Nvidia|Tesla|Trump|Biden|Modi)\b", text, re.IGNORECASE))
        if has_named_entity:
            tags.append("named_entity")

        return SegmentedScene(
            scene_index=index,
            text=text,
            start_time=start,
            end_time=end,
            duration=duration,
            visual_hint=visual_hint,
            is_abstract=is_abstract,
            has_statistics=has_stats,
            is_sensitive=is_sensitive,
            has_named_entity=has_named_entity,
            disambiguated_concept=disambiguated,
            tags=tags
        )

scene_segmenter = SceneSegmenter()
