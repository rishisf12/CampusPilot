"""Distraction-2 v14: MORE background cute patterns - double hearts and sparkles. Self-deletes."""
import io, math, os, re, urllib.parse

T = 240
def rgba(r, g, b, a): return f"rgba({r},{g},{b},{a})"
PINK  = lambda a: rgba(219, 39, 119, a)
LILAC = lambda a: rgba(147, 97, 213, a)
FUR   = lambda a: rgba(255, 255, 255, a)
EDGE  = rgba(219, 39, 119, 0.25)
PAD   = rgba(244, 114, 182, 0.8)
PAD_D = rgba(219, 39, 119, 0.65)
BLUSH = rgba(244, 114, 182, 0.3)
FACE  = rgba(150, 50, 90, 0.78)
WHISK = rgba(150, 50, 90, 0.42)
NOSE  = rgba(190, 60, 110, 0.85)
CHEST = rgba(244, 114, 182, 0.2)

out = []
for x in range(0, T, 48):
    for y in range(0, T, 48):
        out.append(f'<circle cx="{x}" cy="{y}" r="2.4" fill="{PINK(0.28)}"/>')
paw_lattice = ('<g transform="translate({x} {y}) scale({s})">'
               '<ellipse rx="2.6" ry="2.2" fill="{f}"/>'
               '<circle cx="-2.4" cy="-2.7" r="1.0" fill="{f}"/>'
               '<circle cx="0" cy="-3.4" r="1.0" fill="{f}"/>'
               '<circle cx="2.4" cy="-2.7" r="1.0" fill="{f}"/></g>')
for x in range(24, T, 48):
    for y in range(24, T, 48):
        out.append(paw_lattice.format(x=x, y=y, s=0.55, f=LILAC(0.26)))

def heart(x, y, s, f, rot=0):
    return (f'<path transform="translate({x} {y}) rotate({rot}) scale({s})" fill="{f}" '
            'd="M0,-3 C-4,-8 -10,-4 -10,1 C-10,6 -4,9 0,12 C4,9 10,6 10,1 '
            'C10,-4 4,-8 0,-3 Z"/>')

def sparkle(x, y, s, f):
    return (f'<path transform="translate({x} {y}) scale({s})" fill="{f}" '
            'd="M0,-9 C1.4,-3 3,-1.4 9,0 C3,1.4 1.4,3 0,9 C-1.4,3 -3,1.4 -9,0 '
            'C-3,-1.4 -1.4,-3 0,-9 Z"/>')

def wooly(R, n):
    b = (math.pi * R / n) * 1.18
    pts = [(R * math.cos(2 * math.pi * i / n), R * math.sin(2 * math.pi * i / n)) for i in range(n)]
    d = f"M{pts[0][0]:.2f},{pts[0][1]:.2f}"
    for i in range(1, n + 1):
        p = pts[i % n]
        d += f" A{b:.2f},{b:.2f} 0 0 1 {p[0]:.2f},{p[1]:.2f}"
    return d + " Z"

HEAD_R = wooly(6.6, 11)
BODY_R = wooly(7.6, 12)
FOOT   = wooly(3.2, 6)
EAR_R  = wooly(4.4, 8)

def cat_ears():
    return (f'<path d="M-6,-8 L-2,-26 L1.8,-8 Z" fill="{FUR(0.93)}" stroke="{EDGE}" stroke-width="1"/>'
            f'<path d="M6,-8 L2,-26 L-1.8,-8 Z" fill="{FUR(0.93)}" stroke="{EDGE}" stroke-width="1"/>'
            f'<path d="M-4,-10 L-2,-23 L0,-10 Z" fill="{PAD}"/>'
            f'<path d="M4,-10 L2,-23 L0,-10 Z" fill="{PAD}"/>')

