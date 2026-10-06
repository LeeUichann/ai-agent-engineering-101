# Process

- Started from main 48d1d0b on branch week-05-26520024. User requested reuse of
  the prior agents. Read the course README, lecture and structural checker.
- Confirmed existing conda base: Python 3.8.19, Codex CLI 0.153.0. MCP SDK is not
  installed; node/npm are absent. Chose a limited standard-library MCP transport
  instead of changing Python or another conda environment. No packages installed.
- Consulted official MCP 2026-07-28 transport, metadata, discovery and tool
  specifications, plus official Codex non-interactive documentation.
- Reuse week-04's exact four scenarios, role prompt paragraphs and model-call
  adapter; change orchestration to a real HTTP market, not a simulated tool call.
- Drafted DESIGN.md and prompts before any actual model call. Existing staged
  week-02/ARCHITECTURE.md and all earlier branches remain untouched.
- Implementation, tests and report are assisted by Codex. Actual negotiation
  model outputs will be logged independently; no synthetic tests enter results.
- The first offline run had 3 errors in 31 tests: the host read prompts[role]
  instead of prompts['roles'][role], and one role-spoofing test collided with its
  helper's role argument. Also closed two CSV handles after ResourceWarnings.
  Corrected these before live calls; the next run passed all 31 tests.
