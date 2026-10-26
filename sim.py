"""
Game logic (no graphics). game.py draws it; compare.py runs it without a window.

Time is in game minutes. In the game, 1 real second = 1 game minute.
"""
import random
from collections import deque

from astar import astar, dijkstra
from fuzzy_triage import FuzzyTriage

BUILDING, ROAD, TRAFFIC, BLOCKED, HOSPITAL, BASE = range(6)
COST = {ROAD: 1, TRAFFIC: 3, HOSPITAL: 1, BASE: 1}
SPEED = 4.0            # tiles per minute on a normal road
SCENE_TIME = 1.5       # minutes treating the patient
DROPOFF_TIME = 1.0     # minutes handing over at the hospital

CALL_TYPES = {
    "critical": {"severity": (7.5, 10), "deadline": 30, "points": 30, "penalty": 30,
                 "names": ["Heart attack", "Stroke", "Road accident", "Not breathing"]},
    "serious": {"severity": (4.5, 7), "deadline": 50, "points": 20, "penalty": 15,
                "names": ["Fracture", "Asthma attack", "Bad burn", "High fever"]},
    "minor": {"severity": (0.5, 3.5), "deadline": 80, "points": 10, "penalty": 5,
              "names": ["Sprained ankle", "Small cut", "Mild fever", "Dizziness"]},
}
CALL_MIX = [("critical", 0.25), ("serious", 0.35), ("minor", 0.40)]


class CityMap:
    """Grid city: roads every 3rd row and 4th column, buildings in between,
    some slow traffic stretches and a few blocked roads."""

    def __init__(self, rows=15, cols=20, seed=7):
        self.rows, self.cols = rows, cols
        rng = random.Random(seed)
        self.grid = [[ROAD if (r % 3 == 0 or c % 4 == 0) else BUILDING
                      for c in range(cols)] for r in range(rows)]
        self.hospitals = [(3, 16), (12, 4)]
        self.base = (6, 8)
        reserved = set(self.hospitals) | {self.base}

        roads = [(r, c) for r in range(rows) for c in range(cols) if self.grid[r][c] == ROAD]
        for _ in range(7):                       # traffic jams: 3-tile stretches
            r, c = rng.choice(roads)
            dr, dc = (0, 1) if r % 3 == 0 else (1, 0)
            for k in range(3):
                rr, cc = r + dr * k, c + dc * k
                if 0 <= rr < rows and 0 <= cc < cols and self.grid[rr][cc] == ROAD and (rr, cc) not in reserved:
                    self.grid[rr][cc] = TRAFFIC
        blocked = 0
        while blocked < 5:                       # road works, keep the city connected
            r, c = rng.choice(roads)
            if (r, c) in reserved or self.grid[r][c] != ROAD:
                continue
            self.grid[r][c] = BLOCKED
            if self._connected():
                blocked += 1
            else:
                self.grid[r][c] = ROAD
        for h in self.hospitals:
            self.grid[h[0]][h[1]] = HOSPITAL
        self.grid[self.base[0]][self.base[1]] = BASE
        self.call_spots = [(r, c) for r in range(rows) for c in range(cols)
                           if self.grid[r][c] in (ROAD, TRAFFIC)]

    def passable(self, node):
        r, c = node
        return 0 <= r < self.rows and 0 <= c < self.cols and self.grid[r][c] in COST

    def cost(self, node):
        return COST[self.grid[node[0]][node[1]]]

    def neighbors(self, node):
        r, c = node
        for nb in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
            if self.passable(nb):
                yield nb

    def _connected(self):
        tiles = [(r, c) for r in range(self.rows) for c in range(self.cols)
                 if self.grid[r][c] in (ROAD, TRAFFIC)]
        seen, q = {tiles[0]}, deque([tiles[0]])
        while q:
            for nb in self.neighbors(q.popleft()):
                if nb not in seen:
                    seen.add(nb)
                    q.append(nb)
        return len(seen) == len(tiles)


class Call:
    def __init__(self, cid, node, kind, rng, t):
        info = CALL_TYPES[kind]
        self.id, self.node, self.kind = cid, node, kind
        self.name = rng.choice(info["names"])
        self.severity = round(rng.uniform(*info["severity"]), 1)
        if self.name == "High fever":
            self.age = rng.choice([rng.randint(1, 10), rng.randint(65, 90)])
        else:
            self.age = rng.randint(3, 90)
        self.t_call = t
        self.deadline = t + info["deadline"]
        self.status = "waiting"          # waiting -> assigned -> saved / lost
        self.response = None

    def wait(self, t):
        return t - self.t_call

    def time_left(self, t):
        return self.deadline - t


class Ambulance:
    def __init__(self, aid, node):
        self.id, self.node = aid, node
        self.state = "idle"     # idle, to_patient, on_scene, to_hospital, dropoff, returning
        self.path, self.progress, self.timer = [], 0.0, 0.0
        self.call = None

    @property
    def available(self):
        return self.state in ("idle", "returning")

    def set_path(self, path, state):
        self.path, self.progress, self.state = path[1:], 0.0, state

    def position(self):
        """Smooth position between tiles, for drawing."""
        if not self.path:
            return float(self.node[0]), float(self.node[1])
        nxt = self.path[0]
        f = min(1.0, self.progress)
        return (self.node[0] + (nxt[0] - self.node[0]) * f,
                self.node[1] + (nxt[1] - self.node[1]) * f)


