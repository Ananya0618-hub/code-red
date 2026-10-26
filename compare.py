"""
Runs the game without graphics many times and compares
FIFO (first come, first served) with fuzzy priority dispatch.

Usage:  python compare.py
"""
from sim import Simulation


def run(mode, seed):
    sim = Simulation(mode=mode, seed=seed)
    while not sim.finished:
        sim.update(0.05)
    return sim.stats()


def main(runs=20):
    print(f"Average over {runs} shifts (same calls for both methods)\n")
    print(f"{'':10s}{'Critical saved':>16s}{'Serious saved':>16s}{'Minor saved':>14s}{'Score':>8s}")
    for mode in ("fifo", "fuzzy"):
        tot = {"critical": [0, 0], "serious": [0, 0], "minor": [0, 0]}
        score = 0
        for seed in range(runs):
            s = run(mode, seed)
            for k in tot:
                tot[k][0] += s[k][0]
                tot[k][1] += s[k][1]
            score += s["score"]
        pct = {k: 100 * v[0] / max(1, v[1]) for k, v in tot.items()}
        print(f"{mode.upper():10s}{pct['critical']:>15.0f}%{pct['serious']:>15.0f}%"
              f"{pct['minor']:>13.0f}%{score / runs:>8.0f}")


if __name__ == "__main__":
    main()
