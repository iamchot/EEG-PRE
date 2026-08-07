from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models.user import Role, User
from app.schemas.system_health import ServiceHealth, ServiceHealthState, SystemHealth
from app.services.auth_service import create_access_token


def test_comfyui_is_available_only_when_system_stats_has_a_system_object():
    """Break caught: accepting a successful but malformed ComfyUI response as healthy."""
    from app.services.system_health import SystemHealthService

    async def scenario():
        async def comfy_get(url: str, timeout: float) -> httpx.Response:
            assert url == "http://comfy.test/system_stats"
            assert timeout == 2.0
            return httpx.Response(200, json={"system": {"os": "test"}})

        service = SystemHealthService(
            settings=SimpleNamespace(comfyui_url="http://comfy.test", gemini_api_key="placeholder", gemini_model="gemini-1.5-flash"),
            comfy_get=comfy_get,
            wall_clock=lambda: datetime(2026, 7, 29, tzinfo=UTC),
            monotonic_clock=lambda: 10.0,
        )

        health = await service.get_health()

        assert health.comfyui.state == "available"
        assert health.comfyui.latency_ms is not None

    asyncio.run(scenario())


def test_comfyui_malformed_system_stats_is_unavailable_without_exposing_the_body():
    """Break caught: malformed upstream JSON reaching an authenticated health response or leaking it."""
    from app.services.system_health import SystemHealthService

    async def scenario():
        async def comfy_get(_url: str, _timeout: float) -> httpx.Response:
            return httpx.Response(200, json=["provider secret: key-123"])

        service = SystemHealthService(
            settings=SimpleNamespace(comfyui_url="http://comfy.test", gemini_api_key="placeholder", gemini_model="gemini-1.5-flash"),
            comfy_get=comfy_get,
            wall_clock=lambda: datetime(2026, 7, 29, tzinfo=UTC),
            monotonic_clock=lambda: 10.0,
        )

        health = await service.get_health()

        assert health.comfyui.state == "unavailable"
        assert "key-123" not in health.comfyui.detail

    asyncio.run(scenario())


def test_placeholder_gemini_key_is_unavailable_without_making_a_network_probe():
    """Break caught: attempting a Gemini request with the example API key."""
    from app.services.system_health import SystemHealthService

    async def scenario():
        async def gemini_get(_model_name: str) -> object:
            raise AssertionError("placeholder keys must not reach Gemini")

        service = SystemHealthService(
            settings=SimpleNamespace(comfyui_url="http://comfy.test", gemini_api_key="YOUR_GEMINI_API_KEY_HERE", gemini_model="gemini-1.5-flash"),
            gemini_get=gemini_get,
            wall_clock=lambda: datetime(2026, 7, 29, tzinfo=UTC),
        )

        health = await service.get_health()

        assert health.gemini.state == "unavailable"
        assert health.gemini.detail == "บริการไม่พร้อมใช้งาน"

    asyncio.run(scenario())


def test_rate_limited_normalized_gemini_model_is_degraded():
    """Break caught: classifying Gemini rate limits as an unavailable configuration."""
    from app.services.system_health import SystemHealthService

    class RateLimited(Exception):
        code = 429

    async def scenario():
        requested_models = []

        async def gemini_get(model_name: str) -> object:
            requested_models.append(model_name)
            raise RateLimited("provider response must not be exposed")

        service = SystemHealthService(
            settings=SimpleNamespace(comfyui_url="http://comfy.test", gemini_api_key="live-key", gemini_model="models/gemini-1.5-flash"),
            gemini_get=gemini_get,
            wall_clock=lambda: datetime(2026, 7, 29, tzinfo=UTC),
            monotonic_clock=lambda: 10.0,
        )

        health = await service.get_health()

        assert requested_models == ["models/gemini-1.5-flash"]
        assert health.gemini.state == "degraded"
        assert health.gemini.detail == "บริการตอบสนองผิดปกติ"

    asyncio.run(scenario())


