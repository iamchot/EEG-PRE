from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from datetime import datetime
from types import SimpleNamespace

import httpx

from app.config import get_settings
from app.schemas.muse import MuseBridgeState
from app.schemas.system_health import ServiceHealth, ServiceHealthState, SystemHealth
from app.services.muse_bridge_manager import managed_muse_bridge_manager

_AVAILABLE = "บริการพร้อมใช้งาน"
_UNAVAILABLE = "บริการไม่พร้อมใช้งาน"
_UNKNOWN = "ยังไม่ได้ตรวจสอบบริการ"
_DEGRADED = "บริการตอบสนองผิดปกติ"
_CACHE_TTL_SECONDS = 30.0


class SystemHealthService:
    def __init__(
        self,
        *,
        settings: SimpleNamespace | None = None,
        comfy_get: Callable[[str, float], Awaitable[httpx.Response]] | None = None,
        gemini_get: Callable[[str], Awaitable[object]] | None = None,
        muse_snapshot: Callable[[], Awaitable[MuseBridgeState]] | None = None,
        wall_clock: Callable[[], datetime] = datetime.now,
        monotonic_clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._settings = settings or get_settings()
        self._comfy_get = comfy_get or self._get_comfyui
        self._gemini_get = gemini_get
        self._muse_snapshot = muse_snapshot or managed_muse_bridge_manager.health_snapshot
        self._wall_clock = wall_clock
        self._monotonic_clock = monotonic_clock
        self._cached_gemini: ServiceHealth | None = None
        self._gemini_checked_at: float | None = None
        self._cache_lock = asyncio.Lock()

    async def get_health(self) -> SystemHealth:
        async with self._cache_lock:
            checked_at = self._wall_clock()
            now = self._monotonic_clock()
            cache_ttl = float(getattr(self._settings, "health_cache_ttl_seconds", _CACHE_TTL_SECONDS))

            if (
                self._cached_gemini is None
                or self._gemini_checked_at is None
                or now - self._gemini_checked_at >= cache_ttl
            ):
                gemini_health = await self._check_gemini(checked_at)
                self._cached_gemini = gemini_health
                self._gemini_checked_at = now
            else:
                gemini_health = self._cached_gemini.model_copy(deep=True)

            api = ServiceHealth(
                state=ServiceHealthState.available,
                detail=_AVAILABLE,
                checked_at=checked_at,
                latency_ms=0,
            )
            comfyui, muse = await asyncio.gather(
                self._check_comfyui(checked_at),
                self._check_muse(checked_at),
            )

            return SystemHealth(api=api, comfyui=comfyui, gemini=gemini_health, muse=muse)

    async def _collect_health(self) -> SystemHealth:
        checked_at = self._wall_clock()
        api = ServiceHealth(state=ServiceHealthState.available, detail=_AVAILABLE, checked_at=checked_at, latency_ms=0)
        comfyui, gemini, muse = await asyncio.gather(
            self._check_comfyui(checked_at),
            self._check_gemini(checked_at),
            self._check_muse(checked_at),
        )
        return SystemHealth(api=api, comfyui=comfyui, gemini=gemini, muse=muse)

    async def _check_comfyui(self, checked_at: datetime) -> ServiceHealth:
        started = self._monotonic_clock()
        try:
            timeout = float(getattr(self._settings, "health_comfyui_timeout_seconds", 2.0))
            response = await self._comfy_get(f"{self._settings.comfyui_url.rstrip('/')}/system_stats", timeout)
            payload = response.json()
            valid = response.status_code == 200 and isinstance(payload, dict) and isinstance(payload.get("system"), dict)
        except (httpx.HTTPError, ValueError, TimeoutError, AttributeError):
            valid = False
        latency_ms = max(0, round((self._monotonic_clock() - started) * 1000))
        return ServiceHealth(
            state=ServiceHealthState.available if valid else ServiceHealthState.unavailable,
            detail=_AVAILABLE if valid else _UNAVAILABLE,
            checked_at=checked_at,
            latency_ms=latency_ms,
        )

    async def _get_comfyui(self, url: str, timeout: float) -> httpx.Response:
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.get(url)

    async def _check_gemini(self, checked_at: datetime) -> ServiceHealth:
        key = self._settings.gemini_api_key.strip()
        model = self._settings.gemini_model.strip().removeprefix("models/")
        if self._is_placeholder_key(key) or not model:
            return ServiceHealth(state=ServiceHealthState.unavailable, detail=_UNAVAILABLE, checked_at=checked_at)
        started = self._monotonic_clock()
        try:
            timeout = float(getattr(self._settings, "health_gemini_timeout_seconds", 8.0))
            model_name = f"models/{model}"
            verification = self._gemini_get(model_name) if self._gemini_get is not None else self._get_gemini_model(model_name, timeout)
            await asyncio.wait_for(verification, timeout=timeout)
        except Exception as exc:
            state = ServiceHealthState.degraded if self._is_transient_gemini_error(exc) else ServiceHealthState.unavailable
        else:
            state = ServiceHealthState.available
        latency_ms = max(0, round((self._monotonic_clock() - started) * 1000))
        return ServiceHealth(
            state=state,
            detail=_AVAILABLE if state is ServiceHealthState.available else (_DEGRADED if state is ServiceHealthState.degraded else _UNAVAILABLE),
            checked_at=checked_at,
            latency_ms=latency_ms,
        )

    @staticmethod
    def _is_placeholder_key(key: str) -> bool:
        normalized = key.casefold()
        return not normalized or normalized in {"placeholder", "change-me", "changeme"} or normalized.startswith("your_")

    @staticmethod
    def _is_transient_gemini_error(exc: Exception) -> bool:
        if isinstance(exc, (httpx.NetworkError, httpx.TimeoutException, OSError, TimeoutError)):
            return True
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code == 429 or 500 <= exc.response.status_code < 600
        code = str(getattr(exc, "code", "")).casefold().replace("_", "")
        return (
            code == "429"
            or (code.isdigit() and 500 <= int(code) < 600)
            or any(marker in code for marker in ("resourceexhausted", "unavailable", "deadlineexceeded", "internal"))
        )

    async def _get_gemini_model(self, model_name: str, timeout: float) -> object:
        url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}"
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, params={"key": self._settings.gemini_api_key})
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("name") != model_name:
            raise ValueError("Gemini returned a different or malformed model")
        return payload

    async def _check_muse(self, checked_at: datetime) -> ServiceHealth:
        started = self._monotonic_clock()
        try:
            state = await self._muse_snapshot()
        except Exception:
            health_state = ServiceHealthState.degraded
        else:
            if state is MuseBridgeState.connected:
                health_state = ServiceHealthState.available
            elif state in {MuseBridgeState.scanning, MuseBridgeState.starting_bridge, MuseBridgeState.connecting_bluetooth, MuseBridgeState.waiting_for_lsl}:
                health_state = ServiceHealthState.checking
            elif state is MuseBridgeState.failed:
                health_state = ServiceHealthState.degraded
            else:
                health_state = ServiceHealthState.unavailable
        latency_ms = max(0, round((self._monotonic_clock() - started) * 1000))
        detail = {
            ServiceHealthState.available: _AVAILABLE,
            ServiceHealthState.degraded: _DEGRADED,
            ServiceHealthState.unavailable: _UNAVAILABLE,
            ServiceHealthState.checking: _UNKNOWN,
        }[health_state]
        return ServiceHealth(state=health_state, detail=detail, checked_at=checked_at, latency_ms=latency_ms)
