"""House style: shades of green (matches the book and slides), plus small reusable mobjects."""
from manim import *

BG = "#f2f8f4"
FOREST, MID, LIGHT, PALE = "#1c4a37", "#2f7d5b", "#5fb083", "#a9d6bb"
LIME, OLIVE, MUTE, INK = "#8fb81f", "#5b7d12", "#6b8a7a", "#173d2e"
config.background_color = BG
Text.set_default(font="Liberation Sans")   # house sans-serif (Pango's default is a serif)

# Layout zones, in Manim units (frame is 14.22 x 8): keep content inside them.
#   header   y > 2.9   chapter label and scene title (added by Narrated.header)
#   content  -3.0 < y < 2.9
#   captions y < -3.0  reserved for the burned-in karaoke captions
CONTENT_TOP, CONTENT_BOTTOM = 2.9, -3.0


def block(label, width=2.1, height=0.95, size=26, fill=WHITE):
    box = RoundedRectangle(corner_radius=0.12, width=width, height=height, stroke_color=FOREST,
                           stroke_width=4, fill_color=fill, fill_opacity=1)
    return VGroup(box, Text(label, font_size=size, color=FOREST, weight=BOLD))


def pill(label, color=MID, text_color=WHITE, size=22):
    t = Text(label, font_size=size, color=text_color, weight=BOLD)
    return VGroup(RoundedRectangle(corner_radius=0.2, width=t.width + 0.5, height=t.height + 0.3,
                                   fill_color=color, fill_opacity=1, stroke_width=0), t)


def polyline(points, **kw):
    line = VMobject(**kw)
    line.set_points_as_corners(points)
    return line


def card(width, height, **kw):
    return RoundedRectangle(corner_radius=0.18, width=width, height=height, stroke_color=PALE, stroke_width=3,
                            fill_color=WHITE, fill_opacity=1, **kw)


def small_axes(x_range, y_range, width, height, **kw):
    return Axes(x_range=x_range, y_range=y_range, x_length=width, y_length=height,
                axis_config={"color": MUTE, "include_ticks": False}, tips=False, **kw)


def part(mob, substring):
    """Glyphs of `substring` inside a Text mobject (Manim drops whitespace, and Text.text is stored without it)."""
    sub = "".join(substring.split())
    start = mob.text.index(sub)
    return mob[start:start + len(sub)]


def label(text, size=22, color=INK, weight=NORMAL):
    return Text(text, font_size=size, color=color, weight=weight)


# ------------------------------------------------------------------ maths, diagrams, s-plane 
def tex(s, size=44, color=INK, **kw):
    """MathTex in house colours. Pass `substrings_to_isolate=[...]` or split `s` into several args via tex_parts."""
    return MathTex(s, font_size=size, color=color, **kw)


def tex_parts(*parts, size=44, color=INK, **kw):
    """MathTex built from several pieces so that tex_parts(...)[i] is the i-th piece (reveal or colour it alone)."""
    return MathTex(*parts, font_size=size, color=color, **kw)


def tf_block(s, size=34, min_width=2.1, height=1.15):
    """Block-diagram box with a transfer function typeset inside: tf_block(r"\\frac{1}{s+1}")."""
    t = MathTex(s, font_size=size, color=FOREST)
    box = RoundedRectangle(corner_radius=0.12, width=max(min_width, t.width + 0.6), height=max(height, t.height + 0.45),
                           stroke_color=FOREST, stroke_width=4, fill_color=WHITE, fill_opacity=1)
    return VGroup(box, t)


def flow_arrow(a, b, color=FOREST, width=4):
    return Arrow(a, b, buff=0, stroke_width=width, color=color, max_tip_length_to_length_ratio=0.2)


def summing_junction(radius=0.3):
    """Circle with a cross, as in ch01's error detector. Label the signs yourself with label("+") / label("−")."""
    return VGroup(Circle(radius=radius, stroke_color=FOREST, stroke_width=4, fill_color=WHITE, fill_opacity=1),
                  Line(UL * radius * 0.7, DR * radius * 0.7, color=FOREST, stroke_width=3),
                  Line(DL * radius * 0.7, UR * radius * 0.7, color=FOREST, stroke_width=3))


def highlight_box(mob, color=LIME, buff=0.12):
    return SurroundingRectangle(mob, color=color, buff=buff, corner_radius=0.08, stroke_width=4)


def callout(text, tag="EXAM TIP", color=OLIVE, size=22, width=None):
    """Card with a small tag pill: callout("always reduce the\\ninner loop first"). Newlines in `text` wrap it."""
    body = Text(text, font_size=size, color=INK, line_spacing=0.9)
    pl = pill(tag, color=color, size=16)
    w = width or max(body.width, pl.width) + 0.7
    box = RoundedRectangle(corner_radius=0.16, width=w, height=body.height + pl.height + 0.65, stroke_color=color, stroke_width=3,
                           fill_color=WHITE, fill_opacity=1)
    pl.move_to(box.get_top() + DOWN * 0.3).align_to(box, LEFT).shift(RIGHT * 0.25)
    body.next_to(pl, DOWN, buff=0.18).align_to(pl, LEFT)
    return VGroup(box, pl, body)


def pole_marker(point, color=FOREST, size=0.16, width=5):
    """A pole: a cross."""
    return VGroup(Line(point + (UL * size), point + (DR * size), color=color, stroke_width=width),
                  Line(point + (DL * size), point + (UR * size), color=color, stroke_width=width))


