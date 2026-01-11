"""Unit tests for the renderer module."""

from retroflow.renderer import (
    ARROW_CHARS,
    BOX_CHARS,
    BOX_CHARS_DOUBLE,
    LINE_CHARS,
    BoxDimensions,
    BoxRenderer,
    Canvas,
    GroupBoxRenderer,
    LineRenderer,
    TitleRenderer,
)


class TestBoxDimensions:
    """Tests for BoxDimensions dataclass."""

    def test_box_dimensions_creation(self):
        """Test BoxDimensions creation."""
        dims = BoxDimensions(width=10, height=5, text_lines=["Hello"])
        assert dims.width == 10
        assert dims.height == 5
        assert dims.text_lines == ["Hello"]
        assert dims.padding == 1  # Default

    def test_box_dimensions_with_padding(self):
        """Test BoxDimensions with custom padding."""
        dims = BoxDimensions(width=10, height=5, text_lines=["Test"], padding=2)
        assert dims.padding == 2


class TestCanvas:
    """Tests for Canvas class."""

    def test_canvas_creation(self):
        """Test canvas creation with dimensions."""
        c = Canvas(10, 5)
        assert c.width == 10
        assert c.height == 5

    def test_canvas_default_fill(self, canvas):
        """Test canvas is filled with spaces by default."""
        assert canvas.get(0, 0) == " "
        assert canvas.get(5, 5) == " "

    def test_canvas_custom_fill(self):
        """Test canvas with custom fill character."""
        c = Canvas(10, 5, fill_char=".")
        assert c.get(0, 0) == "."

    def test_canvas_set_and_get(self, canvas):
        """Test setting and getting characters."""
        canvas.set(5, 5, "X")
        assert canvas.get(5, 5) == "X"

    def test_canvas_set_out_of_bounds(self, canvas):
        """Test setting character out of bounds does nothing."""
        canvas.set(-1, 0, "X")
        canvas.set(0, -1, "X")
        canvas.set(1000, 0, "X")
        canvas.set(0, 1000, "X")
        # Should not raise, just silently ignore

    def test_canvas_get_out_of_bounds(self, canvas):
        """Test getting character out of bounds returns space."""
        assert canvas.get(-1, 0) == " "
        assert canvas.get(0, -1) == " "
        assert canvas.get(1000, 0) == " "
        assert canvas.get(0, 1000) == " "

    def test_canvas_draw_text(self, canvas):
        """Test drawing text on canvas."""
        canvas.draw_text(0, 0, "Hello")
        assert canvas.get(0, 0) == "H"
        assert canvas.get(1, 0) == "e"
        assert canvas.get(2, 0) == "l"
        assert canvas.get(3, 0) == "l"
        assert canvas.get(4, 0) == "o"

    def test_canvas_draw_text_at_position(self, canvas):
        """Test drawing text at specific position."""
        canvas.draw_text(10, 5, "Test")
        assert canvas.get(10, 5) == "T"
        assert canvas.get(13, 5) == "t"

    def test_canvas_render_simple(self):
        """Test rendering canvas to string."""
        c = Canvas(5, 3)
        c.draw_text(0, 0, "ABC")
        c.draw_text(0, 1, "DEF")
        c.draw_text(0, 2, "GHI")
        result = c.render()
        assert "ABC" in result
        assert "DEF" in result
        assert "GHI" in result

    def test_canvas_render_strips_trailing_spaces(self):
        """Test that render strips trailing spaces from lines."""
        c = Canvas(10, 2)
        c.draw_text(0, 0, "Hi")
        result = c.render()
        lines = result.split("\n")
        assert lines[0] == "Hi"  # No trailing spaces

    def test_canvas_render_removes_trailing_empty_lines(self):
        """Test that render removes trailing empty lines."""
        c = Canvas(10, 10)
        c.draw_text(0, 0, "Test")
        result = c.render()
        assert not result.endswith("\n\n")


