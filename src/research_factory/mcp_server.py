from mcp.server import MCPServer
from pydantic import BaseModel

mcp = MCPServer("Systematic Research Factory")


class Health(BaseModel):
    status: str
    version: str


@mcp.tool()
def healthcheck() -> Health:
    """Return service health."""
    return Health(status="ok", version="0.1.0")


@mcp.resource("project://policies")
def policies() -> str:
    return "No live trading in MVP | No hypothesis mutation without new experiment ID | Every market/filing query requires as_of | No LLM calculation of returns/statistics"


app = mcp.streamable_http_app()
