from pathlib import Path
from typing import List, Dict, Any

class CaptionsService:
    """Generates standard SRT caption files and formatting for video burn-in."""

    def format_timestamp_srt(self, seconds: float) -> str:
        """Formats seconds into SRT timestamp 00:00:00,000."""
        hrs = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int(round((seconds - int(seconds)) * 1000))
        return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"

    def generate_srt(self, words_or_scenes: List[Dict[str, Any]], output_path: Path) -> Path:
        """Builds an SRT file from word or scene intervals."""
        srt_lines = []
        for idx, item in enumerate(words_or_scenes, start=1):
            text = item.get("text") or item.get("word") or ""
            start = float(item.get("start") or item.get("start_time") or 0.0)
            end = float(item.get("end") or item.get("end_time") or 0.0)
            
            start_str = self.format_timestamp_srt(start)
            end_str = self.format_timestamp_srt(end)
            
            srt_lines.append(f"{idx}\n{start_str} --> {end_str}\n{text.strip()}\n\n")

        content = "".join(srt_lines)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        return output_path

captions_service = CaptionsService()
