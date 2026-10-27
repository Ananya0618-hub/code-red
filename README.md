# CODE RED: AI Ambulance Dispatcher

A game for the AISC project. Emergency calls appear around a city and two ambulances have to reach them before time runs out.

- **Fuzzy logic** decides *who goes first*, from how serious the case is, the patient's age, how long they have waited and how far away they are.
- **A\* search** decides *which road to take*, around traffic jams and blocked roads.

You can let the AI play, or play yourself and try to beat it.

## Play online

**https://ananya0618-hub.github.io/code-red/** (opens in the browser, no install; click the page once to start)

## Run on your computer

```bash
pip install -r requirements.txt
python game.py        # play the game
python compare.py     # FIFO vs fuzzy over 20 shifts, no graphics
```

The web version is the same Python code, built automatically with [pygbag](https://pypi.org/project/pygbag/) by the GitHub Action in `.github/workflows/pages.yml` every time code is pushed.

## Controls

| Key | Action |
|---|---|
| 1 / 2 / 3 | Restart in **Fuzzy AI** / **FIFO** / **Manual** mode (same calls, so it is a fair comparison) |
| Click a call | See its fuzzy logic breakdown (memberships and rules that fired) |
| SPACE | Manual mode: send the nearest free ambulance to the selected call |
| V | Show or hide the tiles A* checked (blue) |
| P / R / N | Pause / restart / new set of calls |
| + / − | Game speed |

## What is on screen

- **Grey tiles:** roads (cost 1). **Orange tiles:** traffic jams (cost 3). **Red-white stripes:** blocked roads.
- **White ✚ tiles:** hospitals. **Blue B:** ambulance base.
- **Coloured circles:** emergencies. Red is critical, orange serious, yellow minor. The white ring is the time left before the patient is lost.
- **Coloured lines:** each ambulance's A* route. **Light blue tiles:** the tiles A* checked for the last route.
- **Bottom bar:** how many tiles A* checked compared with Dijkstra for the same route.

## Game rules

- One game minute passes every real second. A shift lasts 180 minutes, and a new call arrives on average every 3.5 minutes.
- Time limits: critical 30 min, serious 50 min, minor 80 min.
- One trip: drive to the patient, 1.5 min on scene, drive to the nearest hospital, 1 min handover, then back to base. An ambulance driving back to base can be sent to a new call.
- Points for each patient saved: critical +30, serious +20, minor +10. Points lost for each patient lost: critical −30, serious −15, minor −5.

## Results (`python compare.py`, 20 shifts)

| Method | Critical saved | Serious saved | Minor saved | Avg score |
|---|---|---|---|---|
| FIFO (first come, first served) | 66% | 98% | 100% | 694 |
| **Fuzzy priority** | **100%** | 97% | 85% | **902** |

With FIFO, a heart attack can wait behind a sprained ankle and run out of time. Fuzzy logic sends ambulances to the most urgent patients first, so every critical patient was saved. The trade-off is that a few minor patients wait too long.

## Files

```
main.py          Entry point (used by the browser version)
game.py          Pygame window: drawing, mouse and keyboard
sim.py           Game logic: city map, calls, ambulances, dispatching (no graphics)
astar.py         A* search and Dijkstra
fuzzy_triage.py  Fuzzy logic system (Mamdani), written from scratch in plain Python
compare.py       Runs FIFO vs fuzzy many times and prints the results
```

---

## How the AI works

### A* search (astar.py)

The city is a grid of tiles. Moving onto a road tile costs 1 and onto a traffic tile costs 3. Buildings and blocked roads cannot be entered.

```
f(n) = g(n) + h(n)
g(n) = cost of the route so far
h(n) = Manhattan distance to the goal = |row difference| + |column difference|
```

A* always expands the tile with the smallest f(n). It uses a priority queue (min-heap).

- **Admissible:** the cheapest tile costs 1 and the ambulance moves only up, down, left or right, so the real cost is always at least the Manhattan distance. The heuristic never overestimates, so A* finds the cheapest route.
- **Consistent:** h(a) ≤ cost(a→b) + h(b) for neighbouring tiles, so a tile never has to be expanded twice.
- **Dijkstra** is A* with h(n) = 0. The game runs it for every route only to count its work. A* typically checks about half as many tiles and finds a route of the same cost.

A* is used three times in every trip: base to patient, patient to nearest hospital, hospital back to base. It is also used to choose the nearest free ambulance, by comparing route costs rather than straight-line distance.

### Fuzzy logic (fuzzy_triage.py)

| Variable | Range | Fuzzy sets |
|---|---|---|
| Severity (input) | 0–10 | low, medium, high |
| Age (input) | 0–100 | child, adult, elderly |
| Waiting time (input) | 0–30 min | short, medium, long |
| Distance (input) | 0–12 min | near, medium, far (driving time for the nearest ambulance, from Dijkstra on the road grid) |
| Priority (output) | 0–100 | low, medium, high, critical |

Rules:

1. IF severity is high THEN priority is critical
2. IF severity is medium AND age is child OR elderly THEN high
3. IF severity is medium AND age is adult THEN medium
4. IF severity is medium AND wait is long THEN high
5. IF severity is low AND age is adult AND wait is not long THEN low
6. IF severity is low AND age is child OR elderly THEN medium
7. IF severity is low AND wait is long THEN medium
8. IF severity is medium AND distance is near THEN high
9. IF severity is low AND distance is near AND wait is not long THEN medium
10. IF severity is low AND distance is far AND wait is not long THEN low

Rules 8–10 use distance: a nearby patient can be reached quickly, so moderate and minor cases close to an ambulance move up, and far-away minor cases move down. Severe cases are always critical, however far away they are.

Steps (Mamdani inference):

1. **Fuzzify** each input into membership degrees, e.g. age 74 means elderly 1.0, and 2 minutes away means near 1.0.
2. **Evaluate the rules:** AND = min, OR = max.
3. **Clip** each rule's output set at its strength.
4. **Combine** the clipped sets with max.
5. **Defuzzify** with the centroid, which gives one priority number.

The priority is recalculated every half game-minute, because waiting time and distance keep changing as ambulances move. That is how a minor case slowly rises up the list and is not forgotten.

## Viva questions

1. **What does your project do?** It is an ambulance dispatch game. Fuzzy logic decides which emergency to serve first, and A* finds the fastest route through the city.
2. **Why fuzzy logic?** Triage is vague: "fairly serious", "elderly", "waited a while". Fixed cut-offs like "age > 60" treat 59 and 61 completely differently. Fuzzy sets change smoothly and every decision can be explained by the rules that fired.
3. **What is defuzzification?** Turning the combined fuzzy output into one number. We use the centroid (centre of gravity).
4. **Why is waiting time an input?** So low-priority patients slowly rise in priority and are not ignored forever (no starvation).
5. **What is your heuristic and is it admissible?** Manhattan distance. Yes: every move costs at least 1 and only 4-direction moves are allowed, so it never overestimates.
6. **What if the heuristic overestimated?** A* could return a route that is not the cheapest.
7. **A* vs Dijkstra?** Dijkstra is A* with h = 0 and searches in all directions. A* is pulled towards the goal and checked about half as many tiles in our tests for the same cost.
8. **Why do traffic tiles cost 3?** A traffic jam takes three times as long to cross, so A* will often go around it. This shows A* minimises time, not number of tiles.
9. **Why add distance?** Serving a nearby patient uses less ambulance time, so the ambulance is free sooner for the next emergency. But a severe case stays critical even when it is far, so distance never pushes a heart attack down the list.
10. **What is the trade-off of fuzzy dispatch?** Minor patients wait longer. FIFO saved all minor patients but only 66% of critical ones; fuzzy saved 100% of critical patients and 85% of minor ones.
11. **How could it be improved?** Real city maps, more ambulances, time-of-day traffic, or letting a genetic algorithm tune the fuzzy membership functions automatically.