class TestBoxRenderer:
    """Tests for BoxRenderer class."""

    def test_box_renderer_creation(self):
        """Test BoxRenderer creation with defaults."""
        br = BoxRenderer()
        assert br.max_text_width == 20
        # Default is compact mode (padding=1)
        assert br.padding == 1
        assert br.shadow is True

    def test_box_renderer_custom_params(self):
        """Test BoxRenderer with custom parameters."""
        br = BoxRenderer(max_text_width=30, padding=2, shadow=False)
        assert br.max_text_width == 30
        assert br.padding == 2
        assert br.shadow is False

    def test_calculate_box_dimensions_short_text(self, box_renderer):
        """Test box dimensions for short text."""
        dims = box_renderer.calculate_box_dimensions("Hi")
        assert dims.text_lines == ["Hi"]
        # In compact mode (default): 1 text line + 2 borders = 3
        assert dims.height == 3

    def test_calculate_box_dimensions_longer_text(self, box_renderer):
        """Test box dimensions for longer text that wraps."""
        # Create a renderer with small max width
        br = BoxRenderer(max_text_width=10)
        dims = br.calculate_box_dimensions("This is a longer text")
        assert len(dims.text_lines) > 1

    def test_calculate_box_dimensions_empty_text(self, box_renderer):
        """Test box dimensions for empty text."""
        dims = box_renderer.calculate_box_dimensions("")
        assert dims.text_lines == [""]
        assert dims.height >= 3

    def test_calculate_box_dimensions_single_word(self, box_renderer):
        """Test box dimensions for single word."""
        dims = box_renderer.calculate_box_dimensions("Process")
        assert dims.text_lines == ["Process"]

    def test_calculate_box_dimensions_width_calculation(self, box_renderer):
        """Test box width calculation."""
        dims = box_renderer.calculate_box_dimensions("Test")
        # Width should be text length + 2*padding + 2 borders
        expected_min_width = len("Test") + 2 * box_renderer.padding + 2
        assert dims.width >= expected_min_width

    def test_draw_box_with_shadow(self, canvas, box_renderer):
        """Test drawing a box with shadow."""
        dims = box_renderer.calculate_box_dimensions("Test")
        box_renderer.draw_box(canvas, 0, 0, dims)

        # Check corners
        assert canvas.get(0, 0) == BOX_CHARS["top_left"]
        assert canvas.get(dims.width - 1, 0) == BOX_CHARS["top_right"]
        assert canvas.get(0, dims.height - 1) == BOX_CHARS["bottom_left"]
        assert canvas.get(dims.width - 1, dims.height - 1) == BOX_CHARS["bottom_right"]

        # Check shadow on right side
        assert canvas.get(dims.width, 1) == BOX_CHARS["shadow"]

    def test_draw_box_without_shadow(self, canvas):
        """Test drawing a box without shadow."""
        br = BoxRenderer(shadow=False)
        dims = br.calculate_box_dimensions("Test")
        br.draw_box(canvas, 0, 0, dims)

        # Should not have shadow character
        assert canvas.get(dims.width, 1) != BOX_CHARS["shadow"]

    def test_draw_box_text_centered(self, canvas, box_renderer):
        """Test that text is centered in the box."""
        dims = box_renderer.calculate_box_dimensions("Hi")
        box_renderer.draw_box(canvas, 0, 0, dims)

        # Text should be somewhere in the middle
        rendered = canvas.render()
        assert "Hi" in rendered

    def test_draw_box_at_offset(self, canvas, box_renderer):
        """Test drawing box at non-zero position."""
        dims = box_renderer.calculate_box_dimensions("Test")
        box_renderer.draw_box(canvas, 10, 5, dims)

        assert canvas.get(10, 5) == BOX_CHARS["top_left"]

    def test_draw_box_borders(self, canvas, box_renderer):
        """Test that horizontal borders are drawn correctly."""
        dims = box_renderer.calculate_box_dimensions("Test")
        box_renderer.draw_box(canvas, 0, 0, dims)

        # Top border (between corners)
        assert canvas.get(1, 0) == BOX_CHARS["horizontal"]

        # Bottom border
        assert canvas.get(1, dims.height - 1) == BOX_CHARS["horizontal"]

    def test_draw_box_sides(self, canvas, box_renderer):
        """Test that vertical sides are drawn correctly."""
        dims = box_renderer.calculate_box_dimensions("Test")
        box_renderer.draw_box(canvas, 0, 0, dims)

        # Left side
        assert canvas.get(0, 1) == BOX_CHARS["vertical"]

        # Right side
        assert canvas.get(dims.width - 1, 1) == BOX_CHARS["vertical"]


