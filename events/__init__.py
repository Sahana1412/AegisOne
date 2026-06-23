"""
Top-level `events` package.

The hackathon brief's required top-level layout lists `events/` alongside
`band/`. The canonical event-type definitions live in `band/events/` since
they are Band's own vocabulary — re-exported here so `from events import
EventType` also works for anyone scanning the repo by the brief's layout.
"""
from band.events.event_types import EventType

__all__ = ["EventType"]
