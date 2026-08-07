from __future__ import annotations
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",          # ignore DB_HOST, DB_PORT, etc. extra fields
    )

    # App
    app_env: str = "development"
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

    # Database
    database_url: str = "mysql+pymysql://dreamcomic:dreamcomic_pass@localhost:3306/dreamcomic"

    # AI
    gemini_api_key: str = "YOUR_GEMINI_API_KEY_HERE"
    gemini_model: str = "gemini-1.5-flash"

    # ComfyUI
    comfyui_url: str = "http://127.0.0.1:8188"
    comfyui_output_dir: str = "./comfyui_outputs"

    # Authenticated dependency health
    health_comfyui_timeout_seconds: float = 2.0
    health_gemini_timeout_seconds: float = 8.0
    health_cache_ttl_seconds: float = 30.0

    # EEG
    raw_eeg_dir: str = "./recordings"
    baseline_seconds: int = 20
    accepted_recording_seconds: int = 30
    wall_clock_timeout_seconds: int = 120
    resume_stable_seconds: int = 2

    # Dataset collection (Muse 2)
    collection_raw_dir: str = "./collection_data"
    collection_stimulus_dir: str = "./collection_stimuli"
    collection_lock_dir: str = "./collection_locks"
    collection_sampling_rate_hz: int = 256
    collection_sampling_tolerance_hz: int = 8
    collection_baseline_wall_seconds: int = 60
    collection_baseline_min_clean_seconds: int = 30
    collection_rest_min_seconds: int = 10
    collection_rest_max_seconds: int = 15
    collection_stimulus_finish_grace_seconds: float = Field(default=5.0, ge=0, le=10)

    # Muse BLE
    muse_scan_timeout_seconds: float = 30.0
    muse_connect_timeout_seconds: float = 45.0
    muse_lsl_timeout_seconds: float = 10.0

    # Emotion Classification
    emotion_rule_version: str = "v1.0"


@lru_cache
def get_settings() -> Settings:
    return Settings()
