"""experience_memory — Tony's confidence-weighted, self-decaying rule lifecycle (T1.2 + T1.7).

The anti-catastrophic-forgetting core. A learned rule is not a permanent truth; it is a hypothesis
that must keep earning its place:

  quarantine ──(proves out on resolved outcomes)──▶ active ──(keeps helping)──▶ stays, confidence ↑
       ▲                                              │
       └──────────────(contradicted / goes stale)─────┴──▶ retired   (confidence ↓, anti-forgetting)

Confidence is a Beta-posterior mean over a "did following this help?" tally, with RECENCY DECAY so a
rule that stops being supported fades instead of lingering forever. New/changed rules start in
QUARANTINE and only promote once they clear a confidence + sample bar — the shadow-gate that stops a
false-rosy rule from ever biasing a live verdict (the audit incident). Retrieval returns the few most
relevant + recent ACTIVE rules (FinMem-style) instead of dumping the whole file into every verdict.

Pure logic over plain dicts; persistence is an optional fail-soft JSON layer. No live verdict is
changed by this module until something wires `relevant_rules` into the prompt — kept inert for now.
"""
import json
import logging
import math
import os
from datetime import date, datetime
from pathlib import Path

_log = logging.getLogger(__name__)

PROMOTE_THRESHOLD = float(os.environ.get("TONY_RULE_PROMOTE_CONF", "0.62"))
RETIRE_THRESHOLD = float(os.environ.get("TONY_RULE_RETIRE_CONF", "0.45"))
MIN_OBS = int(os.environ.get("TONY_RULE_MIN_OBS", "5"))
MAX_IDLE_DAYS = int(os.environ.get("TONY_RULE_MAX_IDLE_DAYS", "45"))
DECAY_HALF_LIFE_DAYS = float(os.environ.get("TONY_RULE_DECAY_HALF_LIFE", "30"))

RULES_FILE = Path(os.environ.get(
    "TONY_RULES_FILE",
    str(Path(__file__).parent.parent.parent / "vault" / "agents" / "market_research_worker" / "experience_rules.json"),
))


def _today() -> str:
    return str(date.today())


def _days_between(a: str, b: str) -> float:
    try:
        da = datetime.fromisoformat(str(a)[:10]).date()
        db = datetime.fromisoformat(str(b)[:10]).date()
        return abs((db - da).days)
    except (ValueError, TypeError):
        return 0.0


def new_rule(text: str, tags=None, *, direction: str = "win", regime=None, created=None) -> dict:
    """A fresh hypothesis. direction: 'win' = the tags predict a winner; 'avoid' = predict a loser."""
    created = created or _today()
    return {
        "text": text,
        "tags": list(tags or []),
        "direction": direction if direction in ("win", "avoid") else "win",
        "regime": regime,
        "state": "quarantine",
        "helped": 0.0,
        "hurt": 0.0,
        "created": created,
        "last_support": None,
        "last_updated": created,
    }


def observe(rule: dict, helped: bool, *, weight: float = 1.0, on_date=None) -> dict:
    """Record one outcome of following the rule. Mutates and returns the rule."""
    on_date = on_date or _today()
    if helped:
        rule["helped"] = float(rule.get("helped", 0.0)) + weight
    else:
        rule["hurt"] = float(rule.get("hurt", 0.0)) + weight
    rule["last_support"] = on_date
    rule["last_updated"] = on_date
    return rule


def _decay(rule: dict, as_of: str, half_life: float) -> float:
    """Recency multiplier in (0,1] applied to the evidence pseudo-counts."""
    last = rule.get("last_support") or rule.get("created")
    if not last or half_life <= 0:
        return 1.0
    return 0.5 ** (_days_between(last, as_of) / half_life)


def confidence(rule: dict, *, as_of=None, half_life: float = DECAY_HALF_LIFE_DAYS) -> float:
    """Beta-posterior mean of 'helped' vs 'hurt' with recency decay. Beta(1,1) prior => an unproven
    rule sits at 0.5; sustained help climbs it, contradiction drags it down, staleness pulls both
    counts toward the prior (the rule forgets) so confidence reverts to 0.5, not to a stale high."""
    as_of = as_of or _today()
    d = _decay(rule, as_of, half_life)
    h = float(rule.get("helped", 0.0)) * d
    m = float(rule.get("hurt", 0.0)) * d
    return (h + 1.0) / (h + m + 2.0)