def cat_head(cx, cy, rot, closed=False):
    head_el = (f'<ellipse cx="0" cy="0" rx="6.6" ry="7" fill="{FUR(0.94)}" stroke="{EDGE}" stroke-width="0.6"/>')
    eyes = ('<path d="M-3.5,-0.9 q1.15,1.15 2.3,0 M1.2,-0.9 q1.15,1.15 2.3,0" '
            f'fill="none" stroke="{FACE}" stroke-width="0.85" stroke-linecap="round"/>') if closed \
        else (f'<circle cx="-2.6" cy="-0.7" r="1.1" fill="{FACE}"/>'
              f'<circle cx="2.6" cy="-0.7" r="1.1" fill="{FACE}"/>')
    whiskers = (f'<path d="M-4.5,1.4 L-9,0.2 M-4.5,2.2 L-9,3.6 M4.5,1.4 L9,0.2 '
                f'M4.5,2.2 L9,3.6" fill="none" stroke="{WHISK}" stroke-width="0.5" '
                'stroke-linecap="round"/>')
    nose_mouth = (f'<ellipse cx="0" cy="1.7" rx="3.2" ry="2.1" fill="{CHEST}"/>'
                  f'<ellipse cx="0" cy="0.5" rx="1.1" ry="0.85" fill="{NOSE}"/>'
                  f'<path d="M0,1.2 q0,0.9 -1.2,1.3 M0,1.2 q0,0.9 1.2,1.3" fill="none" '
                  f'stroke="{FACE}" stroke-width="0.7" stroke-linecap="round"/>')
    ears = cat_ears()
    return (f'<g transform="translate({cx} {cy}) rotate({rot})">'
            f'{head_el}{ears}{eyes}'
            f'<circle cx="-3.9" cy="1.5" r="1.5" fill="{BLUSH}"/>'
            f'<circle cx="3.9" cy="1.5" r="1.5" fill="{BLUSH}"/>'
            f'{nose_mouth}{whiskers}</g>')

def rabbit_head(cx, cy, rot, closed=False, tilt=0):
    ear = (f'<path transform="translate(-3.8 -14.2) rotate(-9) scale(0.5 1.55)" d="{EAR_R}" '
           f'fill="{FUR(0.93)}" stroke="{EDGE}" stroke-width="0.7"/>'
           f'<path transform="translate(3.8 -14.2) rotate(9) scale(0.5 1.55)" d="{EAR_R}" '
           f'fill="{FUR(0.93)}" stroke="{EDGE}" stroke-width="0.7"/>'
           f'<ellipse cx="-4" cy="-14.2" rx="1.4" ry="4" fill="{PAD}" transform="rotate(-10 -4 -14.2)"/>'
           f'<ellipse cx="4" cy="-14.2" rx="1.4" ry="4" fill="{PAD}" transform="rotate(10 4 -14.2)"/>')
    nose_mouth = (f'<ellipse cx="0" cy="0.6" rx="1.1" ry="0.9" fill="{rgba(244,114,182,0.75)}"/>'
                  f'<path d="M0,1.4 q0,1 -1.3,1.4 M0,1.4 q0,1 1.3,1.4" fill="none" '
                  f'stroke="{FACE}" stroke-width="0.7" stroke-linecap="round"/>')
    eyes = ('<path d="M-3.9,-1 q1.3,1.3 2.6,0 M1.3,-1 q1.3,1.3 2.6,0" '
            f'fill="none" stroke="{FACE}" stroke-width="0.85" stroke-linecap="round"/>') if closed \
        else (f'<circle cx="-2.7" cy="-0.9" r="1.1" fill="{FACE}"/>'
              f'<circle cx="2.7" cy="-0.9" r="1.1" fill="{FACE}"/>')
    return (f'<g transform="translate({cx} {cy}) rotate({rot})">'
            f'{ear}<path d="{HEAD_R}" fill="{FUR(0.94)}" stroke="{EDGE}" stroke-width="0.6"/>'
            f'{eyes}<circle cx="-3.9" cy="1.5" r="1.5" fill="{BLUSH}"/>'
            f'<circle cx="3.9" cy="1.5" r="1.5" fill="{BLUSH}"/>'
            f'{nose_mouth}</g>')

