"""Source map: tracks and tags all source content with unique SRC_IDs.

Implements the "Source Map Pattern" from ARCHITECTURE.md Section 4.
Every piece of content that enters the system gets a SRC_ID assigned here,
and that ID travels with the content through all LLM prompts. The LLM
never sees or outputs raw URLs — only SRC_IDs.

Usage:
    source_map = SourceMap()

    src_id = source_map.add(
        url="https://reddit.com/r/...",
        title="Complaints about PM tools",
        snippet="I hate that every tool charges per seat...",
        source_type="reddit",
    )

    # Tag content before injecting into any LLM prompt
    tagged = source_map.tag_content(src_id, cleaned_text)
    # → "[SRC_01] I hate that every tool charges per seat..."

    # Resolve SRC_ID → real URL when building the final report
    real_url = source_map.resolve(src_id)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from src.graph.state import SourceEntry


class SourceMap:
    """Manages the mapping from SRC_IDs to source metadata.

    SRC_IDs are assigned sequentially (SRC_01, SRC_02, ...) and are
    zero-padded to two digits. IDs are only ever created here — no other
    part of the system generates SRC_IDs. See CONVENTIONS.md Section 2.
    """

    def __init__(self, existing_map: dict[str, SourceEntry] | None = None) -> None:
        self._map: dict[str, SourceEntry] = dict(existing_map) if existing_map else {}

    def add(
        self,
        url: str,
        title: str,
        snippet: str,
        source_type: Literal["web", "reddit", "hn", "app_store"],
    ) -> str:
        """Register a new source and return its SRC_ID.

        Args:
            url: The source URL.
            title: Title or headline of the source.
            snippet: A short text excerpt from the source.
            source_type: One of "web", "reddit", "hn", "app_store".

        Returns:
            The assigned SRC_ID (e.g. "SRC_7F2A").
        """
        import uuid

        # Generate a unique 4-character hex ID (e.g., SRC_A1B2)
        # Using random IDs instead of sequential to prevent collisions
        # when parallel branches (competitor/pain points) add sources.
        while True:
            short_id = uuid.uuid4().hex[:4].upper()
            src_id = f"SRC_{short_id}"
            if src_id not in self._map:
                break

        self._map[src_id] = SourceEntry(
            url=url,
            title=title,
            snippet=snippet,
            source_type=source_type,
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )

        return src_id

    def tag_content(self, src_id: str, text: str) -> str:
        """Tag content with its SRC_ID for injection into LLM prompts.

        This is the ONLY way content should be formatted before reaching
        an LLM. Untagged content in a prompt is a convention violation
        (see CONVENTIONS.md Section 3).

        Args:
            src_id: A previously registered SRC_ID.
            text: The content to tag.

        Returns:
            Tagged string: "[SRC_XX] text..."

        Raises:
            KeyError: If src_id was never registered via add().
        """
        if src_id not in self._map:
            raise KeyError(f"Unknown source ID '{src_id}'. Was it registered with add()?")
        return f"[{src_id}] {text}"

    def resolve(self, src_id: str) -> str:
        """Resolve a SRC_ID back to its real URL for the final report.

        This is called once, by report_builder, when producing the output.
        The LLM never calls this — it only ever works with SRC_IDs.

        Args:
            src_id: A previously registered SRC_ID.

        Returns:
            The source's URL.

        Raises:
            KeyError: If src_id was never registered.
        """
        if src_id not in self._map:
            raise KeyError(f"Unknown source ID '{src_id}'. Was it registered with add()?")
        return self._map[src_id]["url"]

    def get(self, src_id: str) -> SourceEntry:
        """Get the full source entry for a SRC_ID."""
        if src_id not in self._map:
            raise KeyError(f"Unknown source ID '{src_id}'. Was it registered with add()?")
        return self._map[src_id]

    def to_dict(self) -> dict[str, SourceEntry]:
        """Export the full source map for storing in ResearchState.source_map."""
        return dict(self._map)

    def __len__(self) -> int:
        return len(self._map)

    def __contains__(self, src_id: str) -> bool:
        return src_id in self._map
