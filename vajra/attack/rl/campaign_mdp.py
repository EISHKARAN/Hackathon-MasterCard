"""Level 2 of the hierarchical RL attacker: the Campaign MDP, solved with Watkins Q(λ).

Full specification in docs/RL_LOOP.md. Literature grounding in docs/RESEARCH.md §7 — the closest
prior work is Fraud-RLA (Lunghi et al., IEEE TDSC 2026).

WHY THIS LEVEL EXISTS AT ALL, stated as the honest null: A BANDIT CANNOT DO CREDIT ASSIGNMENT. In a
kill chain the reward is DELAYED — probing spends `probe_cost` now to raise the approval rate later;
extending mule dwell pays `lambda * elapsed_steps` now to avoid a beneficiary freeze later. A bandit
maximises immediate reward and will therefore NEVER learn to spend early. Temporal-difference learning
is exactly the tool for that, and `eval/control_arm` ships a `bandit_only` arm so the claim is
falsifiable: if the bandit matches the full agent, we report that this level bought nothing.

STATE, deliberately small and deliberately attacker-observable only:
    stage (4) x last_outcome (8) x budget_bucket (3) x heat (3) = 288 states
    x 11 tactics = 3,168 floats.
Tabular is a CHOICE: it converges inside the execution budget we actually have, and the LOOP screen
renders the learned policy as a readable table. A deep policy would do neither.

NO REWARD SHAPING FROM DEFENDER INTERNALS. We do not add a potential-based term from the detector's
score even though it would speed convergence a lot: that would smuggle defender-internal information
into the attacker through the reward channel and invalidate every "observes only what an attacker
observes" claim in this repo. The convergence cost is real and we pay it. There is deliberately no
config key for it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from attack.rl.observation import AttackerObservation
from core.paths import paths
from core.rng import stream

# ---------------------------------------------------------------------------------------
# The state and action spaces
# ---------------------------------------------------------------------------------------

STAGES: tuple[str, ...] = ("recon", "establish", "extract", "cashout")

OUTCOMES: tuple[str, ...] = (
    "none",
    "approve",
    "decline",
    "step_up",
    "credit_landed",
    "credit_held",
    "onward_blocked",
    "account_frozen",
)

BUDGET_BUCKETS: tuple[str, ...] = ("high", "mid", "low")

#: The attacker's OWN running estimate of its adverse-event rate. NOT a detector score — it is
#: computed from the attacker's own observations, which is the only thing it is allowed to use.
HEAT_LEVELS: tuple[str, ...] = ("cold", "warm", "hot")

TACTICS: tuple[str, ...] = (
    "probe",
    "escalate_amount",
    "deescalate_amount",
    "hug_threshold",
    "split_velocity",
    "rotate_entity",
    "inherit_trust",
    "switch_acquirer",
    "extend_dwell",
    "pad_payer_set",
    "cash_out",
)

#: Which EVASION morpheme licenses which tactics. The action mask is DERIVED from the grammar rather
#: than hand-listed per family, so the agent cannot learn a tactic its own composition does not
#: license — which would silently decouple the archive's behaviour axes from what the agent does.
TACTIC_BY_EVASION: dict[str, tuple[str, ...]] = {
    "velocity-splitting": ("split_velocity", "rotate_entity", "deescalate_amount"),
    "threshold-hugging": ("hug_threshold", "deescalate_amount"),
    "trust-inheritance": ("inherit_trust", "escalate_amount"),
    "graph-camouflage": ("extend_dwell", "pad_payer_set", "rotate_entity"),
    "label-attack": ("probe", "split_velocity", "cash_out"),
    "oracle-probing": ("probe", "escalate_amount", "switch_acquirer"),
    "low-visibility-rail": ("switch_acquirer", "rotate_entity"),
    "cohort-splitting": ("rotate_entity", "pad_payer_set", "split_velocity"),
}

#: Tactics every composition may use regardless of morpheme: you can always try to take the money.
UNIVERSAL_TACTICS: tuple[str, ...] = ("cash_out",)

#: Tactics that require a beneficiary leg to be meaningful.
BENEFICIARY_TACTICS: frozenset[str] = frozenset({"extend_dwell", "pad_payer_set"})


def state_index(stage: str, outcome: str, budget: str, heat: str) -> int:
    return (
        STAGES.index(stage) * len(OUTCOMES) * len(BUDGET_BUCKETS) * len(HEAT_LEVELS)
        + OUTCOMES.index(outcome) * len(BUDGET_BUCKETS) * len(HEAT_LEVELS)
        + BUDGET_BUCKETS.index(budget) * len(HEAT_LEVELS)
        + HEAT_LEVELS.index(heat)
    )


def n_states() -> int:
    return len(STAGES) * len(OUTCOMES) * len(BUDGET_BUCKETS) * len(HEAT_LEVELS)


def describe_state(idx: int) -> dict[str, str]:
    h = idx % len(HEAT_LEVELS)
    idx //= len(HEAT_LEVELS)
    b = idx % len(BUDGET_BUCKETS)
    idx //= len(BUDGET_BUCKETS)
    o = idx % len(OUTCOMES)
    idx //= len(OUTCOMES)
    return {
        "stage": STAGES[idx],
        "last_outcome": OUTCOMES[o],
        "budget": BUDGET_BUCKETS[b],
        "heat": HEAT_LEVELS[h],
    }


def outcome_from_observation(obs: AttackerObservation) -> str:
    """Map attacker-visible feedback to a state component. Severity order, worst wins."""
    if obs.account_frozen:
        return "account_frozen"
    if obs.onward_send_blocked:
        return "onward_blocked"
    if obs.credit_held:
        return "credit_held"
    if obs.stepped_up:
        return "step_up"
    if obs.declined:
        return "decline"
    if obs.credit_landed:
        return "credit_landed"
    if obs.approved:
        return "approve"
    return "none"


def budget_bucket(remaining: float, total: float) -> str:
    if total <= 0:
        return "low"
    frac = remaining / total
    return "high" if frac > 0.66 else ("mid" if frac > 0.33 else "low")


def heat_level(adverse_rate: float) -> str:
    return "cold" if adverse_rate < 0.15 else ("warm" if adverse_rate < 0.45 else "hot")


def allowed_tactics(evasion: str, *, has_beneficiary_leg: bool) -> tuple[str, ...]:
    """The action mask, DERIVED from the composition's EVASION morpheme."""
    base = set(TACTIC_BY_EVASION.get(evasion, ())) | set(UNIVERSAL_TACTICS)
    if not has_beneficiary_leg:
        base -= BENEFICIARY_TACTICS
    return tuple(t for t in TACTICS if t in base)