def body_cat(cx, cy, s=1.0):
    return (f'<g transform="translate({cx} {cy}) scale({s} {s})">'
            f'<path d="{FOOT}" transform="translate(-4.8 11.2)" fill="{FUR(0.93)}" stroke="{EDGE}" stroke-width="0.55"/>'
            f'<path d="{FOOT}" transform="translate(4.8 11.2)" fill="{FUR(0.93)}" stroke="{EDGE}" stroke-width="0.55"/>'
            f'<circle cx="-4.8" cy="11.5" r="1.6" fill="{PAD}"/><circle cx="4.8" cy="11.5" r="1.6" fill="{PAD}"/>'
            f'<ellipse cx="0" cy="5.2" rx="7" ry="8" fill="{FUR(0.94)}" stroke="{EDGE}" stroke-width="0.6"/>'
            f'<ellipse cx="0" cy="5.6" rx="3.6" ry="3.3" fill="{CHEST}"/></g>')

def body_rabbit(cx, cy, s=1.0):
    return (f'<g transform="translate({cx} {cy}) scale({s} {s})">'
            f'<path d="{FOOT}" transform="translate(-4.8 11.2)" fill="{FUR(0.93)}" stroke="{EDGE}" stroke-width="0.55"/>'
            f'<path d="{FOOT}" transform="translate(4.8 11.2)" fill="{FUR(0.93)}" stroke="{EDGE}" stroke-width="0.55"/>'
            f'<circle cx="-4.8" cy="11.5" r="1.6" fill="{PAD}"/><circle cx="4.8" cy="11.5" r="1.6" fill="{PAD}"/>'
            f'<path d="{BODY_R}" fill="{FUR(0.94)}" stroke="{EDGE}" stroke-width="0.6"/>'
            f'<ellipse cx="0" cy="5.8" rx="3.8" ry="3.5" fill="{CHEST}"/></g>')

def cat_tail(x, y):
    return (f'<path d="M{x},{y} Q{x+8},{y-1} {x+6.5},{y-9}" fill="none" '
            f'stroke="{FUR(0.93)}" stroke-width="3.2" stroke-linecap="round"/>')

def arm_paw(xp, yp, ang, s=1.0):
    rad = math.radians(ang)
    ex = math.cos(rad) * 7
    ey = math.sin(rad) * 7
    return (f'<g transform="translate({xp} {yp}) scale({s} {s})">'
            f'<path d="M0,0 L{ex},{ey}" fill="none" stroke="{FUR(0.93)}" stroke-width="4.5" stroke-linecap="round"/>'
            f'<g transform="translate({ex} {ey}) rotate({ang}) scale(1.15 1.15)">'
            f'<ellipse cx="0" cy="0" rx="4" ry="3.3" fill="{PAD}" stroke="{PAD_D}" stroke-width="1.2"/>'
            f'<circle cx="-3.2" cy="-3.8" r="1.4" fill="{FUR(0.95)}"/>'
            f'<circle cx="0" cy="-4.8" r="1.4" fill="{FUR(0.95)}"/>'
            f'<circle cx="3.2" cy="-3.8" r="1.4" fill="{FUR(0.95)}"/></g>'
            f'</g>')

def holding_hands(cat_cx, rabbit_cx, y, s=1.0):
    return (f'<g transform="scale({s} {s})">'
            + arm_paw(cat_cx + 3.4, y - 2, 28, s)
            + arm_paw(rabbit_cx - 3.4, y - 2, 152, s)
            + f'<circle cx="{(cat_cx + rabbit_cx) / 2}" cy="{y - 4}" r="2" fill="{PAD}"/>'
            + '</g>')

def s_together(x, y, s, rot):
    return (f'<g transform="translate({x} {y}) rotate({rot}) scale({s})">'
            + cat_tail(-17, 4) + body_cat(-11, 0) + body_rabbit(11, 0)
            + cat_head(-11, -8.4, -3) + rabbit_head(11, -8.8, 3, False, 2)
            + holding_hands(-11, 11, 2, s)
            + heart(0, -28, 0.62, rgba(219, 39, 119, 0.62)) + '</g>')

def s_nuzzle(x, y, s, rot):
    return (f'<g transform="translate({x} {y}) rotate({rot}) scale({s})">'
            + cat_tail(-16, 4) + body_cat(-9.8, 0) + body_rabbit(9.8, 0)
            + cat_head(-6.4, -9.6, 18, True) + rabbit_head(6.4, -10, -18, True, -3)
            + holding_hands(-9.8, 9.8, 2, s)
            + heart(0, -26, 0.48, rgba(219, 39, 119, 0.55), 8) + '</g>')

