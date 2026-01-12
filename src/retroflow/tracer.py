"""
Debug tracing infrastructure for retroflow.

This module provides data structures for capturing detailed traces of the
flowchart generation pipeline. When debug mode is enabled, the generator
captures information about every stage of processing and every character
placement on the canvas.

This is primarily useful for:
1. Debugging rendering issues (understanding why characters appear where they do)
2. Understanding the pipeline flow (seeing intermediate states)
3. Writing targeted tests (verifying specific rendering decisions)

Usage:
    >>> generator = FlowchartGenerator()
    >>> result = generator.generate("A -> B", debug=True)
    >>> trace = generator.get_trace()
    >>> print(trace.summary())
    >>> trace.dump_to_file("debug_trace.txt")

The trace captures:
- Pipeline stages (parse, layout, positioning, edge drawing)
- Canvas snapshots at each stage
- Every character placement with coordinates, previous character, and reason
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CharacterPlacement:
    """
    Record of a single character placement on the canvas.

    Each time a character is placed on the canvas during rendering,
    a CharacterPlacement record is created to track what happened.

    Attributes:
        x: X coordinate on canvas
        y: Y coordinate on canvas
        char: The character that was placed
        previous_char: What character was at this position before
        reason: Why this character was placed (e.g., "vertical_line",
                "corner_upgrade_to_tee", "box_border")
        source: The method/function that placed the character
                (e.g., "EdgeDrawer._draw_vertical_line")
    """

    x: int
    y: int
    char: str
    previous_char: str
    reason: str
    source: str

    def __str__(self) -> str:
        if self.previous_char == " ":
            return (
                f"({self.x},{self.y}): '{self.char}' "
                f"[{self.reason}] from {self.source}"
            )
        return (
            f"({self.x},{self.y}): '{self.previous_char}' -> '{self.char}' "
            f"[{self.reason}] from {self.source}"
        )


@dataclass
class PipelineStage:
    """
    Snapshot of state at a pipeline stage.

    The flowchart generation pipeline has multiple stages:
    1. parse - Convert input text to connections and groups
    2. layout - Assign nodes to layers and positions
    3. dimensions - Calculate box sizes
    4. positions - Calculate canvas coordinates
    5. boundaries - Calculate safe routing zones
    6. groups - Calculate group bounding boxes
    7. canvas_created - Initial empty canvas
    8. boxes_drawn - After drawing all boxes
    9. forward_edges_drawn - After drawing forward edges
    10. back_edges_drawn - After drawing back edges (cycles)

    Attributes:
        name: Name of this pipeline stage
        data: Dictionary of relevant data at this stage
        canvas_snapshot: Optional list of canvas lines (ASCII art at this point)
    """

    name: str
    data: Dict[str, Any]
    canvas_snapshot: Optional[List[str]] = None

    def __str__(self) -> str:
        lines = [f"=== Stage: {self.name} ==="]
        for key, value in self.data.items():
            # Truncate long values
            str_val = str(value)
            if len(str_val) > 100:
                str_val = str_val[:100] + "..."
            lines.append(f"  {key}: {str_val}")
        if self.canvas_snapshot:
            lines.append("  Canvas preview (first 15 rows):")
            for row in self.canvas_snapshot[:15]:
                lines.append(f"    |{row}|")
        return "\n".join(lines)


@dataclass
class RenderTrace:
    """
    Complete trace of a render operation.

    This is the main container for all debug information collected during
    a flowchart generation. It stores both high-level pipeline stages and
    low-level character placement details.

    Usage:
        >>> generator = FlowchartGenerator()
        >>> result = generator.generate("A -> B\\nB -> C", debug=True)
        >>> trace = generator.get_trace()
        >>>
        >>> # Get summary
        >>> print(trace.summary())
        >>>
        >>> # Find all character upgrades (where existing char was modified)
        >>> upgrades = trace.get_character_upgrades()
        >>> for p in upgrades:
        ...     print(p)
        >>>
        >>> # Get canvas at specific stage
        >>> canvas_after_boxes = trace.get_canvas_at_stage("boxes_drawn")
        >>>
        >>> # Find placements at specific coordinate
        >>> at_5_10 = trace.get_placements_at(5, 10)

    Attributes:
        stages: List of pipeline stages with their data
        character_placements: List of all character placements
        input_text: The original input text
        direction: The flow direction (TB or LR)
    """

    stages: List[PipelineStage] = field(default_factory=list)
    character_placements: List[CharacterPlacement] = field(default_factory=list)
    input_text: str = ""
    direction: str = "TB"

    def add_stage(
        self,
        name: str,
        data: Dict[str, Any],
        canvas: Optional[Any] = None,
    ) -> None:
        """
        Add a pipeline stage snapshot.

        Args:
            name: Name of the stage (e.g., "after_layout")
            data: Dictionary of relevant data at this stage
            canvas: Optional Canvas object to snapshot
        """
        snapshot = None
        if canvas is not None:
            # Take a snapshot of the canvas at this point
            rendered = canvas.render()
            snapshot = rendered.split("\n") if rendered else []

        self.stages.append(PipelineStage(name, data.copy(), snapshot))

    def add_placement(
        self,
        x: int,
        y: int,
        char: str,
        previous_char: str,
        reason: str,
        source: str,
    ) -> None:
        """
        Record a character placement.

        Args:
            x: X coordinate
            y: Y coordinate
            char: Character being placed
            previous_char: Character that was there before
            reason: Why this placement happened
            source: The method that made this placement
        """
        self.character_placements.append(
            CharacterPlacement(x, y, char, previous_char, reason, source)
        )

    def get_stage(self, name: str) -> Optional[PipelineStage]:
        """Get a specific pipeline stage by name."""
        for stage in self.stages:
            if stage.name == name:
                return stage
        return None

    def get_canvas_at_stage(self, name: str) -> Optional[List[str]]:
        """Get the canvas snapshot at a specific stage."""
        stage = self.get_stage(name)
        if stage and stage.canvas_snapshot:
            return stage.canvas_snapshot
        return None

    def get_placements_at(self, x: int, y: int) -> List[CharacterPlacement]:
        """Get all character placements at a specific coordinate."""
        return [p for p in self.character_placements if p.x == x and p.y == y]

    def get_character_upgrades(self) -> List[CharacterPlacement]:
        """
        Get all placements where an existing character was upgraded.

        This is useful for debugging character merge issues - it shows
        all the places where a character was modified rather than placed
        on an empty cell.
        """
        return [
            p
            for p in self.character_placements
            if p.previous_char not in (" ", "░")  # Not empty or shadow
        ]

    def get_placements_by_source(
        self, source_substring: str
    ) -> List[CharacterPlacement]:
        """Get all placements from a specific source (partial match)."""
        return [
            p for p in self.character_placements if source_substring in p.source
        ]

    def get_placements_by_reason(
        self, reason_substring: str
    ) -> List[CharacterPlacement]:
        """Get all placements with a specific reason (partial match)."""
        return [
            p for p in self.character_placements if reason_substring in p.reason
        ]

    def summary(self) -> str:
        """
        Generate a human-readable summary of the trace.

        Returns a string with:
        - Input text
        - Pipeline stages overview
        - Character placement statistics
        """
        lines = [
            "=" * 60,
            "RENDER TRACE SUMMARY",
            "=" * 60,
            "",
            f"Direction: {self.direction}",
            f"Input: {repr(self.input_text[:100])}"
            f"{'...' if len(self.input_text) > 100 else ''}",
            "",
            f"Pipeline stages: {len(self.stages)}",
        ]

        for stage in self.stages:
            has_canvas = "+" if stage.canvas_snapshot else "-"
            lines.append(f"  [{has_canvas}] {stage.name}")

        lines.extend(
            [
                "",
                f"Total character placements: {len(self.character_placements)}",
                f"Character upgrades (overwrites): "
                f"{len(self.get_character_upgrades())}",
                "",
            ]
        )

        # Count by reason
        reason_counts: Dict[str, int] = {}
        for p in self.character_placements:
            reason_counts[p.reason] = reason_counts.get(p.reason, 0) + 1

        lines.append("Placements by reason:")
        for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
            lines.append(f"  {reason}: {count}")

        return "\n".join(lines)

    def dump(self) -> str:
        """
        Generate a complete human-readable dump of the trace.

        This includes all stages with their full data and all character
        placements. Can be quite long for complex diagrams.
        """
        lines = [self.summary(), "", "=" * 60, "DETAILED TRACE", "=" * 60, ""]

        # Stages
        lines.append("PIPELINE STAGES:")
        lines.append("-" * 40)
        for stage in self.stages:
            lines.append(str(stage))
            lines.append("")

        # Character placements
        lines.append("CHARACTER PLACEMENTS:")
        lines.append("-" * 40)
        for p in self.character_placements:
            lines.append(str(p))

        return "\n".join(lines)

    def dump_to_file(self, filename: str) -> None:
        """Write the complete trace dump to a file."""
        with open(filename, "w", encoding="utf-8") as f:
            f.write(self.dump())

    def dump_canvas_evolution(self) -> str:
        """
        Show how the canvas evolved through each stage.

        Returns a string showing the canvas snapshot at each stage
        that has one, making it easy to see how the diagram was built up.
        """
        lines = [
            "=" * 60,
            "CANVAS EVOLUTION",
            "=" * 60,
        ]

        for stage in self.stages:
            if stage.canvas_snapshot:
                lines.append("")
                lines.append(f"--- After: {stage.name} ---")
                for row in stage.canvas_snapshot:
                    lines.append(f"|{row}|")

        return "\n".join(lines)
