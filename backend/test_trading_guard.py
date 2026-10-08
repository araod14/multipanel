"""Offline regression tests; never connect to Docker, exchanges or a live database."""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.bootstrap import _apply_additive_columns
from app.database import Base, get_db
from app.models.audit_log import AuditLog
from app.models.bot_instance import BotInstance
from app.models.exchange_credential import ExchangeCredential
from app.models.user import User
from app.routers.user import router
from app.routers import admin
from app.schemas.bots import BotInstanceOut
from app.security.deps import get_current_admin, get_current_user
from app.services import bot_config, proxy, public_stats, reconciler, trading_guard, tradingview


class EvaluationTests(unittest.TestCase):
    def evaluate(self, values):
        pairs = {f"{i}/USDT" for i in range(len(values))}
        return trading_guard.evaluate(pairs, "5m", "binance", {
            (f"{i}/USDT", "5m"): value for i, value in enumerate(values)
        })

    def test_all_sell_including_strong_and_boundary(self):
        self.assertEqual(self.evaluate([-0.1, -0.5, -1])["reason"], "all_sell")

    def test_neutral_prevents_all_sell(self):
        self.assertEqual(self.evaluate([-0.8, 0])["reason"], "mixed")

    def test_strict_majority_and_neutral_denominator(self):
        self.assertEqual(self.evaluate([0.1, 0.8, 0, -0.3])["reason"], "mixed")
        self.assertEqual(self.evaluate([0.1, 0.8, 1, 0])["reason"], "majority_buy")

    def test_missing_even_with_buy_majority_cannot_resume(self):
        result = self.evaluate([0.4, 0.8, None])
        self.assertFalse(result["data_complete"])
        self.assertEqual(result["missing"], 1)

    def test_empty_list(self):
        self.assertFalse(self.evaluate([])["data_complete"])

    def test_defaults_and_validation(self):
        self.assertTrue(bot_config.effective({})["tradingview_guard_enabled"])
        self.assertFalse(bot_config.validate({"tradingview_guard_enabled": False}, dry_run=True)["tradingview_guard_enabled"])
        with self.assertRaises(bot_config.ConfigValidationError):
            bot_config.validate({"tradingview_guard_enabled": "false"}, dry_run=True)

    def test_additive_migration_is_repeatable_and_preserves_old_rows(self):
        engine = create_engine("sqlite://")
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE bot_instances (id INTEGER PRIMARY KEY)"))
            conn.execute(text("INSERT INTO bot_instances (id) VALUES (7)"))
        with patch("app.bootstrap.engine", engine):
            _apply_additive_columns()
            _apply_additive_columns()
        self.assertIn("tradingview_evaluation", {c["name"] for c in inspect(engine).get_columns("bot_instances")})
        with engine.connect() as conn:
            row = conn.execute(text("SELECT id, manual_paused, tradingview_paused FROM bot_instances")).one()
            self.assertEqual(tuple(row), (7, 0, 0))
        engine.dispose()


class ScannerTests(unittest.IsolatedAsyncioTestCase):
    async def fetch(self, data):
        client = AsyncMock()
        client.post.return_value = httpx.Response(200, json=data, request=httpx.Request("POST", "https://test/"))
        client.__aenter__.return_value = client
        with patch.object(tradingview.httpx, "AsyncClient", return_value=client):
            result = await tradingview.ratings(
                {"1h": {"BTC/USDT"}, "4h": {"ETH/USDT", "BTC/USDT"}}, exchange="kraken"
            )
        return result, client

    async def test_sparse_symbols_use_column_index_not_pair_order(self):
        result, client = await self.fetch({"data": [
            {"s": "KRAKEN:BTCUSDT", "d": [-0.2, 0.7]},
            {"s": "KRAKEN:ETHUSDT", "d": [-0.8, 0.3]},
        ]})
        self.assertEqual(result[("ETH/USDT", "4h")], 0.3)
        self.assertEqual(result[("BTC/USDT", "1h")], -0.2)
        self.assertEqual(result[("BTC/USDT", "4h")], 0.7)
        self.assertEqual(client.post.call_args.kwargs["json"]["columns"], ["Recommend.All|60", "Recommend.All|240"])

    async def test_invalid_and_short_rows_stay_missing(self):
        result, _ = await self.fetch({"data": [
            {"s": "KRAKEN:BTCUSDT", "d": [True]},
            {"s": "KRAKEN:ETHUSDT", "d": [0, "bad"]},
            {"s": [], "d": [0]}, "bad row",
        ]})
        self.assertIsNone(result[("BTC/USDT", "1h")])
        self.assertIsNone(result[("BTC/USDT", "4h")])
        self.assertIsNone(result[("ETH/USDT", "4h")])

    async def test_malformed_payload(self):
        result, _ = await self.fetch(["unexpected"])
        self.assertEqual(result, {})

    async def test_network_failure(self):
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.post.side_effect = httpx.ConnectError("offline")
        with patch.object(tradingview.httpx, "AsyncClient", return_value=client):
            self.assertEqual(await tradingview.ratings({"5m": {"BTC/USDT"}}), {})


class GuardIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)
        self.db = self.sessions()
        self.user = User(username="guard", email="guard@example.test", password_hash="unused")
        self.bot = BotInstance(user=self.user, container_name="cp-bot-guard", internal_hostname="cp-bot-guard",
                               db_path="unused", api_username="unused", api_password_enc="unused",
                               jwt_secret_enc="unused", ws_token_enc="unused", trading_enabled=True)
        self.db.add(self.bot)
        self.db.commit()
        self.state = "running"
        self.pairs = ["BTC/USDT", "ETH/USDT"]
        self.commands = []
        self.reject = None

        async def forward(instance, method, path, **kwargs):
            if method == "POST":
                self.commands.append(path)
                if path == self.reject:
                    return httpx.Response(503, json={"error": "unavailable"})
                if path in {"start", "pause", "stop"}:
                    self.state = {"start": "running", "pause": "paused", "stop": "stopped"}[path]
                return httpx.Response(200, json={"status": self.state})
            data = {"state": self.state} if path == "show_config" else {"whitelist": self.pairs}
            return httpx.Response(200, json=data)

        self.forward_patch = patch("app.services.proxy.forward", side_effect=forward)
        self.forward_patch.start()
        self.app = FastAPI()
        self.app.include_router(router, prefix="/api")
        self.app.include_router(admin.router, prefix="/api")
        async def test_db():
            return self.db

        async def test_user():
            return self.user

        async def test_admin():
            return SimpleNamespace(id=1)

        self.app.dependency_overrides[get_db] = test_db
        self.app.dependency_overrides[get_current_user] = test_user
        self.app.dependency_overrides[get_current_admin] = test_admin
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()
        self.forward_patch.stop()
        self.db.close()
        self.engine.dispose()
        public_stats.invalidate()

    def refresh(self):
        self.db.expire_all()
        self.db.refresh(self.bot)

    async def pass_with(self, values):
        ratings = {(p, "5m"): value for p, value in zip(self.pairs, values)}
        with patch.object(reconciler, "SessionLocal", self.sessions), \
             patch.object(reconciler, "_container_states", return_value={self.bot.container_name: "running"}), \
             patch.object(tradingview, "ratings", AsyncMock(return_value=ratings)):
            result = await reconciler.reconcile_once()
        self.refresh()
        return result

    async def test_sell_pause_missing_hold_and_majority_resume(self):
        self.assertEqual((await self.pass_with([-0.3, -0.8]))["paused"], 1)
        self.assertTrue(self.bot.tradingview_paused)
        self.assertTrue(self.bot.trading_enabled)
        await self.pass_with([None, 0.8])
        self.assertEqual(self.state, "paused")
        await self.pass_with([0.2, 0])  # one of two is not a majority
        self.assertEqual(self.state, "paused")
        await self.pass_with([0.2, 0.8])
        self.assertEqual(self.state, "running")
        self.assertFalse(self.bot.tradingview_paused)
        actions = self.db.scalars(select(AuditLog.action)).all()
        self.assertIn("tradingview.pause", actions)
        self.assertIn("tradingview.resume", actions)

    async def test_reboot_restores_automatic_pause_without_starting_entries(self):
        await self.pass_with([-0.8, -0.4])
        self.state = "stopped"
        self.commands.clear()
        await self.pass_with([None, None])
        self.assertEqual(self.commands, ["pause"])

    async def test_failed_pause_and_failed_resume_are_retried(self):
        self.reject = "pause"
        await self.pass_with([-0.2, -0.8])
        self.assertTrue(self.bot.tradingview_paused)
        self.assertTrue(self.bot.entry_pause_pending)
        self.reject = None
        await self.pass_with([None, None])
        self.assertEqual(self.state, "paused")
        self.reject = "start"
        await self.pass_with([0.3, 0.8])
        self.assertTrue(self.bot.entry_pause_managed)
        self.reject = None
        await self.pass_with([0, 0])
        self.assertEqual(self.state, "running")

    async def test_manual_stop_prevents_automatic_resume(self):
        await self.pass_with([-0.2, -0.8])
        response = await self.client.post("/api/me/bot/ft/stop")
        self.assertEqual(response.status_code, 200)
        await self.pass_with([0.4, 0.8])
        self.assertFalse(self.bot.trading_enabled)
        self.assertEqual(self.state, "stopped")

    async def test_manual_pause_survives_majority_and_reboot(self):
        await self.client.post("/api/me/bot/ft/pause")
        self.state = "stopped"
        await self.pass_with([0.4, 0.8])
        self.assertEqual(self.state, "paused")
        self.assertTrue(self.bot.manual_paused)

    async def test_start_does_not_override_guard(self):
        await self.pass_with([-0.3, -0.8])
        response = await self.client.post("/api/me/bot/ft/start")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.state, "paused")
        self.assertTrue(self.bot.trading_enabled)
        self.assertFalse(self.bot.manual_paused)

    async def test_force_entry_cannot_bypass_guard(self):
        await self.pass_with([-0.3, -0.8])
        response = await self.client.post("/api/me/bot/ft/forceenter", json={"pair": "BTC/USDT"})
        self.assertEqual(response.status_code, 409)
        self.assertNotIn("forceenter", self.commands)

    async def test_disable_guard_resumes_without_reprovisioning(self):
        await self.pass_with([-0.3, -0.8])
        with patch("app.services.provisioning.provision_bot") as provision:
            response = await self.client.put("/api/me/bot/config", json={"tradingview_guard_enabled": False})
        self.assertEqual(response.status_code, 200, response.text)
        provision.assert_not_called()
        self.assertEqual(self.state, "running")
        self.assertFalse(self.bot.tradingview_guard_enabled)

    async def test_disabling_preserves_manual_pause(self):
        await self.client.post("/api/me/bot/ft/pause")
        await self.client.put("/api/me/bot/config", json={"tradingview_guard_enabled": False})
        self.assertEqual(self.state, "paused")

    async def test_external_pause_is_not_owned_or_resumed(self):
        self.state = "paused"
        await self.pass_with([-0.3, -0.8])
        await self.pass_with([0.3, 0.8])
        self.assertEqual(self.state, "paused")
        self.assertEqual(self.commands, [])

    async def test_dynamic_list_and_full_denominator(self):
        self.pairs = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT"]
        await self.pass_with([-0.3] * 4)
        await self.pass_with([0.3, 0.3, 0, 0])
        self.assertEqual(self.state, "paused")
        self.pairs = ["SOL/USDT"]
        await self.pass_with([0.3])
        self.assertEqual(self.state, "running")
        self.assertEqual(self.bot.tradingview_evaluation["total"], 1)

    async def test_config_change_during_scan_discards_old_evaluation(self):
        async def scanner(*args, **kwargs):
            response = await self.client.put("/api/me/bot/config", json={"tradingview_guard_enabled": False})
            self.assertEqual(response.status_code, 200)
            return {(p, "5m"): -0.8 for p in self.pairs}
        with patch.object(reconciler, "SessionLocal", self.sessions), \
             patch.object(reconciler, "_container_states", return_value={self.bot.container_name: "running"}), \
             patch.object(tradingview, "ratings", side_effect=scanner):
            await reconciler.reconcile_once()
        self.refresh()
        self.assertFalse(self.bot.tradingview_paused)
        self.assertEqual(self.state, "running")

    async def test_status_and_public_config_expose_enabled_without_secrets(self):
        output = BotInstanceOut.model_validate(self.bot).model_dump()
        self.assertTrue(output["tradingview_guard_enabled"])
        self.assertNotIn("api_password_enc", output)
        block = public_stats._config_block(self.bot)
        self.assertTrue(block["tradingview_guard_enabled"])
        self.assertNotIn("container_name", block)

    async def test_admin_stop_clears_intent_and_start_respects_guard(self):
        await self.pass_with([-0.3, -0.8])
        with patch("app.services.provisioning.stop_bot") as stop:
            response = await self.client.post(f"/api/admin/users/{self.user.id}/bot/stop")
        self.assertEqual(response.status_code, 200)
        stop.assert_called_once()
        self.assertFalse(self.bot.trading_enabled)
        self.state = "stopped"
        with patch("app.services.provisioning.start_bot") as start:
            response = await self.client.post(f"/api/admin/users/{self.user.id}/bot/start")
        self.assertEqual(response.status_code, 200)
        start.assert_called_once()
        self.assertTrue(self.bot.trading_enabled)
        await self.pass_with([None, None])
        self.assertEqual(self.state, "paused")

    async def test_rejected_manual_start_does_not_change_intent(self):
        self.bot.trading_enabled = False
        self.db.commit()
        self.reject = "start"
        response = await self.client.post("/api/me/bot/ft/start")
        self.assertEqual(response.status_code, 503)
        self.assertFalse(self.bot.trading_enabled)

    async def test_lost_pause_response_keeps_ownership_and_can_resume(self):
        original_forward = proxy.forward.side_effect

        async def lose_response(instance, method, path, **kwargs):
            response = await original_forward(instance, method, path, **kwargs)
            if method == "POST" and path == "pause":
                raise proxy.ProxyError("response lost after applying pause")
            return response

        with patch("app.services.proxy.forward", side_effect=lose_response):
            await self.pass_with([-0.3, -0.8])
        self.assertEqual(self.state, "paused")
        self.assertTrue(self.bot.entry_pause_pending)
        await self.pass_with([None, None])
        self.assertFalse(self.bot.entry_pause_pending)
        await self.pass_with([0.3, 0.8])
        self.assertEqual(self.state, "running")

    async def test_manual_stop_while_scanner_runs_wins(self):
        async def scanner(*args, **kwargs):
            await self.client.post("/api/me/bot/ft/stop")
            return {(p, "5m"): 0.8 for p in self.pairs}
        with patch.object(reconciler, "SessionLocal", self.sessions), \
             patch.object(reconciler, "_container_states", return_value={self.bot.container_name: "running"}), \
             patch.object(tradingview, "ratings", side_effect=scanner):
            await reconciler.reconcile_once()
        self.refresh()
        self.assertFalse(self.bot.trading_enabled)
        self.assertEqual(self.state, "stopped")

    async def test_exchange_batches_and_timeframes_are_isolated(self):
        self.user.exchange_credential = ExchangeCredential(exchange_name="kraken", key_enc="unused", secret_enc="unused")
        second_user = User(username="second", email="second@example.test", password_hash="unused")
        second = BotInstance(user=second_user, container_name="cp-bot-second", internal_hostname="cp-bot-second",
                             db_path="unused", api_username="unused", api_password_enc="unused",
                             jwt_secret_enc="unused", ws_token_enc="unused", trading_enabled=True,
                             user_config_json={"timeframe": "4h"})
        second_user.exchange_credential = ExchangeCredential(exchange_name="binance", key_enc="unused", secret_enc="unused")
        self.db.add(second)
        self.db.commit()

        async def scanner(pairs_by_timeframe, *, exchange):
            value = -0.3 if exchange == "kraken" else 0.4
            return {(pair, tf): value for tf, pairs in pairs_by_timeframe.items() for pair in pairs}

        mock_scanner = AsyncMock(side_effect=scanner)
        with patch.object(reconciler, "SessionLocal", self.sessions), \
             patch.object(reconciler, "_container_states", return_value={self.bot.container_name: "running", second.container_name: "running"}), \
             patch.object(tradingview, "ratings", mock_scanner):
            await reconciler.reconcile_once()
        self.refresh()
        self.db.refresh(second)
        self.assertTrue(self.bot.tradingview_paused)
        self.assertFalse(second.tradingview_paused)
        self.assertEqual(self.bot.tradingview_evaluation["exchange"], "kraken")
        self.assertEqual(second.tradingview_evaluation["timeframe"], "4h")
        self.assertEqual(mock_scanner.await_count, 2)


if __name__ == "__main__":
    unittest.main()
