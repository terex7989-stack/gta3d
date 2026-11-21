from ursina import *
from ursina.color import Color
from PIL import Image, ImageDraw
from panda3d.core import Filename, AudioSound
import builtins
import math
import os
import random
import sys
import tempfile
import wave
from array import array

P, RW, N = 64, 18, 8
WORLD = P * N
ROAD_C = RW / 2
LANE = 4.5
S_BLOCK = P - RW
DIR_H = [90, 0, 270, 180]
DIR_X = [1, 0, -1, 0]
DIR_Z = [0, 1, 0, -1]
TAU = math.tau

TINTS = [
    [(196, 218, 238), (176, 204, 220), (205, 210, 220), (166, 196, 206)],
    [(255, 255, 255), (255, 242, 228), (244, 230, 220), (255, 248, 238)],
    [(255, 252, 246), (236, 236, 236), (255, 242, 220), (228, 236, 246)],
]
CAR_COLORS = [(200, 40, 40), (40, 90, 200), (235, 205, 50), (60, 160, 80), (230, 130, 40),
              (120, 60, 160), (215, 215, 215), (38, 38, 44), (150, 150, 158), (20, 110, 120)]
CAR_BODIES = ["sedan", "hatch", "suv", "pickup", "van", "sedan", "hatch", "suv"]
SKINS = [(236, 190, 150), (214, 160, 120), (180, 128, 92), (130, 88, 62), (250, 214, 184)]
HAIRS = [(42, 30, 24), (90, 60, 35), (20, 20, 20), (190, 160, 90), (150, 60, 40), (200, 200, 200)]
SHIRTS = [(230, 90, 90), (90, 170, 230), (240, 220, 90), (120, 220, 130), (220, 140, 220),
          (240, 160, 80), (240, 240, 240), (60, 60, 70), (90, 200, 190)]
PANTS = [(40, 50, 90), (60, 60, 60), (90, 70, 50), (30, 30, 30), (70, 90, 130), (120, 110, 90)]
SHOES = [(30, 30, 34), (235, 235, 235), (90, 60, 40), (180, 40, 40)]


def cl(v, a, b):
    return max(a, min(b, v))


def rgb(r, g, b, a=255):
    return Color(r / 255, g / 255, b / 255, a / 255)


def tc(col, k=1.0):
    return Color(min(1.0, col[0] * k / 255), min(1.0, col[1] * k / 255), min(1.0, col[2] * k / 255), 1)


def adiff(a, b):
    return (a - b + 180) % 360 - 180


def shade(c, k):
    return tuple(cl(int(v * k), 0, 255) for v in c)


SR = 22050


def noise(n, rng):
    return [rng.uniform(-1.0, 1.0) for _ in range(n)]


def lowpass(s, a):
    y = 0.0
    out = []
    for x in s:
        y += a * (x - y)
        out.append(y)
    return out


def highpass(s, a):
    lo = lowpass(s, a)
    return [x - l for x, l in zip(s, lo)]


def normalize(s, peak):
    m = max(1e-9, max(abs(x) for x in s))
    k = peak / m
    return [x * k for x in s]


def loopify(s, fade):
    n = len(s) - fade
    out = s[:n]
    for i in range(fade):
        k = i / fade
        out[i] = out[i] * k + s[n + i] * (1 - k)
    return out


def save_wav(path, s):
    data = array("h", [int(max(-1.0, min(1.0, x)) * 32000) for x in s])
    if sys.byteorder == "big":
        data.byteswap()
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


def gen_engine():
    rng = random.Random(1)
    fade = 800
    n = SR + fade
    sig = []
    for i in range(n):
        t = i / SR
        ph = 46.0 * t
        s = (0.45 * math.sin(TAU * ph) + 0.32 * math.sin(2 * TAU * ph) + 0.22 * math.sin(3 * TAU * ph)
             + 0.12 * math.sin(5 * TAU * ph))
        s *= 0.82 + 0.18 * math.sin(TAU * 9 * t)
        sig.append(s)
    nz = lowpass(noise(n, rng), 0.1)
    sig = [a + 0.35 * b for a, b in zip(sig, nz)]
    return loopify(normalize(sig, 0.7), fade)


def gen_gun():
    rng = random.Random(2)
    n = int(SR * 0.4)
    nz = noise(n, rng)
    out = []
    for i in range(n):
        t = i / SR
        out.append(nz[i] * math.exp(-t * 28) * 0.9 + math.sin(TAU * 95 * t) * math.exp(-t * 16) * 0.8
                   + math.sin(TAU * 1700 * t) * math.exp(-t * 90) * 0.25)
    return normalize(out, 0.95)


def gen_smg():
    rng = random.Random(7)
    n = int(SR * 0.2)
    nz = noise(n, rng)
    out = []
    for i in range(n):
        t = i / SR
        out.append(nz[i] * math.exp(-t * 60) * 0.85 + math.sin(TAU * 120 * t) * math.exp(-t * 32) * 0.7
                   + math.sin(TAU * 2300 * t) * math.exp(-t * 130) * 0.2)
    return normalize(out, 0.85)


def gen_shotgun():
    rng = random.Random(8)
    n = int(SR * 0.7)
    nz = noise(n, rng)
    lo = lowpass(nz, 0.35)
    out = []
    for i in range(n):
        t = i / SR
        out.append(lo[i] * math.exp(-t * 8) * 1.6 + nz[i] * math.exp(-t * 45) * 0.7
                   + math.sin(TAU * 62 * t) * math.exp(-t * 9) * 1.0)
    return normalize(out, 0.98)


def gen_boom():
    rng = random.Random(9)
    n = int(SR * 1.8)
    nz = noise(n, rng)
    rumble = lowpass(nz, 0.05)
    mid = lowpass(nz, 0.2)
    out = []
    for i in range(n):
        t = i / SR
        ph = TAU * (80 / 1.6) * (1 - math.exp(-1.6 * t))
        out.append(rumble[i] * math.exp(-t * 2.2) * 6.0 + mid[i] * math.exp(-t * 6) * 2.0
                   + nz[i] * math.exp(-t * 35) * 0.8 + math.sin(ph) * math.exp(-t * 3.5) * 1.0)
    return normalize(out, 0.98)


def gen_click():
    rng = random.Random(10)
    n = int(SR * 0.06)
    nz = noise(n, rng)
    out = [nz[i] * math.exp(-(i / SR) * 160) * 0.6 + math.sin(TAU * 1100 * (i / SR)) * math.exp(-(i / SR) * 120) * 0.5
           for i in range(n)]
    return normalize(out, 0.5)


def gen_reload():
    rng = random.Random(11)
    n = int(SR * 0.6)
    nz = noise(n, rng)
    out = []
    for i in range(n):
        t = i / SR
        v = 0.0
        for t0, amp in ((0.02, 0.6), (0.32, 1.0)):
            d = t - t0
            if d >= 0:
                v += amp * (nz[i] * math.exp(-d * 140) * 0.7 + math.sin(TAU * 1400 * d) * math.exp(-d * 80) * 0.4
                            + math.sin(TAU * 200 * d) * math.exp(-d * 60) * 0.5)
        out.append(v)
    return normalize(out, 0.7)


def gen_pin():
    rng = random.Random(12)
    n = int(SR * 0.18)
    nz = noise(n, rng)
    out = [math.sin(TAU * 3200 * (i / SR)) * math.exp(-(i / SR) * 60) * 0.5 + nz[i] * math.exp(-(i / SR) * 90) * 0.4
           for i in range(n)]
    return normalize(out, 0.6)


def gen_step():
    rng = random.Random(6)
    n = int(SR * 0.14)
    nz = lowpass(noise(n, rng), 0.25)
    return normalize([nz[i] * math.exp(-(i / SR) * 35) for i in range(n)], 0.7)


GENS = {"engine": gen_engine, "gun": gen_gun, "smg": gen_smg, "shotgun": gen_shotgun, "boom": gen_boom,
        "click": gen_click, "reload": gen_reload, "pin": gen_pin, "step": gen_step}
POOL_SIZE = {"gun": 5, "smg": 6, "shotgun": 3, "boom": 4, "click": 2, "reload": 2, "pin": 2, "step": 3}
SFX_DIR = os.path.join(tempfile.gettempdir(), "gta3d_sfx_v2")


def ensure_sounds(folder):
    os.makedirs(folder, exist_ok=True)
    marker = os.path.join(folder, "ready")
    if os.path.exists(marker):
        return
    print("Генерирую звуки (только при первом запуске)...")
    for name, fn in GENS.items():
        save_wav(os.path.join(folder, name + ".wav"), fn())
    open(marker, "w").close()


class Sound:
    def __init__(self):
        self.ok = False
        self.pools = {}
        self.idx = {}
        self.slots = {}
        try:
            ensure_sounds(SFX_DIR)
            self.ok = True
        except Exception:
            self.ok = False

    def load(self, name):
        return builtins.base.loader.loadSfx(Filename.fromOsSpecific(os.path.join(SFX_DIR, name + ".wav")))

    def preload(self):
        if not self.ok:
            return
        try:
            for name in GENS:
                if name == "engine":
                    continue
                self.pools[name] = [self.load(name) for _ in range(POOL_SIZE.get(name, 3))]
                self.idx[name] = 0
        except Exception:
            self.ok = False

    def play(self, name, vol=1.0, rate=1.0, pan=0.0):
        if not self.ok or vol < 0.02:
            return
        try:
            pool = self.pools[name]
            i = self.idx[name]
            self.idx[name] = (i + 1) % len(pool)
            s = pool[i]
            s.setVolume(min(1.0, vol))
            s.setPlayRate(rate)
            s.setBalance(pan)
            s.play()
        except Exception:
            self.ok = False

    def at(self, name, x, z, vol=1.0, rate=1.0, rng=110.0):
        dx, dz = x - cam_pos[0], z - cam_pos[2]
        d = math.hypot(dx, dz)
        if d > rng:
            return
        att = (1 - d / rng) ** 1.5
        sy, cy = math.sin(math.radians(cam_yaw)), math.cos(math.radians(cam_yaw))
        pan = cl((dx * cy - dz * sy) / max(d, 6.0), -1, 1) * 0.85
        self.play(name, vol * att, rate, pan)

    def loop(self, slot, name, vol, rate=1.0, pan=0.0):
        if not self.ok:
            return
        try:
            s = self.slots.get(slot)
            if s is None:
                s = self.load(name)
                s.setLoop(True)
                self.slots[slot] = s
            if vol < 0.015:
                if s.status() == AudioSound.PLAYING:
                    s.stop()
                return
            s.setVolume(min(1.0, vol))
            s.setPlayRate(rate)
            s.setBalance(pan)
            if s.status() != AudioSound.PLAYING:
                s.play()
        except Exception:
            self.ok = False

    def loop_at(self, slot, name, x, z, vol, rate=1.0, rng=110.0):
        dx, dz = x - cam_pos[0], z - cam_pos[2]
        d = math.hypot(dx, dz)
        if d > rng:
            self.loop(slot, name, 0)
            return
        att = (1 - d / rng) ** 1.5
        sy, cy = math.sin(math.radians(cam_yaw)), math.cos(math.radians(cam_yaw))
        pan = cl((dx * cy - dz * sy) / max(d, 6.0), -1, 1) * 0.85
        self.loop(slot, name, vol * att, rate, pan)


app = Ursina(title="GRAND THEFT PYTHON 3D", borderless=False)
window.exit_button.visible = False
window.fps_counter.enabled = True
mouse_look = True
mouse.visible = False
mouse.locked = True
camera.fov = 85
camera.clip_plane_near = 0.3
cam_pos = [0.0, 1.7, 0.0]
cam_yaw, cam_pitch, cam_free, cam_idle = 0.0, 14.0, 0.0, 0.0

try:
    Sky()
except Exception:
    pass
try:
    scene.fog_color = Color(0.72, 0.8, 0.9, 1)
    scene.fog_density = (90, 340)
except Exception:
    pass

snd = Sound()
snd.preload()


class MB:
    def __init__(self):
        self.v, self.c, self.uv, self.t = [], [], [], []

    def quad(self, p0, p1, p2, p3, c0, c1, c2, c3, uv=None):
        n = len(self.v)
        self.v += [p0, p1, p2, p3]
        self.c += [c0, c1, c2, c3]
        self.uv += uv if uv else [Vec2(0, 0)] * 4
        self.t.append((n, n + 1, n + 2))
        self.t.append((n, n + 2, n + 3))

    def mesh(self):
        return Mesh(vertices=self.v, triangles=self.t, colors=self.c, uvs=self.uv, static=True)


SK = {"z+": 0.95, "x+": 0.82, "z-": 0.62, "x-": 0.7, "top": 1.1}


def wall(mb, ax, az, bx, bz, y0, y1, col, k, nu, ny, textured, ao):
    if ao > 0 and y1 - y0 > 8:
        segs = [(y0, y0 + 8, 1 - ao, 1.0), (y0 + 8, y1, 1.0, 1.0)]
    else:
        segs = [(y0, y1, 1 - ao, 1.0)]
    for ya, yb, ka, kb in segs:
        ca, cb = tc(col, k * ka), tc(col, k * kb)
        va, vb = (ya - y0) / (y1 - y0) * ny, (yb - y0) / (y1 - y0) * ny
        uv = [Vec2(0, va), Vec2(nu, va), Vec2(nu, vb), Vec2(0, vb)] if textured else None
        mb.quad(Vec3(ax, ya, az), Vec3(bx, ya, bz), Vec3(bx, yb, bz), Vec3(ax, yb, az), ca, ca, cb, cb, uv)