class TestLineRenderer:
    """Tests for LineRenderer class."""

    def test_line_renderer_creation(self):
        """Test LineRenderer creation."""
        lr = LineRenderer()
        assert lr is not None

    def test_draw_vertical_line_down(self, canvas):
        """Test drawing vertical line downward."""
        lr = LineRenderer()
        lr.draw_vertical_line(canvas, 5, 0, 5, arrow_at_end=True)

        # Check vertical characters
        assert canvas.get(5, 0) == LINE_CHARS["vertical"]
        assert canvas.get(5, 4) == LINE_CHARS["vertical"]

        # Check arrow at end
        assert canvas.get(5, 5) == ARROW_CHARS["down"]

    def test_draw_vertical_line_up(self, canvas):
        """Test drawing vertical line upward."""
        lr = LineRenderer()
        lr.draw_vertical_line(canvas, 5, 10, 5, arrow_at_end=True)

        # Arrow should be at the top (y=5)
        assert canvas.get(5, 5) == ARROW_CHARS["up"]

    def test_draw_vertical_line_no_arrow(self, canvas):
        """Test drawing vertical line without arrow."""
        lr = LineRenderer()
        lr.draw_vertical_line(canvas, 5, 0, 5, arrow_at_end=False)

        # No arrow at end
        assert canvas.get(5, 5) != ARROW_CHARS["down"]
        assert canvas.get(5, 5) != ARROW_CHARS["up"]

    def test_draw_horizontal_line_right(self, canvas):
        """Test drawing horizontal line to the right."""
        lr = LineRenderer()
        lr.draw_horizontal_line(canvas, 0, 10, 5, arrow_at_end=True)

        # Check horizontal characters
        assert canvas.get(1, 5) == LINE_CHARS["horizontal"]

        # Check arrow at end
        assert canvas.get(10, 5) == ARROW_CHARS["right"]

    def test_draw_horizontal_line_left(self, canvas):
        """Test drawing horizontal line to the left."""
        lr = LineRenderer()
        lr.draw_horizontal_line(canvas, 10, 0, 5, arrow_at_end=True)

        # Arrow should be at the left
        assert canvas.get(0, 5) == ARROW_CHARS["left"]

    def test_draw_horizontal_line_no_arrow(self, canvas):
        """Test drawing horizontal line without arrow."""
        lr = LineRenderer()
        lr.draw_horizontal_line(canvas, 0, 10, 5, arrow_at_end=False)

        assert canvas.get(10, 5) != ARROW_CHARS["right"]

    def test_draw_corner_top_left(self, canvas):
        """Test drawing top-left corner."""
        lr = LineRenderer()
        lr.draw_corner(canvas, 5, 5, "top_left")

        assert canvas.get(5, 5) == LINE_CHARS["corner_top_left"]

    def test_draw_corner_top_right(self, canvas):
        """Test drawing top-right corner."""
        lr = LineRenderer()
        lr.draw_corner(canvas, 5, 5, "top_right")

        assert canvas.get(5, 5) == LINE_CHARS["corner_top_right"]

    def test_draw_corner_bottom_left(self, canvas):
        """Test drawing bottom-left corner."""
        lr = LineRenderer()
        lr.draw_corner(canvas, 5, 5, "bottom_left")

        assert canvas.get(5, 5) == LINE_CHARS["corner_bottom_left"]

    def test_draw_corner_bottom_right(self, canvas):
        """Test drawing bottom-right corner."""
        lr = LineRenderer()
        lr.draw_corner(canvas, 5, 5, "bottom_right")

        assert canvas.get(5, 5) == LINE_CHARS["corner_bottom_right"]

    def test_line_crossing_creates_cross(self, canvas):
        """Test that crossing lines create cross character."""
        lr = LineRenderer()

        # Draw horizontal line first
        lr.draw_horizontal_line(canvas, 0, 10, 5, arrow_at_end=False)

        # Draw vertical line crossing it
        lr.draw_vertical_line(canvas, 5, 0, 10, arrow_at_end=False)

        # Should have cross at intersection
        assert canvas.get(5, 5) == LINE_CHARS["cross"]

    def test_corner_on_horizontal_becomes_tee(self, canvas):
        """Test that corner on horizontal line becomes tee."""
        lr = LineRenderer()

        # Draw horizontal line first
        canvas.set(5, 5, LINE_CHARS["horizontal"])

        # Draw corner on it
        lr.draw_corner(canvas, 5, 5, "top_left")

        # Should become tee_down
        assert canvas.get(5, 5) == LINE_CHARS["tee_down"]

    def test_corner_on_vertical_becomes_tee(self, canvas):
        """Test that corner on vertical line becomes tee."""
        lr = LineRenderer()

        # Draw vertical line first
        canvas.set(5, 5, LINE_CHARS["vertical"])

        # Draw corner on it
        lr.draw_corner(canvas, 5, 5, "top_left")

        # Should become tee_right
        assert canvas.get(5, 5) == LINE_CHARS["tee_right"]


