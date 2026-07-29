"""Swiss Statistics MCP Server – BFS STAT-TAB integration."""

from importlib.metadata import PackageNotFoundError, version

try:
    # Single source of truth is pyproject.toml; read it back from the
    # installed package metadata so __version__ never drifts out of sync.
    __version__ = version("swiss-statistics-mcp")
except PackageNotFoundError:  # pragma: no cover - running from an uninstalled source tree
    # Bewusst mit lokalem Segment: "0.0.0" allein sieht wie ein echtes
    # Release aus. Der Marker macht sichtbar, dass hier keine Version
    # bekannt ist — Portfolio-Konvention.
    __version__ = "0.0.0+source"
