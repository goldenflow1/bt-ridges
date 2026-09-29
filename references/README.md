# references/ — read-only study material

Other miners' public agent files, fetched by `tools/fetch_references.py`, exactly as Ridges serves them.

Rules (see CLAUDE.md):
1. Never copy code, prompts or constants from here into `src/`. Learn an idea, write it yourself, and cite it in an
   ADR or experiment note as `REF set-NN/<folder>/agent.py:<line>`, never in `src/`.
2. Never edit files here; re-run the fetcher instead.
3. `tools/originality_check.py dist/agent.py` compares our bundle against every file here before any upload.