class Simulation:
    def __init__(self, mode="fuzzy", seed=1, shift_length=180, n_ambulances=2,
                 mean_gap=3.5, map_seed=7):
        self.mode = mode                 # "fuzzy", "fifo" or "manual"
        self.city = CityMap(seed=map_seed)
        self.triage = FuzzyTriage()
        self.rng = random.Random(seed)
        self.t, self.shift_length, self.mean_gap = 0.0, shift_length, mean_gap
        self.next_spawn = self.rng.expovariate(1 / mean_gap)
        self.ambulances = [Ambulance(i + 1, self.city.base) for i in range(n_ambulances)]
        self.calls, self.next_id = [], 1
        self.score, self.events = 0, []
        self.last_search = None          # info about the most recent A* route

    # ---------- helpers ----------
    @property
    def waiting(self):
        return [c for c in self.calls if c.status == "waiting"]

    @property
    def finished(self):
        return self.t >= self.shift_length and not any(
            c.status in ("waiting", "assigned") for c in self.calls)

    def priority(self, call):
        return self.triage.priority(call.severity, call.age, call.wait(self.t))

    def log(self, text):
        self.events.append((self.t, text))
        self.events = self.events[-6:]

    def route(self, start, goal, record=True):
        path, cost, explored = astar(self.city, start, goal)
        if record:
            _, _, explored_d = dijkstra(self.city, start, goal)
            self.last_search = {"path": path, "explored": explored, "cost": cost,
                                "astar": len(explored), "dijkstra": len(explored_d)}
        return path, cost

    # ---------- dispatching ----------
    def choose_call(self):
        waiting = self.waiting
        if not waiting:
            return None
        if self.mode == "fifo":
            return min(waiting, key=lambda c: c.t_call)
        return max(waiting, key=self.priority)          # fuzzy

    def dispatch(self, call):
        """Send the nearest free ambulance to this call. Returns True if sent."""
        free = [a for a in self.ambulances if a.available]
        if not free or call.status != "waiting":
            return False
        best = min(free, key=lambda a: self.route(a.node, call.node, record=False)[1])
        path, cost = self.route(best.node, call.node)
        best.set_path(path, "to_patient")
        best.call = call
        call.status = "assigned"
        self.log(f"Ambulance {best.id} -> {call.name} (priority {self.priority(call):.0f})")
        return True

    def auto_dispatch(self):
        if self.mode == "manual":
            return
        while any(a.available for a in self.ambulances):
            call = self.choose_call()
            if call is None or not self.dispatch(call):
                break

    # ---------- main update ----------
    def update(self, dt):
        self.t += dt
        while self.t >= self.next_spawn and self.next_spawn < self.shift_length:
            self.spawn(self.next_spawn)
            self.next_spawn += self.rng.expovariate(1 / self.mean_gap)

        for c in self.waiting:
            if self.t > c.deadline:
                c.status = "lost"
                self.score -= CALL_TYPES[c.kind]["penalty"]
                self.log(f"LOST: {c.name}, nobody came in time")

        self.auto_dispatch()
        for amb in self.ambulances:
            self.move(amb, dt)

    def spawn(self, t):
        used = {c.node for c in self.calls if c.status in ("waiting", "assigned")}
        spots = [s for s in self.city.call_spots if s not in used]
        r, kind = self.rng.random(), "minor"
        acc = 0
        for k, p in CALL_MIX:
            acc += p
            if r < acc:
                kind = k
                break
        call = Call(self.next_id, self.rng.choice(spots), kind, self.rng, t)
        self.next_id += 1
        self.calls.append(call)
        self.log(f"New call: {call.name}, age {call.age}")

    def move(self, amb, dt):
        if amb.state in ("on_scene", "dropoff"):
            amb.timer -= dt
            if amb.timer <= 0:
                if amb.state == "on_scene":
                    hosp = min(self.city.hospitals, key=lambda h: self.route(amb.node, h, False)[1])
                    amb.set_path(self.route(amb.node, hosp, False)[0], "to_hospital")
                else:
                    amb.set_path(self.route(amb.node, self.city.base, False)[0], "returning")
            return
        while amb.path and dt > 0:
            nxt = amb.path[0]
            step_time = self.city.cost(nxt) / SPEED
            need = (1 - amb.progress) * step_time
            if dt >= need:
                dt -= need
                amb.node, amb.progress = nxt, 0.0
                amb.path.pop(0)
            else:
                amb.progress += dt / step_time
                dt = 0
        if not amb.path:
            self.arrive(amb)

    def arrive(self, amb):
        if amb.state == "to_patient":
            call = amb.call
            if self.t <= call.deadline:
                call.status, call.response = "saved", self.t - call.t_call
                self.score += CALL_TYPES[call.kind]["points"]
                self.log(f"SAVED: {call.name} in {call.response:.0f} min")
                amb.state, amb.timer = "on_scene", SCENE_TIME
            else:
                call.status = "lost"
                self.score -= CALL_TYPES[call.kind]["penalty"]
                self.log(f"LOST: {call.name}, arrived too late")
                amb.set_path(self.route(amb.node, self.city.base, False)[0], "returning")
                amb.call = None
        elif amb.state == "to_hospital":
            amb.state, amb.timer, amb.call = "dropoff", DROPOFF_TIME, None
        elif amb.state == "returning":
            amb.state = "idle"

    # ---------- results ----------
    def stats(self):
        def group(kind=None):
            cs = [c for c in self.calls if (kind is None or c.kind == kind)
                  and c.status in ("saved", "lost")]
            saved = [c for c in cs if c.status == "saved"]
            avg = sum(c.response for c in saved) / len(saved) if saved else 0
            return len(saved), len(cs), avg
        return {"all": group(), "critical": group("critical"),
                "serious": group("serious"), "minor": group("minor"), "score": self.score}