def s_gift(x, y, s, rot):
    return (f'<g transform="translate({x} {y}) rotate({rot}) scale({s})">'
            + cat_tail(-20, 4) + body_cat(-13.5, 0) + body_rabbit(11.5, 0)
            + heart(-2, 0, 0.95, rgba(219, 39, 119, 0.6))
            + arm_paw(-10, 4, 50, s) + arm_paw(6, 4, 130, s)
            + f'<circle cx="-2" cy="1" r="2" fill="{PAD}"/>'
            + rabbit_head(11.5, -8.4, -5, True, -2) + cat_head(-13.5, -8.2, 10, True) + '</g>')

out.append(s_together(162, 168, 1.2, -4))
out.append(s_nuzzle(68, 72, 1.05, 5))
out.append(s_gift(172, 60, 1.05, -3))

# MORE hearts and sparkles - doubled density
out.append(heart(30, 160, 0.85, LILAC(0.3), -8))
out.append(heart(120, 122, 0.6, PINK(0.34), 6))
out.append(heart(214, 132, 0.52, PINK(0.3), -12))
out.append(heart(12, 106, 0.52, LILAC(0.28), 10))
out.append(heart(102, 212, 0.58, PINK(0.3), -6))
out.append(heart(190, 40, 0.5, LILAC(0.32), 12))
out.append(heart(40, 40, 0.55, PINK(0.32), -10))
out.append(heart(200, 200, 0.45, LILAC(0.3), 6))

out.append(sparkle(108, 30, 0.7, PINK(0.32)))
out.append(sparkle(36, 126, 0.63, LILAC(0.3)))
out.append(sparkle(208, 102, 0.52, PINK(0.3)))
out.append(sparkle(72, 212, 0.62, LILAC(0.28)))
out.append(sparkle(220, 36, 0.58, PINK(0.3)))
out.append(sparkle(150, 180, 0.6, LILAC(0.3), 0))
out.append(sparkle(30, 40, 0.55, PINK(0.3), 0))
out.append(sparkle(200, 160, 0.5, LILAC(0.3), 0))

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{T}" height="{T}" '
       f'viewBox="0 0 {T} {T}">' + "".join(out) + "</svg>")
css = 'url("data:image/svg+xml,' + urllib.parse.quote(svg, safe="") + '")'

html_path = r"C:\Users\Appex\Documents\Default Project\ThemeVariants\Home-Distraction-2.html"
src = io.open(html_path, encoding="utf-8").read()

start_marker = 'url("data:image/svg+xml,'
end_marker = '")'
start_idx = src.find(start_marker)
end_idx = src.find(end_marker, start_idx) + len(end_marker)

new_wall_block = (f'          radial-gradient(\n'
                  f'            900px 420px at 50% -120px,\n'
                  f'            rgba(255, 166, 205, 0.55),\n'
                  f'            rgba(255, 166, 205, 0) 70%\n'
                  f'          ),\n'
                  f'          {css},\n'
                  f'          #fdeef7;')

wall_start = src.find('--cp-wall:')
wall_end = src.find('#fdeef7;', wall_start) + len('#fdeef7;')
c = src[:wall_start] + new_wall_block + src[wall_end:]

c = c.replace('background-size: auto, 260px 260px, auto;', 'background-size: auto, 240px 240px, auto;')
c = c.replace('Distraction-2 v8\n', 'Distraction-2 v14\n')
c = c.replace(
    'v13 fixes cat ears — drawn AFTER head so they paint on top',
    'v14 doubles the background cute patterns — 8 hearts + 9 sparkles per tile (was 5 hearts + 5 sparkles), plus candy dots + paw prints lattice. Cat ears drawn after head, visible paws.'
)

io.open(html_path, "w", encoding="utf-8", newline="").write(c)
print("wrote", html_path, len(c), "bytes | svg", len(svg))
os.remove(__file__)
