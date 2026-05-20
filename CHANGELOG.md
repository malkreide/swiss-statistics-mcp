# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Structured JSON logging on stderr: one `tool_start` and one `tool_end` event
  per tool call, with `rid` correlation id, `params_keys`, `status`,
  `duration_ms`, and `error_type` on failure. Level configurable via
  `MCP_LOG_LEVEL` (default `INFO`). Addresses audit findings OBS-001,
  OBS-002, OBS-003, SEC-014.

### Security
- Streamable-HTTP transport now binds to `127.0.0.1` by default instead of all
  interfaces. Set `MCP_HOST=0.0.0.0` or pass `--host 0.0.0.0` to expose on a
  container port; README documents the access-control requirements for cloud
  deployments. Addresses audit finding SDK-004.

### Fixed
- HTTP entrypoint passed `port=` to `mcp.run()`, which raises `TypeError` in
  current MCP SDK. Port is now set via `mcp.settings.port` before `run()`.

## [0.1.0] - 2026-03-29

### Added
- Initial release with 9 MCP tools for BFS STAT-TAB PxWeb API access
- Full catalog of 682 datasets across 21 themes
- Convenience tools: `bfs_education_stats`, `bfs_population`, `bfs_compare_cantons`
- Catalog search with TTL-based caching (1h)
- JSON-STAT2 response parsing with human-readable table output
- Dual transport: stdio (Claude Desktop) and Streamable HTTP (cloud)
- 39 unit/integration tests + 4 live smoke tests
- Bilingual documentation (English/German)
- GitHub Actions CI (Python 3.11, 3.12, 3.13)
