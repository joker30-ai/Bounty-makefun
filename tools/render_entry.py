#!/usr/bin/env python3
"""Author the Phase 7 SVG and render it offline with system librsvg/Cairo.

Python standard library only; requires DejaVu Sans, Liberation Sans Narrow,
libpango, librsvg, and libcairo. The competition entrypoint needs only Node.
All news wording and numbers are retained from the approved Friday edition.
"""

from __future__ import annotations

import ctypes as C
import ctypes.util
import hashlib
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAVY, HERO, GOLD = "#0F172A", "#111827", "#F59E0B"
WHITE, BORDER, MUTED = "#FFFFFF", "#CBD5E1", "#475569"
RED, GREEN, BLUE, SLATE = "#DC2626", "#047857", "#2563EB", "#475569"
FONT, NARROW = "DejaVu Sans", "Liberation Sans Narrow"


def library(name):
    path = ctypes.util.find_library(name)
    if not path:
        raise RuntimeError(f"Required offline system library missing: {name}")
    return C.CDLL(path)


def function(lib, name, result, *args):
    fn = getattr(lib, name)
    fn.restype, fn.argtypes = result, list(args)
    return fn


class Rectangle(C.Structure):
    _fields_ = [(key, C.c_int) for key in ("x", "y", "width", "height")]


class Typography:
    """Measure actual font ink to reject overflow and overlapping text."""

    def __init__(self):
        pango, pc = library("pango-1.0"), library("pangocairo-1.0")
        self.unref = function(library("gobject-2.0"), "g_object_unref", None, C.c_void_p)
        fmap = function(pc, "pango_cairo_font_map_get_default", C.c_void_p)()
        context = function(pango, "pango_font_map_create_context", C.c_void_p, C.c_void_p)(fmap)
        self.layout = function(pango, "pango_layout_new", C.c_void_p, C.c_void_p)(context)
        self.unref(context)
        self.description = function(pango, "pango_font_description_from_string", C.c_void_p, C.c_char_p)
        self.free_description = function(pango, "pango_font_description_free", None, C.c_void_p)
        self.set_font = function(pango, "pango_layout_set_font_description", None, C.c_void_p, C.c_void_p)
        self.set_text = function(pango, "pango_layout_set_text", None, C.c_void_p, C.c_char_p, C.c_int)
        self.extents = function(pango, "pango_layout_get_pixel_extents", None, C.c_void_p, C.POINTER(Rectangle), C.POINTER(Rectangle))
        self.baseline = function(pango, "pango_layout_get_baseline", C.c_int, C.c_void_p)

    def measure(self, text, size, bold, family):
        desc = self.description(f"{family} {'Bold' if bold else 'Regular'} {size}px".encode())
        self.set_font(self.layout, desc)
        self.free_description(desc)
        self.set_text(self.layout, text.encode(), -1)
        ink, logical = Rectangle(), Rectangle()
        self.extents(self.layout, C.byref(ink), C.byref(logical))
        return ink, logical.width, self.baseline(self.layout) / 1024