def test_external_health_probes_start_concurrently():
    """Break caught: a slow ComfyUI probe delaying the independent Gemini probe."""
    from app.services.system_health import SystemHealthService

    async def scenario():
        comfy_started, gemini_started, release = asyncio.Event(), asyncio.Event(), asyncio.Event()

        async def comfy_get(_url: str, _timeout: float) -> httpx.Response:
            comfy_started.set()
            await release.wait()
            return httpx.Response(200, json={"system": {}})

        async def gemini_get(_model_name: str) -> object:
            gemini_started.set()
            await release.wait()
            return object()

        service = SystemHealthService(
            settings=SimpleNamespace(comfyui_url="http://comfy.test", gemini_api_key="live-key", gemini_model="gemini-1.5-flash"),
            comfy_get=comfy_get,
            gemini_get=gemini_get,
            wall_clock=lambda: datetime(2026, 7, 29, tzinfo=UTC),
        )
        request = asyncio.create_task(service.get_health())
        await comfy_started.wait()
        try:
            await asyncio.sleep(0)
            assert gemini_started.is_set()
        finally:
            release.set()
            await request

    asyncio.run(scenario())


def test_health_results_are_cached_for_30_seconds_then_refreshed_with_an_injected_clock():
    """Verify Gemini is cached for 30s TTL while ComfyUI and Muse are re-observed freshly."""
    from app.schemas.muse import MuseBridgeState
    from app.services.system_health import SystemHealthService

    async def scenario():
        clock = [100.0]
        comfy_calls = 0
        gemini_calls = 0
        muse_state = [MuseBridgeState.connected]

        async def comfy_get(_url: str, _timeout: float) -> httpx.Response:
            nonlocal comfy_calls
            comfy_calls += 1
            if comfy_calls > 1:
                return httpx.Response(500)
            return httpx.Response(200, json={"system": {}})

        async def gemini_get(_model: str):
            nonlocal gemini_calls
            gemini_calls += 1
            return {"name": "models/gemini-1.5-flash"}

        async def muse_snapshot() -> MuseBridgeState:
            return muse_state[0]

        service = SystemHealthService(
            settings=SimpleNamespace(comfyui_url="http://comfy.test", gemini_api_key="validkey", gemini_model="gemini-1.5-flash"),
            comfy_get=comfy_get,
            gemini_get=gemini_get,
            muse_snapshot=muse_snapshot,
            wall_clock=lambda: datetime(2026, 7, 29, tzinfo=UTC),
            monotonic_clock=lambda: clock[0],
        )

        # First call: all services checked
        h1 = await service.get_health()
        assert comfy_calls == 1
        assert gemini_calls == 1
        assert h1.comfyui.state.value == "available"
        assert h1.gemini.state.value == "available"
        assert h1.muse.state.value == "available"

        # Second call inside TTL (clock unchanged): ComfyUI & Muse turn unavailable immediately, Gemini remains cached
        muse_state[0] = MuseBridgeState.idle
        h2 = await service.get_health()
        assert comfy_calls == 2
        assert gemini_calls == 1  # Gemini cached
        assert h2.comfyui.state.value == "unavailable"  # Fresh observation
        assert h2.gemini.state.value == "available"
        assert h2.muse.state.value == "unavailable"  # Fresh observation

        # Third call after 30s TTL: Gemini re-checked
        clock[0] += 30.0
        h3 = await service.get_health()
        assert comfy_calls == 3
        assert gemini_calls == 2

    asyncio.run(scenario())


def test_muse_health_comes_from_the_live_bridge_snapshot():
    """Break caught: reporting a persisted device as connected when the managed bridge is not live."""
    from app.schemas.muse import MuseBridgeState
    from app.services.system_health import SystemHealthService

    async def scenario():
        async def muse_snapshot() -> MuseBridgeState:
            return MuseBridgeState.connected

        service = SystemHealthService(
            settings=SimpleNamespace(comfyui_url="http://comfy.test", gemini_api_key="placeholder", gemini_model="gemini-1.5-flash"),
            muse_snapshot=muse_snapshot,
            wall_clock=lambda: datetime(2026, 7, 29, tzinfo=UTC),
        )

        health = await service.get_health()

        assert health.muse.state == "available"
        assert health.muse.detail == "บริการพร้อมใช้งาน"

    asyncio.run(scenario())


