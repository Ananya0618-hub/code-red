"""
CODE RED: AI Ambulance Dispatcher
Fuzzy logic decides WHO the ambulance helps first.
A* search decides WHICH ROAD it takes.

Run:  python game.py

Keys
  1 / 2 / 3   restart in Fuzzy AI / FIFO / Manual mode (same calls, fair comparison)
  N           new set of calls
  V           show / hide the A* search (tiles A* checked)
  SPACE       manual mode: send an ambulance to the selected call
  P           pause      +/-  game speed      R  restart      ESC  quit
Click a call (on the map or in the list) to see its fuzzy logic breakdown.
"""
import asyncio
import math
import pygame

from sim import (Simulation, BUILDING, ROAD, TRAFFIC, BLOCKED, HOSPITAL, BASE,
                 CALL_TYPES)

TILE = 40
MAP_W, MAP_H = 20 * TILE, 15 * TILE
PANEL_W, BAR_H = 380, 120
W, H = MAP_W + PANEL_W, MAP_H + BAR_H

C = {
    "bg": (24, 27, 38), "panel": (32, 36, 50), "line": (60, 66, 86),
    "building": (52, 60, 82), "roof": (66, 76, 102), "road": (138, 143, 153),
    "traffic": (205, 140, 60), "blocked_a": (200, 40, 40), "blocked_b": (240, 240, 240),
    "hospital": (245, 245, 245), "cross": (220, 40, 40), "base": (47, 111, 214),
    "text": (235, 238, 245), "muted": (160, 168, 186), "good": (90, 200, 120),
    "bad": (240, 90, 90), "explored": (66, 135, 245, 80), "select": (255, 255, 255),
    "critical": (229, 57, 53), "serious": (251, 140, 0), "minor": (253, 216, 53),
}
AMB_COLORS = [(0, 200, 230), (224, 64, 251), (120, 230, 120)]
MODE_NAMES = {"fuzzy": "FUZZY AI", "fifo": "FIFO (first come, first served)", "manual": "MANUAL (you decide)"}


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("CODE RED: AI Ambulance Dispatcher")
        self.screen = pygame.display.set_mode((W, H))
        self.clock = pygame.time.Clock()
        self.f_big = pygame.font.Font(None, 44)
        self.f_mid = pygame.font.Font(None, 28)
        self.f_small = pygame.font.Font(None, 22)
        self.seed, self.mode = 1, "fuzzy"
        self.speed, self.paused, self.show_search = 1, False, True
        self.selected, self.list_rects, self.message = None, [], ""
        self._text_cache = {}
        self.restart()

    def restart(self, mode=None):
        if mode:
            self.mode = mode
        self.sim = Simulation(mode=self.mode, seed=self.seed)
        self._map_cache, self._search_key = None, None
        self.selected, self.message = None, ""

    # ---------- input ----------
    def handle(self, event):
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.KEYDOWN:
            k = event.key
            if k == pygame.K_ESCAPE:
                return False
            if k == pygame.K_1: self.restart("fuzzy")
            if k == pygame.K_2: self.restart("fifo")
            if k == pygame.K_3: self.restart("manual")
            if k == pygame.K_r: self.restart()
            if k == pygame.K_n:
                self.seed += 1
                self.restart()
            if k == pygame.K_v: self.show_search = not self.show_search
            if k == pygame.K_p: self.paused = not self.paused
            if k in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS): self.speed = min(8, self.speed * 2)
            if k in (pygame.K_MINUS, pygame.K_KP_MINUS): self.speed = max(1, self.speed // 2)
            if k == pygame.K_SPACE and self.mode == "manual" and self.selected:
                if self.sim.dispatch(self.selected):
                    self.message = ""
                else:
                    self.message = "No ambulance is free right now!"
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            x, y = event.pos
            if x < MAP_W and y < MAP_H:
                tile = (y // TILE, x // TILE)
                for c in self.sim.calls:
                    if c.node == tile and c.status in ("waiting", "assigned"):
                        self.selected = c
            for rect, call in self.list_rects:
                if rect.collidepoint(x, y):
                    self.selected = call
        return True

    # ---------- drawing helpers ----------
    def text(self, s, pos, font=None, color=None):
        key = (s, id(font or self.f_small), color or C["text"])
        img = self._text_cache.get(key)
        if img is None:
            if len(self._text_cache) > 2000:
                self._text_cache.clear()
            img = (font or self.f_small).render(s, True, color or C["text"])
            self._text_cache[key] = img
        self.screen.blit(img, pos)
        return img.get_width()

    def tile_rect(self, r, c):
        return pygame.Rect(c * TILE, r * TILE, TILE, TILE)

    def draw_map(self):
        if getattr(self, "_map_cache", None) is None:
            real = self.screen
            self.screen = pygame.Surface((MAP_W, MAP_H))
            self._draw_map_tiles()
            self._map_cache, self.screen = self.screen, real
            self._bg_key = "none"
        info = self.sim.last_search
        key = (id(info) if info else None, self.show_search)
        if key != self._bg_key:
            self._bg = self._map_cache.copy()
            if self.show_search and info and info["path"]:
                overlay = pygame.Surface((MAP_W, MAP_H), pygame.SRCALPHA)
                for (r, c) in info["explored"]:
                    overlay.fill(C["explored"], self.tile_rect(r, c).inflate(-4, -4))
                self._bg.blit(overlay, (0, 0))
            self._bg_key = key
        self.screen.blit(self._bg, (0, 0))

    def _draw_map_tiles(self):
        city = self.sim.city
        for r in range(city.rows):
            for c in range(city.cols):
                t, rect = city.grid[r][c], self.tile_rect(r, c)
                if t == BUILDING:
                    pygame.draw.rect(self.screen, C["building"], rect)
                    pygame.draw.rect(self.screen, C["roof"], rect.inflate(-10, -10), border_radius=4)
                elif t == TRAFFIC:
                    pygame.draw.rect(self.screen, C["traffic"], rect)
                    for i in range(3):
                        pygame.draw.circle(self.screen, (120, 70, 20), (rect.x + 10 + i * 10, rect.centery), 3)
                elif t == BLOCKED:
                    pygame.draw.rect(self.screen, C["blocked_b"], rect)
                    self.screen.set_clip(rect)
                    for i in range(-TILE, TILE, 12):
                        pygame.draw.line(self.screen, C["blocked_a"], (rect.x + i, rect.bottom),
                                         (rect.x + i + TILE, rect.y), 5)
                    self.screen.set_clip(None)
                elif t == HOSPITAL:
                    pygame.draw.rect(self.screen, C["hospital"], rect)
                    pygame.draw.rect(self.screen, C["cross"], (rect.centerx - 4, rect.y + 8, 8, 24))
                    pygame.draw.rect(self.screen, C["cross"], (rect.x + 8, rect.centery - 4, 24, 8))
                elif t == BASE:
                    pygame.draw.rect(self.screen, C["base"], rect)
                    self.text("B", (rect.x + 13, rect.y + 11), self.f_mid)
                else:
                    pygame.draw.rect(self.screen, C["road"], rect)
                pygame.draw.rect(self.screen, C["bg"], rect, 1)

    def draw_search(self):
        info = self.sim.last_search
        if not (self.show_search and info and info["path"]):
            return
        if getattr(self, "_search_key", None) is not info:
            overlay = pygame.Surface((MAP_W, MAP_H), pygame.SRCALPHA)
            for (r, c) in info["explored"]:
                overlay.fill(C["explored"], self.tile_rect(r, c).inflate(-4, -4))
            self._search_overlay, self._search_key = overlay, info
        self.screen.blit(self._search_overlay, (0, 0))

    def draw_paths(self):
        for amb in self.sim.ambulances:
            if not amb.path:
                continue
            color = AMB_COLORS[(amb.id - 1) % len(AMB_COLORS)]
            pr, pc = amb.position()
            pts = [(pc * TILE + TILE / 2, pr * TILE + TILE / 2)]
            pts += [(c * TILE + TILE / 2, r * TILE + TILE / 2) for r, c in amb.path]
            if len(pts) > 1:
                pygame.draw.lines(self.screen, color, False, pts, 4)

    def draw_calls(self):
        t = self.sim.t
        for c in self.sim.calls:
            if c.status not in ("waiting", "assigned"):
                continue
            rect = self.tile_rect(*c.node)
            col = C[c.kind]
            pulse = 2 * math.sin(t * 6) if c.kind == "critical" else 0
            pygame.draw.circle(self.screen, col, rect.center, 13 + pulse)
            self.text("!", (rect.centerx - 3, rect.centery - 8), self.f_mid, (20, 20, 20))
            frac = max(0.0, c.time_left(t)) / CALL_TYPES[c.kind]["deadline"]
            arc = pygame.Rect(0, 0, 36, 36)
            arc.center = rect.center
            pygame.draw.arc(self.screen, C["text"], arc, math.pi / 2, math.pi / 2 + 2 * math.pi * frac, 3)
            if c is self.selected:
                pygame.draw.rect(self.screen, C["select"], rect, 2)

    def draw_ambulances(self):
        for amb in self.sim.ambulances:
            r, c = amb.position()
            x, y = c * TILE + 4, r * TILE + 8
            color = AMB_COLORS[(amb.id - 1) % len(AMB_COLORS)]
            pygame.draw.rect(self.screen, (250, 250, 250), (x, y, 32, 24), border_radius=5)
            pygame.draw.rect(self.screen, color, (x, y, 32, 24), 3, border_radius=5)
            pygame.draw.rect(self.screen, C["cross"], (x + 14, y + 5, 4, 14))
            pygame.draw.rect(self.screen, C["cross"], (x + 9, y + 10, 14, 4))
            self.text(str(amb.id), (x + 2, y + 2), self.f_small, (30, 30, 30))

    def draw_panel(self):
        sim, x0 = self.sim, MAP_W + 18
        pygame.draw.rect(self.screen, C["panel"], (MAP_W, 0, PANEL_W, H))
        self.text("CODE RED", (x0, 14), self.f_big, C["critical"])
        self.text("AI Ambulance Dispatcher", (x0, 48), self.f_small, C["muted"])
        self.text("Mode: " + MODE_NAMES[self.mode], (x0, 76), self.f_small)
        st = sim.stats()
        clock = min(sim.t, sim.shift_length)
        self.text(f"Time {clock:.0f}/{sim.shift_length} min   x{self.speed}" + ("   PAUSED" if self.paused else ""),
                  (x0, 100), self.f_small, C["muted"])
        saved = sum(1 for c in sim.calls if c.status == "saved")
        lost = sum(1 for c in sim.calls if c.status == "lost")
        self.text(f"Score {st['score']}", (x0, 126), self.f_mid)
        self.text(f"Saved {saved}", (x0 + 140, 126), self.f_mid, C["good"])
        self.text(f"Lost {lost}", (x0 + 250, 126), self.f_mid, C["bad"])

        y = 162
        self.text("WAITING CALLS (highest fuzzy priority first)", (x0, y), self.f_small, C["muted"])
        y += 22
        self.list_rects = []
        waiting = sorted(sim.waiting, key=sim.priority, reverse=True)[:6]
        for call in waiting:
            rect = pygame.Rect(x0 - 6, y, PANEL_W - 24, 30)
            if call is self.selected:
                pygame.draw.rect(self.screen, C["line"], rect, border_radius=6)
            pygame.draw.circle(self.screen, C[call.kind], (x0 + 6, y + 15), 7)
            self.text(f"{call.name}, {call.age}y", (x0 + 20, y + 7))
            self.text(f"wait {call.wait(sim.t):.0f}m", (x0 + 200, y + 7), color=C["muted"])
            self.text(f"P {sim.priority(call):.0f}", (x0 + 285, y + 7), color=C["minor"])
            self.list_rects.append((rect, call))
            y += 32
        if not waiting:
            self.text("No one waiting", (x0, y + 4), color=C["muted"])
            y += 32
        self.draw_explanation(x0, max(y + 10, 392))

    def draw_explanation(self, x0, y):
        call, sim = self.selected, self.sim
        pygame.draw.line(self.screen, C["line"], (MAP_W + 10, y), (W - 10, y), 1)
        y += 10
        if call is None or call.status not in ("waiting", "assigned"):
            self.text("Click a call to see how fuzzy logic", (x0, y), color=C["muted"])
            self.text("calculates its priority.", (x0, y + 20), color=C["muted"])
            return
        dist = round(sim.distance(call) * 2) / 2
        ekey = (call.id, round(call.wait(sim.t) * 2) / 2, dist)
        if getattr(self, "_explain_key", None) != ekey:
            self._explain = sim.triage.infer(call.severity, call.age, ekey[1], dist, explain=True)
            self._explain_key = ekey
        score, info = self._explain
        self.text(f"{call.name}", (x0, y), self.f_mid, C[call.kind])
        self.text(f"Priority {score:.0f}/100", (x0 + 220, y + 2), self.f_small, C["minor"])
        y += 26
        self.text(f"Severity {call.severity}  Age {call.age}  Waited {call.wait(sim.t):.0f}m  Distance {dist:.1f}m",
                  (x0, y), color=C["muted"])
        y += 24
        names = {"severity": "Severity", "age": "Age", "wait": "Wait", "distance": "Distance"}
        for var, terms in info["memberships"].items():
            parts = ", ".join(f"{t} {v:.2f}" for t, v in terms.items() if v > 0)
            self.text(f"{names[var]}: {parts}", (x0, y))
            y += 20
        y += 4
        self.text("Rules that fired:", (x0, y), color=C["muted"])
        y += 20
        for desc, strength in info["fired_rules"][:4]:
            short = (desc.replace("IF ", "").replace(" THEN ", " -> ").replace("severity", "sev")
                     .replace("is ", "").replace(" AND ", " & ").replace(" OR ", "/")
                     .replace("wait (short/medium)", "short wait").replace("distance", "dist"))
            self.text(f"{short}  ({strength:.2f})", (x0, y))
            y += 20
        if self.mode == "manual" and call.status == "waiting":
            self.text("Press SPACE to send an ambulance", (x0, y + 6), color=C["good"])

    def draw_bar(self):
        y0 = MAP_H
        pygame.draw.rect(self.screen, C["bg"], (0, y0, MAP_W, BAR_H))
        info = self.sim.last_search
        if info and info["path"]:
            fewer = 100 * (1 - info["astar"] / max(1, info["dijkstra"]))
            self.text(f"Last A* route: cost {info['cost']}   A* checked {info['astar']} tiles,"
                      f" Dijkstra {info['dijkstra']}  ({fewer:.0f}% less work)", (14, y0 + 10), self.f_small)
        for i, (t, msg) in enumerate(self.sim.events[-3:]):
            col = C["good"] if msg.startswith("SAVED") else C["bad"] if msg.startswith("LOST") else C["muted"]
            self.text(f"[{t:5.1f}] {msg}", (14, y0 + 34 + i * 20), self.f_small, col)
        if self.message:
            self.text(self.message, (480, y0 + 34), self.f_small, C["bad"])
        self.text("1 Fuzzy  2 FIFO  3 Manual   V show search   SPACE send (manual)   P pause   +/- speed   R restart",
                  (14, y0 + 98), self.f_small, C["muted"])

    def draw_game_over(self):
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 190))
        self.screen.blit(overlay, (0, 0))
        st, x, y = self.sim.stats(), W // 2 - 300, 150
        pygame.draw.rect(self.screen, C["panel"], (x - 30, y - 30, 660, 380), border_radius=16)
        pygame.draw.rect(self.screen, C["line"], (x - 30, y - 30, 660, 380), 2, border_radius=16)
        self.text("SHIFT OVER", (x, y), self.f_big, C["critical"])
        self.text("Mode: " + MODE_NAMES[self.mode], (x, y + 50), self.f_mid)
        y += 100
        for kind in ("critical", "serious", "minor"):
            saved, total, avg = st[kind]
            pct = 100 * saved / total if total else 0
            self.text(f"{kind.capitalize():9s} saved {saved}/{total} ({pct:.0f}%)   avg response {avg:.1f} min",
                      (x, y), self.f_mid, C[kind])
            y += 36
        self.text(f"Final score: {st['score']}", (x, y + 10), self.f_big)
        self.text("Press 1 / 2 / 3 to replay the same calls in another mode, N for new",
                  (x, y + 70), self.f_small, C["muted"])

    # ---------- main loop ----------
    def frame(self, real_dt):
        if not self.paused and not self.sim.finished:
            remaining = real_dt * self.speed
            while remaining > 0:
                step = min(0.05, remaining)
                self.sim.update(step)
                remaining -= step
        self.screen.fill(C["bg"])
        self.draw_map()
        self.draw_paths()
        self.draw_calls()
        self.draw_ambulances()
        self.draw_panel()
        self.draw_bar()
        if self.sim.finished:
            self.draw_game_over()
        pygame.display.flip()

    async def run(self):
        # async so the same loop also works in the browser version (pygbag)
        running = True
        while running:
            for event in pygame.event.get():
                running = self.handle(event)
                if not running:
                    break
            self.frame(self.clock.tick(30) / 1000)
            await asyncio.sleep(0)
        pygame.quit()


if __name__ == "__main__":
    asyncio.run(Game().run())
