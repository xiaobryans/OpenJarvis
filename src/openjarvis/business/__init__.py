"""Universal business-ops subsystem for VANTA (Sprint 3, 3A–3D).

A single local SQLite store backs quotes, jobs, clients and payments so VANTA
can run the operational side of *any* kind of work — plumbing, tattoo, AI
clients, OMNIX — by voice or text. The store is import-light and side-effect
free until first use, and every function accepts an explicit db path so it is
fully unit-testable against a temp database.
"""

from openjarvis.business.store import BusinessStore

__all__ = ["BusinessStore"]