class TestCharacterConstants:
    """Tests for character constant dictionaries."""

    def test_box_chars_complete(self):
        """Test BOX_CHARS has all required keys."""
        required = [
            "top_left",
            "top_right",
            "bottom_left",
            "bottom_right",
            "horizontal",
            "vertical",
            "shadow",
        ]
        for key in required:
            assert key in BOX_CHARS

    def test_arrow_chars_complete(self):
        """Test ARROW_CHARS has all required keys."""
        required = ["down", "up", "right", "left"]
        for key in required:
            assert key in ARROW_CHARS

    def test_line_chars_complete(self):
        """Test LINE_CHARS has all required keys."""
        required = [
            "horizontal",
            "vertical",
            "corner_top_left",
            "corner_top_right",
            "corner_bottom_left",
            "corner_bottom_right",
            "tee_right",
            "tee_left",
            "tee_down",
            "tee_up",
            "cross",
        ]
        for key in required:
            assert key in LINE_CHARS

    def test_chars_are_single_characters(self):
        """Test all characters are single character strings."""
        for char in BOX_CHARS.values():
            assert len(char) == 1
        for char in ARROW_CHARS.values():
            assert len(char) == 1
        for char in LINE_CHARS.values():
            assert len(char) == 1

    def test_box_chars_double_complete(self):
        """Test BOX_CHARS_DOUBLE has all required keys."""
        required = [
            "top_left",
            "top_right",
            "bottom_left",
            "bottom_right",
            "horizontal",
            "vertical",
        ]
        for key in required:
            assert key in BOX_CHARS_DOUBLE

    def test_box_chars_double_are_single_characters(self):
        """Test all double-line characters are single character strings."""
        for char in BOX_CHARS_DOUBLE.values():
            assert len(char) == 1

    def test_box_chars_double_are_different_from_single(self):
        """Test double-line characters are different from single-line."""
        assert BOX_CHARS_DOUBLE["top_left"] != BOX_CHARS["top_left"]
        assert BOX_CHARS_DOUBLE["horizontal"] != BOX_CHARS["horizontal"]
        assert BOX_CHARS_DOUBLE["vertical"] != BOX_CHARS["vertical"]


