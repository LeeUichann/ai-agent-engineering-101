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
