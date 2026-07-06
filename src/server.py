"""MCP Server for circuit breakers — failure tracking, states, recovery."""
import json, sys, argparse
from typing import Any, Dict, List, Optional
from .breaker_engine import CircuitBreakerEngine

_store = {}

TOOL_DEFS = [
    {"name":"create","description":"Create a new circuit breaker.","inputSchema":{"type":"object","properties":{"name":{"type":"string"},"failure_threshold":{"type":"integer","default":5},"recovery_timeout":{"type":"number","default":60},"half_open_max":{"type":"integer","default":3}},"required":["name"]}},
    {"name":"record_success","description":"Record a successful call.","inputSchema":{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}},
    {"name":"record_failure","description":"Record a failed call.","inputSchema":{"type":"object","properties":{"name":{"type":"string"},"error":{"type":"string","default":"unknown"}},"required":["name"]}},
    {"name":"can_execute","description":"Check if a call is allowed.","inputSchema":{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}},
    {"name":"get_state","description":"Get circuit breaker state.","inputSchema":{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}},
    {"name":"force_open","description":"Force the circuit breaker open.","inputSchema":{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}},
    {"name":"force_close","description":"Force the circuit breaker closed.","inputSchema":{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}},
    {"name":"reset","description":"Reset the circuit breaker to initial state.","inputSchema":{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}},
    {"name":"configure","description":"Configure circuit breaker parameters.","inputSchema":{"type":"object","properties":{"name":{"type":"string"},"failure_threshold":{"type":"integer"},"recovery_timeout":{"type":"number"},"half_open_max":{"type":"integer"}},"required":["name"]}},
    {"name":"get_history","description":"Get event history.","inputSchema":{"type":"object","properties":{"name":{"type":"string"},"limit":{"type":"integer","default":20}},"required":["name"]}},
    {"name":"get_stats","description":"Get circuit breaker statistics.","inputSchema":{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}},
    {"name":"simulate","description":"Simulate a series of calls.","inputSchema":{"type":"object","properties":{"name":{"type":"string"},"calls":{"type":"array","items":{"type":"object"}}},"required":["name","calls"]}},
    {"name":"list_breakers","description":"List all circuit breakers.","inputSchema":{"type":"object","properties":{},"required":[]}},
]

class MCPCircuitBreakerToolsServer:
    def __init__(self,name="mcp-circuit-breaker-tools",version="1.0.0"):
        self.name=name;self.version=version
    def list_tools(self):return TOOL_DEFS
    def manifest(self):return{"server":{"name":self.name,"version":self.version},"capabilities":{"tools":{"listChanged":False},"resources":{},"prompts":{}},"tools":self.list_tools()}
    def _get(self,n):
        if n not in _store:_store[n]=CircuitBreakerEngine.create_breaker()
        return _store[n]
    def handle_tool_call(self,name,args):
        try:
            if name=="create":_store[args["name"]]=CircuitBreakerEngine.create_breaker(args.get("failure_threshold",5),args.get("recovery_timeout",60),args.get("half_open_max",3));return json.dumps({"success":True,"name":args["name"],"created":True})
            elif name=="record_success":return json.dumps(CircuitBreakerEngine.record_success(self._get(args["name"]),args["name"]))
            elif name=="record_failure":return json.dumps(CircuitBreakerEngine.record_failure(self._get(args["name"]),args["name"],args.get("error","unknown")))
            elif name=="can_execute":return json.dumps(CircuitBreakerEngine.can_execute(self._get(args["name"]),args["name"]))
            elif name=="get_state":return json.dumps(CircuitBreakerEngine.get_state(self._get(args["name"]),args["name"]))
            elif name=="force_open":return json.dumps(CircuitBreakerEngine.force_open(self._get(args["name"]),args["name"]))
            elif name=="force_close":return json.dumps(CircuitBreakerEngine.force_close(self._get(args["name"]),args["name"]))
            elif name=="reset":return json.dumps(CircuitBreakerEngine.reset(self._get(args["name"]),args["name"]))
            elif name=="configure":return json.dumps(CircuitBreakerEngine.configure(self._get(args["name"]),args.get("failure_threshold"),args.get("recovery_timeout"),args.get("half_open_max")))
            elif name=="get_history":return json.dumps(CircuitBreakerEngine.get_history(self._get(args["name"]),args["name"],args.get("limit",20)))
            elif name=="get_stats":return json.dumps(CircuitBreakerEngine.get_stats(self._get(args["name"]),args["name"]))
            elif name=="simulate":return json.dumps(CircuitBreakerEngine.simulate(self._get(args["name"]),args["name"],args["calls"]))
            elif name=="list_breakers":return json.dumps(CircuitBreakerEngine.list_breakers(_store))
            else:return json.dumps({"error":f"Unknown tool: {name}"})
        except KeyError as e:return json.dumps({"error":f"Missing required parameter: {e}","tool":name})
        except Exception as e:return json.dumps({"error":str(e),"tool":name})

def _run_stdio():
    server=MCPCircuitBreakerToolsServer()
    for line in sys.stdin:
        line=line.strip()
        if not line:continue
        try:request=json.loads(line)
        except json.JSONDecodeError:print(json.dumps({"jsonrpc":"2.0","error":{"code":-32700,"message":"Parse error"}}),flush=True);continue
        method=request.get("method","");req_id=request.get("id");params=request.get("params",{})
        if method=="initialize":response={"jsonrpc":"2.0","id":req_id,"result":{"server":server.name,"version":server.version}}
        elif method=="tools/list":response={"jsonrpc":"2.0","id":req_id,"result":{"tools":server.list_tools()}}
        elif method=="tools/call":
            result=server.handle_tool_call(params.get("name",""),params.get("arguments",{}))
            response={"jsonrpc":"2.0","id":req_id,"result":{"content":[{"type":"text","text":result}]}}
        elif method=="shutdown":response={"jsonrpc":"2.0","id":req_id,"result":{}};print(json.dumps(response),flush=True);break
        else:response={"jsonrpc":"2.0","id":req_id,"error":{"code":-32601,"message":f"Method not found: {method}"}}
        print(json.dumps(response),flush=True)

def main():
    parser=argparse.ArgumentParser(description="MCP Circuit Breaker Tools Server")
    parser.add_argument("--stdio",action="store_true")
    parser.add_argument("--manifest",action="store_true")
    args=parser.parse_args()
    if args.manifest:print(json.dumps(MCPCircuitBreakerToolsServer().manifest(),indent=2))
    elif args.stdio:_run_stdio()
    else:parser.print_help()

if __name__=="__main__":main()
