"""
Triage checklist: how SEVERITY is decided.

Severity is NOT the caller's opinion ("it's very serious!"). Like real
ambulance dispatchers (e.g. India's 108 service), the operator asks fixed
yes/no questions about symptoms. Each YES adds a fixed medical weight:

    severity = sum of weights of the symptoms present   (capped at 10)

Red-flag symptoms (unconscious, stroke signs, chest pain, heavy bleeding)
have high weights, so one of them alone makes the call urgent. The same
symptoms always give the same severity, however worried the caller is.
"""
import random

# key: (question asked by the dispatcher, short label, weight)
QUESTIONS = {
    "unconscious": ("Is the patient unconscious or not responding?", "unconscious", 7.5),
    "stroke":      ("Face drooping, arm weakness or slurred speech?", "stroke signs", 7.5),
    "chest_pain":  ("Chest pain or pressure?", "chest pain", 5.0),
    "bleeding":    ("Heavy bleeding that won't stop?", "heavy bleeding", 5.0),
    "breathing":   ("Difficulty breathing?", "breathing difficulty", 4.0),
    "burn":        ("Serious burn?", "serious burn", 4.0),
    "broken_bone": ("Broken bone or can't move a limb?", "broken bone", 3.5),
    "high_fever":  ("Fever of 39°C or more?", "high fever", 2.5),
    "dizzy":       ("Vomiting or dizzy?", "vomiting/dizzy", 1.0),
    "pain":        ("In pain?", "pain", 1.0),
    "small_wound": ("Small cut or bruise?", "small wound", 0.5),
}

# What the caller's answers look like for each type of emergency:
# (symptoms always present, {optional symptom: chance it is also present})
PROFILES = {
    "Heart attack":   (["chest_pain", "breathing"], {"pain": 0.6, "unconscious": 0.2, "dizzy": 0.3}),
    "Stroke":         (["stroke"], {"dizzy": 0.5, "unconscious": 0.2}),
    "Road accident":  (["bleeding", "broken_bone"], {"pain": 0.7, "unconscious": 0.3}),
    "Not breathing":  (["unconscious", "breathing"], {}),
    "Fracture":       (["broken_bone", "pain"], {"dizzy": 0.4, "small_wound": 0.4}),
    "Asthma attack":  (["breathing", "dizzy"], {"pain": 0.3}),
    "Bad burn":       (["burn", "pain"], {"small_wound": 0.5, "dizzy": 0.3}),
    "High fever":     (["high_fever", "dizzy", "pain"], {}),
    "Sprained ankle": (["pain"], {"dizzy": 0.2}),
    "Small cut":      (["small_wound", "pain"], {}),
    "Mild fever":     (["dizzy", "pain"], {}),
    "Dizziness":      (["dizzy"], {"pain": 0.4}),
}


def ask(name, rng=random):
    """Simulate the dispatcher's checklist for this emergency: returns the symptoms answered YES."""
    required, optional = PROFILES[name]
    return list(required) + [s for s, p in optional.items() if rng.random() < p]


def severity_from(symptoms):
    return min(10.0, sum(QUESTIONS[s][2] for s in symptoms))


def category(severity):
    """Category used for the patient's time limit and points."""
    if severity >= 7:
        return "critical"
    if severity >= 4:
        return "serious"
    return "minor"


def labels(symptoms):
    return [QUESTIONS[s][1] for s in symptoms]
