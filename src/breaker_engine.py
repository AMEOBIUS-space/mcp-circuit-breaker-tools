"""Circuit breaker engine — zero dependencies.

Uses only Python stdlib (time, json, collections).
Provides circuit breaker pattern with failure tracking, states, recovery.
"""
import time
import json
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional


class CircuitBreakerEngine:
    """Circuit breaker operations with zero external dependencies."""

    @staticmethod
    def create_breaker(failure_threshold: int = 5, recovery_timeout: float = 60.0, half_open_max: int = 3) -> Dict:
        """Create a new circuit breaker."""
        return {
            "state": "closed",
            "failure_count": 0,
            "success_count": 0,
            "failure_threshold": failure_threshold,
            "recovery_timeout": recovery_timeout,
            "half_open_max": half_open_max,
            "half_open_count": 0,
            "last_failure_time": None,
            "opened_at": None,
            "history": deque(maxlen=100),
            "total_calls": 0,
            "total_failures": 0,
            "total_successes": 0,
            "total_rejections": 0,
        }

    @staticmethod
    def record_success(breaker: Dict, name: str = "default") -> Dict:
        """Record a successful call."""
        breaker["total_calls"] += 1
        breaker["total_successes"] += 1
        breaker["history"].append({"event": "success", "timestamp": time.time()})

        if breaker["state"] == "half_open":
            breaker["success_count"] += 1
            breaker["half_open_count"] += 1
            if breaker["success_count"] >= breaker["half_open_max"]:
                breaker["state"] = "closed"
                breaker["failure_count"] = 0
                breaker["success_count"] = 0
                breaker["half_open_count"] = 0
                breaker["opened_at"] = None
                return {"success": True, "name": name, "state": "closed", "event": "recovered", "message": "Circuit breaker closed (recovered)"}
        elif breaker["state"] == "closed":
            breaker["failure_count"] = 0

        return {"success": True, "name": name, "state": breaker["state"], "event": "success"}

    @staticmethod
    def record_failure(breaker: Dict, name: str = "default", error: str = "unknown") -> Dict:
        """Record a failed call."""
        breaker["total_calls"] += 1
        breaker["total_failures"] += 1
        breaker["failure_count"] += 1
        breaker["last_failure_time"] = time.time()
        breaker["history"].append({"event": "failure", "timestamp": time.time(), "error": error})

        if breaker["state"] == "closed":
            if breaker["failure_count"] >= breaker["failure_threshold"]:
                breaker["state"] = "open"
                breaker["opened_at"] = time.time()
                return {"success": True, "name": name, "state": "open", "event": "tripped", "message": "Circuit breaker opened (failure threshold reached)"}
        elif breaker["state"] == "half_open":
            breaker["state"] = "open"
            breaker["opened_at"] = time.time()
            breaker["half_open_count"] = 0
            breaker["success_count"] = 0
            return {"success": True, "name": name, "state": "open", "event": "re-tripped", "message": "Circuit breaker re-opened from half-open"}

        return {"success": True, "name": name, "state": breaker["state"], "event": "failure", "failure_count": breaker["failure_count"]}

    @staticmethod
    def can_execute(breaker: Dict, name: str = "default") -> Dict:
        """Check if a call is allowed based on circuit breaker state."""
        if breaker["state"] == "closed":
            return {"success": True, "allowed": True, "state": "closed", "name": name}

        if breaker["state"] == "open":
            if breaker["opened_at"] is not None:
                elapsed = time.time() - breaker["opened_at"]
                if elapsed >= breaker["recovery_timeout"]:
                    breaker["state"] = "half_open"
                    breaker["half_open_count"] = 0
                    breaker["success_count"] = 0
                    return {"success": True, "allowed": True, "state": "half_open", "name": name, "event": "half_open_transition"}
            breaker["total_rejections"] += 1
            return {"success": True, "allowed": False, "state": "open", "name": name, "reason": "Circuit breaker is open"}

        if breaker["state"] == "half_open":
            if breaker["half_open_count"] < breaker["half_open_max"]:
                return {"success": True, "allowed": True, "state": "half_open", "name": name}
            breaker["total_rejections"] += 1
            return {"success": True, "allowed": False, "state": "half_open", "name": name, "reason": "Half-open limit reached"}

        return {"success": True, "allowed": True, "state": breaker["state"], "name": name}

    @staticmethod
    def get_state(breaker: Dict, name: str = "default") -> Dict:
        """Get current circuit breaker state."""
        return {
            "success": True,
            "name": name,
            "state": breaker["state"],
            "failure_count": breaker["failure_count"],
            "success_count": breaker["success_count"],
            "failure_threshold": breaker["failure_threshold"],
            "recovery_timeout": breaker["recovery_timeout"],
            "last_failure_time": breaker["last_failure_time"],
            "opened_at": breaker["opened_at"],
        }

    @staticmethod
    def force_open(breaker: Dict, name: str = "default") -> Dict:
        """Force the circuit breaker open."""
        old_state = breaker["state"]
        breaker["state"] = "open"
        breaker["opened_at"] = time.time()
        breaker["history"].append({"event": "force_open", "timestamp": time.time()})
        return {"success": True, "name": name, "old_state": old_state, "new_state": "open"}

    @staticmethod
    def force_close(breaker: Dict, name: str = "default") -> Dict:
        """Force the circuit breaker closed (reset)."""
        old_state = breaker["state"]
        breaker["state"] = "closed"
        breaker["failure_count"] = 0
        breaker["success_count"] = 0
        breaker["half_open_count"] = 0
        breaker["opened_at"] = None
        breaker["history"].append({"event": "force_close", "timestamp": time.time()})
        return {"success": True, "name": name, "old_state": old_state, "new_state": "closed"}

    @staticmethod
    def reset(breaker: Dict, name: str = "default") -> Dict:
        """Reset the circuit breaker to initial state."""
        old = CircuitBreakerEngine.get_state(breaker, name)
        breaker["state"] = "closed"
        breaker["failure_count"] = 0
        breaker["success_count"] = 0
        breaker["half_open_count"] = 0
        breaker["last_failure_time"] = None
        breaker["opened_at"] = None
        breaker["history"].clear()
        breaker["total_calls"] = 0
        breaker["total_failures"] = 0
        breaker["total_successes"] = 0
        breaker["total_rejections"] = 0
        return {"success": True, "name": name, "reset": old}

    @staticmethod
    def configure(breaker: Dict, failure_threshold: int = None, recovery_timeout: float = None, half_open_max: int = None) -> Dict:
        """Configure circuit breaker parameters."""
        old = {"failure_threshold": breaker["failure_threshold"], "recovery_timeout": breaker["recovery_timeout"], "half_open_max": breaker["half_open_max"]}
        if failure_threshold is not None:
            breaker["failure_threshold"] = failure_threshold
        if recovery_timeout is not None:
            breaker["recovery_timeout"] = recovery_timeout
        if half_open_max is not None:
            breaker["half_open_max"] = half_open_max
        return {"success": True, "old": old, "new": {"failure_threshold": breaker["failure_threshold"], "recovery_timeout": breaker["recovery_timeout"], "half_open_max": breaker["half_open_max"]}}

    @staticmethod
    def get_history(breaker: Dict, name: str = "default", limit: int = 20) -> Dict:
        """Get event history."""
        events = list(breaker["history"])[-limit:]
        return {"success": True, "name": name, "events": events, "count": len(events), "total": len(breaker["history"])}

    @staticmethod
    def get_stats(breaker: Dict, name: str = "default") -> Dict:
        """Get circuit breaker statistics."""
        return {
            "success": True,
            "name": name,
            "state": breaker["state"],
            "total_calls": breaker["total_calls"],
            "total_failures": breaker["total_failures"],
            "total_successes": breaker["total_successes"],
            "total_rejections": breaker["total_rejections"],
            "failure_rate": round(breaker["total_failures"] / max(breaker["total_calls"], 1) * 100, 2),
            "current_failure_count": breaker["failure_count"],
            "failure_threshold": breaker["failure_threshold"],
        }

    @staticmethod
    def simulate(breaker: Dict, name: str, calls: List[Dict]) -> Dict:
        """Simulate a series of calls (success/failure)."""
        results = []
        for call in calls:
            outcome = call.get("outcome", "success")
            error = call.get("error", "simulated error")
            check = CircuitBreakerEngine.can_execute(breaker, name)
            if not check["allowed"]:
                results.append({"call": len(results) + 1, "allowed": False, "state": check["state"], "reason": check.get("reason")})
                continue
            if outcome == "success":
                r = CircuitBreakerEngine.record_success(breaker, name)
            else:
                r = CircuitBreakerEngine.record_failure(breaker, name, error)
            results.append({"call": len(results) + 1, "allowed": True, "state": r["state"], "event": r["event"]})
        return {"success": True, "name": name, "results": results, "total_calls": len(results)}

    @staticmethod
    def list_breakers(store: Dict) -> Dict:
        """List all circuit breakers in a store."""
        result = {k: v["state"] for k, v in store.items()}
        return {"success": True, "breakers": result, "count": len(result)}