class Edition:
    def __init__(self):
        self.fonts, self.text_boxes = Typography(), []
        self.parts = [
            '<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024" role="img" aria-labelledby="title description">',
            '<title id="title">World News — Friday 20 November 2026</title>',
            '<desc id="description">Five news panels: Kyiv bridges, the COP31 draft, Myanmar and the ICJ, the US Senate Iran vote, and world markets. Bridge art is symbolic. The market area connects only the previous close and Friday close; it is not an intraday price series.</desc>',
            '<defs><linearGradient id="market-area" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#DC2626" stop-opacity="0.08"/><stop offset="1" stop-color="#DC2626" stop-opacity="0.38"/></linearGradient></defs>',
        ]

    def add(self, xml):
        self.parts.append(xml)

    def rect(self, x, y, width, height, fill, radius=0, stroke="none", sw=1):
        self.add(f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')

    def path(self, d, fill="none", stroke="none", sw=1, extra=""):
        self.add(f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round" {extra}/>')

    def circle(self, x, y, radius, fill, stroke="none", sw=1):
        self.add(f'<circle cx="{x}" cy="{y}" r="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')

    def text(self, text, x, y, size, color=NAVY, bold=True, family=FONT, maxw=None, anchor="start"):
        ink, advance, baseline = self.fonts.measure(text, size, bold, family)
        if maxw is not None and advance > maxw:
            raise ValueError(f"Text too wide ({advance} > {maxw}): {text}")
        left = x - (advance if anchor == "end" else advance / 2 if anchor == "middle" else 0)
        self.text_boxes.append({"text": text, "box": [left + ink.x, y + ink.y - baseline, ink.width, ink.height]})
        self.add(f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" font-weight="{700 if bold else 400}" text-anchor="{anchor}" fill="{color}">{html.escape(text)}</text>')

    def lines(self, lines, x, y, size, color=NAVY, leading=1.12, **kw):
        for i, line in enumerate(lines):
            self.text(line, x, y + i * size * leading, size, color, **kw)

    def card(self, key, x, y, width, height, accent, fill=WHITE):
        self.rect(x, y, width, height, fill, 10, BORDER, 1.5)
        self.add(f'<clipPath id="clip-{key}"><rect x="{x}" y="{y}" width="{width}" height="{height}" rx="10"/></clipPath>')
        self.add(f'<g clip-path="url(#clip-{key})">')
        self.rect(x, y, width, 6, accent)
        self.add('</g>')

    def validate(self):
        for i, first in enumerate(self.text_boxes):
            x, y, w, h = first["box"]
            if x < 28 or y < 15 or x + w > 995 or y + h > 1008:
                raise ValueError(f"Text outside safe canvas: {first}")
            for second in self.text_boxes[i + 1:]:
                a, b, c, d = second["box"]
                if min(x + w, a + c) > max(x, a) and min(y + h, b + d) > max(y, b):
                    raise ValueError(f"Overlapping text: {first['text']} / {second['text']}")

    def finish(self):
        self.validate()
        return "\n".join(self.parts + ['</svg>', ''])


def bridge(s):
    """Layered symbolic Kyiv skyline, suspension bridge, and river."""
    s.add('<g aria-label="Symbolic bridge and Kyiv skyline">')
    s.circle(356, 405, 22, "#334155")
    s.path("M62 449V428H83V410H101V434H121V418H142V438H157V397H173V384H179V397H195V429H218V413H236V437H255V421H277V441H297V403H312V392H320V403H334V432H356V421H381V440H416V461H62Z", "#334155")
    s.path("M62 463V447H81V435H103V450H130V440H153V456H172V433H190V449H216V443H243V459H269V437H288V453H311V443H337V453H361V434H382V448H416V465Z", "#475569")
    s.path("M60 482Q92 472 124 482T188 482T252 482T316 482T380 482T418 482M60 502Q92 492 124 502T188 502T252 502T316 502T380 502T418 502M60 522Q92 512 124 522T188 522T252 522T316 522T380 522T418 522", stroke="#334155", sw=3)
    s.path("M66 469H414", stroke="#92400E", sw=9)
    s.path("M64 460H416M69 468H411M114 396V493M357 396V493", stroke=GOLD, sw=6)
    s.path("M67 447L114 404Q236 505 357 404L411 447", stroke="#FBBF24", sw=5)
    for x, top in [(153, 432), (193, 450), (275, 450), (316, 432)]:
        s.path(f"M{x} {top}V460", stroke=GOLD, sw=2.5)
    s.path("M114 397V389M357 397V389", stroke="#FCD34D", sw=4)
    s.path("M78 486H104M167 508H202M303 488H333M354 517H397", stroke="#64748B", sw=2)
    s.add('</g>')


def fuel_emblem(s):
    s.add('<g aria-label="Fossil fuel mentions omitted from the draft">')
    s.circle(706, 456, 56, "#F1F5F9")
    s.circle(706, 456, 55, "none", GREEN, 3)
    s.rect(673, 416, 57, 72, WHITE, 5, BORDER, 2)
    for y in [430, 441, 452]:
        s.path(f"M684 {y}H719", stroke=BORDER, sw=3)
    s.rect(690, 438, 42, 58, NAVY, 7)
    s.path("M691 452H731M691 482H731", stroke="#64748B", sw=3)
    s.path("M709 456C709 456 700 468 700 472A10 10 0 0 0 720 472C720 468 709 456 709 456Z", GOLD)
    s.path("M665 498L747 414", stroke=WHITE, sw=14)
    s.path("M665 498L747 414", stroke=RED, sw=9)
    s.add('</g>')


def chamber(s):
    import math
    s.add('<g aria-label="ICJ chamber: nine votes to six">')
    s.path("M55 699A65 65 0 0 1 185 699", stroke="#E2E8F0", sw=2)
    for count, radius, color in [(9, 57, SLATE), (6, 35, BORDER)]:
        for index in range(count):
            angle = math.pi - index * math.pi / (count - 1)
            x, y = 120 + math.cos(angle) * radius, 697 - math.sin(angle) * radius
            s.rect(round(x - 5, 3), round(y - 5, 3), 10, 10, color, 3)
    s.path("M90 704H150L155 711H85Z", NAVY)
    s.add('</g>')


def senate(s):
    s.add('<g aria-label="Senate vote: 51 against and 48 for">')
    s.path("M378 662H435M382 655H431M387 649V633H426V649M384 630H429M390 626C391 604 422 604 424 626Z", fill="#EFF6FF", stroke=BLUE, sw=2.5)
    s.path("M406 609V601H418L414 605H406M396 636V649M406 636V649M416 636V649", stroke=BLUE, sw=2)
    width = 272 * 51 / (51 + 48)
    s.rect(376, 689, 272, 18, BORDER, 4)
    s.add('<clipPath id="vote-clip"><rect x="376" y="689" width="272" height="18" rx="4"/></clipPath>')
    s.add('<g clip-path="url(#vote-clip)">')
    s.rect(376, 689, f"{width:.8f}", 18, BLUE)
    s.path(f"M{376 + width:.8f} 689V707", stroke=WHITE, sw=2)
    s.add('</g></g>')


def market(s):
    """Only verified endpoints: previous close 0%, Friday close -3.7%."""
    s.add('<g aria-label="S and P 500 close-to-close change, down 3.7 percent">')
    s.path("M704 687H967", stroke=BORDER, sw=1.5, extra='stroke-dasharray="4 5"')
    s.path("M704 687L967 727V687Z", "url(#market-area)")
    s.path("M704 687L967 727", stroke=RED, sw=3)
    s.circle(704, 687, 3, RED)
    s.circle(967, 727, 4, RED)
    s.add('</g>')


def build():
    s = Edition()
    s.rect(0, 0, 1024, 1024, "#F1F5F9")
    s.rect(0, 0, 1024, 143, NAVY)
    s.text("WORLD NEWS", 36, 43, 25, WHITE)
    s.rect(683, 19, 305, 32, "#1E293B", 5, "#64748B", 1)
    s.text("DAILY GLOBAL BRIEFING", 835.5, 41, 17, WHITE, anchor="middle", maxw=280)
    s.text("FRIDAY 20 NOVEMBER 2026", 33, 116, 81, WHITE, family=NARROW, maxw=960)
    s.rect(36, 137, 952, 6, RED)

    s.card("ukraine", 36, 160, 572, 382, RED, HERO)
    s.text("UKRAINE / EUROPE", 59, 202, 24, GOLD)
    s.lines(["Russian missiles hit", "Kyiv bridges"], 57, 266, 47, WHITE, leading=1.15, maxw=531)
    s.text("Rail and power infrastructure also hit", 60, 358, 24, "#E2E8F0", bold=False, maxw=521)
    bridge(s)
    s.text("3", 584, 465, 96, GOLD, anchor="end")
    s.lines(["BRIDGES", "DAMAGED"], 584, 492, 22, GOLD, anchor="end", leading=1.2)

    s.card("climate", 624, 160, 364, 382, GREEN)
    s.text("ANTALYA / CLIMATE", 648, 202, 22, GREEN, maxw=316)
    s.text("COP31 draft", 648, 261, 40, maxw=316)
    s.text("omits fossil fuels", 648, 306, 33, maxw=316)
    s.text("Talks go into overtime", 648, 352, 23, MUTED, bold=False, maxw=316)
    fuel_emblem(s)
    s.text("0", 966, 465, 96, GREEN, anchor="end")
    s.lines(["FOSSIL FUEL", "MENTIONS"], 965, 492, 22, GREEN, anchor="end", leading=1.2)

    for key, x, accent in [("myanmar", 36, SLATE), ("iran", 358, BLUE), ("markets", 680, GOLD)]:
        s.card(key, x, 560, 308, 391, accent)
        s.path(f"M{x + 18} 743H{x + 290}", stroke=BORDER, sw=1.5)

    s.text("MYANMAR / JUSTICE", 54, 597, 21, SLATE, maxw=272)
    chamber(s)
    s.text("9–6", 326, 676, 60, SLATE, anchor="end", maxw=139)
    s.text("ICJ VOTE · 19 NOV", 326, 732, 18, SLATE, anchor="end", maxw=272)
    s.lines(["Myanmar rejects", "Rohingya genocide", "ruling"], 54, 785, 35, family=NARROW, maxw=272, leading=1.03)
    s.lines(["The Gambia brought", "the case. Myanmar", "responded Friday."], 54, 881, 22, MUTED, bold=False, maxw=272, leading=1.18)

    s.text("US / IRAN", 376, 597, 21, BLUE)
    senate(s)
    s.text("51–48", 648, 670, 58, BLUE, anchor="end", maxw=198)
    s.text("AGAINST / FOR", 648, 732, 18, BLUE, anchor="end")
    s.lines(["Senate rejects", "Iran war powers", "resolution"], 376, 785, 35, family=NARROW, maxw=272, leading=1.03)
    s.lines(["19 Nov vote on", "ending US action", "against Iran."], 376, 881, 22, MUTED, bold=False, maxw=272, leading=1.18)

    s.text("GLOBAL / MARKETS", 698, 597, 21, "#92400E", maxw=272)
    s.text("−3.7%", 970, 655, 58, RED, anchor="end", maxw=272)
    s.text("S&P 500 CLOSE", 970, 679, 18, RED, anchor="end")
    market(s)
    s.lines(["AI sell-off hits", "world markets"], 698, 785, 35, family=NARROW, maxw=272, leading=1.03)
    s.lines(["Shares fell across", "Asia, Europe and", "the US on Friday."], 698, 881, 22, MUTED, bold=False, maxw=272, leading=1.18)

    s.path("M36 972H988", stroke=BORDER, sw=1.5)
    s.text("Reporting from AP, Al Jazeera, BBC and Reuters", 36, 1000, 20, MUTED, bold=False, maxw=952)
    return s.finish(), s.text_boxes


def rasterize(svg, target, size):
    rsvg, cairo = library("rsvg-2"), library("cairo")
    unref = function(library("gobject-2.0"), "g_object_unref", None, C.c_void_p)
    create = function(rsvg, "rsvg_handle_new_from_data", C.c_void_p, C.c_char_p, C.c_size_t, C.POINTER(C.c_void_p))
    surface_new = function(cairo, "cairo_image_surface_create", C.c_void_p, C.c_int, C.c_int, C.c_int)
    context_new = function(cairo, "cairo_create", C.c_void_p, C.c_void_p)
    scale = function(cairo, "cairo_scale", None, C.c_void_p, C.c_double, C.c_double)
    draw = function(rsvg, "rsvg_handle_render_cairo", C.c_int, C.c_void_p, C.c_void_p)
    save = function(cairo, "cairo_surface_write_to_png", C.c_int, C.c_void_p, C.c_char_p)
    context_free = function(cairo, "cairo_destroy", None, C.c_void_p)
    surface_free = function(cairo, "cairo_surface_destroy", None, C.c_void_p)
    raw, error = svg.encode(), C.c_void_p()
    handle = create(raw, len(raw), C.byref(error))
    if not handle:
        raise RuntimeError("Invalid SVG")
    surface, context = None, None
    try:
        surface = surface_new(0, size, size)
        context = context_new(surface)
        scale(context, size / 1024, size / 1024)
        if not draw(handle, context) or save(surface, str(target).encode()):
            raise RuntimeError("Offline rasterization failed")
    finally:
        if context:
            context_free(context)
        if surface:
            surface_free(surface)
        unref(handle)
    target.chmod(0o644)


def main():
    svg, boxes = build()
    destination = ROOT / "assets"
    destination.mkdir(exist_ok=True)
    (destination / "entry.svg").write_text(svg)
    rasterize(svg, destination / "entry.png", 1024)
    preview = ROOT / ".private" / "phase7"
    preview.mkdir(parents=True, exist_ok=True)
    rasterize(svg, preview / "entry-512.png", 512)
    rasterize(svg, preview / "entry-300.png", 300)
    raw = (destination / "entry.png").read_bytes()
    if len(raw) >= 1024 * 1024:
        raise ValueError("PNG must be strictly below 1 MiB")
    print(json.dumps({"dimensions": [1024, 1024], "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "measured_text_runs": len(boxes), "overlapping_text_runs": 0}, indent=2))


if __name__ == "__main__":
    main()
