"""Tests for MCP Circuit Breaker Tools — states, failure tracking, recovery."""
import json, pytest, os, sys, time
from unittest.mock import patch
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.server import MCPCircuitBreakerToolsServer, TOOL_DEFS
from src.breaker_engine import CircuitBreakerEngine

class TestToolDefs:
    def test_names(self):
        for t in TOOL_DEFS: assert "name" in t and len(t["name"])>0
    def test_descs(self):
        for t in TOOL_DEFS: assert "description" in t and len(t["description"])>10
    def test_schema(self):
        for t in TOOL_DEFS: assert "inputSchema" in t and t["inputSchema"]["type"]=="object"
    def test_count(self):
        assert len(TOOL_DEFS)==13
    def test_required(self):
        names={t["name"] for t in TOOL_DEFS}
        expected={"create","record_success","record_failure","can_execute","get_state","force_open","force_close","reset","configure","get_history","get_stats","simulate","list_breakers"}
        assert names==expected

class TestManifest:
    def test_manifest(self):
        s=MCPCircuitBreakerToolsServer();m=s.manifest()
        assert m["server"]["name"]=="mcp-circuit-breaker-tools"
        assert len(m["tools"])==13

class TestStates:
    def test_closed_initially(self):
        b=CircuitBreakerEngine.create_breaker()
        assert b["state"]=="closed"
    def test_open_on_threshold(self):
        b=CircuitBreakerEngine.create_breaker(failure_threshold=3)
        for _ in range(3):
            CircuitBreakerEngine.record_failure(b,"test")
        assert b["state"]=="open"
    def test_half_open_after_timeout(self):
        b=CircuitBreakerEngine.create_breaker(failure_threshold=1,recovery_timeout=0)
        CircuitBreakerEngine.record_failure(b,"test")
        assert b["state"]=="open"
        time.sleep(0.01)
        r=CircuitBreakerEngine.can_execute(b,"test")
        assert r["state"]=="half_open"
    def test_close_after_half_open_success(self):
        b=CircuitBreakerEngine.create_breaker(failure_threshold=1,recovery_timeout=0,half_open_max=2)
        CircuitBreakerEngine.record_failure(b,"test")
        time.sleep(0.01)
        CircuitBreakerEngine.can_execute(b,"test")
        CircuitBreakerEngine.record_success(b,"test")
        CircuitBreakerEngine.record_success(b,"test")
        assert b["state"]=="closed"

class TestCanExecute:
    def test_closed_allowed(self):
        b=CircuitBreakerEngine.create_breaker()
        r=CircuitBreakerEngine.can_execute(b,"test")
        assert r["allowed"] is True
    def test_open_blocked(self):
        b=CircuitBreakerEngine.create_breaker(failure_threshold=1)
        CircuitBreakerEngine.record_failure(b,"test")
        r=CircuitBreakerEngine.can_execute(b,"test")
        assert r["allowed"] is False

class TestForceOpenClose:
    def test_force_open(self):
        b=CircuitBreakerEngine.create_breaker()
        r=CircuitBreakerEngine.force_open(b,"test")
        assert r["new_state"]=="open"
    def test_force_close(self):
        b=CircuitBreakerEngine.create_breaker()
        CircuitBreakerEngine.force_open(b,"test")
        r=CircuitBreakerEngine.force_close(b,"test")
        assert r["new_state"]=="closed"

class TestReset:
    def test_reset(self):
        b=CircuitBreakerEngine.create_breaker()
        CircuitBreakerEngine.record_failure(b,"test")
        r=CircuitBreakerEngine.reset(b,"test")
        assert r["reset"]["state"] in ("closed","open")
        assert b["state"]=="closed"

class TestConfigure:
    def test_update(self):
        b=CircuitBreakerEngine.create_breaker(failure_threshold=5)
        r=CircuitBreakerEngine.configure(b,failure_threshold=10)
        assert r["new"]["failure_threshold"]==10
        assert r["old"]["failure_threshold"]==5

class TestHistory:
    def test_basic(self):
        b=CircuitBreakerEngine.create_breaker()
        CircuitBreakerEngine.record_success(b,"test")
        CircuitBreakerEngine.record_failure(b,"test")
        r=CircuitBreakerEngine.get_history(b,"test")
        assert r["count"]==2

class TestStats:
    def test_basic(self):
        b=CircuitBreakerEngine.create_breaker()
        CircuitBreakerEngine.record_success(b,"test")
        CircuitBreakerEngine.record_failure(b,"test")
        r=CircuitBreakerEngine.get_stats(b,"test")
        assert r["total_calls"]==2
        assert r["total_failures"]==1

class TestSimulate:
    def test_all_success(self):
        b=CircuitBreakerEngine.create_breaker(failure_threshold=3)
        r=CircuitBreakerEngine.simulate(b,"test",[{"outcome":"success"},{"outcome":"success"}])
        assert r["total_calls"]==2
    def test_trip(self):
        b=CircuitBreakerEngine.create_breaker(failure_threshold=3)
        r=CircuitBreakerEngine.simulate(b,"test",[{"outcome":"failure"},{"outcome":"failure"},{"outcome":"failure"}])
        assert any(res["state"]=="open" for res in r["results"])

class TestDispatch:
    def test_unknown(self):
        s=MCPCircuitBreakerToolsServer();assert "error" in json.loads(s.handle_tool_call("nope",{}))
    def test_missing(self):
        s=MCPCircuitBreakerToolsServer();assert "error" in json.loads(s.handle_tool_call("create",{}))
    def test_create_dispatch(self):
        s=MCPCircuitBreakerToolsServer()
        r=json.loads(s.handle_tool_call("create",{"name":"test"}))
        assert r["created"] is True

class TestSTDIO:
    def test_manifest_flag(self,capsys):
        from src.server import main
        with patch("sys.argv",["server","--manifest"]):main()
        parsed=json.loads(capsys.readouterr().out.strip())
        assert parsed["server"]["name"]=="mcp-circuit-breaker-tools"