def zero_marker(point, color=FOREST, radius=0.15, width=4):
    """A zero: an open circle."""
    return Circle(radius=radius, stroke_color=color, stroke_width=width, fill_opacity=0).move_to(point)


class SPlane(VGroup):
    """The s-plane: axes with sigma and j-omega labels, the stable (left) half lightly shaded.

        sp = SPlane(x_range=(-5, 2), y_range=(-3, 3), width=6.5, height=4.6)
        sp.c2p(-1, 2)         # point on screen
        sp.pole(-1, 2)        # cross marker;  sp.zero(-3, 0)  open circle
        sp.ax                 # the underlying Axes (for plotting curves, ax.c2p, ...)
    """

    def __init__(self, x_range=(-5, 2), y_range=(-3, 3), width=6.5, height=4.6, shade=True, **kw):
        super().__init__(**kw)
        self.ax = Axes(x_range=[x_range[0], x_range[1], 1], y_range=[y_range[0], y_range[1], 1], x_length=width, y_length=height,
                       axis_config={"color": MUTE, "include_ticks": False}, tips=False)
        parts = []
        if shade and x_range[0] < 0 < x_range[1]:
            lhp = Rectangle(width=self.ax.c2p(0, 0)[0] - self.ax.c2p(x_range[0], 0)[0], height=height, fill_color=PALE, fill_opacity=0.25, stroke_width=0)
            lhp.move_to([(self.ax.c2p(0, 0)[0] + self.ax.c2p(x_range[0], 0)[0]) / 2, self.ax.c2p(0, (y_range[0] + y_range[1]) / 2)[1], 0])
            parts.append(lhp)
        self.sigma = MathTex(r"\sigma", font_size=30, color=MUTE).next_to(self.ax.c2p(x_range[1], 0), UP, buff=0.12).shift(LEFT * 0.25)
        self.jw = MathTex(r"j\omega", font_size=30, color=MUTE).next_to(self.ax.c2p(0, y_range[1]), RIGHT, buff=0.12)
        self.add(*parts, self.ax, self.sigma, self.jw)

    def c2p(self, x, y=0):
        return self.ax.c2p(x, y)

    def pole(self, x, y=0, color=FOREST):
        return pole_marker(self.c2p(x, y), color=color)

    def zero(self, x, y=0, color=FOREST):
        return zero_marker(self.c2p(x, y), color=color)


def tex_table(rows, col_w=1.6, row_h=0.7, size=32, header=True, color=INK):
    """A grid of MathTex cells with rules. Returns VGroup(grid_lines, cells) where `cells[r][c]` is each cell,
    so a scene can reveal a table cell by cell. `rows` is a list of lists of LaTeX strings ("" for empty).
    col_w may be one number or a list per column."""
    ncols = len(rows[0])
    widths = col_w if isinstance(col_w, (list, tuple)) else [col_w] * ncols
    total_w, total_h = sum(widths), row_h * len(rows)
    cells = VGroup()
    for r, row in enumerate(rows):
        line = VGroup()
        for c, s in enumerate(row):
            m = MathTex(s, font_size=size, color=(FOREST if header and r == 0 else color)) if s else VMobject()
            x = -total_w / 2 + sum(widths[:c]) + widths[c] / 2
            m.move_to([x, total_h / 2 - row_h * (r + 0.5), 0])
            line.add(m)
        cells.add(line)
    rules = VGroup()
    for r in range(len(rows) + 1):
        if r in (0, 1, len(rows)) or not header:
            rules.add(Line([-total_w / 2, total_h / 2 - row_h * r, 0], [total_w / 2, total_h / 2 - row_h * r, 0], color=PALE if r else MID, stroke_width=3))
    table = VGroup(rules, cells)
    table.cells = cells
    return table


def trace(ax, xs, ys, **kw):
    """Polyline through sample points (xs, ys) in the data coordinates of `ax`: use for simulated responses."""
    kw.setdefault("color", MID)
    kw.setdefault("stroke_width", 5)
    return polyline([ax.c2p(x, y) for x, y in zip(xs, ys)], **kw)


def formula_card(title, lines, width=6.4, size=36, title_size=24, gap=0.28, accent=MID):
    """A cheat-sheet card: a title and MathTex lines in a white card. `card.lines[i]` is each line (reveal them one by one).

        c = formula_card("Overshoot", [r"M_p=e^{-\\zeta\\pi/\\sqrt{1-\\zeta^2}}", r"t_p=\\pi/\\omega_d"], width=6.4)
    """
    head = Text(title, font_size=title_size, color=accent, weight=BOLD)
    body = VGroup(*[MathTex(s, font_size=size, color=INK) for s in lines]).arrange(DOWN, buff=gap, aligned_edge=LEFT)
    for m in body:
        if m.width > width - 0.7:
            m.scale((width - 0.7) / m.width)
    inner = VGroup(head, body).arrange(DOWN, buff=0.3, aligned_edge=LEFT)
    box = RoundedRectangle(corner_radius=0.16, width=width, height=inner.height + 0.6, stroke_color=accent, stroke_width=3,
                           fill_color=WHITE, fill_opacity=1)
    inner.move_to(box).align_to(box, LEFT).shift(RIGHT * 0.35)
    group = VGroup(box, head.move_to(inner[0]), body)
    group.box, group.head, group.lines = box, head, list(body)
    return group