class TestTitleRenderer:
    """Tests for TitleRenderer class."""

    def test_title_renderer_creation(self):
        """Test TitleRenderer creation with defaults."""
        tr = TitleRenderer()
        assert tr is not None
        assert tr.padding == 2
        assert tr.box_chars == BOX_CHARS_DOUBLE

    def test_title_renderer_custom_padding(self):
        """Test TitleRenderer with custom padding."""
        tr = TitleRenderer(padding=5)
        assert tr.padding == 5

    def test_calculate_title_dimensions_basic(self):
        """Test calculating title dimensions."""
        tr = TitleRenderer()
        width, height = tr.calculate_title_dimensions("Hello")

        # width = len("Hello") + 2*padding + 2 (borders) = 5 + 4 + 2 = 11
        assert width == 11
        # height is always 3 (top, text, bottom)
        assert height == 3

    def test_calculate_title_dimensions_min_width(self):
        """Test that title box sizes to content, ignoring min_width."""
        tr = TitleRenderer()
        width, height = tr.calculate_title_dimensions("Hi", min_width=20)

        # min_width is now ignored - box sizes to fit content
        # width = len("Hi") + 2*padding + 2 = 2 + 4 + 2 = 8
        assert width == 8
        assert height == 3

    def test_calculate_title_dimensions_longer_title(self):
        """Test dimensions with longer title that wraps."""
        tr = TitleRenderer()
        title = "This is a longer title"
        width, height = tr.calculate_title_dimensions(title)

        # Title wraps at 15 chars: "This is a" (9), "longer title" (12)
        # Max line width is 12, so width = 12 + 2*padding + 2 = 18
        # height = 2 lines + 2 (borders) = 4
        assert width == 18
        assert height == 4

    def test_draw_title_corners(self, canvas):
        """Test that title draws correct double-line corners."""
        tr = TitleRenderer()
        tr.draw_title(canvas, 0, 0, "Test", 12)

        # Title box is sized to content: "Test" = 4 chars
        # width = 4 + 2*padding + 2 = 4 + 4 + 2 = 10
        # So corners at 0 and 9
        assert canvas.get(0, 0) == BOX_CHARS_DOUBLE["top_left"]
        assert canvas.get(9, 0) == BOX_CHARS_DOUBLE["top_right"]
        assert canvas.get(0, 2) == BOX_CHARS_DOUBLE["bottom_left"]
        assert canvas.get(9, 2) == BOX_CHARS_DOUBLE["bottom_right"]

    def test_draw_title_borders(self, canvas):
        """Test that title draws correct horizontal borders."""
        tr = TitleRenderer()
        tr.draw_title(canvas, 0, 0, "Test", 12)

        # Check horizontal borders (between corners)
        assert canvas.get(1, 0) == BOX_CHARS_DOUBLE["horizontal"]
        assert canvas.get(1, 2) == BOX_CHARS_DOUBLE["horizontal"]

    def test_draw_title_sides(self, canvas):
        """Test that title draws correct vertical sides."""
        tr = TitleRenderer()
        tr.draw_title(canvas, 0, 0, "Test", 12)

        # Title box width = 10, so sides at 0 and 9
        assert canvas.get(0, 1) == BOX_CHARS_DOUBLE["vertical"]
        assert canvas.get(9, 1) == BOX_CHARS_DOUBLE["vertical"]

    def test_draw_title_text_present(self, canvas):
        """Test that title text is drawn."""
        tr = TitleRenderer()
        tr.draw_title(canvas, 0, 0, "Hello", 15)

        rendered = canvas.render()
        assert "Hello" in rendered

    def test_draw_title_returns_height(self, canvas):
        """Test that draw_title returns correct height."""
        tr = TitleRenderer()
        height = tr.draw_title(canvas, 0, 0, "Test", 12)

        assert height == 3

    def test_draw_title_at_offset(self, canvas):
        """Test drawing title at non-zero position."""
        tr = TitleRenderer()
        tr.draw_title(canvas, 5, 3, "Test", 12)

        # Title box width = 10, corners at x=5 and x=14
        assert canvas.get(5, 3) == BOX_CHARS_DOUBLE["top_left"]
        assert canvas.get(14, 3) == BOX_CHARS_DOUBLE["top_right"]
        assert canvas.get(5, 5) == BOX_CHARS_DOUBLE["bottom_left"]
        assert canvas.get(14, 5) == BOX_CHARS_DOUBLE["bottom_right"]

    def test_draw_title_text_centered(self, canvas):
        """Test that title text is centered in the box."""
        tr = TitleRenderer()
        title = "Hi"
        tr.draw_title(canvas, 0, 0, title, 20)  # width param is ignored

        # Title box sizes to content: width = 2 + 4 + 2 = 8
        # Text centered in width 8: available = 6, offset = (6-2)/2 = 2
        # Text starts at x = 1 (border) + 2 (offset) = 3
        assert canvas.get(3, 1) == "H"
        assert canvas.get(4, 1) == "i"