def test_system_health_endpoint_requires_authentication_and_returns_the_service_response(monkeypatch):
    """Break caught: exposing dependency health to an anonymous caller."""
    from app.routers import system

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        role = Role(name="user")
        db.add(role)
        db.flush()
        user = User(username="health-user", email="health@example.com", password_hash="x", role_id=role.id)
        db.add(user)
        db.commit()
        token = create_access_token(user.id, "user")

    def override_db():
        with factory() as db:
            yield db

    checked_at = datetime(2026, 7, 29, tzinfo=UTC)
    result = SystemHealth(
        api=ServiceHealth(state=ServiceHealthState.available, detail="บริการพร้อมใช้งาน", checked_at=checked_at, latency_ms=0),
        comfyui=ServiceHealth(state=ServiceHealthState.unavailable, detail="บริการไม่พร้อมใช้งาน", checked_at=checked_at),
        gemini=ServiceHealth(state=ServiceHealthState.degraded, detail="บริการตอบสนองผิดปกติ", checked_at=checked_at),
        muse=ServiceHealth(state=ServiceHealthState.unavailable, detail="บริการไม่พร้อมใช้งาน", checked_at=checked_at),
    )

    class HealthService:
        async def get_health(self) -> SystemHealth:
            return result

    monkeypatch.setattr(system, "system_health_service", HealthService())
    app = FastAPI()
    app.include_router(system.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        assert client.get("/api/v1/system/health").status_code == 401
        response = client.get("/api/v1/system/health", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["gemini"] == {
        "state": "degraded",
        "detail": "บริการตอบสนองผิดปกติ",
        "checked_at": "2026-07-29T00:00:00Z",
        "latency_ms": None,
    }
    engine.dispose()


def test_gemini_probe_timeout_is_degraded_without_provider_detail():
    """Break caught: allowing a Gemini verification call to exceed its health-check timeout."""
    from app.services.system_health import SystemHealthService

    async def scenario():
        async def gemini_get(_model_name: str) -> object:
            await asyncio.Event().wait()

        async def comfy_get(_url: str, _timeout: float) -> httpx.Response:
            return httpx.Response(200, json={"system": {}})

        service = SystemHealthService(
            settings=SimpleNamespace(
                comfyui_url="http://comfy.test",
                gemini_api_key="live-key",
                gemini_model="gemini-1.5-flash",
                health_gemini_timeout_seconds=0.01,
            ),
            comfy_get=comfy_get,
            gemini_get=gemini_get,
            wall_clock=lambda: datetime(2026, 7, 29, tzinfo=UTC),
        )

        health = await asyncio.wait_for(service.get_health(), timeout=0.1)

        assert health.gemini.state == "degraded"
        assert health.gemini.detail == "บริการตอบสนองผิดปกติ"

    asyncio.run(scenario())


def test_concurrent_health_requests_share_one_inflight_probe():
    """Break caught: concurrent callers each starting their own dependency probes."""
    from app.services.system_health import SystemHealthService

    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()
        calls = 0

        async def comfy_get(_url: str, _timeout: float) -> httpx.Response:
            nonlocal calls
            calls += 1
            started.set()
            await release.wait()
            return httpx.Response(200, json={"system": {}})

        service = SystemHealthService(
            settings=SimpleNamespace(comfyui_url="http://comfy.test", gemini_api_key="placeholder", gemini_model="gemini-1.5-flash"),
            comfy_get=comfy_get,
            wall_clock=lambda: datetime(2026, 7, 29, tzinfo=UTC),
        )
        first = asyncio.create_task(service.get_health())
        await started.wait()
        second = asyncio.create_task(service.get_health())
        try:
            await asyncio.sleep(0)
            assert calls == 1
        finally:
            release.set()
        first_health, second_health = await asyncio.gather(first, second)
        assert first_health.comfyui.state == second_health.comfyui.state == "available"

    asyncio.run(scenario())


def test_gemini_provider_outage_is_degraded_but_an_auth_error_is_unavailable():
    """Break caught: treating a transient provider outage as a bad Gemini configuration."""
    from app.services.system_health import SystemHealthService

    class ProviderUnavailable(Exception):
        code = 503

    class AuthenticationFailed(Exception):
        code = 401

    async def scenario():
        errors = iter((ProviderUnavailable(), AuthenticationFailed()))

        async def gemini_get(_model_name: str) -> object:
            raise next(errors)

        async def comfy_get(_url: str, _timeout: float) -> httpx.Response:
            return httpx.Response(200, json={"system": {}})

        service = SystemHealthService(
            settings=SimpleNamespace(comfyui_url="http://comfy.test", gemini_api_key="live-key", gemini_model="gemini-1.5-flash", health_cache_ttl_seconds=0),
            comfy_get=comfy_get,
            gemini_get=gemini_get,
            wall_clock=lambda: datetime(2026, 7, 29, tzinfo=UTC),
        )

        assert (await service.get_health()).gemini.state == "degraded"
        assert (await service.get_health()).gemini.state == "unavailable"

    asyncio.run(scenario())


def test_live_muse_snapshot_reports_an_active_scan_and_cleans_its_job():
    """Break caught: active managed scans being reported as unavailable by health."""
    from app.schemas.muse import MuseBridgeState
    from app.services.muse_bridge_manager import ManagedMuseBridgeManager
    from app.services.system_health import SystemHealthService

    async def scenario():
        scan_started, finish_scan = asyncio.Event(), asyncio.Event()

        class Scanner:
            async def scan(self, *, timeout: float):
                assert timeout == 30.0
                scan_started.set()
                await finish_scan.wait()
                return []

        manager = ManagedMuseBridgeManager(
            scanner=Scanner(),
            settings=SimpleNamespace(muse_scan_timeout_seconds=30.0),
        )
        await manager.start_scan(actor_id=1)
        await scan_started.wait()
        assert await manager.health_snapshot() is MuseBridgeState.scanning

        async def comfy_get(_url: str, _timeout: float) -> httpx.Response:
            return httpx.Response(200, json={"system": {}})

        health = await SystemHealthService(
            settings=SimpleNamespace(comfyui_url="http://comfy.test", gemini_api_key="placeholder", gemini_model="gemini-1.5-flash"),
            comfy_get=comfy_get,
            muse_snapshot=manager.health_snapshot,
            wall_clock=lambda: datetime(2026, 7, 29, tzinfo=UTC),
        ).get_health()
        assert health.muse.state == "checking"

        finish_scan.set()
        await asyncio.sleep(0)
        await manager.shutdown()
        assert manager._scan_jobs == {}

    asyncio.run(scenario())


def test_production_gemini_timeout_cancels_the_provider_request_before_returning(monkeypatch):
    """Break caught: a timed-out production Gemini probe continuing after health has returned."""
    from app.services import system_health

    async def scenario():
        request_started, request_cancelled, request_finished, client_closed = (
            asyncio.Event(),
            asyncio.Event(),
            asyncio.Event(),
            asyncio.Event(),
        )

        class BlockingClient:
            def __init__(self, *, timeout: float):
                assert timeout == 0.01

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                client_closed.set()
                return False

            async def get(self, url: str, *, params: dict[str, str]):
                assert url == "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash"
                assert params == {"key": "live-key"}
                request_started.set()
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    request_cancelled.set()
                    raise
                finally:
                    request_finished.set()

        monkeypatch.setattr(system_health.httpx, "AsyncClient", BlockingClient)

        async def comfy_get(_url: str, _timeout: float) -> httpx.Response:
            return httpx.Response(200, json={"system": {}})

        service = system_health.SystemHealthService(
            settings=SimpleNamespace(
                comfyui_url="http://comfy.test",
                gemini_api_key="live-key",
                gemini_model="gemini-1.5-flash",
                health_gemini_timeout_seconds=0.01,
            ),
            comfy_get=comfy_get,
            wall_clock=lambda: datetime(2026, 7, 29, tzinfo=UTC),
        )

        health = await asyncio.wait_for(service.get_health(), timeout=0.1)

        assert request_started.is_set()
        assert request_cancelled.is_set()
        assert request_finished.is_set()
        assert client_closed.is_set()
        assert health.gemini.state == "degraded"

    asyncio.run(scenario())


def test_production_gemini_http_rate_limit_is_degraded(monkeypatch):
    """Break caught: an actual HTTP 429 being classified as a bad Gemini configuration."""
    from app.services import system_health

    async def scenario():
        class RateLimitedClient:
            def __init__(self, *, timeout: float):
                assert timeout == 8.0

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return False

            async def get(self, url: str, *, params: dict[str, str]) -> httpx.Response:
                return httpx.Response(429, request=httpx.Request("GET", url, params=params))

        monkeypatch.setattr(system_health.httpx, "AsyncClient", RateLimitedClient)

        async def comfy_get(_url: str, _timeout: float) -> httpx.Response:
            return httpx.Response(200, json={"system": {}})

        health = await system_health.SystemHealthService(
            settings=SimpleNamespace(comfyui_url="http://comfy.test", gemini_api_key="live-key", gemini_model="gemini-1.5-flash"),
            comfy_get=comfy_get,
            wall_clock=lambda: datetime(2026, 7, 29, tzinfo=UTC),
        ).get_health()

        assert health.gemini.state == "degraded"
        assert health.gemini.detail == "บริการตอบสนองผิดปกติ"

    asyncio.run(scenario())
