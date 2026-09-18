"""Swiss Statistics MCP Server – BFS STAT-TAB integration."""

from importlib.metadata import PackageNotFoundError, metadata, version

try:
    # Single source of truth is pyproject.toml; read it back from the
    # installed package metadata so __version__ never drifts out of sync.
    __version__ = version("swiss-statistics-mcp")
except PackageNotFoundError:  # pragma: no cover - running from an uninstalled source tree
    # Bewusst mit lokalem Segment: "0.0.0" allein sieht wie ein echtes
    # Release aus. Der Marker macht sichtbar, dass hier keine Version
    # bekannt ist — Portfolio-Konvention.
    __version__ = "0.0.0+source"

try:
    # Dieselbe Quelle, derselbe Grund: die Beschreibung geht ab Spec
    # `2026-07-28` als `serverInfo.description` an jeden Aufrufer. Als Literal
    # in `server.py` waere sie eine dritte Fassung neben `pyproject.toml` und
    # `server.json` — und die einzige, die niemand nachfuehrt, weil sie nirgends
    # sichtbar ist.
    #
    # `None` und nicht `""`, wenn nichts da ist — aus demselben Grund wie bei
    # `__homepage__` unten: der Stempel wird mit `exclude_none` gedumpt, ein
    # Leerstring kaeme als `"description": ""` beim Aufrufer an.
    __description__: str | None = metadata("swiss-statistics-mcp")["Summary"] or None
except PackageNotFoundError:  # pragma: no cover - running from an uninstalled source tree
    __description__ = None

try:
    # Und dieselbe Quelle ein drittes Mal, aus demselben Grund. `Project-URL`
    # ist mehrwertig ("<Label>, <URL>" je Eintrag); gesucht ist `Homepage`.
    # Fehlt der Eintrag, ist `None` der Wert — nicht `""`. Nachgemessen, weil
    # der Unterschied unsichtbar aussieht und keiner ist: `website_url` ist
    # `str | None` ohne URL-Pruefung, und der Stempel wird mit `exclude_none`
    # gedumpt. `None` laesst das Feld also ganz weg; `""` schickt
    # `"websiteUrl": ""` an jeden Aufrufer — dieselbe falsche Angabe wie die
    # leere `version`, gegen die dieses Paket gerade erst abgesichert wurde.
    __homepage__: str | None = next(
        (
            url.strip()
            for label, _, url in (
                entry.partition(", ")
                for entry in metadata("swiss-statistics-mcp").get_all("Project-URL") or []
            )
            if label.strip() == "Homepage"
        ),
        None,
    )
except PackageNotFoundError:  # pragma: no cover - running from an uninstalled source tree
    __homepage__ = None
