import asyncio
import pytest
from pathlib import Path

from src.services.tts_service import tts_service
from src.services.scene_segmenter import scene_segmenter, SegmentedScene
from src.services.footage_selector import footage_selector
from src.services.captions import captions_service
from src.services.relevance_scorer import relevance_scorer
from src.api.schemas import SceneTimelineItem

def test_tts_service_speech_generation(tmp_path):
    text = "Welcome to IncuBrix video generation engine. We turn narration into finished video."
    out_file = tmp_path / "test_tts.mp3"
    result = asyncio.run(tts_service.generate_speech(text, voice="en-IN-female", output_path=out_file))

    assert result["audio_path"].exists()
    assert result["duration"] > 1.0
    assert len(result["words"]) > 0
    assert result["words"][0]["word"] != ""

def test_scene_segmenter_pacing_and_coverage():
    # Synthetic word timestamps totaling 10.0 seconds
    words = [
        {"word": f"word{i}", "start": round(i * 0.5, 2), "end": round((i + 1) * 0.5, 2)}
        for i in range(20)
    ]
    # Add a period at word 8 and word 19
    words[7]["word"] += "."
    words[19]["word"] += "."

    scenes = scene_segmenter.segment(words, total_duration=10.0)

    assert len(scenes) >= 2
    # Verify continuous coverage (no gaps)
    for i in range(len(scenes)):
        if i == 0:
            assert scenes[i].start_time == 0.0
        else:
            assert scenes[i].start_time == scenes[i - 1].end_time
        # Sensible pacing: minimum scene duration >= 1.8s
        assert scenes[i].duration >= 1.8

    assert scenes[-1].end_time == 10.0

def test_footage_selector_decision_rule():
    # Abstract scene -> must choose generative
    abstract_scene = SegmentedScene(
        scene_index=0,
        text="Trust is earned slowly and lost quickly.",
        start_time=0.0,
        end_time=4.0,
        duration=4.0,
        is_abstract=True
    )
    src, reason = footage_selector.evaluate_source_decision_rule(abstract_scene)
    assert src == "generative"
    assert "Abstract" in reason

    # Real-world scene -> must choose stock
    real_scene = SegmentedScene(
        scene_index=1,
        text="Developers working in modern office space.",
        start_time=4.0,
        end_time=8.0,
        duration=4.0,
        is_abstract=False
    )
    src_real, reason_real = footage_selector.evaluate_source_decision_rule(real_scene)
    assert src_real == "stock"
    assert "stock" in reason_real.lower()

    # Sensitive scene -> must choose stock (verified commercial)
    sensitive_scene = SegmentedScene(
        scene_index=2,
        text="Memorial service in memory of the tragedy victims.",
        start_time=8.0,
        end_time=12.0,
        duration=4.0,
        is_sensitive=True
    )
    src_sens, _ = footage_selector.evaluate_source_decision_rule(sensitive_scene)
    assert src_sens == "stock"

def test_captions_srt_generation(tmp_path):
    scenes = [
        {"text": "Hello world", "start_time": 0.0, "end_time": 2.5},
        {"text": "IncuBrix video engine", "start_time": 2.5, "end_time": 5.0}
    ]
    srt_file = tmp_path / "test.srt"
    captions_service.generate_srt(scenes, srt_file)

    assert srt_file.exists()
    content = srt_file.read_text(encoding="utf-8")
    assert "00:00:00,000 --> 00:00:02,500" in content
    assert "Hello world" in content
    assert "IncuBrix video engine" in content

def test_relevance_scorer_agreement():
    items = [
        SceneTimelineItem(
            scene_index=0,
            text="Cloud data center servers computing",
            start_time=0.0,
            end_time=4.0,
            duration=4.0,
            clip_id="c1",
            clip_url="local://c1",
            source="stock",
            licence="CC0",
            attribution="Open",
            is_ai_generated=False,
            reason_chosen="Match",
            relevance_score=4.6
        ),
        SceneTimelineItem(
            scene_index=1,
            text="Abstract upward financial value chart",
            start_time=4.0,
            end_time=8.0,
            duration=4.0,
            clip_id="c2",
            clip_url="local://c2",
            source="generative",
            licence="CC0",
            attribution="IncuBrix",
            is_ai_generated=True,
            reason_chosen="Abstract",
            relevance_score=4.5
        )
    ]

    metrics = relevance_scorer.evaluate_timeline(items)
    assert metrics["average_relevance_score"] >= 4.0
    assert metrics["high_relevance_percentage"] == 100.0
    assert metrics["scenes_rated_4_or_5"] == 2