def box(mb, cx, cy, cz, sx, sy, sz, col, sides=True, top=True, tex=False, ao=0.0, bright=1.0):
    xa, xb, ya, yb, za, zb = cx - sx / 2, cx + sx / 2, cy - sy / 2, cy + sy / 2, cz - sz / 2, cz + sz / 2
    if sides:
        nx_, nz_, ny_ = max(1, round(sx / 16)), max(1, round(sz / 16)), max(1, round(sy / 14))
        wall(mb, xa, zb, xb, zb, ya, yb, col, SK["z+"] * bright, nx_, ny_, tex, ao)
        wall(mb, xb, za, xa, za, ya, yb, col, SK["z-"] * bright, nx_, ny_, tex, ao)
        wall(mb, xb, zb, xb, za, ya, yb, col, SK["x+"] * bright, nz_, ny_, tex, ao)
        wall(mb, xa, za, xa, zb, ya, yb, col, SK["x-"] * bright, nz_, ny_, tex, ao)
    if top:
        c = tc(col, SK["top"] * bright)
        mb.quad(Vec3(xa, yb, za), Vec3(xb, yb, za), Vec3(xb, yb, zb), Vec3(xa, yb, zb), c, c, c, c)


def flat(mb, xa, za, xb, zb, y, col):
    c = tc(col)
    mb.quad(Vec3(xa, y, za), Vec3(xb, y, za), Vec3(xb, y, zb), Vec3(xa, y, zb), c, c, c, c)


def tex_from(im):
    t = Texture(im)
    try:
        t.filtering = "mipmap"
    except Exception:
        pass
    return t


def make_glass():
    S = 256
    im = Image.new("RGB", (S, S), (60, 75, 95))
    d = ImageDraw.Draw(im)
    rng = random.Random(21)
    for gx in range(8):
        for gy in range(8):
            x0, y0 = gx * 32, gy * 32
            base = rng.randint(-14, 14)
            for yy in range(y0 + 2, y0 + 30):
                t = (yy - y0) / 32
                d.line((x0 + 2, yy, x0 + 29, yy), fill=(int(96 + base - 35 * t), int(142 + base - 30 * t), int(188 + base - 24 * t)))
            if rng.random() < 0.1:
                d.rectangle((x0 + 2, y0 + 2, x0 + 29, y0 + 29), fill=(250, 232, 170))
            d.polygon([(x0 + 3, y0 + 3), (x0 + 14, y0 + 3), (x0 + 3, y0 + 16)], fill=(175, 205, 230))
    for k in range(9):
        d.line((k * 32, 0, k * 32, S), fill=(44, 52, 64), width=2)
        d.line((0, k * 32, S, k * 32), fill=(44, 52, 64), width=2)
    return tex_from(im)


