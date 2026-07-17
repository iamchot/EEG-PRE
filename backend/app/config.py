from __future__ import annotations
from functools import lru_cache
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

    # EEG
    raw_eeg_dir: str = "./recordings"
    baseline_seconds: int = 20
    accepted_recording_seconds: int = 30
    wall_clock_timeout_seconds: int = 120
    resume_stable_seconds: int = 2

    # Emotion Classification
    emotion_rule_version: str = "v1.0"


@lru_cache
def get_settings() -> Settings:
    return Settings()
