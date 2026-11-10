"""Nothing up my sleeve as a viable system, laid out by system (Justin, 2026-11-07: "structure it like VSM in the file directory").

Each folder is one of Beer's systems and holds the code it owns:

- s1_operations: the voyages and the fitouts they sail (running a fitout's prechecks, readiness to sail)
- s2_coordination: what keeps operations from colliding (the shared tokeniser every class reads through)
- s3_control: resources and the gate (the Postgres fitout store, the library checks, the precheck gate)
- s3star_audit: independent checks that cleaning and the stores still do what they say
- s4_intelligence: the outside view and the next version (planned prechecks and the measurements behind them)
- s5_policy: the standards (what clean text is; the policies Justin adopts)

The older single-file map (thorp/vsm.py) keeps the policies, the gate and the helm until they move here.
"""