def observations(rule: dict) -> float:
    return float(rule.get("helped", 0.0)) + float(rule.get("hurt", 0.0))


def update_state(rule: dict, *, as_of=None, min_obs: int = MIN_OBS,
                 promote: float = PROMOTE_THRESHOLD, retire: float = RETIRE_THRESHOLD,
                 max_idle_days: int = MAX_IDLE_DAYS) -> dict:
    """Apply the lifecycle transitions. Fail-closed on promotion: a rule promotes ONLY with enough
    observations AND confidence above the bar; it retires when contradicted OR gone stale."""
    as_of = as_of or _today()
    conf = confidence(rule, as_of=as_of)
    n = observations(rule)
    idle = _days_between(rule.get("last_support") or rule.get("created"), as_of)
    state = rule.get("state", "quarantine")

    if state == "retired":
        return rule
    if conf < retire and n >= min_obs:
        rule["state"] = "retired"  # contradicted by the evidence
    elif idle >= max_idle_days and rule.get("last_support"):
        rule["state"] = "retired"  # stale: anti catastrophic-forgetting
    elif state == "quarantine" and n >= min_obs and conf >= promote:
        rule["state"] = "active"
    elif state == "active" and conf < retire:
        rule["state"] = "retired"
    rule["last_updated"] = as_of
    return rule


def score_edge_rule(rule: dict, picks: list) -> dict:
    """Evaluate an edge rule against resolved picks: a pick carrying ALL the rule's tags is a test.
    direction 'win'  -> helped when the pick was right (a winner);
    direction 'avoid'-> helped when the pick was a loser (avoiding it would have helped)."""
    tags = set(rule.get("tags") or [])
    helped = hurt = 0
    for p in picks:
        ptags = set(p.get("evidence") or [])
        if not tags or not tags.issubset(ptags):
            continue
        winner = float(p.get("return_pct", 0) or 0) > 0
        good = winner if rule.get("direction") == "win" else (not winner)
        helped += int(good)
        hurt += int(not good)
    return {"helped": helped, "hurt": hurt, "n": helped + hurt}


def ingest(rules: list, picks: list, *, as_of=None) -> list:
    """Score every rule against a batch of newly-resolved picks, fold the result into its tally, and
    re-run the lifecycle. This is the shadow-gate tick: quarantined rules accumulate evidence here
    and promote only when they prove out — they never touch a live verdict while in quarantine."""
    as_of = as_of or _today()
    for rule in rules:
        s = score_edge_rule(rule, picks)
        if s["n"]:
            rule["helped"] = float(rule.get("helped", 0.0)) + s["helped"]
            rule["hurt"] = float(rule.get("hurt", 0.0)) + s["hurt"]
            rule["last_support"] = as_of
        update_state(rule, as_of=as_of)
    return rules


def relevant_rules(rules: list, *, tags=(), regime=None, k: int = 5, as_of=None) -> list:
    """Retrieve the top-k ACTIVE rules by relevance (tag overlap, regime match) + recency + confidence.
    Returns the rules to inject into a verdict — NOT the whole file (FinMem-style retrieval)."""
    as_of = as_of or _today()
    want = set(tags or [])
    scored = []
    for r in rules:
        if r.get("state") != "active":
            continue
        overlap = len(want & set(r.get("tags") or []))
        regime_match = 1 if (regime and r.get("regime") == regime) else 0
        recency = _decay(r, as_of, DECAY_HALF_LIFE_DAYS)
        conf = confidence(r, as_of=as_of)
        score = overlap * 2 + regime_match + recency + conf
        scored.append((score, r))
    scored.sort(key=lambda x: -x[0])
    return [r for _, r in scored[:k]]


def load_rules(path=None) -> list:
    path = Path(path or RULES_FILE)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        return []


def save_rules(rules: list, path=None) -> bool:
    path = Path(path or RULES_FILE)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rules, indent=2), encoding="utf-8")
        return True
    except OSError as exc:
        _log.warning("experience rules write failed: %s", exc)
        return False