# ---------------------------------------------------------------------------------------
# Q(lambda)
# ---------------------------------------------------------------------------------------

@dataclass
class Transition:
    state: int
    action: int
    reward: float
    next_state: int
    terminal: bool
    #: The action mask at `next_state`, so a replayed transition cannot bootstrap through an action
    #: the composition never licensed.
    next_mask: tuple[int, ...] = ()


@dataclass
class QLambdaAgent:
    """Watkins Q(λ) with eligibility traces, ε-greedy exploration, and experience replay.

    Tabular by choice. See the module docstring.
    """

    alpha: float = 0.15
    gamma: float = 0.92
    trace_lambda: float = 0.70
    epsilon: float = 0.35
    epsilon_end: float = 0.05
    epsilon_decay_ticks: int = 12
    optimistic_init: float = 0.0
    replay_capacity: int = 200_000
    replay_batch_per_tick: int = 2_000
    seed_name: str = "attack.bandit"

    Q: np.ndarray = field(default_factory=lambda: np.zeros((n_states(), len(TACTICS))))
    E: np.ndarray = field(default_factory=lambda: np.zeros((n_states(), len(TACTICS))))
    replay: list[Transition] = field(default_factory=list)
    n_updates: int = 0
    tick: int = 0

    @classmethod
    def from_config(cls) -> "QLambdaAgent":
        import yaml

        with (paths.config / "rl.yaml").open("r", encoding="utf-8") as fh:
            doc = yaml.safe_load(fh) or {}
        m = dict(doc.get("campaign_mdp") or {})
        agent = cls(
            alpha=float(m.get("alpha", 0.15)),
            gamma=float(m.get("gamma", 0.92)),
            trace_lambda=float(m.get("trace_lambda", 0.70)),
            epsilon=float(m.get("epsilon_start", 0.35)),
            epsilon_end=float(m.get("epsilon_end", 0.05)),
            epsilon_decay_ticks=int(m.get("epsilon_decay_ticks", 12)),
            optimistic_init=float(m.get("optimistic_init", 0.0)),
            replay_capacity=int(m.get("replay_capacity", 200_000)),
            replay_batch_per_tick=int(m.get("replay_batch_per_tick", 2_000)),
        )
        if agent.optimistic_init:
            agent.Q[:] = agent.optimistic_init
        return agent

    # ---- acting ----------------------------------------------------------------------
    def epsilon_now(self) -> float:
        if self.epsilon_decay_ticks <= 0:
            return self.epsilon_end
        frac = min(1.0, self.tick / float(self.epsilon_decay_ticks))
        return float(self.epsilon + (self.epsilon_end - self.epsilon) * frac)

    def act(self, state: int, mask: Sequence[int], rng: np.random.Generator | None = None) -> int:
        """ε-greedy over the MASKED action set."""
        r = rng if rng is not None else stream(self.seed_name)
        m = list(mask)
        if not m:
            raise ValueError(
                "the action mask is empty: no tactic is licensed by this composition's EVASION "
                "morpheme. That means the mask derivation and the grammar have diverged."
            )
        if r.random() < self.epsilon_now():
            return int(m[int(r.integers(0, len(m)))])
        q = self.Q[state]
        best = max(m, key=lambda a: float(q[a]))
        return int(best)

    def greedy(self, state: int, mask: Sequence[int]) -> int:
        q = self.Q[state]
        return int(max(list(mask), key=lambda a: float(q[a])))

    # ---- learning --------------------------------------------------------------------
    def update(self, tr: Transition) -> float:
        """One Q(λ) update. Returns the TD error, so a caller can log convergence."""
        q_sa = float(self.Q[tr.state, tr.action])
        if tr.terminal:
            target = tr.reward
        else:
            mask = list(tr.next_mask) or list(range(len(TACTICS)))
            q_next = float(max(self.Q[tr.next_state, a] for a in mask))
            target = tr.reward + self.gamma * q_next
        delta = target - q_sa

        self.E[tr.state, tr.action] += 1.0
        self.Q += self.alpha * delta * self.E
        # Watkins: on an EXPLORATORY (non-greedy) action, cut the traces. Otherwise credit flows
        # backwards through a step the policy would not have taken, and the value estimate becomes a
        # statement about a policy that does not exist.
        mask = list(tr.next_mask) or list(range(len(TACTICS)))
        greedy_a = int(max(mask, key=lambda a: float(self.Q[tr.next_state, a])))
        if tr.terminal or tr.action != greedy_a:
            self.E[:] = 0.0
        else:
            self.E *= self.gamma * self.trace_lambda
        self.n_updates += 1
        return float(delta)

    def remember(self, transitions: Iterable[Transition]) -> None:
        self.replay.extend(transitions)
        if len(self.replay) > self.replay_capacity:
            self.replay = self.replay[-self.replay_capacity :]

    def replay_batch(self, rng: np.random.Generator | None = None) -> dict[str, float]:
        """Replay a sample of past transitions.

        WHY REPLAY IS NECESSARY, not an optimisation: with a >=25-evaluations-per-cell budget, each
        cell's agent would otherwise learn from its own handful of episodes only. Replay is what makes
        that budget sufficient.
        """
        if not self.replay:
            return {"n_replayed": 0.0, "mean_abs_td_error": 0.0}
        r = rng if rng is not None else stream("attack.bandit")
        k = int(min(self.replay_batch_per_tick, len(self.replay)))
        idx = r.integers(0, len(self.replay), size=k)
        errs = []
        self.E[:] = 0.0
        for i in idx:
            errs.append(abs(self.update(self.replay[int(i)])))
        self.E[:] = 0.0
        return {
            "n_replayed": float(k),
            "mean_abs_td_error": float(np.mean(errs)) if errs else 0.0,
        }

    def end_tick(self) -> None:
        self.tick += 1
        self.E[:] = 0.0

    # ---- inspection ------------------------------------------------------------------
    def policy_table(self, *, top_n: int = 20) -> list[dict[str, Any]]:
        """The learned policy, RENDERED AS A READABLE TABLE.

        This is why the agent is tabular: the LOOP screen shows a judge exactly what the attacker
        learned to do in which situation. A deep policy would be a black box on both sides of the
        loop, and half the point of the loop is that it is auditable.
        """
        visited = np.flatnonzero(np.abs(self.Q).sum(axis=1) > 1e-9)
        rows: list[dict[str, Any]] = []
        for s in visited:
            q = self.Q[s]
            a = int(np.argmax(q))
            rows.append(
                {
                    **describe_state(int(s)),
                    "best_tactic": TACTICS[a],
                    "q_value": float(q[a]),
                    "q_spread": float(q.max() - q.min()),
                }
            )
        rows.sort(key=lambda r: -abs(r["q_value"]))
        return rows[:top_n]

    def diagnostics(self) -> dict[str, Any]:
        visited = int((np.abs(self.Q).sum(axis=1) > 1e-9).sum())
        return {
            "algorithm": "Watkins Q(lambda), tabular, eligibility traces",
            "n_states": n_states(),
            "n_actions": len(TACTICS),
            "q_table_size": int(self.Q.size),
            "n_states_visited": visited,
            "state_coverage": visited / max(1, n_states()),
            "n_updates": self.n_updates,
            "epsilon_now": self.epsilon_now(),
            "tick": self.tick,
            "replay_size": len(self.replay),
            "hyperparameters": {
                "alpha": self.alpha, "gamma": self.gamma, "lambda": self.trace_lambda,
            },
            "reward_shaping": (
                "NONE from defender internals, deliberately. A potential-based term from the "
                "detector's score would speed convergence and would also smuggle defender-internal "
                "information into the attacker through the reward channel."
            ),
            "why_not_a_bandit": (
                "A bandit maximises IMMEDIATE reward, so it never learns to spend on probing or dwell "
                "that pays off later. eval/control_arm ships a bandit-only arm; if it matches this "
                "agent we report that the MDP level bought nothing."
            ),
        }

    # ---- persistence -----------------------------------------------------------------
    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path.with_suffix(".npz"), Q=self.Q)
        path.with_suffix(".json").write_text(
            json.dumps(
                {
                    "diagnostics": self.diagnostics(),
                    "policy_table": self.policy_table(top_n=60),
                    "tick": self.tick,
                    "n_updates": self.n_updates,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path) -> "QLambdaAgent":
        agent = cls.from_config()
        npz = path.with_suffix(".npz")
        if npz.exists():
            agent.Q = np.load(npz)["Q"]
        meta = path.with_suffix(".json")
        if meta.exists():
            d = json.loads(meta.read_text(encoding="utf-8"))
            agent.tick = int(d.get("tick", 0))
            agent.n_updates = int(d.get("n_updates", 0))
        return agent


# ---------------------------------------------------------------------------------------
# Reward
# ---------------------------------------------------------------------------------------

def step_reward(
    obs: AttackerObservation,
    *,
    probes: int,
    mules: int,
    credentials: int,
    elapsed_steps: int,
    costs: Mapping[str, Any],
    ruin_fired: bool,
    unrecovered_spend_inr: float,
) -> tuple[float, dict[str, float]]:
    """The per-step reward: the INCREMENT in attacker P&L.

    THREE PROPERTIES THAT ARE DECISIONS, NOT DETAILS:

    1.  `value_retained`, NOT gross debits. Value is what is still in attacker control after
        auto-release and clawback. Crediting gross debits would reward money GATE-B already took
        back, while the agent simultaneously observes `account_frozen` — an incoherent reward that
        teaches the agent that being frozen is fine.
    2.  Ruin is a PENALTY proportional to unrecovered spend, plus a flag. Not a deletion.
    3.  Every cost constant is an ASSUMPTION, and `make sensitivity` sweeps them. Their absolute
        level is unknown; what we defend is their relative ordering.
    """
    probe_cost = float(costs.get("probe_cost", 0.0)) * float(probes)
    mule_cost = float(costs.get("mule_burn", 0.0)) * float(mules)
    cred_cost = float(costs.get("credential_cost", 0.0)) * float(credentials)
    time_cost = float(costs.get("lambda_step_cost", 0.0)) * float(elapsed_steps)
    penalty = 0.0
    if ruin_fired:
        penalty = float(costs.get("ruin_penalty_multiplier", 1.5)) * float(unrecovered_spend_inr)
    reward = float(obs.value_retained_inr) - (probe_cost + mule_cost + cred_cost + time_cost) - penalty
    return reward, {
        "value_retained_inr": float(obs.value_retained_inr),
        "probe_cost": probe_cost,
        "mule_cost": mule_cost,
        "credential_cost": cred_cost,
        "time_cost": time_cost,
        "ruin_penalty": penalty,
    }


def ruin_decision(
    *,
    detection_latency_hours: float,
    break_even_hours: float,
    trigger: str,
) -> tuple[bool, str]:
    """Was the campaign ruined? An EXPLICIT COMPARISON IN SIM CLOCK, on a NAMED observable event.

    "Detected" is not a usable word: at a 0.1% base rate any multi-transaction campaign draws some
    declines, so a decline-based trigger fires either always or never. So ruin requires (a) a named
    observable event — a beneficiary freeze, blocked onward send, or an analyst-confirmed fraud
    disposition — AND (b) that it arrived BEFORE break-even.
    """
    if not trigger:
        return False, ""
    if detection_latency_hours < 0 or break_even_hours < 0:
        return False, ""
    if detection_latency_hours < break_even_hours:
        return True, trigger
    return False, f"{trigger} after break-even, not ruin"