def make_brick():
    S = 256
    im = Image.new("RGB", (S, S), (205, 195, 180))
    d = ImageDraw.Draw(im)
    rng = random.Random(22)
    for row in range(32):
        y = row * 8
        off = 0 if row % 2 == 0 else 8
        for bx in range(-1, 17):
            x = bx * 16 + off
            v = rng.randint(-14, 14)
            d.rectangle((x + 1, y + 1, x + 15, y + 7), fill=(176 + v, 92 + v // 2, 74 + v // 2))
    for gx in range(4):
        for gy in range(4):
            x0, y0 = gx * 64 + 14, gy * 64 + 10
            x1, y1 = x0 + 36, y0 + 36
            lit = rng.random() < 0.14
            d.rectangle((x0 - 3, y0 - 3, x1 + 3, y1 + 3), fill=(238, 236, 230))
            for yy in range(y0, y1):
                t = (yy - y0) / 36
                d.line((x0, yy, x1, yy), fill=(255, 228, 150) if lit else (int(84 - 28 * t), int(112 - 32 * t), int(146 - 36 * t)))
            d.line(((x0 + x1) // 2, y0, (x0 + x1) // 2, y1), fill=(238, 236, 230), width=2)
            d.rectangle((x0 - 8, y1 + 4, x1 + 8, y1 + 9), fill=(112, 108, 104))
            for k in range(5):
                xx = x0 - 6 + k * 11
                d.line((xx, y1 + 9, xx, y1 + 18), fill=(70, 70, 74), width=1)
            d.line((x0 - 8, y1 + 18, x1 + 8, y1 + 18), fill=(70, 70, 74), width=2)
    return tex_from(im)


def make_concrete():
    S = 256
    im = Image.new("RGB", (S, S), (208, 208, 204))
    d = ImageDraw.Draw(im)
    rng = random.Random(23)
    for gy in range(4):
        y0 = gy * 64
        for yy in range(y0 + 14, y0 + 46):
            t = (yy - y0 - 14) / 32
            d.line((0, yy, S, yy), fill=(int(78 - 26 * t), int(104 - 30 * t), int(138 - 34 * t)))
        for gx in range(8):
            x0 = gx * 32
            if rng.random() < 0.16:
                d.rectangle((x0 + 2, y0 + 16, x0 + 30, y0 + 44), fill=(255, 228, 150))
            d.line((x0, y0 + 14, x0, y0 + 46), fill=(220, 220, 216), width=3)
        d.rectangle((0, y0 + 10, S, y0 + 14), fill=(176, 176, 172))
        d.rectangle((0, y0 + 46, S, y0 + 50), fill=(176, 176, 172))
        d.line((0, y0 + 2, S, y0 + 2), fill=(190, 190, 186), width=2)
    for k in range(0, S, 64):
        d.line((k, 0, k, S), fill=(190, 190, 186), width=1)
    return tex_from(im)


def make_asphalt():
    S = 128
    im = Image.new("RGB", (S, S), (50, 52, 56))
    px = im.load()
    rng = random.Random(24)
    for x in range(S):
        for y in range(S):
            v = rng.randint(-8, 8)
            px[x, y] = (50 + v, 52 + v, 56 + v)
    d = ImageDraw.Draw(im)
    for _ in range(5):
        x, y = rng.randint(0, S), rng.randint(0, S)
        d.line((x, y, x + rng.randint(-30, 30), y + rng.randint(-30, 30)), fill=(36, 37, 40), width=1)
    return Texture(im)


blocks = {}
parks = set()
block_rects_for_map = []
chunk_meshes = {}
CH = 2


def mb_for(x, z, kind):
    key = (int(x // (P * CH)), int(z // (P * CH)), kind)
    m = chunk_meshes.get(key)
    if m is None:
        m = chunk_meshes[key] = MB()
    return m


Entity(model="plane", scale=(WORLD + 3000, 1, WORLD + 3000), position=(WORLD / 2, -0.1, WORLD / 2),
       color=rgb(86, 132, 80))
Entity(model="plane", scale=(WORLD, 1, WORLD), position=(WORLD / 2, 0, WORLD / 2), color=rgb(255, 255, 255),
       texture=make_asphalt(), texture_scale=(WORLD / 5, WORLD / 5))

Y_MARK = 0.07
YEL, WHT = (232, 202, 70), (225, 225, 225)

for k in range(N):
    rc = k * P + ROAD_C
    for i in range(N):
        s0 = i * P + RW + 4.5
        s1 = (i + 1) * P - 4.5 if i < N - 1 else WORLD - 0.5
        mid = (s0 + s1) / 2
        gx = mb_for(mid, rc, "g")
        gz = mb_for(rc, mid, "g")
        for off in (-0.18, 0.18):
            flat(gx, s0, rc + off - 0.1, s1, rc + off + 0.1, Y_MARK, YEL)
            flat(gz, rc + off - 0.1, s0, rc + off + 0.1, s1, Y_MARK, YEL)
        for off in (0.7, RW - 0.7):
            flat(gx, s0, k * P + off - 0.08, s1, k * P + off + 0.08, Y_MARK, WHT)
            flat(gz, k * P + off - 0.08, s0, k * P + off + 0.08, s1, Y_MARK, WHT)

for i in range(N):
    for j in range(N):
        ix, jz = i * P, j * P
        g = mb_for(ix + RW / 2, jz + RW / 2, "g")
        for s in range(8):
            o = 1.2 + s * 2.1
            flat(g, ix + RW + 0.8, jz + o, ix + RW + 3.8, jz + o + 1.1, Y_MARK, (232, 232, 232))
            if i > 0:
                flat(g, ix - 3.8, jz + o, ix - 0.8, jz + o + 1.1, Y_MARK, (232, 232, 232))
            flat(g, ix + o, jz + RW + 0.8, ix + o + 1.1, jz + RW + 3.8, Y_MARK, (232, 232, 232))
            if j > 0:
                flat(g, ix + o, jz - 3.8, ix + o + 1.1, jz - 0.8, Y_MARK, (232, 232, 232))


def traffic_light(g, x, z, state):
    box(g, x, 3.05, z, 0.2, 5.5, 0.2, (58, 60, 66))
    box(g, x, 5.55, z, 0.5, 1.2, 0.5, (28, 28, 32))
    for face_z in (1, -1):
        for n_, (cy, on, off) in enumerate(((5.95, (255, 50, 40), (80, 20, 20)),
                                            (5.55, (255, 200, 40), (90, 70, 20)),
                                            (5.15, (60, 230, 90), (20, 70, 30)))):
            lit = (state == 0 and n_ == 2) or (state == 1 and n_ == 0)
            box(g, x, cy, z + face_z * 0.26, 0.26, 0.26, 0.04, on if lit else off, bright=1.0)
    for face_x in (1, -1):
        for n_, (cy, on, off) in enumerate(((5.95, (255, 50, 40), (80, 20, 20)),
                                            (5.55, (255, 200, 40), (90, 70, 20)),
                                            (5.15, (60, 230, 90), (20, 70, 30)))):
            lit = (state == 1 and n_ == 2) or (state == 0 and n_ == 0)
            box(g, x + face_x * 0.26, cy, z, 0.04, 0.26, 0.26, on if lit else off, bright=1.0)


def street_tree(g, tx, tz):
    box(g, tx, 2.0, tz, 0.35, 3.4, 0.35, (96, 66, 40))
    gcol = random.choice([(56, 128, 62), (70, 146, 72), (48, 110, 56)])
    box(g, tx, 4.4, tz, 2.6, 2.0, 2.6, gcol)
    box(g, tx, 5.7, tz, 1.7, 1.2, 1.7, shade(gcol, 1.1))


def bench(g, x, z, along_x):
    if along_x:
        box(g, x, 0.75, z, 1.8, 0.1, 0.5, (120, 80, 50))
        box(g, x, 1.1, z - 0.22, 1.8, 0.4, 0.08, (120, 80, 50))
        for s in (-0.7, 0.7):
            box(g, x + s, 0.55, z, 0.1, 0.5, 0.45, (50, 50, 54))
    else:
        box(g, x, 0.75, z, 0.5, 0.1, 1.8, (120, 80, 50))
        box(g, x - 0.22, 1.1, z, 0.08, 0.4, 1.8, (120, 80, 50))
        for s in (-0.7, 0.7):
            box(g, x, 0.55, z + s, 0.45, 0.5, 0.1, (50, 50, 54))


def bus_stop(g, x, z):
    box(g, x, 3.1, z, 3.4, 0.14, 1.6, (60, 70, 90))
    for sx in (-1.6, 1.6):
        box(g, x + sx, 1.7, z + 0.7, 0.1, 2.8, 0.1, (60, 60, 66))
    box(g, x, 1.8, z + 0.74, 3.2, 1.8, 0.04, (150, 190, 215))
    box(g, x, 0.85, z + 0.4, 2.2, 0.08, 0.5, (110, 80, 54))


def add_building(xa, za, xb, zb):
    bw, bd = xb - xa, zb - za
    cx, cz = (xa + xb) / 2, (za + zb) / 2
    tall = random.random() < 0.17
    h = random.uniform(34, 64) if tall else random.uniform(10, 26)
    ti = 0 if tall else random.choice((0, 1, 1, 2, 2))
    tint = random.choice(TINTS[ti])
    g = mb_for(cx, cz, "g")
    f = mb_for(cx, cz, "f%d" % ti)
    flat(g, xa - 2.2, za - 2.2, xb + 2.2, zb + 2.2, 0.31, (126, 126, 120))
    band = random.choice([(66, 74, 88), (92, 62, 58), (64, 84, 76), (88, 88, 94)])
    box(g, cx, 2.1, cz, bw + 0.15, 3.6, bd + 0.15, band, top=False, ao=0.3)
    for side in (1, -1):
        zz = zb + 0.09 if side == 1 else za - 0.09
        box(g, cx - bw * 0.22, 2.0, zz, bw * 0.34, 1.9, 0.05, (150, 192, 218))
        box(g, cx + bw * 0.28, 1.7, zz, 1.5, 2.6, 0.08, (40, 36, 34))
        box(g, cx + bw * 0.28, 1.0, zz + 0.03, 0.12, 0.12, 0.05, (210, 190, 80))
    awn = random.choice([(190, 50, 50), (50, 110, 170), (60, 140, 80), (210, 170, 50)])
    box(g, cx, 4.0, cz, bw + 0.9, 0.18, bd + 0.9, awn)
    box(g, cx, 3.82, cz, bw + 0.9, 0.18, bd + 0.9, shade(awn, 0.7), top=False)
    sign = random.choice([(255, 60, 120), (60, 220, 255), (255, 220, 60), (120, 255, 120)])
    box(g, cx - bw * 0.22, 4.7, zb + 0.35, bw * 0.34, 0.6, 0.1, sign, bright=1.0)
    box(f, cx, 0.3 + h / 2, cz, bw, h, bd, tint, top=False, tex=True, ao=0.3)
    cornice = (200, 196, 190)
    box(g, cx, 0.3 + h + 0.25, cz, bw + 0.5, 0.5, bd + 0.5, shade(cornice, 0.85))
    ry = 0.3 + h + 0.5
    flat(g, xa + 0.3, za + 0.3, xb - 0.3, zb - 0.3, ry + 0.01, (86, 86, 90))
    for _ in range(random.randint(1, 3)):
        ax = random.uniform(xa + 2, xb - 2)
        az = random.uniform(za + 2, zb - 2)
        box(g, ax, ry + 0.6, az, random.uniform(1.5, 3), 1.2, random.uniform(1.5, 3), (150, 150, 156))
        box(g, ax, ry + 1.3, az, 0.8, 0.2, 0.8, (110, 110, 116))
    if random.random() < 0.4:
        tx, tz = random.uniform(xa + 3, xb - 3), random.uniform(za + 3, zb - 3)
        for lx in (-0.9, 0.9):
            for lz in (-0.9, 0.9):
                box(g, tx + lx, ry + 1.0, tz + lz, 0.12, 2.0, 0.12, (70, 70, 74))
        box(g, tx, ry + 3.0, tz, 2.6, 2.0, 2.6, (150, 110, 80))
        box(g, tx, ry + 4.2, tz, 2.8, 0.4, 2.8, (90, 70, 54))
    box(g, xb - 2.0, ry + 1.3, zb - 2.0, 2.4, 2.6, 2.4, shade(cornice, 0.8))
    if tall:
        th = random.uniform(8, 16)
        box(f, cx, ry + th / 2, cz, bw * 0.62, th, bd * 0.62, tint, top=False, tex=True)
        box(g, cx, ry + th + 0.25, cz, bw * 0.62 + 0.4, 0.5, bd * 0.62 + 0.4, shade(cornice, 0.85))
        box(g, cx, ry + th + 4.5, cz, 0.2, 8, 0.2, (170, 40, 40))
        box(g, cx, ry + th + 8.6, cz, 0.4, 0.4, 0.4, (255, 60, 60), bright=1.0)
    elif random.random() < 0.3:
        box(g, xa + 1.5, ry + 3.5, za + 1.5, 0.2, 7, 0.2, (170, 40, 40))


for i in range(N):
    for j in range(N):
        x0, z0 = i * P + RW, j * P + RW
        cx0, cz0 = x0 + S_BLOCK / 2, z0 + S_BLOCK / 2
        g = mb_for(cx0, cz0, "g")
        box(g, cx0, 0.15, cz0, S_BLOCK, 0.3, S_BLOCK, (164, 164, 158))
        for off in range(4, int(S_BLOCK), 6):
            flat(g, x0 + off, z0 + 0.05, x0 + off + 0.08, z0 + S_BLOCK - 0.05, 0.305, (140, 140, 134))
        block_rects_for_map.append((x0, z0, i, j))
        for lx, lz in ((x0 + 0.9, z0 + 0.9), (x0 + S_BLOCK - 0.9, z0 + 0.9),
                       (x0 + 0.9, z0 + S_BLOCK - 0.9), (x0 + S_BLOCK - 0.9, z0 + S_BLOCK - 0.9)):
            box(g, lx, 3.05, lz, 0.18, 5.5, 0.18, (62, 64, 70))
            box(g, lx, 5.9, lz, 0.55, 0.18, 0.55, (255, 244, 200), bright=1.0)
        if (i + j) % 2 == 0:
            traffic_light(g, x0 + 0.6, z0 + 0.6, (i + j) // 2 % 2)
        else:
            traffic_light(g, x0 + S_BLOCK - 0.6, z0 + S_BLOCK - 0.6, (i * j) % 2)
        box(g, x0 + 1.0, 0.65, z0 + 12, 0.35, 0.7, 0.35, (200, 40, 40))
        box(g, x0 + 1.0, 1.05, z0 + 12, 0.42, 0.12, 0.42, (170, 30, 30))
        box(g, x0 + S_BLOCK - 1.0, 0.7, z0 + S_BLOCK - 14, 0.5, 0.8, 0.5, (40, 90, 60))
        for tz_ in (14, 32):
            if random.random() < 0.6:
                street_tree(g, x0 + 0.8, z0 + tz_)
        if random.random() < 0.5:
            bench(g, x0 + 10, z0 + 0.9, True)
        if random.random() < 0.15:
            bus_stop(g, x0 + S_BLOCK / 2, z0 + 1.6)
        if random.random() < 0.13:
            parks.add((i, j))
            blocks[(i, j)] = []
            box(g, cx0, 0.375, cz0, S_BLOCK - 5, 0.15, S_BLOCK - 5, (84, 150, 80))
            box(g, cx0, 0.46, cz0, 2.4, 0.04, S_BLOCK - 5, (190, 176, 140))
            box(g, cx0, 0.46, cz0, S_BLOCK - 5, 0.04, 2.4, (190, 176, 140))
            box(g, cx0, 0.7, cz0, 3.0, 0.5, 3.0, (150, 150, 150))
            box(g, cx0, 1.2, cz0, 1.6, 0.6, 1.6, (120, 170, 220))
            for _ in range(9):
                tx = x0 + random.uniform(6, S_BLOCK - 6)
                tz = z0 + random.uniform(6, S_BLOCK - 6)
                if abs(tx - cx0) < 3 or abs(tz - cz0) < 3:
                    continue
                box(g, tx, 1.95, tz, 0.5, 3, 0.5, (100, 68, 42))
                gc = random.choice([(56, 128, 62), (70, 146, 72), (48, 110, 56)])
                box(g, tx, 4.4, tz, random.uniform(3.2, 4.2), 2.2, random.uniform(3.2, 4.2), gc)
                box(g, tx, 6.0, tz, 2.3, 1.6, 2.3, shade(gc, 1.1))
            for _ in range(6):
                fx = x0 + random.uniform(4, S_BLOCK - 4)
                fz = z0 + random.uniform(4, S_BLOCK - 4)
                box(g, fx, 0.6, fz, 1.2, 0.3, 1.2, random.choice([(220, 60, 90), (240, 200, 60), (160, 80, 200)]))
            continue
        m = 3
        inner = S_BLOCK - 2 * m
        w = (inner - 3) / 2
        mode = random.choice((1, 2, 4, 4))
        if mode == 1:
            rects = [(x0 + m, z0 + m, x0 + m + inner, z0 + m + inner)]
        elif mode == 2:
            if random.random() < 0.5:
                rects = [(x0 + m, z0 + m, x0 + m + w, z0 + m + inner),
                         (x0 + m + w + 3, z0 + m, x0 + m + inner, z0 + m + inner)]
            else:
                rects = [(x0 + m, z0 + m, x0 + m + inner, z0 + m + w),
                         (x0 + m, z0 + m + w + 3, x0 + m + inner, z0 + m + inner)]
        else:
            rects = []
            for a in (0, 1):
                for b in (0, 1):
                    xa, za = x0 + m + a * (w + 3), z0 + m + b * (w + 3)
                    rects.append((xa, za, xa + w, za + w))
        blocks[(i, j)] = rects
        for r in rects:
            add_building(*r)

cloud = MB()
for _ in range(16):
    ccx, ccz, cy_ = random.uniform(-100, WORLD + 100), random.uniform(-100, WORLD + 100), random.uniform(110, 160)
    for _ in range(random.randint(3, 5)):
        sx, sz = random.uniform(30, 70), random.uniform(20, 40)
        px_, pz_ = ccx + random.uniform(-30, 30), ccz + random.uniform(-20, 20)
        sy = random.uniform(8, 14)
        box(cloud, px_, cy_, pz_, sx, sy, sz, (246, 248, 252), bright=0.92)
        flat(cloud, px_ - sx / 2, pz_ - sz / 2, px_ + sx / 2, pz_ + sz / 2, cy_ - sy / 2, (214, 220, 232))
Entity(model=cloud.mesh(), double_sided=True)

FACADES = [make_glass(), make_brick(), make_concrete()]
for (ci, cj, kind), mbx in chunk_meshes.items():
    if kind == "g":
        Entity(model=mbx.mesh(), double_sided=True)
    else:
        Entity(model=mbx.mesh(), texture=FACADES[int(kind[1])], double_sided=True)


def hits_building(x, z, r):
    for xa, za, xb, zb in blocks.get((int(x // P), int(z // P)), ()):
        cx = max(xa, min(x, xb))
        cz = max(za, min(z, zb))
        if (x - cx) ** 2 + (z - cz) ** 2 < r * r:
            return True
    return False


def move_circle(o, dx, dz, r):
    nx = cl(o.x + dx, 3, WORLD - 3)
    if not hits_building(nx, o.z, r):
        o.x = nx
    nz = cl(o.z + dz, 3, WORLD - 3)
    if not hits_building(o.x, nz, r):
        o.z = nz


def build_person(shirt, pants, skin, hair, style, outfit, shoes, glasses=False, beard=False):
    body, leg, arm = MB(), MB(), MB()
    dark = (36, 30, 26)
    box(body, 0, 0.9, 0, 0.6, 0.26, 0.34, pants)
    box(body, 0, 1.02, 0, 0.62, 0.07, 0.36, dark)
    box(body, 0, 1.02, 0.185, 0.09, 0.06, 0.02, (210, 190, 80))
    box(body, 0, 1.31, 0, 0.66, 0.6, 0.36, shirt)
    box(body, 0, 1.64, 0, 0.15, 0.14, 0.15, shade(skin, 0.95))
    box(body, 0, 1.6, 0.02, 0.3, 0.05, 0.22, shade(shirt, 1.15))
    if outfit == "jacket":
        box(body, 0, 1.3, 0.185, 0.035, 0.58, 0.02, shade(shirt, 0.6))
        box(body, -0.19, 1.15, 0.185, 0.16, 0.12, 0.02, shade(shirt, 0.8))
        box(body, 0.19, 1.15, 0.185, 0.16, 0.12, 0.02, shade(shirt, 0.8))
    elif outfit == "cop":
        box(body, 0, 1.32, 0.185, 0.08, 0.34, 0.02, (20, 20, 24))
        box(body, 0.18, 1.46, 0.185, 0.08, 0.08, 0.02, (230, 200, 60))
        box(body, -0.18, 1.46, 0.185, 0.1, 0.06, 0.02, (180, 180, 190))
        box(body, 0, 1.06, 0.185, 0.6, 0.06, 0.02, (20, 20, 24))
    elif outfit == "stripe":
        for yy in (1.12, 1.3, 1.48):
            box(body, 0, yy, 0, 0.67, 0.06, 0.37, shade(shirt, 0.55))
    elif outfit == "hoodie":
        box(body, 0, 1.6, -0.1, 0.4, 0.12, 0.2, shade(shirt, 0.9))
        box(body, 0, 1.12, 0.185, 0.4, 0.14, 0.02, shade(shirt, 0.8))
    hy = 1.9
    box(body, 0, hy, 0, 0.34, 0.36, 0.34, skin)
    for sx in (-1, 1):
        box(body, sx * 0.19, hy - 0.02, 0, 0.04, 0.1, 0.07, shade(skin, 0.9))
        box(body, sx * 0.085, hy + 0.03, 0.172, 0.08, 0.055, 0.02, (250, 250, 250))
        box(body, sx * 0.085, hy + 0.03, 0.182, 0.04, 0.045, 0.02, (30, 40, 60))
        box(body, sx * 0.085, hy + 0.1, 0.176, 0.1, 0.022, 0.02, hair)
    box(body, 0, hy - 0.04, 0.2, 0.06, 0.09, 0.06, shade(skin, 0.88))
    box(body, 0, hy - 0.13, 0.176, 0.11, 0.025, 0.02, (160, 70, 70))
    if glasses:
        box(body, 0, hy + 0.03, 0.19, 0.3, 0.07, 0.03, (14, 14, 18))
        box(body, 0, hy + 0.03, 0.2, 0.05, 0.02, 0.02, (14, 14, 18))
    if beard:
        box(body, 0, hy - 0.11, 0.18, 0.28, 0.1, 0.03, hair)
        box(body, 0, hy - 0.05, 0.2, 0.12, 0.025, 0.03, hair)
    if style == "short":
        box(body, 0, hy + 0.2, 0, 0.37, 0.1, 0.37, hair)
        box(body, 0, hy + 0.06, -0.15, 0.37, 0.3, 0.08, hair)
        for sx in (-1, 1):
            box(body, sx * 0.18, hy + 0.1, 0, 0.04, 0.16, 0.3, hair)
        box(body, 0, hy + 0.16, 0.17, 0.3, 0.06, 0.04, hair)
    elif style == "long":
        box(body, 0, hy + 0.2, 0, 0.38, 0.1, 0.38, hair)
        box(body, 0, hy - 0.08, -0.16, 0.38, 0.55, 0.08, hair)
        for sx in (-1, 1):
            box(body, sx * 0.19, hy - 0.04, 0.0, 0.04, 0.45, 0.3, hair)
        box(body, 0, hy + 0.16, 0.17, 0.3, 0.06, 0.04, hair)
    elif style == "cap":
        capc = (25, 35, 90) if outfit == "cop" else random.choice([(200, 40, 40), (40, 90, 200), (30, 30, 34), (240, 240, 240)])
        box(body, 0, hy + 0.2, 0, 0.38, 0.1, 0.38, capc)
        box(body, 0, hy + 0.15, 0.27, 0.34, 0.03, 0.2, shade(capc, 0.6))
        box(body, 0, hy + 0.06, -0.15, 0.36, 0.14, 0.06, hair)
        if outfit == "cop":
            box(body, 0, hy + 0.2, 0.2, 0.08, 0.06, 0.02, (230, 200, 60))
    elif style == "afro":
        box(body, 0, hy + 0.2, -0.02, 0.52, 0.34, 0.52, hair)
    sleeve_long = outfit != "tee"
    if sleeve_long:
        box(arm, 0, -0.27, 0, 0.2, 0.54, 0.24, shirt, top=False)
        box(arm, 0, -0.55, 0, 0.21, 0.05, 0.25, shade(shirt, 0.7), top=False)
        box(arm, 0, -0.64, 0, 0.15, 0.16, 0.17, skin, top=False)
    else:
        box(arm, 0, -0.14, 0, 0.21, 0.28, 0.25, shirt, top=False)
        box(arm, 0, -0.48, 0, 0.17, 0.4, 0.2, skin, top=False)
        box(arm, 0, -0.7, 0, 0.15, 0.12, 0.17, skin, top=False)
    box(leg, 0, -0.36, 0, 0.27, 0.72, 0.3, pants, top=False)
    box(leg, 0, -0.66, 0, 0.285, 0.05, 0.315, shade(pants, 0.75), top=False)
    box(leg, 0, -0.74, 0.06, 0.29, 0.12, 0.42, shoes, top=False)
    box(leg, 0, -0.79, 0.06, 0.3, 0.04, 0.44, (235, 235, 235) if shoes != (235, 235, 235) else (120, 120, 120), top=False)
    return body, leg, arm


def build_gun(kind=0):
    g = MB()
    if kind == 0:
        box(g, 0, 0.02, 0.15, 0.055, 0.08, 0.34, (44, 44, 50))
        box(g, 0, 0.02, 0.34, 0.03, 0.03, 0.06, (20, 20, 22))
        box(g, 0, -0.02, 0.12, 0.05, 0.04, 0.24, (70, 70, 76))
        box(g, 0, -0.09, 0.04, 0.05, 0.14, 0.07, (36, 28, 22))
        box(g, 0, -0.05, 0.1, 0.02, 0.05, 0.06, (30, 30, 34))
        box(g, 0, 0.07, 0.3, 0.015, 0.02, 0.02, (220, 220, 220))
    elif kind == 1:
        box(g, 0, 0.02, 0.2, 0.06, 0.1, 0.5, (38, 38, 44))
        box(g, 0, 0.03, 0.52, 0.03, 0.03, 0.22, (20, 20, 22))
        box(g, 0, -0.1, 0.14, 0.045, 0.2, 0.07, (28, 28, 32))
        box(g, 0, -0.08, 0.0, 0.05, 0.13, 0.06, (36, 28, 22))
        box(g, 0, 0.09, 0.2, 0.02, 0.03, 0.3, (60, 60, 66))
        box(g, 0, 0.0, -0.12, 0.04, 0.08, 0.2, (30, 30, 34))
    else:
        box(g, 0, 0.04, 0.45, 0.04, 0.04, 0.8, (30, 30, 34))
        box(g, 0, 0.0, 0.38, 0.07, 0.06, 0.25, (110, 74, 44))
        box(g, 0, 0.0, 0.05, 0.06, 0.1, 0.4, (50, 50, 56))
        box(g, 0, -0.02, -0.2, 0.05, 0.12, 0.3, (110, 74, 44))
        box(g, 0, -0.08, 0.0, 0.05, 0.12, 0.06, (36, 28, 22))
    return g


GUN_MESHES = [build_gun(k).mesh() for k in range(3)]

WEAPONS = [
    dict(name="Пистолет", snd="gun", cd=0.26, auto=False, mag=12, reserve=60, max_res=120, pellets=1,
         hip_spread=3.0, aim_spread=0.3, hip_assist=4.0, aim_assist=1.2, rng=80, cop_dmg=34, car_dmg=14,
         reload=1.2, kick=0.9, vol=0.85, rate=(0.95, 1.08)),
    dict(name="ПП", snd="smg", cd=0.075, auto=True, mag=30, reserve=150, max_res=300, pellets=1,
         hip_spread=5.5, aim_spread=1.6, hip_assist=3.0, aim_assist=1.0, rng=70, cop_dmg=13, car_dmg=7,
         reload=1.7, kick=0.5, vol=0.8, rate=(0.95, 1.1)),
    dict(name="Дробовик", snd="shotgun", cd=0.85, auto=False, mag=6, reserve=36, max_res=60, pellets=8,
         hip_spread=7.0, aim_spread=4.0, hip_assist=2.0, aim_assist=1.0, rng=45, cop_dmg=14, car_dmg=6,
         reload=2.0, kick=3.5, vol=1.0, rate=(0.95, 1.05)),
]
GRENADE_MAX = 9


class Person:
    def __init__(self, shirt, pants, skin, hair, style, outfit, shoes, glasses=False, beard=False):
        body, leg, arm = build_person(shirt, pants, skin, hair, style, outfit, shoes, glasses, beard)
        self.root = Entity(enabled=False)
        Entity(parent=self.root, model=body.mesh(), double_sided=True)
        self.legs = [Entity(parent=self.root, model=leg.mesh(), double_sided=True, position=(s * 0.16, 0.8, 0))
                     for s in (-1, 1)]
        self.arms = [Entity(parent=self.root, model=arm.mesh(), double_sided=True, position=(s * 0.43, 1.54, 0))
                     for s in (-1, 1)]
        self.gun = Entity(parent=self.root, model=GUN_MESHES[0], double_sided=True,
                          position=(0.43, 1.52, 0.6), enabled=False)
        self.shadow = Entity(parent=self.root, model="plane", scale=(0.95, 1, 0.95), position=(0, 0.06, 0),
                             color=rgb(30, 31, 34))
        self.phase = 0.0

    def animate(self, speed, dt, aiming=False):
        self.phase += speed * dt * 1.8
        sw = math.sin(self.phase) * 38 * min(1, speed / 3)
        self.legs[0].rotation_x = sw
        self.legs[1].rotation_x = -sw
        self.arms[0].rotation_x = -sw * 0.8 if not aiming else -35
        self.arms[1].rotation_x = -90 if aiming else sw * 0.8
        self.gun.enabled = aiming


def random_person(kind="ped"):
    if kind == "cop":
        return Person((40, 60, 140), (25, 30, 70), random.choice(SKINS), (30, 24, 20), "cap", "cop", (20, 20, 22))
    return Person(random.choice(SHIRTS), random.choice(PANTS), random.choice(SKINS), random.choice(HAIRS),
                  random.choice(["short", "short", "long", "cap", "afro", "bald"]),
                  random.choice(["tee", "tee", "jacket", "stripe", "hoodie"]), random.choice(SHOES),
                  glasses=random.random() < 0.15, beard=random.random() < 0.18)


def build_car(col, kind, body):
    mb = MB()
    L = {"sedan": 4.5, "hatch": 3.9, "suv": 4.7, "pickup": 5.1, "van": 4.8, "taxi": 4.5, "police": 4.6}[body]
    hl = L / 2
    dark = (30, 30, 34)
    flat(mb, -1.3, -hl - 0.4, 1.3, hl + 0.4, 0.06, (20, 21, 24))
    wz = hl - 1.0
    for sx in (-1, 1):
        for sz in (-1, 1):
            box(mb, sx * 1.0, 0.37, sz * wz, 0.32, 0.74, 0.74, (20, 20, 22))
            box(mb, sx * 1.17, 0.37, sz * wz, 0.04, 0.46, 0.46, (196, 196, 202))
            box(mb, sx * 1.19, 0.37, sz * wz, 0.02, 0.14, 0.14, (90, 90, 96))
    box(mb, 0, 0.68, 0, 2.0, 0.62, L, col)
    box(mb, 0, 0.42, 0, 2.03, 0.1, L - 1.0, dark)
    for sz in (-1, 1):
        box(mb, 0, 0.55, sz * (hl + 0.01), 2.06, 0.3, 0.2, (46, 46, 52))
        box(mb, 0, 0.7, sz * (hl + 0.02), 2.04, 0.05, 0.2, (200, 200, 205))
    box(mb, 0, 1.03, hl * 0.45, 1.82, 0.05, hl * 0.75, shade(col, 1.12))
    dims = {"sedan": (2.0, 0.62, -0.25), "hatch": (2.2, 0.64, -0.3), "suv": (2.7, 0.78, -0.35),
            "pickup": (1.5, 0.66, 0.55), "van": (2.0, 0.8, 0.6), "taxi": (2.0, 0.62, -0.25),
            "police": (2.0, 0.62, -0.25)}
    cl_, ch_, cz_ = dims[body]
    if body == "van":
        box(mb, 0, 1.69, -0.1, 2.0, 1.4, L - 1.2, col)
        box(mb, 0, 1.85, hl - 0.58, 1.8, 0.62, 0.05, (48, 68, 94))
        for sx in (-1, 1):
            box(mb, sx * 1.005, 1.95, 0.9, 0.03, 0.5, 1.2, (48, 68, 94))
        box(mb, 0, 2.4, -0.1, 1.9, 0.08, L - 1.4, shade(col, 0.9))
        ch_ = 1.4
    else:
        cy = 0.99 + ch_ / 2
        box(mb, 0, cy, cz_, 1.76, ch_, cl_, (48, 68, 94))
        for sz in (-1, 1):
            for sx in (-1, 1):
                box(mb, sx * 0.88, cy, cz_ + sz * (cl_ / 2 - 0.05), 0.07, ch_, 0.1, col)
        for sx in (-1, 1):
            box(mb, sx * 0.88, cy, cz_, 0.07, ch_, 0.09, col)
        box(mb, 0, 0.99 + ch_ + 0.05, cz_, 1.8, 0.1, cl_ + 0.1, shade(col, 0.94))
        box(mb, 0, cy + 0.05, cz_ + cl_ / 2 + 0.005, 1.4, ch_ * 0.45, 0.02, (130, 166, 200))
    if body == "pickup":
        bz = -hl + 1.0
        box(mb, 0, 1.0, bz, 1.8, 0.06, 1.9, (34, 34, 38))
        for sx in (-1, 1):
            box(mb, sx * 0.95, 1.2, bz, 0.1, 0.42, 2.0, col)
        box(mb, 0, 1.2, bz - 1.0, 1.9, 0.42, 0.1, col)
        box(mb, 0, 1.2, bz + 1.0, 1.9, 0.46, 0.1, col)
    if body == "suv":
        for sx in (-1, 1):
            box(mb, sx * 0.8, 1.84, cz_, 0.06, 0.06, cl_, (60, 60, 66))
    for sx in (-1, 1):
        box(mb, sx * 0.68, 0.86, hl + 0.01, 0.52, 0.2, 0.1, (60, 60, 66))
        box(mb, sx * 0.68, 0.86, hl + 0.06, 0.44, 0.14, 0.04, (255, 246, 196))
        box(mb, sx * 0.68, 0.86, -hl - 0.01, 0.52, 0.2, 0.1, (80, 12, 12))
        box(mb, sx * 0.68, 0.86, -hl - 0.06, 0.44, 0.14, 0.04, (220, 30, 30))
        box(mb, sx * 0.9, 0.5, hl + 0.1, 0.16, 0.1, 0.06, (255, 230, 150))
        box(mb, sx * 1.08, 1.12, cz_ + cl_ / 2 - 0.1, 0.14, 0.12, 0.22, col)
        for hz_ in (0.5, -0.6):
            box(mb, sx * 1.01, 0.72, hz_, 0.03, 0.06, 0.2, (210, 210, 215))
        for sz_ in (0.1, -1.0):
            box(mb, sx * 1.012, 0.68, sz_, 0.02, 0.56, 0.03, (30, 30, 34))
    box(mb, 0, 0.8, hl + 0.03, 0.9, 0.2, 0.06, (30, 30, 34))
    for k in range(3):
        box(mb, 0, 0.74 + k * 0.06, hl + 0.065, 0.86, 0.02, 0.02, (190, 190, 195))
    for sz in (-1, 1):
        box(mb, 0, 0.52, sz * (hl + 0.12), 0.5, 0.22, 0.03, (236, 236, 226))
        box(mb, 0, 0.52, sz * (hl + 0.14), 0.4, 0.07, 0.02, (40, 40, 60))
    box(mb, 0.6, 0.3, -hl - 0.1, 0.1, 0.1, 0.22, (70, 70, 76))
    light_y, light_z = 0.99 + ch_ + 0.25, cz_
    if body == "taxi":
        box(mb, 0, 0.99 + ch_ + 0.2, cz_, 0.7, 0.22, 0.3, (250, 240, 200), bright=1.0)
        box(mb, 0, 0.99 + ch_ + 0.2, cz_, 0.72, 0.06, 0.32, (30, 30, 34))
    if body == "police":
        box(mb, 0, 0.7, 0.0, 2.04, 0.3, 2.2, (24, 36, 100))
        for sx in (-1, 1):
            box(mb, sx * 1.015, 0.7, 0.05, 0.02, 0.5, 1.5, (25, 25, 30))
        box(mb, 0, 0.99 + ch_ + 0.14, cz_, 1.2, 0.1, 0.34, (30, 30, 34))
    return mb, light_y, light_z


class Car:
    def __init__(self, col, kind="civ", body="sedan"):
        self.col, self.kind, self.body = col, kind, body
        self.x = self.z = self.h = self.v = 0.0
        self.hp = 100.0
        self.driver = None
        self.dir = 0
        self.cruise = 10.0
        self.maxv = 30.0
        self.nox = self.stuck = self.ghost = self.rev = self.idle = self.smoke_t = self.honk_cd = self.crash_cd = 0.0
        self.rev_steer = 1
        self.deployed = False
        self.vis = True
        self.active = False
        mb, ly, lz = build_car(col, kind, body)
        self.root = Entity(model=mb.mesh(), double_sided=True, enabled=False)
        self.l1 = self.l2 = None
        if kind == "police":
            self.l1 = Entity(parent=self.root, model="cube", scale=(0.6, 0.15, 0.35), position=(-0.45, ly, lz),
                             color=rgb(255, 40, 40))
            self.l2 = Entity(parent=self.root, model="cube", scale=(0.6, 0.15, 0.35), position=(0.45, ly, lz),
                             color=rgb(60, 80, 255))

    def reset(self, x, z, h):
        self.x, self.z, self.h = x, z, h
        self.v = 0.0
        self.hp = 100.0
        self.driver = None
        self.dir = min(range(4), key=lambda d: abs(adiff(DIR_H[d], h)))
        self.cruise = random.uniform(9, 14)
        self.maxv = random.uniform(26, 36) if self.kind == "civ" else 34
        self.nox = self.stuck = self.ghost = self.rev = self.idle = self.smoke_t = self.honk_cd = self.crash_cd = 0.0
        self.deployed = False
        self.vis = True
        self.active = True
        self.root.enabled = True
        self.sync()

    def sync(self):
        self.root.position = (self.x, 0, self.z)
        self.root.rotation_y = self.h

    def pts(self, offs=(-1.5, 0, 1.5)):
        sh, ch = math.sin(math.radians(self.h)), math.cos(math.radians(self.h))
        return [(self.x + sh * o, self.z + ch * o) for o in offs]


class Ped:
    def __init__(self):
        self.person = random_person("ped")
        self.root = self.person.root
        self.person.root.scale = random.uniform(0.93, 1.07)
        self.x = self.z = self.h = 0.0
        self.t = 1.0
        self.state = "walk"
        self.idle = False
        self.vis = True
        self.active = False

    def activate(self, x, z):
        self.x, self.z = x, z
        self.h = random.uniform(0, 360)
        self.t = random.uniform(1, 4)
        self.state = "walk"
        self.idle = random.random() < 0.25
        self.vis = True
        self.active = True
        self.root.rotation_x = 0
        self.root.y = 0
        self.person.shadow.enabled = True
        self.root.position = (x, 0, z)
        self.root.enabled = True

    def update(self, dt):
        far = abs(self.x - player.x) > 130 or abs(self.z - player.z) > 130
        if far:
            if self.vis:
                self.root.enabled = False
                self.vis = False
            return
        if not self.vis:
            self.root.enabled = True
            self.vis = True
        self.t -= dt
        if self.t <= 0:
            self.t = random.uniform(1.5, 4)
            self.state = "walk"
            self.h = random.uniform(0, 360)
            self.idle = random.random() < 0.25
        sp = 7.5 if self.state == "flee" else (0 if self.idle else 1.6)
        if sp:
            nx = self.x + math.sin(math.radians(self.h)) * sp * dt
            nz = self.z + math.cos(math.radians(self.h)) * sp * dt
            if hits_building(nx, nz, 0.5) or not (3 < nx < WORLD - 3 and 3 < nz < WORLD - 3):
                self.h += 180 + random.uniform(-30, 30)
            else:
                self.x, self.z = nx, nz
        self.person.animate(sp, dt)
        self.root.position = (self.x, 0, self.z)
        self.root.rotation_y = self.h


class Cop:
    def __init__(self):
        self.person = random_person("cop")
        self.root = self.person.root
        self.x = self.z = self.h = 0.0
        self.hp = 60.0
        self.cd = 1.0
        self.idle = 0.0
        self.active = False

    def activate(self, x, z):
        self.x, self.z = x, z
        self.h = 0.0
        self.hp = 60.0
        self.cd = random.uniform(0.3, 1.0)
        self.idle = 0.0
        self.active = True
        self.root.rotation_x = 0
        self.root.y = 0
        self.person.shadow.enabled = True
        self.root.position = (x, 0, z)
        self.root.enabled = True

    def update(self, dt):
        moving = 0
        if player.alive:
            dx, dz = player.x - self.x, player.z - self.z
            d = math.hypot(dx, dz) + 1e-6
            self.h = math.degrees(math.atan2(dx, dz))
            if player.stars > 0:
                if d > 12:
                    move_circle(self, dx / d * 5.5 * dt, dz / d * 5.5 * dt, 0.5)
                    moving = 5.5
                elif d < 6:
                    move_circle(self, -dx / d * 3 * dt, -dz / d * 3 * dt, 0.5)
                    moving = 3
                self.cd -= dt
                if d < 24 and self.cd <= 0:
                    self.cd = random.uniform(0.7, 1.3)
                    tracer(self.x, 1.3, self.z, self.h, min(d, 24))
                    scare(self.x, self.z)
                    snd.at("gun", self.x, self.z, 0.7, 0.85, 140)
                    if random.random() < 0.35:
                        hurt_player(7)
        self.person.animate(moving, dt, aiming=moving == 0 and player.stars > 0)
        self.root.position = (self.x, 0, self.z)
        self.root.rotation_y = self.h


class Player:
    def __init__(self):
        self.person = Person((200, 40, 40), (50, 70, 120), (236, 190, 150), (42, 30, 24), "short", "jacket",
                             (235, 235, 235), glasses=True)
        self.root = self.person.root
        self.money = 500
        self.reset()

    def reset(self):
        self.x = 3 * P + RW + 1.4
        self.z = 3 * P + RW + 20
        self.y = 0.0
        self.vy = 0.0
        self.h = 0.0
        self.hp = 100.0
        self.car = None
        self.cd = 0.0
        self.stars = 0
        self.crime_t = 0.0
        self.hit_cd = 0.0
        self.alive = True
        self.dead_t = 0.0
        self.weapon = 0
        self.ammo = [w["mag"] for w in WEAPONS]
        self.reserve = [w["reserve"] for w in WEAPONS]
        self.grenades = 5
        self.reload_t = 0.0
        self.fire_t = 0.0
        self.gcd = 0.0
        self.person.gun.model = GUN_MESHES[0]
        self.root.enabled = True
        self.root.rotation_x = 0
        self.root.y = 0
        self.person.shadow.enabled = True


player = Player()
cam_pos[0], cam_pos[2] = player.x, player.z

cars, peds, cops, corpses = [], [], [], []
car_free = {"civ": [], "police": []}
ped_free, cop_free = [], []
for _ in range(32):
    car_free["civ"].append(Car(random.choice(CAR_COLORS), "civ", random.choice(CAR_BODIES)))
for _ in range(2):
    car_free["civ"].append(Car((240, 200, 40), "civ", "taxi"))
for _ in range(6):
    car_free["police"].append(Car((240, 240, 245), "police", "police"))
for _ in range(46):
    ped_free.append(Ped())
for _ in range(8):
    cop_free.append(Cop())
mine = Car((200, 40, 40), "civ", "sedan")


def ui(**kw):
    return Entity(parent=camera.ui, **kw)


_hud_cache = {}


def set_text(t, key, s):
    if _hud_cache.get(key) != s:
        _hud_cache[key] = s
        t.text = s


hud_money = Text(text="", position=(0.86, 0.47), origin=(0.5, 0.5), scale=2, color=rgb(120, 230, 120))
hud_speed = Text(text="", position=(0.86, -0.40), origin=(0.5, 0.5), scale=2.2, color=rgb(255, 255, 255))
hud_stars = [ui(model="quad", scale=0.03, rotation_z=45, position=(0.855 - k * 0.05, 0.40, -0.01),
                color=rgb(70, 70, 70)) for k in range(5)]
ui(model="quad", origin=(-0.5, 0), scale=(0.31, 0.03), position=(-0.84, -0.44, 0), color=rgb(0, 0, 0))
hud_hp = ui(model="quad", origin=(-0.5, 0), scale=(0.3, 0.022), position=(-0.835, -0.44, -0.01), color=rgb(200, 40, 40))
ui(model="quad", origin=(-0.5, 0), scale=(0.31, 0.03), position=(-0.84, -0.40, 0), color=rgb(0, 0, 0))
hud_car = ui(model="quad", origin=(-0.5, 0), scale=(0.3, 0.022), position=(-0.835, -0.40, -0.01), color=rgb(70, 140, 220))
hud_cross = Text(text="+", origin=(0, 0), scale=2, color=rgb(255, 255, 255))
hud_dot = ui(model="quad", scale=0.006, position=(0, 0, -0.02), color=rgb(255, 40, 40), enabled=False)
hud_ammo = Text(text="", position=(0.0, -0.40), origin=(0, 0), scale=1.6, color=rgb(255, 255, 255))
WSLOT = ["1 Пистолет", "2 ПП", "3 Дробовик", "4 Граната"]
hud_slots = [Text(text=WSLOT[k], position=(-0.36 + k * 0.24, -0.45), origin=(0, 0), scale=1.1,
                  color=rgb(150, 150, 150)) for k in range(4)]
hud_hint = Text(text="ЛКМ огонь | ПКМ прицел | 1-4 / колесо оружие | R перезарядка | G граната | F машина",
                position=(0, 0.485), origin=(0, 0), scale=0.9, color=rgb(220, 220, 220))
hud_wasted = Text(text="WASTED", origin=(0, 0), scale=9, color=rgb(200, 30, 30), enabled=False)
hud_flash = ui(model="quad", scale=(3, 2), color=Color(0.85, 0.05, 0.05, 0.0), z=0.5, enabled=False)

MM = 0.30
MMX, MMY = -0.70, 0.33


def quad_xy(mb, cx, cy, hs, col):
    c = tc(col)
    n = len(mb.v)
    mb.v += [Vec3(cx - hs, cy - hs, 0), Vec3(cx + hs, cy - hs, 0), Vec3(cx + hs, cy + hs, 0), Vec3(cx - hs, cy + hs, 0)]
    mb.c += [c] * 4
    mb.uv += [Vec2(0, 0)] * 4
    mb.t += [(n, n + 1, n + 2), (n, n + 2, n + 3)]


mm_bg, mm_blocks = MB(), MB()
quad_xy(mm_bg, MMX, MMY, MM / 2 + 0.005, (10, 10, 14))
quad_xy(mm_bg, MMX, MMY, MM / 2, (70, 72, 78))
for (x0, z0, i, j) in block_rects_for_map:
    quad_xy(mm_blocks, MMX + ((x0 + S_BLOCK / 2) / WORLD - 0.5) * MM, MMY + ((z0 + S_BLOCK / 2) / WORLD - 0.5) * MM,
            S_BLOCK / WORLD * MM / 2, (80, 140, 80) if (i, j) in parks else (125, 125, 120))
ui(model=mm_bg.mesh(), double_sided=True, z=0)
ui(model=mm_blocks.mesh(), double_sided=True, z=-0.01)
mm_player = ui(model="quad", scale=0.012, position=(MMX, MMY, -0.03), color=rgb(255, 255, 255))
mm_dots = [ui(model="quad", scale=0.01, position=(MMX, MMY, -0.02), color=rgb(60, 90, 255), enabled=False)
           for _ in range(10)]


def mm_pos(x, z):
    return (MMX + (x / WORLD - 0.5) * MM, MMY + (z / WORLD - 0.5) * MM)


fx_free, fx_live = [], []
for _ in range(240):
    fx_free.append([Entity(model="cube", enabled=False), 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0.0])
tr_pool = [[Entity(model="cube", enabled=False, color=rgb(255, 235, 120)), 0.0] for _ in range(16)]
tr_idx = 0
decal_pool = [[Entity(model="plane", enabled=False), 0.0] for _ in range(80)]
decal_idx = 0
pick_pool = [[Entity(model="cube", enabled=False, scale=(0.5, 0.12, 0.3), color=rgb(50, 190, 80)), 0, False, "money", 0.0]
             for _ in range(24)]
t_game = 0.0
spawn_timer = 0.0
cop_timer = 0.0
hud_timer = 0.0
audio_t = 0.0
skid_t = 0.0
skid_on = False
step_sign = 1.0
was_air = False
prev_stars = 0
prev_hp = 100.0
flash_a = 0.0
hurt_cd = 0.0
aiming = False
aim_k = 0.0
click_buf = 0.0
quick_gren = False
shake_t = 0.0
gren_pool = [Entity(model="cube", scale=0.22, color=rgb(60, 90, 50), enabled=False) for _ in range(6)]
gren_free = list(gren_pool)
grenades = []


def spawn_fx(x, y, z, vx, vy, vz, life, size, col, grav=0.0):
    if not fx_free:
        return
    p = fx_free.pop()
    e = p[0]
    e.position = (x, y, z)
    e.scale = size
    e.color = col
    e.enabled = True
    p[1], p[2], p[3], p[4], p[5], p[6], p[7] = vx, vy, vz, life, life, size, grav
    fx_live.append(p)


def update_fx(dt):
    for p in fx_live[:]:
        p[4] -= dt
        e = p[0]
        if p[4] <= 0:
            e.enabled = False
            fx_live.remove(p)
            fx_free.append(p)
            continue
        p[2] -= p[7] * dt
        e.x += p[1] * dt
        e.y += p[2] * dt
        e.z += p[3] * dt
        e.scale = p[6] * (p[4] / p[5])
    for t in tr_pool:
        if t[1] > 0:
            t[1] -= dt
            if t[1] <= 0:
                t[0].enabled = False
    for d in decal_pool:
        if d[1] > 0:
            d[1] -= dt
            if d[1] <= 0:
                d[0].enabled = False
    for pk in pick_pool:
        if pk[2]:
            pk[0].rotation_y += 120 * dt
            pk[4] -= dt
            if pk[4] <= 0:
                pk[2] = False
                pk[0].enabled = False


def spawn_decal(x, z, sx, sz, rot, col, life, y=0.09):
    global decal_idx
    d = decal_pool[decal_idx]
    decal_idx = (decal_idx + 1) % len(decal_pool)
    e = d[0]
    e.position = (x, y, z)
    e.scale = (sx, 1, sz)
    e.rotation_y = rot
    e.color = col
    e.enabled = True
    d[1] = life


def spawn_pickup(x, z, amt, kind="money"):
    for pk in pick_pool:
        if not pk[2]:
            pk[0].position = (x, 0.5, z)
            pk[0].color = rgb(50, 190, 80) if kind == "money" else rgb(235, 140, 40)
            pk[0].enabled = True
            pk[1], pk[2], pk[3], pk[4] = amt, True, kind, 45.0
            return


def give_ammo():
    p = player
    for i, w in enumerate(WEAPONS):
        p.reserve[i] = min(w["max_res"], p.reserve[i] + w["mag"])
    p.grenades = min(GRENADE_MAX, p.grenades + 1)


def tracer(x, y, z, h, length):
    global tr_idx
    sh, ch = math.sin(math.radians(h)), math.cos(math.radians(h))
    t = tr_pool[tr_idx]
    tr_idx = (tr_idx + 1) % len(tr_pool)
    e = t[0]
    e.scale = (0.05, 0.05, length)
    e.position = (x + sh * (0.8 + length / 2), y, z + ch * (0.8 + length / 2))
    e.rotation_y = h
    e.enabled = True
    t[1] = 0.06
    spawn_fx(x + sh * 0.9, y, z + ch * 0.9, 0, 0, 0, 0.05, 0.3, rgb(255, 210, 90))


def scare(x, z):
    for pd in peds:
        if abs(pd.x - x) < 45 and abs(pd.z - z) < 45:
            pd.state = "flee"
            pd.t = 5
            pd.h = math.degrees(math.atan2(pd.x - x, pd.z - z)) + random.uniform(-30, 30)


def add_wanted(level):
    player.stars = cl(max(player.stars, level), 0, 5)
    player.crime_t = 0


def hurt_player(dmg):
    if not player.alive:
        return
    if player.car:
        player.car.hp -= dmg
        player.hp -= dmg * 0.3
    else:
        player.hp -= dmg


def blood_burst(x, z):
    for _ in range(9):
        a = random.uniform(0, TAU)
        sp = random.uniform(1.5, 4.5)
        spawn_fx(x, 1.0, z, math.cos(a) * sp, random.uniform(2, 5), math.sin(a) * sp, 0.6, 0.16, rgb(150, 20, 20), 14)


def kill_ped(pd, by_player=True):
    if pd in peds:
        peds.remove(pd)
    pd.root.enabled = True
    pd.vis = True
    pd.root.rotation_x = 85
    pd.root.y = 0.2
    pd.person.shadow.enabled = False
    pd.person.gun.enabled = False
    corpses.append([pd, 10.0, ped_free])
    blood_burst(pd.x, pd.z)
    spawn_decal(pd.x, pd.z, 0.7, 0.7, random.uniform(0, 360), rgb(120, 18, 18), 20)
    if random.random() < 0.5:
        spawn_pickup(pd.x, pd.z, random.randint(20, 120))
    if by_player:
        add_wanted(1)


def kill_cop(cp):
    if cp in cops:
        cops.remove(cp)
    cp.root.rotation_x = 85
    cp.root.y = 0.2
    cp.person.shadow.enabled = False
    cp.person.gun.enabled = False
    corpses.append([cp, 10.0, cop_free])
    blood_burst(cp.x, cp.z)
    spawn_decal(cp.x, cp.z, 0.7, 0.7, random.uniform(0, 360), rgb(120, 18, 18), 20)
    spawn_pickup(cp.x, cp.z, random.randint(50, 200))
    spawn_pickup(cp.x + 0.9, cp.z, 1, "ammo")
    add_wanted(min(5, player.stars + 1))


def release_car(c):
    if c in cars:
        cars.remove(c)
    c.active = False
    c.driver = None
    c.root.enabled = False
    car_free[c.kind].append(c)


def release_cop(cp):
    if cp in cops:
        cops.remove(cp)
    cp.active = False
    cp.root.enabled = False
    cop_free.append(cp)


def release_ped(pd):
    if pd in peds:
        peds.remove(pd)
    pd.active = False
    pd.root.enabled = False
    ped_free.append(pd)


def fx_boom(x, z, col=None, k=1.0):
    global shake_t
    for _ in range(22):
        a = random.uniform(0, TAU)
        sp = random.uniform(1, 9) * k
        spawn_fx(x, 1.0, z, math.cos(a) * sp, random.uniform(1, 7), math.sin(a) * sp, random.uniform(0.5, 1.0),
                 random.uniform(0.5, 1.3) * k, random.choice([rgb(255, 170, 40), rgb(255, 90, 30), rgb(255, 220, 90)]), 4)
    for _ in range(14):
        a = random.uniform(0, TAU)
        sp = random.uniform(0.5, 3)
        spawn_fx(x, 1.5, z, math.cos(a) * sp, random.uniform(2, 6), math.sin(a) * sp, random.uniform(1.0, 1.8),
                 random.uniform(1.2, 2.4) * k, rgb(60, 60, 62), -1.5)
    dc = col if col else (110, 110, 110)
    for _ in range(10):
        a = random.uniform(0, TAU)
        sp = random.uniform(3, 10)
        spawn_fx(x, 1.0, z, math.cos(a) * sp, random.uniform(3, 9), math.sin(a) * sp, 1.2, 0.35, rgb(*dc), 18)
    spawn_fx(x, 1.2, z, 0, 0, 0, 0.18, 7 * k, rgb(255, 240, 180))
    spawn_decal(x, z, 4 * k, 4 * k, random.uniform(0, 360), rgb(22, 22, 22), 40)
    d = math.hypot(x - cam_pos[0], z - cam_pos[2])
    shake_t = max(shake_t, cl(1 - d / 80, 0, 1) * 1.2)


def explode(c):
    if not c.active:
        return
    fx_boom(c.x, c.z, c.col, 1.0)
    snd.at("boom", c.x, c.z, 1.0, random.uniform(0.9, 1.1), 300)
    for o in cars:
        if o is not c and o.active and math.hypot(o.x - c.x, o.z - c.z) < 7:
            o.hp -= 45
    if player.car is c:
        player.car = None
        player.x, player.z = c.x, c.z
        player.root.enabled = True
        player.hp -= 35
    elif player.alive and math.hypot(player.x - c.x, player.z - c.z) < 5:
        player.hp -= 40
    release_car(c)
    for pd in peds[:]:
        if math.hypot(pd.x - c.x, pd.z - c.z) < 5:
            kill_ped(pd, False)
    for cp in cops[:]:
        if math.hypot(cp.x - c.x, cp.z - c.z) < 5:
            kill_cop(cp)


def blast(x, z, radius=10.0, by_player=True):
    fx_boom(x, z, None, 1.2)
    snd.at("boom", x, z, 1.0, random.uniform(0.92, 1.08), 300)
    scare(x, z)
    hit_any = False
    for pd in peds[:]:
        if math.hypot(pd.x - x, pd.z - z) < radius:
            kill_ped(pd, False)
            hit_any = True
    for cp in cops[:]:
        d = math.hypot(cp.x - x, cp.z - z)
        if d < radius:
            cp.hp -= 140 * (1 - d / radius) + 25
            hit_any = True
            if cp.hp <= 0:
                kill_cop(cp)
    for c in cars[:]:
        d = math.hypot(c.x - x, c.z - z)
        if d < radius + 2 and c.active:
            c.hp -= 120 * (1 - d / (radius + 2)) + 15
            if c.driver == "ai":
                hit_any = True
    for c in cars[:]:
        if c.hp <= 0 and c.active:
            explode(c)
    if player.alive:
        d = math.hypot(player.x - x, player.z - z)
        if d < radius:
            dmg = 90 * (1 - d / radius) + 10
            if player.car:
                dmg *= 0.4
            player.hp -= dmg
    if by_player and hit_any:
        add_wanted(2)


def die():
    player.alive = False
    player.dead_t = 3.5
    if player.car:
        player.car.driver = None
        player.car = None
    player.root.enabled = True
    player.root.rotation_x = 85
    player.root.y = 0.2
    player.person.shadow.enabled = False
    hud_wasted.enabled = True


def respawn():
    money = int(player.money * 0.9)
    player.reset()
    player.money = money
    hud_wasted.enabled = False
    for cp in cops[:]:
        release_cop(cp)
    for c in cars[:]:
        if c.kind == "police":
            release_car(c)


def road_spot(mind, maxd):
    for _ in range(25):
        a, d = random.uniform(0, TAU), random.uniform(mind, maxd)
        x = cl(player.x + math.cos(a) * d, 10, WORLD - 10)
        z = cl(player.z + math.sin(a) * d, 10, WORLD - 10)
        dr = random.randrange(4)
        if dr in (0, 2):
            rj = int(cl(round((z - ROAD_C) / P), 0, N - 1))
            z = rj * P + ROAD_C + (-LANE if dr == 0 else LANE)
        else:
            ri = int(cl(round((x - ROAD_C) / P), 0, N - 1))
            x = ri * P + ROAD_C + (LANE if dr == 1 else -LANE)
        if math.hypot(x - player.x, z - player.z) < mind:
            continue
        if any(abs(c.x - x) < 10 and abs(c.z - z) < 10 for c in cars):
            continue
        return x, z, dr
    return None


def spawn_civ(mind, maxd, parked=False):
    pool = car_free["civ"]
    if not pool:
        return
    spot = road_spot(mind, maxd)
    if not spot:
        return
    x, z, d = spot
    if parked:
        along = x if d in (0, 2) else z
        if along % P < RW + 8:
            return
        if d in (0, 2):
            z = (round((z - ROAD_C) / P) * P + ROAD_C) + (-6.8 if d == 0 else 6.8)
        else:
            x = (round((x - ROAD_C) / P) * P + ROAD_C) + (6.8 if d == 1 else -6.8)
    c = pool.pop(random.randrange(len(pool)))
    c.reset(x, z, DIR_H[d])
    c.dir = d
    c.driver = None if parked else "ai"
    cars.append(c)


def spawn_ped(mind, maxd):
    if not ped_free:
        return
    for _ in range(15):
        a, d = random.uniform(0, TAU), random.uniform(mind, maxd)
        x, z = player.x + math.cos(a) * d, player.z + math.sin(a) * d
        if not (6 < x < WORLD - 6 and 6 < z < WORLD - 6) or hits_building(x, z, 1.0):
            continue
        pd = ped_free.pop()
        pd.activate(x, z)
        peds.append(pd)
        return


def physics(c, dt, throttle, steer, handbrake=False):
    if throttle > 0:
        c.v += (18 if c.v >= 0 else 34) * throttle * dt
    elif throttle < 0:
        c.v -= (34 if c.v > 0 else 12) * (-throttle) * dt
    c.v -= c.v * 0.4 * dt
    if handbrake:
        c.v *= max(0.0, 1 - 2.0 * dt)
    c.v = cl(c.v, -8, c.maxv)
    if abs(c.v) < 0.2 and throttle == 0:
        c.v = 0
    c.h += steer * 75 * dt * cl(c.v / 6, -1, 1) * (1 - 0.5 * min(1, abs(c.v) / 35))


def move_car(c, dt):
    ox, oz, oh = c.x, c.z, c.h
    c.x = cl(c.x + math.sin(math.radians(c.h)) * c.v * dt, 4, WORLD - 4)
    c.z = cl(c.z + math.cos(math.radians(c.h)) * c.v * dt, 4, WORLD - 4)
    for px, pz in c.pts((-1.7, 0, 1.7)):
        if hits_building(px, pz, 1.05):
            c.x, c.z, c.h = ox, oz, oh
            if abs(c.v) > 6 and c.crash_cd <= 0:
                c.crash_cd = 0.3
                for _ in range(5):
                    spawn_fx(px, 0.8, pz, random.uniform(-3, 3), random.uniform(1, 4), random.uniform(-3, 3),
                             0.4, 0.15, rgb(255, 210, 90), 10)
            if abs(c.v) > 12:
                c.hp -= (abs(c.v) - 10) * 2.2
            c.v = -c.v * 0.3
            c.stuck += 0.3
            break


def ai_drive(c, dt):
    c.h += cl(adiff(DIR_H[c.dir], c.h), -240 * dt, 240 * dt)
    c.honk_cd -= dt
    sh, ch = math.sin(math.radians(c.h)), math.cos(math.radians(c.h))
    blocked = False
    if c.ghost > 0:
        c.ghost -= dt
    else:
        for o in cars:
            if o is c:
                continue
            dx, dz = o.x - c.x, o.z - c.z
            if abs(dx) > 25 or abs(dz) > 25:
                continue
            f, l = dx * sh + dz * ch, dx * ch - dz * sh
            if 0 < f < 14 and abs(l) < 3.2:
                if math.cos(math.radians(o.h - c.h)) > 0.5 or o.driver in (None, "player"):
                    blocked = True
                    break
        if not blocked and player.alive and player.car is None:
            dx, dz = player.x - c.x, player.z - c.z
            f, l = dx * sh + dz * ch, dx * ch - dz * sh
            if 0 < f < 15 and abs(l) < 2.4:
                blocked = True
    if blocked:
        c.stuck += dt
        if c.stuck > 3:
            c.ghost, c.stuck = 2.5, 0
    else:
        c.stuck = max(0, c.stuck - dt)
    c.v += cl((0 if blocked else c.cruise) - c.v, -25 * dt, 11 * dt)
    px, pz = c.x, c.z
    c.x += DIR_X[c.dir] * c.v * dt
    c.z += DIR_Z[c.dir] * c.v * dt
    if c.dir in (0, 2):
        tz = round((c.z - ROAD_C) / P) * P + ROAD_C + (-LANE if c.dir == 0 else LANE)
        c.z += (tz - c.z) * min(1, 5 * dt)
    else:
        tx = round((c.x - ROAD_C) / P) * P + ROAD_C + (LANE if c.dir == 1 else -LANE)
        c.x += (tx - c.x) * min(1, 5 * dt)
    if (c.dir == 0 and c.x > WORLD - 25) or (c.dir == 2 and c.x < 25) or \
       (c.dir == 1 and c.z > WORLD - 25) or (c.dir == 3 and c.z < 25):
        c.dir = (c.dir + 2) % 4
        c.nox = 40
        return
    c.nox -= abs(c.v) * dt
    if c.nox <= 0 and (c.x != px or c.z != pz):
        if c.dir in (0, 2):
            ni = round((c.x - ROAD_C) / P)
            cx = ni * P + ROAD_C
            if (px - cx) * (c.x - cx) <= 0 and 0 <= ni < N and random.random() < 0.35:
                rj = round((c.z - ROAD_C) / P)
                opts = ([1] if rj < N - 1 else []) + ([3] if rj > 0 else [])
                if opts:
                    c.dir = random.choice(opts)
                    c.x = cx + (LANE if c.dir == 1 else -LANE)
                    c.nox = 25
        else:
            nj = round((c.z - ROAD_C) / P)
            cz = nj * P + ROAD_C
            if (pz - cz) * (c.z - cz) <= 0 and 0 <= nj < N and random.random() < 0.35:
                ri = round((c.x - ROAD_C) / P)
                opts = ([0] if ri < N - 1 else []) + ([2] if ri > 0 else [])
                if opts:
                    c.dir = random.choice(opts)
                    c.z = cz + (-LANE if c.dir == 0 else LANE)
                    c.nox = 25


def cop_drive(c, dt):
    dx, dz = player.x - c.x, player.z - c.z
    dist = math.hypot(dx, dz)
    if dist < 10 and player.car is None and not c.deployed and player.alive:
        c.deployed = True
        side = (math.cos(math.radians(c.h)), -math.sin(math.radians(c.h)))
        for s in (-1, 1):
            if cop_free:
                cp = cop_free.pop()
                cp.activate(c.x + side[0] * 2.5 * s, c.z + side[1] * 2.5 * s)
                cops.append(cp)
        c.driver = None
        return
    diff = adiff(math.degrees(math.atan2(dx, dz)), c.h)
    if c.rev > 0:
        c.rev -= dt
        physics(c, dt, -1, c.rev_steer)
    else:
        throttle = 1
        if abs(diff) > 75 and c.v > 8:
            throttle = -0.4
        physics(c, dt, throttle, cl(diff / 30, -1, 1))
        if abs(c.v) < 1.5 and dist > 6:
            c.stuck += dt
            if c.stuck > 0.8:
                c.rev, c.stuck = 1.0, 0
                c.rev_steer = random.choice((-1, 1))
        else:
            c.stuck = 0


def car_collisions():
    n = len(cars)
    for i in range(n):
        a = cars[i]
        for j in range(i + 1, n):
            b = cars[j]
            if a.driver == "ai" and b.driver == "ai":
                continue
            if abs(a.x - b.x) > 6 or abs(a.z - b.z) > 6:
                continue
            best = None
            for p in a.pts((-1.4, 0, 1.4)):
                for q in b.pts((-1.4, 0, 1.4)):
                    d = math.hypot(q[0] - p[0], q[1] - p[1])
                    if d < 2.1 and (best is None or d < best[0]):
                        best = (d, p, q)
            if best:
                d, p, q = best
                if d < 0.01:
                    nx, nz, d = 1, 0, 0.01
                else:
                    nx, nz = (q[0] - p[0]) / d, (q[1] - p[1]) / d
                push = (2.1 - d) / 2
                a.x -= nx * push
                a.z -= nz * push
                b.x += nx * push
                b.z += nz * push
                imp = abs(a.v) + abs(b.v)
                a.v *= 0.75
                b.v *= 0.75
                if imp > 8 and a.crash_cd <= 0:
                    a.crash_cd = 0.3
                    for _ in range(5):
                        spawn_fx(p[0], 0.8, p[1], random.uniform(-3, 3), random.uniform(1, 4), random.uniform(-3, 3),
                                 0.4, 0.15, rgb(255, 210, 90), 10)
                if imp > 12:
                    dmg = (imp - 10) * 1.6
                    a.hp -= dmg
                    b.hp -= dmg


def car_impacts(c):
    if abs(c.v) < 4.5:
        return
    pts = c.pts()
    by_player = c.driver == "player"
    for pd in peds[:]:
        if abs(pd.x - c.x) < 4 and abs(pd.z - c.z) < 4:
            if any(math.hypot(pd.x - px, pd.z - pz) < 1.3 for px, pz in pts):
                kill_ped(pd, by_player)
    for cp in cops[:]:
        if abs(cp.x - c.x) < 4 and abs(cp.z - c.z) < 4:
            if any(math.hypot(cp.x - px, cp.z - pz) < 1.3 for px, pz in pts):
                cp.hp -= 90
                if cp.hp <= 0:
                    kill_cop(cp)
    if not by_player and player.alive and player.car is None and player.hit_cd <= 0:
        if any(math.hypot(player.x - px, player.z - pz) < 1.4 for px, pz in pts):
            player.hp -= abs(c.v) * 2.2
            player.hit_cd = 0.6


def clear_line(ox, oz, tx, tz):
    d = math.hypot(tx - ox, tz - oz)
    steps = int(d / 1.5)
    for s in range(1, steps):
        t = s / max(1, steps)
        if hits_building(ox + (tx - ox) * t, oz + (tz - oz) * t, 0.1):
            return False
    return True


def make_targets():
    t = [("ped", o, 0.55) for o in peds] + [("cop", o, 0.55) for o in cops]
    t += [("car", o, 1.4) for o in cars if o.driver != "player"]
    return t


def trace(ox, oz, yaw, rng, assist):
    sh, ch = math.sin(math.radians(yaw)), math.cos(math.radians(yaw))
    best_d = rng
    t = 1.0
    while t < rng:
        if hits_building(ox + sh * t, oz + ch * t, 0.1):
            best_d = t
            break
        t += 1.0
    hit = None
    ta = math.tan(math.radians(assist))
    for kind, o, rad in make_targets():
        rx, rz = o.x - ox, o.z - oz
        along = rx * sh + rz * ch
        if along < 1.0 or along >= best_d:
            continue
        if abs(rx * ch - rz * sh) < rad + along * ta:
            best_d = along
            hit = (kind, o)
    return hit, best_d


def apply_hit(kind, obj, w, dist):
    fall = max(0.35, 1.0 - dist / (w["rng"] * 1.3)) if w["pellets"] > 1 else 1.0
    if kind == "ped":
        kill_ped(obj)
    elif kind == "cop":
        obj.hp -= w["cop_dmg"] * fall
        add_wanted(1)
        if obj.hp <= 0:
            kill_cop(obj)
    else:
        obj.hp -= w["car_dmg"] * fall
        for _ in range(3):
            spawn_fx(obj.x, 1.0, obj.z, random.uniform(-3, 3), random.uniform(1, 4), random.uniform(-3, 3),
                     0.35, 0.14, rgb(255, 210, 90), 10)
        if obj.driver == "ai":
            add_wanted(1)
        if obj.hp <= 0 and obj.active:
            explode(obj)


def start_reload():
    p = player
    i = p.weapon
    if i > 2:
        return
    w = WEAPONS[i]
    if p.reload_t > 0 or p.ammo[i] >= w["mag"] or p.reserve[i] <= 0:
        return
    p.reload_t = w["reload"]
    snd.play("reload", 0.8, 1.0 if i != 2 else 0.85)


def finish_reload():
    p = player
    i = p.weapon
    if i > 2:
        return
    w = WEAPONS[i]
    take = min(w["mag"] - p.ammo[i], p.reserve[i])
    p.ammo[i] += take
    p.reserve[i] -= take


def fire_weapon():
    global cam_pitch
    p = player
    i = p.weapon
    w = WEAPONS[i]
    if p.reload_t > 0:
        return
    if p.ammo[i] <= 0:
        p.cd = 0.35
        snd.play("click", 0.7)
        start_reload()
        return
    p.ammo[i] -= 1
    p.cd = w["cd"]
    p.fire_t = 1.2
    ox, oz = p.x, p.z
    spread = w["aim_spread"] if aiming else w["hip_spread"]
    assist = w["aim_assist"] if aiming else w["hip_assist"]
    for _ in range(w["pellets"]):
        yaw = cam_yaw + random.uniform(-spread, spread)
        hit, dist = trace(ox, oz, yaw, w["rng"], assist)
        tracer(ox, 1.4, oz, yaw, max(1.0, dist - 0.8))
        if hit:
            apply_hit(hit[0], hit[1], w, dist)
    snd.play(w["snd"], w["vol"], random.uniform(*w["rate"]))
    scare(ox, oz)
    cam_pitch = cl(cam_pitch - w["kick"] * (0.5 if aiming else 1.0), -8, 55)


def select_weapon(i):
    p = player
    if i == p.weapon:
        return
    p.weapon = i
    p.reload_t = 0.0
    p.cd = 0.25
    p.fire_t = 0.8
    if i < 3:
        p.person.gun.model = GUN_MESHES[i]


def throw_grenade():
    p = player
    if p.grenades <= 0 or p.gcd > 0 or not gren_free:
        return
    p.grenades -= 1
    p.gcd = 0.7
    p.cd = 0.5
    up = 14.0 - cam_pitch
    sp = cl(18 + up * 0.4, 10, 30)
    vy = cl(7 + up * 0.3, 3, 14)
    sh, ch = math.sin(math.radians(cam_yaw)), math.cos(math.radians(cam_yaw))
    x, z = p.x + sh * 0.7, p.z + ch * 0.7
    if hits_building(x, z, 0.3):
        x, z = p.x, p.z
    y = 1.6 + p.y
    e = gren_free.pop()
    e.position = (x, y, z)
    e.enabled = True
    grenades.append([e, x, y, z, sh * sp, vy, ch * sp, 2.6])
    snd.play("pin", 0.7, random.uniform(0.95, 1.05))


def update_grenades(dt):
    for g in grenades[:]:
        e = g[0]
        g[7] -= dt
        g[5] -= 18 * dt
        nx = cl(g[1] + g[4] * dt, 3, WORLD - 3)
        if hits_building(nx, g[3], 0.25):
            g[4] = -g[4] * 0.4
        else:
            g[1] = nx
        nz = cl(g[3] + g[6] * dt, 3, WORLD - 3)
        if hits_building(g[1], nz, 0.25):
            g[6] = -g[6] * 0.4
        else:
            g[3] = nz
        g[2] += g[5] * dt
        if g[2] <= 0.15:
            g[2] = 0.15
            if g[5] < 0:
                g[5] = -g[5] * 0.35
            if abs(g[5]) < 1.2:
                g[5] = 0
            fr = max(0.0, 1 - 4 * dt)
            g[4] *= fr
            g[6] *= fr
        e.position = (g[1], g[2], g[3])
        e.rotation_x += 400 * dt
        if g[7] <= 0:
            grenades.remove(g)
            e.enabled = False
            gren_free.append(e)
            blast(g[1], g[3], 10.0, True)


def try_exit_car():
    c = player.car
    if abs(c.v) > 8:
        return
    rx, rz = math.cos(math.radians(c.h)), -math.sin(math.radians(c.h))
    fx, fz = math.sin(math.radians(c.h)), math.cos(math.radians(c.h))
    for sx, sz in ((rx * 2.3, rz * 2.3), (-rx * 2.3, -rz * 2.3), (-fx * 3.2, -fz * 3.2)):
        if not hits_building(c.x + sx, c.z + sz, 0.6):
            player.x, player.z = c.x + sx, c.z + sz
            player.y, player.vy = 0.0, 0.0
            c.driver = None
            player.car = None
            player.root.enabled = True
            return


def try_enter_car():
    best, bd = None, 4.0
    for c in cars:
        d = min(math.hypot(player.x - px, player.z - pz) for px, pz in c.pts())
        if d < bd:
            best, bd = c, d
    if not best:
        return
    if best.driver == "ai":
        rx, rz = math.cos(math.radians(best.h)), -math.sin(math.radians(best.h))
        if ped_free:
            pd = ped_free.pop()
            pd.activate(best.x - rx * 2.3, best.z - rz * 2.3)
            pd.state, pd.t = "flee", 6
            peds.append(pd)
        add_wanted(1)
    elif best.driver == "cop":
        add_wanted(2)
    best.driver = "player"
    best.v = 0
    best.root.enabled = True
    player.car = best
    player.root.enabled = False


def input(key):
    global mouse_look, click_buf, quick_gren
    if key == "escape":
        application.quit()
    if key == "f" and player.alive:
        if player.car:
            try_exit_car()
        else:
            try_enter_car()
    if key == "m":
        mouse_look = not mouse_look
        mouse.locked = mouse_look
        mouse.visible = not mouse_look
    if key in ("left mouse down", "j", "enter"):
        click_buf = 0.18
    if player.alive and player.car is None:
        if key in ("1", "2", "3", "4"):
            select_weapon(int(key) - 1)
        elif key == "scroll up":
            select_weapon((player.weapon - 1) % 4)
        elif key == "scroll down":
            select_weapon((player.weapon + 1) % 4)
        elif key == "r":
            start_reload()
    if key == "g":
        quick_gren = True


cam_pivot = Entity()
camera.parent = cam_pivot


def update_camera(dt):
    global cam_yaw, cam_pitch, cam_free, cam_idle, aim_k, shake_t
    look = int(bool(held_keys["right arrow"])) - int(bool(held_keys["left arrow"]))
    pit = int(bool(held_keys["down arrow"])) - int(bool(held_keys["up arrow"]))
    mv = mouse.velocity if mouse_look else (0, 0, 0)
    moved = look != 0 or pit != 0 or abs(mv[0]) > 0.0003 or abs(mv[1]) > 0.0003
    sens = 0.5 if aiming else 1.0
    cam_yaw += look * 115 * dt + mv[0] * 40 * sens
    cam_pitch = cl(cam_pitch + pit * 60 * dt - mv[1] * 40 * sens, -8, 55)
    aim_k += ((1.0 if aiming else 0.0) - aim_k) * min(1, 12 * dt)
    cam_idle = 0.0 if moved else cam_idle + dt
    c = player.car
    heading = c.h if c else player.h
    if held_keys["c"]:
        cam_yaw += adiff(heading, cam_yaw) * min(1, 6 * dt)
    if c:
        if cam_idle > 1.2:
            cam_yaw += adiff(c.h, cam_yaw) * min(1, 2.5 * dt)
        tx, ty, tz = c.x, 1.9, c.z
        dist = 8.5 + abs(c.v) * 0.12
        camera.x = 0
        camera.fov += ((85 + abs(c.v) * 0.8) - camera.fov) * min(1, 3 * dt)
    else:
        tx, ty, tz = player.x, player.y + 1.7, player.z
        dist = 4.2 - 1.8 * aim_k
        camera.x = 0.7 + 0.1 * aim_k
        camera.fov += ((85 - 34 * aim_k) - camera.fov) * min(1, 8 * dt)
    k = min(1, 14 * dt)
    cam_pos[0] += (tx - cam_pos[0]) * k
    cam_pos[1] += (ty - cam_pos[1]) * k
    cam_pos[2] += (tz - cam_pos[2]) * k
    sy, cy = math.sin(math.radians(cam_yaw)), math.cos(math.radians(cam_yaw))
    cp = math.cos(math.radians(cam_pitch))
    while dist > 1.3:
        bx, bz = cam_pos[0] - sy * cp * dist, cam_pos[2] - cy * cp * dist
        if not hits_building(bx, bz, 0.8):
            break
        dist -= 0.5
    cam_pivot.position = (cam_pos[0], cam_pos[1], cam_pos[2])
    if shake_t > 0:
        cam_pivot.position = (cam_pos[0] + random.uniform(-1, 1) * shake_t * 0.5,
                              cam_pos[1] + random.uniform(-1, 1) * shake_t * 0.5,
                              cam_pos[2] + random.uniform(-1, 1) * shake_t * 0.5)
        shake_t = max(0.0, shake_t - dt * 2.5)
    cam_pivot.rotation = (cam_pitch, cam_yaw, 0)
    camera.z = -dist


def update_audio(dt):
    global audio_t
    audio_t -= dt
    if audio_t > 0:
        return
    audio_t = 0.08
    p = player
    if p.car:
        c = p.car
        r = abs(c.v) / max(1.0, c.maxv)
        snd.loop("eng_p", "engine", 0.3 + 0.3 * min(1.0, r), 0.55 + r * 1.9)
    else:
        snd.loop("eng_p", "engine", 0.0)
    movers = [c for c in cars if c.driver in ("ai", "cop") and c.active]
    movers.sort(key=lambda c: (c.x - cam_pos[0]) ** 2 + (c.z - cam_pos[2]) ** 2)
    for k in range(3):
        if k < len(movers):
            c = movers[k]
            snd.loop_at("eng%d" % k, "engine", c.x, c.z, 0.55, 0.55 + min(1.0, abs(c.v) / 30) * 1.6, 70)
        else:
            snd.loop("eng%d" % k, "engine", 0.0)


def update():
    global t_game, spawn_timer, cop_timer, hud_timer, cam_yaw, skid_t, skid_on, step_sign, was_air
    global prev_stars, prev_hp, flash_a, hurt_cd, aiming, click_buf, quick_gren
    dt = min(time.dt, 0.05)
    t_game += dt
    hurt_cd -= dt
    p = player
    p.hit_cd -= dt
    aiming = bool(p.alive and p.car is None and held_keys["right mouse"])
    click_buf = max(0.0, click_buf - dt)
    qg = quick_gren
    quick_gren = False
    update_camera(dt)

    up, down = held_keys["w"], held_keys["s"]
    left, right = held_keys["a"], held_keys["d"]
    shooting = bool(held_keys["left mouse"] or held_keys["j"] or held_keys["enter"])
    skid_on = False

    if p.alive:
        if p.car is None:
            fx, fz = math.sin(math.radians(cam_yaw)), math.cos(math.radians(cam_yaw))
            rx, rz = fz, -fx
            sx_, sz_ = int(bool(right)) - int(bool(left)), int(bool(up)) - int(bool(down))
            mx = sx_ * rx + sz_ * fx
            mz = sx_ * rz + sz_ * fz
            ml = math.hypot(mx, mz)
            speed = 0.0
            face_cam = aiming or (shooting and p.weapon < 3) or p.fire_t > 0.9
            if ml > 0:
                speed = 3.0 if aiming else (9.0 if (held_keys["left shift"] or held_keys["shift"]) else 5.0)
                move_circle(p, mx / ml * speed * dt, mz / ml * speed * dt, 0.45)
                if not face_cam:
                    target = math.degrees(math.atan2(mx, mz))
                    p.h += adiff(target, p.h) * min(1, 12 * dt)
                    if sz_ > 0 and cam_idle > 0.8:
                        cam_yaw += adiff(p.h, cam_yaw) * min(1, 1.6 * dt)
            if face_cam:
                p.h += adiff(cam_yaw, p.h) * min(1, 18 * dt)
            if held_keys["space"] and p.y <= 0.001:
                p.vy = 7.0
            p.vy -= 22 * dt
            p.y = max(0.0, p.y + p.vy * dt)
            if p.y == 0.0 and p.vy < 0:
                p.vy = 0.0
            was_air = p.y > 0.001
            p.cd -= dt
            p.gcd -= dt
            p.fire_t = max(0.0, p.fire_t - dt)
            if p.reload_t > 0:
                p.reload_t -= dt
                if p.reload_t <= 0:
                    finish_reload()
            if qg:
                throw_grenade()
            if p.weapon < 3:
                wp = WEAPONS[p.weapon]
                if p.cd <= 0 and p.reload_t <= 0:
                    if (wp["auto"] and shooting) or click_buf > 0:
                        click_buf = 0.0
                        fire_weapon()
            elif click_buf > 0 and p.cd <= 0:
                click_buf = 0.0
                throw_grenade()
            holding = p.weapon < 3 and (aiming or p.fire_t > 0)
            p.person.animate(speed, dt, aiming=holding)
            s_ = math.sin(p.person.phase)
            if speed > 0 and p.y <= 0.001 and s_ * step_sign < 0:
                snd.play("step", 0.35 if speed < 6 else 0.5, random.uniform(0.9, 1.15))
            if s_ != 0:
                step_sign = s_
            p.root.position = (p.x, p.y, p.z)
            p.root.rotation_y = p.h
        else:
            p.x, p.z = p.car.x, p.car.z
            c = p.car
            steer_abs = abs(int(bool(right)) - int(bool(left)))
            if abs(c.v) > 10 and (held_keys["space"] or (steer_abs and abs(c.v) > 24)):
                skid_on = True
                skid_t -= dt
                if skid_t <= 0:
                    skid_t = 0.06
                    sh, ch = math.sin(math.radians(c.h)), math.cos(math.radians(c.h))
                    for side in (-1, 1):
                        wx = c.x - sh * 1.3 + ch * side
                        wz = c.z - ch * 1.3 - sh * side
                        spawn_decal(wx, wz, 0.3, 0.9, c.h, rgb(24, 24, 26), 14, 0.085)
                        spawn_fx(wx, 0.3, wz, random.uniform(-1, 1), random.uniform(0.5, 1.5), random.uniform(-1, 1),
                                 0.6, 0.7, rgb(190, 190, 195), -1.0)
        if p.hp <= 0:
            die()
    else:
        p.dead_t -= dt
        if p.dead_t <= 0:
            respawn()

    for c in cars[:]:
        c.crash_cd -= dt
        if c.driver == "player":
            physics(c, dt, int(bool(up)) - int(bool(down)), int(bool(right)) - int(bool(left)),
                    bool(held_keys["space"]))
            move_car(c, dt)
        elif c.driver == "ai":
            ai_drive(c, dt)
        elif c.driver == "cop":
            cop_drive(c, dt)
            move_car(c, dt)
        elif abs(c.v) > 0.2:
            physics(c, dt, 0, 0, True)
            move_car(c, dt)
        if c.hp < 35:
            c.smoke_t -= dt
            if c.smoke_t <= 0:
                c.smoke_t = 0.12
                spawn_fx(c.x, 1.3, c.z, random.uniform(-0.5, 0.5), 3.0, random.uniform(-0.5, 0.5), 1.0, 0.9,
                         rgb(70, 70, 72), -0.5)
        if c.l1 is not None and c.driver in ("cop", "player"):
            on = int(t_game * 6) % 2 == 0
            c.l1.color = rgb(255, 40, 40) if on else rgb(80, 0, 0)
            c.l2.color = rgb(0, 0, 90) if on else rgb(60, 80, 255)
    car_collisions()
    for c in cars[:]:
        car_impacts(c)
    for c in cars[:]:
        if c.hp <= 0:
            explode(c)
        else:
            far = abs(c.x - p.x) > 190 or abs(c.z - p.z) > 190
            if far == c.vis:
                c.vis = not far
                c.root.enabled = c.vis
            if c.vis:
                c.sync()

    for pd in peds:
        pd.update(dt)
    for cp in cops:
        cp.update(dt)
    for co in corpses[:]:
        co[1] -= dt
        if co[1] <= 0:
            corpses.remove(co)
            co[0].active = False
            co[0].root.enabled = False
            co[2].append(co[0])

    for pk in pick_pool:
        if pk[2] and p.alive and math.hypot(pk[0].x - p.x, pk[0].z - p.z) < 1.8:
            if pk[3] == "ammo":
                give_ammo()
            else:
                p.money += pk[1]
            pk[2] = False
            pk[0].enabled = False
    update_fx(dt)
    update_grenades(dt)

    if p.stars > 0:
        p.crime_t += dt
        if p.crime_t > 14:
            p.stars -= 1
            p.crime_t = 8
    prev_stars = p.stars

    spawn_timer -= dt
    cop_timer -= dt
    want = (0, 1, 2, 2, 3, 4)[p.stars]
    n_cop = sum(1 for c in cars if c.kind == "police" and c.driver == "cop")
    if p.alive and n_cop < want and cop_timer <= 0 and car_free["police"]:
        spot = road_spot(110, 190)
        if spot:
            x, z, d = spot
            c = car_free["police"].pop()
            c.reset(x, z, DIR_H[d])
            c.driver = "cop"
            cars.append(c)
        cop_timer = 3
    for c in cars[:]:
        far = math.hypot(c.x - p.x, c.z - p.z)
        if c.driver == "player":
            continue
        if c.kind == "police":
            if p.stars == 0:
                c.idle += dt
                if c.idle > 8 and far > 80:
                    release_car(c)
                    continue
            if far > 320:
                release_car(c)
        elif far > 270:
            release_car(c)
    for cp in cops[:]:
        far = math.hypot(cp.x - p.x, cp.z - p.z)
        if p.stars == 0:
            cp.idle += dt
            if cp.idle > 10 and far > 70:
                release_cop(cp)
                continue
        if far > 250:
            release_cop(cp)

    if spawn_timer <= 0:
        spawn_timer = 0.25
        if sum(1 for c in cars if c.driver == "ai") < 22:
            spawn_civ(90, 210)
        if len(peds) < 40:
            spawn_ped(45, 150)
    for pd in peds[:]:
        if math.hypot(pd.x - p.x, pd.z - p.z) > 230:
            release_ped(pd)

    if p.hp < prev_hp - 1 and p.alive and hurt_cd <= 0:
        flash_a = min(0.55, flash_a + 0.35)
        hurt_cd = 0.3
    prev_hp = p.hp
    if not p.alive:
        hud_flash.enabled = True
        hud_flash.color = Color(0, 0, 0, 0.5)
    elif flash_a > 0:
        flash_a = max(0.0, flash_a - dt * 1.2)
        hud_flash.enabled = flash_a > 0.01
        hud_flash.color = Color(0.85, 0.05, 0.05, flash_a)
    else:
        hud_flash.enabled = False

    update_audio(dt)

    set_text(hud_money, "money", "$ %d" % p.money)
    if _hud_cache.get("stars") != p.stars:
        _hud_cache["stars"] = p.stars
        for k, s in enumerate(hud_stars):
            s.color = rgb(255, 215, 0) if k < p.stars else rgb(70, 70, 70)
    hud_hp.scale_x = 0.3 * cl(p.hp, 0, 100) / 100
    if p.car:
        hud_car.enabled = True
        hud_car.scale_x = 0.3 * cl(p.car.hp, 0, 100) / 100
        set_text(hud_speed, "speed", "%d км/ч" % (int(abs(p.car.v) * 3.6 / 5) * 5))
    else:
        hud_car.enabled = False
        set_text(hud_speed, "speed", "")
    foot = p.alive and p.car is None
    hud_cross.enabled = foot and not aiming
    hud_dot.enabled = foot and aiming
    hud_ammo.enabled = foot
    for sl in hud_slots:
        sl.enabled = foot
    if foot:
        if p.weapon < 3:
            txt = "ПЕРЕЗАРЯДКА" if p.reload_t > 0 else "%d / %d" % (p.ammo[p.weapon], p.reserve[p.weapon])
        else:
            txt = "Гранат: %d" % p.grenades
        set_text(hud_ammo, "ammo", txt)
        if _hud_cache.get("wsel") != p.weapon:
            _hud_cache["wsel"] = p.weapon
            for k, sl in enumerate(hud_slots):
                sl.color = rgb(255, 215, 0) if k == p.weapon else rgb(150, 150, 150)
    hud_timer -= dt
    if hud_timer <= 0:
        hud_timer = 0.12
        mm_player.position = (*mm_pos(p.x, p.z), -0.03)
        dots = [c for c in cars if c.kind == "police"] + cops
        for k, dot in enumerate(mm_dots):
            if k < len(dots):
                dot.enabled = True
                dot.position = (*mm_pos(dots[k].x, dots[k].z), -0.02)
                dot.color = rgb(255, 50, 50) if int(t_game * 4) % 2 else rgb(60, 90, 255)
            else:
                dot.enabled = False


for _ in range(22):
    spawn_civ(0, 260)
for _ in range(10):
    spawn_civ(0, 260, parked=True)
for _ in range(40):
    spawn_ped(0, 200)

mine.reset(3 * P + ROAD_C + 6.8, 3 * P + RW + 20, 0)
mine.maxv = 38
cars.append(mine)
cam_yaw = 0.0

app.run()