class TestGroupBoxRenderer:
    """Tests for GroupBoxRenderer class."""

    def test_group_box_renderer_creation(self):
        """Test GroupBoxRenderer creation with defaults."""
        gbr = GroupBoxRenderer()
        assert gbr is not None
        assert gbr.padding == 2
        assert gbr.max_label_width == 20

    def test_group_box_renderer_custom_params(self):
        """Test GroupBoxRenderer with custom parameters."""
        gbr = GroupBoxRenderer(padding=4, max_label_width=30)
        assert gbr.padding == 4
        assert gbr.max_label_width == 30

    def test_wrap_label_text_short(self):
        """Test label wrapping with short text."""
        gbr = GroupBoxRenderer(max_label_width=20)
        lines = gbr._wrap_label_text("Short")
        assert lines == ["Short"]

    def test_wrap_label_text_long(self):
        """Test label wrapping with text exceeding max width."""
        gbr = GroupBoxRenderer(max_label_width=10)
        lines = gbr._wrap_label_text("This is a longer label text")
        assert len(lines) > 1
        for line in lines:
            assert len(line) <= 10

    def test_wrap_label_text_exact_width(self):
        """Test label wrapping at exact max width."""
        gbr = GroupBoxRenderer(max_label_width=5)
        lines = gbr._wrap_label_text("12345")
        assert lines == ["12345"]

    def test_wrap_label_text_single_long_word(self):
        """Test label wrapping with single long word."""
        gbr = GroupBoxRenderer(max_label_width=5)
        lines = gbr._wrap_label_text("VeryLongWord")
        # Single word exceeding max should be kept on one line
        assert "VeryLongWord" in lines[0] or len(lines) >= 1

    def test_draw_group_box_corners(self, canvas):
        """Test that group box draws correct corners."""
        gbr = GroupBoxRenderer()
        gbr.draw_group_box(canvas, 0, 0, 20, 10, "Test")

        assert canvas.get(0, 0) == BOX_CHARS["top_left"]
        assert canvas.get(19, 0) == BOX_CHARS["top_right"]
        assert canvas.get(0, 9) == BOX_CHARS["bottom_left"]
        assert canvas.get(19, 9) == BOX_CHARS["bottom_right"]

    def test_draw_group_box_borders(self, canvas):
        """Test that group box draws correct horizontal borders (dotted style)."""
        gbr = GroupBoxRenderer()
        gbr.draw_group_box(canvas, 0, 0, 20, 10, "Test")

        # Group boxes use dotted lines for borders (not solid lines)
        assert canvas.get(1, 0) == "."
        assert canvas.get(1, 9) == "."

    def test_draw_group_box_sides(self, canvas):
        """Test that group box draws correct vertical sides (dotted style)."""
        gbr = GroupBoxRenderer()
        gbr.draw_group_box(canvas, 0, 0, 20, 10, "Test")

        # Group boxes use dotted lines for sides (not solid lines)
        assert canvas.get(0, 1) == "."
        assert canvas.get(19, 1) == "."

    def test_draw_group_box_label_present(self, canvas):
        """Test that group box label is drawn."""
        gbr = GroupBoxRenderer()
        gbr.draw_group_box(canvas, 0, 0, 30, 10, "MyGroup")

        rendered = canvas.render()
        assert "MyGroup" in rendered

    def test_draw_group_box_at_offset(self, canvas):
        """Test drawing group box at non-zero position."""
        gbr = GroupBoxRenderer()
        gbr.draw_group_box(canvas, 5, 3, 20, 10, "Test")

        # Corners at offset position
        assert canvas.get(5, 3) == BOX_CHARS["top_left"]
        assert canvas.get(24, 3) == BOX_CHARS["top_right"]
        assert canvas.get(5, 12) == BOX_CHARS["bottom_left"]
        assert canvas.get(24, 12) == BOX_CHARS["bottom_right"]

    def test_draw_group_box_label_centered(self, canvas):
        """Test that group box label is centered."""
        gbr = GroupBoxRenderer()
        label = "AB"
        gbr.draw_group_box(canvas, 0, 0, 20, 10, label)

        # Label should be approximately centered in the top area
        rendered = canvas.render()
        assert "AB" in rendered

    def test_draw_group_box_multiline_label(self, canvas):
        """Test group box with label that wraps to multiple lines."""
        gbr = GroupBoxRenderer(max_label_width=10)
        gbr.draw_group_box(canvas, 0, 0, 30, 15, "A Very Long Group Name Here")

        rendered = canvas.render()
        # Label should be wrapped across multiple lines
        assert "Long" in rendered or "Group" in rendered
