from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Dict, Any, Literal

class SceneInput(BaseModel):
    text: str = Field(..., description="Narration text for this scene")
    visual_hint: Optional[str] = Field(None, description="Visual guidance or hint for footage selection")

class CaptionsConfig(BaseModel):
    burn_in: bool = Field(True, description="Whether to burn captions directly into the video")
    srt: bool = Field(True, description="Whether to output a standalone .srt captions file")

class BrollJobRequest(BaseModel):
    audio_url: Optional[str] = Field(None, description="URL to an audio file (mp3, wav, m4a, up to 10 mins)")
    script: Optional[str] = Field(None, description="Plain text script to convert to voiceover")
    scenes: Optional[List[SceneInput]] = Field(None, description="Optional IncuBrix pre-split scene list with visual hints")
    voice: Optional[str] = Field("en-IN-female", description="Voice identifier for TTS if script or scenes provided")
    aspect_ratios: List[str] = Field(default_factory=lambda: ["16:9", "9:16"], description="Target aspect ratios (16:9, 9:16, 1:1)")
    style: Optional[str] = Field("bright, modern, real-world footage", description="Stylistic direction for B-roll selection")
    avoid: Optional[List[str]] = Field(default_factory=list, description="List of visual content tags to avoid")
    captions: Optional[CaptionsConfig] = Field(default_factory=CaptionsConfig, description="Captions configuration")
    callback_url: Optional[str] = Field(None, description="Optional webhook URL called upon job completion")

    @model_validator(mode="after")
    def validate_one_input_present(self):
        has_audio = bool(self.audio_url and self.audio_url.strip())
        has_script = bool(self.script and self.script.strip())
        has_scenes = bool(self.scenes and len(self.scenes) > 0)
        
        if not (has_audio or has_script or has_scenes):
            raise ValueError("At least one input must be provided: audio_url, script, or scenes.")
        return self

class ClipSwapRequest(BaseModel):
    scene_index: int = Field(..., description="Zero-based index of the scene to swap")
    new_query: Optional[str] = Field(None, description="New query or visual hint for the replacement clip")
    preferred_source: Optional[Literal["stock", "generative"]] = Field(None, description="Forced footage source: 'stock' or 'generative'")
    specific_clip_url: Optional[str] = Field(None, description="Direct URL of a custom replacement clip")

class SceneTimelineItem(BaseModel):
    scene_index: int
    text: str
    start_time: float
    end_time: float
    duration: float
    clip_id: str
    clip_url: str
    source: str
    licence: str
    attribution: str
    is_ai_generated: bool
    reason_chosen: str
    relevance_score: float
    visual_hint: Optional[str] = None
    crop_info: Optional[Dict[str, Any]] = None

class TimelineData(BaseModel):
    scenes: List[SceneTimelineItem]
    total_duration: float
    scene_count: int

class ManifestData(BaseModel):
    app_version: str
    job_id: str
    models: Dict[str, str]
    providers: Dict[str, str]
    settings: Dict[str, Any]
    seed: int
    timings: Dict[str, float]
    cost_estimate: Dict[str, float]
    warnings: List[str]
    licence_rights_summary: Dict[str, Any]

class JobStatusResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "succeeded", "failed"]
    progress: int = Field(..., ge=0, le=100)
    stage: str
    created_at: str
    updated_at: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    timings: Optional[Dict[str, float]] = None

class JobAcceptedResponse(BaseModel):
    job_id: str
    status: str = "queued"
    created_at: str
    message: str = "Job accepted for processing"
