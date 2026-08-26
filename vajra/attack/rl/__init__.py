"""The hierarchical RL attacker. Full specification in docs/RL_LOOP.md.

    LEVEL 3  MAP-Elites archive        automatic curriculum over an INTERPRETABLE behaviour space
             (archive/map_elites.py)   -- not RL, and calling it RL would be wrong
    LEVEL 2  Campaign MDP, Q(lambda)   credit assignment across the kill chain
             (campaign_mdp.py)
    LEVEL 1  Thompson bandit           parametric choice inside a tactic, discounted for drift
             (bandit.py)
    +        LLM Composer              semantic variation operator, ONE call per tick
             (attack/composer.py)

The constraint that makes any of it meaningful is `observation.py`: the agent observes EXACTLY what a
real adversary observes and nothing else.
"""

from attack.rl.bandit import Arm, Context, ThompsonBandit, context_for
from attack.rl.campaign_mdp import (
    BUDGET_BUCKETS,
    HEAT_LEVELS,
    OUTCOMES,
    STAGES,
    TACTICS,
    QLambdaAgent,
    Transition,
    allowed_tactics,
    budget_bucket,
    describe_state,
    heat_level,
    n_states,
    outcome_from_observation,
    ruin_decision,
    state_index,
    step_reward,
)
from attack.rl.observation import AttackerObservation, assert_observability_contract

__all__ = [
    "Arm", "Context", "ThompsonBandit", "context_for",
    "QLambdaAgent", "Transition", "AttackerObservation", "assert_observability_contract",
    "STAGES", "OUTCOMES", "BUDGET_BUCKETS", "HEAT_LEVELS", "TACTICS",
    "allowed_tactics", "budget_bucket", "heat_level", "n_states", "state_index",
    "describe_state", "outcome_from_observation", "step_reward", "ruin_decision",
]
