# Process

- Started branch week-06-26520024 from main 3defe07. User requested the required
  assignment only and no push. Read the README, SDK-based lab seller, official
  trade-test implementation and structural checker.
- Base is Python 3.8.19; a2a is absent. Confirmed from package metadata that
  a2a-sdk 1.2.0 needs Python >=3.10. Asked about a project-local isolated runtime
  instead of changing base or any existing conda environment.
- Plan: reuse the prior model adapter, SDK server, guarded model decisions,
  FTS5 catalog retrieval, and model-selected multi-shop budget allocations.
  Implementation and analysis are assisted by Codex; all live model calls will
  be recorded separately from scripted offline tests.
# Implementation and runtime update

- User selected the existing `eraseanything` interpreter after the base Python
  incompatibility was explained. It is Python 3.10.22, but has no A2A SDK.
  A project-local `.venv` uses that interpreter; no packages in any existing
  conda environment were installed, upgraded or removed.
- Added the seller/buyer, 3,016-item synthetic catalog, six frozen descriptive
  cases, twenty shop configurations, and three four-item shopping runs.
- The first SDK lifecycle test exposed SQLite's default thread affinity under
  Starlette TestClient. The failure was reproduced in `logs/offline-01-failed.log`
  before changing the connection to allow cross-thread access with a lock.
  All 15 offline tests then passed (`logs/offline-02.log`). These tests use
  explicitly scripted decisions, not live model evidence.
- Before live execution, corrected `agent.json` to the course's nested
  seller/buyer command schema. No official test had yet been run.
