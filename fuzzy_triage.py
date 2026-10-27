"""
Fuzzy triage: Mamdani fuzzy inference system written from scratch in plain
Python (no libraries), so it also runs in the browser version of the game.

Inputs
  severity  0-10   how serious the emergency is
  age       0-100  patient age in years
  wait      0-30   minutes the call has already been waiting
  distance  0-12   minutes for the nearest ambulance to drive there (from A*)
Output
  priority  0-100

Steps: fuzzification -> rule evaluation (AND = min, OR = max)
       -> implication (clip) -> aggregation (max) -> defuzzification (centroid)
"""


def trimf(x, a, b, c):
    """Triangle: 0 at a, rises to 1 at b, falls to 0 at c."""
    left = (x - a) / (b - a) if b > a else (1.0 if x >= b else 0.0)
    right = (c - x) / (c - b) if c > b else (1.0 if x <= b else 0.0)
    return max(0.0, min(left, right, 1.0))


def trapmf(x, a, b, c, d):
    """Trapezoid: 0 at a, 1 from b to c, 0 at d."""
    if b == a:
        left = 1.0 if x >= a else 0.0
    else:
        left = (x - a) / (b - a)
    if d == c:
        right = 1.0 if x <= d else 0.0
    else:
        right = (d - x) / (d - c)
    return max(0.0, min(left, 1.0, right))


def linspace(lo, hi, n):
    step = (hi - lo) / (n - 1)
    return [lo + i * step for i in range(n)]


class FuzzyTriage:
    def __init__(self):
        self.universe = {
            "severity": linspace(0, 10, 201),
            "age": linspace(0, 100, 201),
            "wait": linspace(0, 30, 201),
            "distance": linspace(0, 12, 201),
            "priority": linspace(0, 100, 201),
        }
        # Membership functions: name -> (shape, parameters)
        self.mfs = {
            "severity": {
                "low": ("trap", (0, 0, 2, 4)),
                "medium": ("tri", (3, 5, 7)),
                "high": ("trap", (6, 8, 10, 10)),
            },
            "age": {
                "child": ("trap", (0, 0, 8, 15)),
                "adult": ("trap", (12, 20, 50, 62)),
                "elderly": ("trap", (55, 68, 100, 100)),
            },
            "wait": {
                "short": ("trap", (0, 0, 3, 7)),
                "medium": ("tri", (5, 10, 15)),
                "long": ("trap", (12, 18, 30, 30)),
            },
            "distance": {
                "near": ("trap", (0, 0, 2, 4)),
                "medium": ("tri", (3, 5.5, 8)),
                "far": ("trap", (7, 9, 12, 12)),
            },
            "priority": {
                "low": ("trap", (0, 0, 15, 35)),
                "medium": ("tri", (25, 45, 65)),
                "high": ("tri", (55, 72, 88)),
                "critical": ("trap", (80, 92, 100, 100)),
            },
        }
        # Rule base: (description, firing strength function, output set)
        self.rules = [
            ("IF severity is high THEN critical",
             lambda m: m["severity"]["high"], "critical"),
            ("IF severity is medium AND age is (child OR elderly) THEN high",
             lambda m: min(m["severity"]["medium"],
                           max(m["age"]["child"], m["age"]["elderly"])), "high"),
            ("IF severity is medium AND age is adult THEN medium",
             lambda m: min(m["severity"]["medium"], m["age"]["adult"]), "medium"),
            ("IF severity is medium AND wait is long THEN high",
             lambda m: min(m["severity"]["medium"], m["wait"]["long"]), "high"),
            ("IF severity is low AND age is adult AND wait is (short OR medium) THEN low",
             lambda m: min(m["severity"]["low"], m["age"]["adult"],
                           max(m["wait"]["short"], m["wait"]["medium"])), "low"),
            ("IF severity is low AND age is (child OR elderly) THEN medium",
             lambda m: min(m["severity"]["low"],
                           max(m["age"]["child"], m["age"]["elderly"])), "medium"),
            ("IF severity is low AND wait is long THEN medium",
             lambda m: min(m["severity"]["low"], m["wait"]["long"]), "medium"),
            # distance rules: a nearby patient can be reached quickly, a far one costs a lot of ambulance time
            ("IF severity is medium AND distance is near THEN high",
             lambda m: min(m["severity"]["medium"], m["distance"]["near"]), "high"),
            ("IF severity is low AND distance is near AND wait is (short OR medium) THEN medium",
             lambda m: min(m["severity"]["low"], m["distance"]["near"],
                           max(m["wait"]["short"], m["wait"]["medium"])), "medium"),
            ("IF severity is low AND distance is far AND wait is (short OR medium) THEN low",
             lambda m: min(m["severity"]["low"], m["distance"]["far"],
                           max(m["wait"]["short"], m["wait"]["medium"])), "low"),
        ]
        # Pre-compute the output membership curves once
        y = self.universe["priority"]
        self._out_curves = {t: [self.mf("priority", t, v) for v in y]
                            for t in self.mfs["priority"]}

    def mf(self, var, term, x):
        kind, p = self.mfs[var][term]
        return trimf(x, *p) if kind == "tri" else trapmf(x, *p)

    def curve(self, var, term):
        """Membership values over the whole range (used for drawing graphs)."""
        return [self.mf(var, term, v) for v in self.universe[var]]

    def fuzzify(self, severity, age, wait, distance):
        crisp = {"severity": min(max(severity, 0), 10),
                 "age": min(max(age, 0), 100),
                 "wait": min(max(wait, 0), 30),
                 "distance": min(max(distance, 0), 12)}
        return {var: {t: self.mf(var, t, crisp[var]) for t in self.mfs[var]}
                for var in crisp}

    def infer(self, severity, age, wait, distance, explain=False):
        m = self.fuzzify(severity, age, wait, distance)
        y = self.universe["priority"]
        aggregated = [0.0] * len(y)
        fired = []
        for desc, fn, out in self.rules:
            strength = fn(m)
            if strength > 0:
                fired.append((desc, round(strength, 3)))
                curve = self._out_curves[out]
                for i in range(len(y)):
                    clipped = min(strength, curve[i])          # implication
                    if clipped > aggregated[i]:                # aggregation
                        aggregated[i] = clipped
        total = sum(aggregated)
        score = sum(v * a for v, a in zip(y, aggregated)) / total if total else 0.0  # centroid
        if explain:
            return score, {"memberships": m, "fired_rules": fired, "aggregated": aggregated}
        return score

    def priority(self, severity, age, wait, distance):
        return self.infer(severity, age, wait, distance)
