"""Build the multipartite entity graph — deliberately with benign density that looks like fraud.

THE LOAD-BEARING DECISION IN THIS FILE: if the benign graph is clean, every graph feature works
perfectly and the detection result is worthless. So we generate, on purpose:

*   families and households sharing devices,
*   gig-worker fan-in (many payers -> one receiver, entirely legitimately),
*   marketplace sellers with high payer diversity,
*   joint accounts co-spending on one instrument,
*   NRI remittance corridors with foreign inbound,
*   legitimate multi-token cardholders (one PAN, many merchant tokens).

Every one of those is a false-positive generator for a naive graph feature, and each maps to a
HARD-BENIGN cohort. A graph feature that only works because our benign population is a clean
bipartite graph has learned our code, not payments.
"""

from __future__ import annotations

import hashlib

import numpy as np

from core.config import Config, load_config
from core.rng import stream, substream
from sim.graph.entities import (
    Beneficiary,
    Cardholder,
    Device,
    Merchant,
    OnboardingBatch,
    RESERVED_BIN_PREFIXES,
    SYNTHETIC_VPA_HANDLES,
    Terminal,
    Token,
    World,
)

_DEVICE_MODELS: tuple[str, ...] = (
    "modelA-lite", "modelA-pro", "modelB-4", "modelB-5", "modelC-neo", "modelC-max",
    "modelD-1", "modelD-2", "modelE-tab", "modelF-budget", "modelG-flagship", "modelH-mid",
)
_DEVICE_OS: tuple[str, ...] = ("os-13", "os-14", "os-15", "os-16", "os-17")

_MCC_POOL: tuple[str, ...] = (
    "5411", "5812", "5541", "4111", "5912", "5732", "7011", "4900", "5651", "8220",
    "8062", "5944", "6011", "4814", "5399", "7999", "5977", "5691", "7372", "6540",
    "5300", "5814", "4121", "5045", "8999", "7230", "5992", "7311", "5993", "6051",
)

#: MCCs that read as quasi-cash / wallet-load. Exposure to these is an ATK-G4 observable.
_QUASI_CASH_MCC: frozenset[str] = frozenset({"6011", "6051", "6540", "4814"})

_ASN_POOL: tuple[str, ...] = tuple(f"AS{64500 + i}" for i in range(40))  # private-use ASN range


#: Share of the cardholder population assigned to the SEALED entity pool.
#:
#: The sealed-family holdout must be an ENTITY-LEVEL holdout. Withholding only the sealed attack rows
#: leaves those cardholders, devices and beneficiaries in the training set through their BENIGN
#: traffic, so the model learns their aggregates including the run-up to the attack. Partitioning the
#: population is the only structural fix, and `eval/leakage.py::entity_audit` fails the build if it
#: is not done.
#:
#: The sealed pool still receives ORDINARY BENIGN TRAFFIC, which matters: a pool whose every event
#: was an attack would be trivially separable, and that would be a worse leak than the one we fixed.
SEALED_POOL_SHARE = 0.18


def assign_pool(cardholder_id: str, share: float = SEALED_POOL_SHARE) -> str:
    """Deterministic pool assignment by hash, so it never depends on iteration order."""
    h = hashlib.blake2b(cardholder_id.encode("utf-8"), digest_size=4).digest()
    u = int.from_bytes(h, "big") / float(1 << 32)
    return "sealed" if u < share else "train"


def _zipf_weights(n: int, s: float) -> np.ndarray:
    """Normalised Zipf(s) weights over n items.

    Concentration is the first structure a real corpus shows, so merchants, MCCs and geohashes
    are drawn from an explicit tail with stated support sizes rather than uniformly. F5 checks
    the realised share of volume in the top-k against a band written in config/scenario.yaml
    BEFORE the plot.
    """
    ranks = np.arange(1, n + 1, dtype=np.float64)
    w = ranks ** (-float(s))
    return w / w.sum()


def _synth_pan(rng: np.random.Generator, bin_prefix: str) -> str:
    """A synthetic, deliberately NON-Luhn-valid card number on a reserved prefix.

    Two independent protections: the 999xxx prefix is not an assigned IIN range we are aware of,
    and the final digit is forced to break the Luhn checksum. A VAJRA PAN therefore cannot be
    presented anywhere as a card number even by accident.
    """
    body = "".join(str(int(d)) for d in rng.integers(0, 10, size=9))
    partial = bin_prefix + body
    # Luhn check digit for `partial`, then deliberately offset by 5 to guarantee invalidity.
    total = 0
    for i, ch in enumerate(reversed(partial)):
        d = int(ch)
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    valid_check = (10 - (total % 10)) % 10
    broken_check = (valid_check + 5) % 10
    return partial + str(broken_check)


def _synth_vpa(rng: np.random.Generator, seq: int) -> str:
    handle = SYNTHETIC_VPA_HANDLES[int(rng.integers(0, len(SYNTHETIC_VPA_HANDLES)))]
    return f"user{seq:07d}{handle}"


def build_world(preset: str | None = None, cfg: Config | None = None) -> World:
    """Deterministically construct the world for a preset."""
    cfg = cfg or load_config()
    p = cfg.preset(preset)
    gcfg = cfg.scenario["graph"]
    ccfg = cfg.scenario["concentration"]

    n_ch = int(p["cardholders"])
    n_mer = int(p["merchants"])
    days = int(p["days"])

    g = stream("sim.graph")
    world = World()

    # ---- institutions -----------------------------------------------------------------
    world.issuers = [f"ISS{i:03d}" for i in range(1, 9)]
    world.acquirers = [f"ACQ{i:03d}" for i in range(1, 13)]
    world.psps = [f"PSP{i:03d}" for i in range(1, 11)]
    world.mcc_pool = list(_MCC_POOL)

    # ---- geography --------------------------------------------------------------------
    geo_support = int(ccfg["geohash_support"])
    world.geo_cells = [f"gc{i:04d}" for i in range(geo_support)]
    geo_w = _zipf_weights(geo_support, float(ccfg["geohash_zipf_s"]))

    # ---- merchants, Zipf-ranked -------------------------------------------------------
    mcc_w = _zipf_weights(len(world.mcc_pool), float(ccfg["mcc_zipf_s"]))
    for rank in range(n_mer):
        mid = f"MID{rank:06d}"
        mcc = world.mcc_pool[int(g.choice(len(world.mcc_pool), p=mcc_w))]
        geo = world.geo_cells[int(g.choice(geo_support, p=geo_w))]
        onboard_day = int(g.integers(-720, max(1, days)))
        world.merchants[mid] = Merchant(
            id=mid,
            mcc=mcc,
            descriptor=f"ACCEPTOR {rank:05d} {geo.upper()}",
            acquirer_id=world.acquirers[int(g.integers(0, len(world.acquirers)))],
            onboard_day=onboard_day,
            geo_cell=geo,
            popularity_rank=rank,
            is_payfac_submerchant=bool(g.random() < 0.22),
        )
        n_terms = 1 + int(g.poisson(0.7))
        for t in range(n_terms):
            tid = f"TRM{rank:06d}{t:02d}"
            world.terminals[tid] = Terminal(
                id=tid,
                merchant_id=mid,
                # A minority of the estate still accepts fallback / no-CVM contactless. This is
                # the ATK-P1 target population and it must be a MINORITY, because blanket
                # blocking of fallback breaks acceptance for genuinely faulty terminals.
                accepts_fallback=bool(g.random() < 0.17),
                accepts_no_cvm_contactless=bool(g.random() < 0.86),
                geo_cell=geo,
            )
            world.merchants[mid].terminals.append(tid)

    # ONE merchant sampling pool, shared by every rail. A previous build minted merchant ids
    # ad hoc inside the UPI and clearing emitters, which pushed the pooled top-10 share to 0.9%
    # against an expected 22-42% band and made the concentration curve meaningless.
    world.merchant_sampling_order = [f"MID{r:06d}" for r in range(n_mer)]
    world.merchant_sampling_weights = _zipf_weights(n_mer, float(ccfg["merchant_zipf_s"])).tolist()

    # ---- cardholders, devices, tokens -------------------------------------------------
    dev_lambda = float(gcfg["devices_per_cardholder_lambda"])
    ben_lambda = float(gcfg["beneficiaries_per_cardholder_lambda"])
    dev_seq = 0
    tok_seq = 0

    for i in range(n_ch):
        cid = f"CH{i:07d}"
        cg = substream("sim.graph", cid)
        bin_prefix = RESERVED_BIN_PREFIXES[int(cg.integers(0, len(RESERVED_BIN_PREFIXES)))]
        geo = world.geo_cells[int(cg.choice(geo_support, p=geo_w))]
        # Account ages span years, so the entity-age strata (0-1d / 1-7d / 7-30d / 30d+) are
        # populated by construction rather than only by fresh attack entities.
        open_day = -int(cg.integers(0, 1500))
        ch = Cardholder(
            id=cid,
            pan_canonical=_synth_pan(cg, bin_prefix),
            bin_prefix=bin_prefix,
            vpa=_synth_vpa(cg, i),
            issuer_id=world.issuers[int(cg.integers(0, len(world.issuers)))],
            open_day=open_day,
            address_id=f"ADR{int(cg.integers(0, max(1, n_ch // 3))):07d}",
            sim_id=f"SIM{i:07d}",
            geo_cell=geo,
            credit_limit_inr=float(np.round(np.exp(cg.normal(11.2, 0.75)), -2)),
            kyc_tier="full_kyc",
            pool=assign_pool(cid),
        )

        n_dev = max(1, int(cg.poisson(dev_lambda)))
        for _ in range(n_dev):
            did = f"DEV{dev_seq:08d}"
            dev_seq += 1
            world.devices[did] = Device(
                id=did,
                model=_DEVICE_MODELS[int(cg.integers(0, len(_DEVICE_MODELS)))],
                os=_DEVICE_OS[int(cg.integers(0, len(_DEVICE_OS)))],
                first_seen_day=int(max(open_day, -int(cg.integers(0, 900)))),
                asn=_ASN_POOL[int(cg.integers(0, len(_ASN_POOL)))],
            )
            ch.devices.append(did)

        # Legitimate multi-token cardholders: one PAN tokenised at several merchants. Without
        # these, PAN-level token fan-out is a perfect fraud signal and ATK-T2 is trivial.
        if cg.random() < float(gcfg["multi_token_cardholder_share"]):
            for _ in range(1 + int(cg.integers(1, 5))):
                tid = f"TOK{tok_seq:08d}"
                tok_seq += 1
                world.tokens[tid] = Token(
                    id=tid,
                    pan_canonical=ch.pan_canonical,
                    requestor_id=f"TRQ{int(cg.integers(1, 40)):03d}",
                    assurance=str(cg.choice(["low", "medium", "high"], p=[0.18, 0.42, 0.40])),
                    provisioned_day=int(max(open_day, -int(cg.integers(0, 700)))),
                    device_id=ch.devices[int(cg.integers(0, len(ch.devices)))],
                )
                ch.tokens.append(tid)

        world.cardholders[cid] = ch

    # ---- benign density: device sharing, joint accounts, corridors ---------------------
    _wire_benign_density(world, g, gcfg)

    # ---- beneficiaries ----------------------------------------------------------------
    ben_seq = 0
    ch_ids = world.cardholder_ids()
    for cid in ch_ids:
        ch = world.cardholders[cid]
        cg = substream("sim.graph", f"ben:{cid}")
        n_ben = max(1, int(cg.poisson(ben_lambda)))
        for _ in range(n_ben):
            # Most payees are shared: a payer's beneficiary set overlaps with other payers'
            # (shops, billers, relatives). A private beneficiary per payer would make fan-in
            # degree a perfect mule signal.
            if ben_seq > 40 and cg.random() < 0.55:
                bid = f"BEN{int(cg.integers(0, ben_seq)):07d}"
                cand = world.beneficiaries.get(bid)
                # A beneficiary shared across pools would bridge the holdout boundary.
                if cand is not None and cand.pool == ch.pool:
                    ch.beneficiaries.append(bid)
                    continue
            bid = f"BEN{ben_seq:07d}"
            ben_seq += 1
            cat = str(
                cg.choice(
                    ["p2p_individual", "small_merchant", "biller", "giftcard", "wallet_load",
                     "payroll", "corporate_vendor"],
                    p=[0.40, 0.26, 0.14, 0.04, 0.06, 0.06, 0.04],
                )
            )
            world.beneficiaries[bid] = Beneficiary(
                id=bid,
                payee_vpa=f"payee{ben_seq:07d}{SYNTHETIC_VPA_HANDLES[int(cg.integers(0, len(SYNTHETIC_VPA_HANDLES)))]}",
                payee_name=f"PAYEE {ben_seq:06d}",
                psp_id=world.psps[int(cg.integers(0, len(world.psps)))],
                open_day=-int(cg.integers(0, 1200)),
                category=cat,
                geo_cell=ch.geo_cell,
                pool=ch.pool,
            )
            ch.beneficiaries.append(bid)

    # ---- benign onboarding batches ----------------------------------------------------
    _build_benign_onboarding(world, g, cfg, days)

    return world


def _wire_benign_density(world: World, g: np.random.Generator, gcfg: dict) -> None:
    """Add the legitimate structures that a naive graph feature would call fraud."""
    ch_ids = world.cardholder_ids()
    n = len(ch_ids)
    if n < 4:
        return

    def _tag(cid: str, tag: str) -> None:
        world.cardholders[cid].benign_tags.append(tag)

    # Families / households sharing a device.
    n_family = int(n * float(gcfg["device_sharing_family_share"]) / 3)
    for _ in range(max(0, n_family)):
        seed_cid = ch_ids[int(g.integers(0, n))]
        seed_pool = world.cardholders[seed_cid].pool
        # A device shared ACROSS pools would put the same aggregate on both sides of the holdout
        # boundary, which is precisely the leak the entity audit catches. Households do not span
        # the partition.
        candidates = [c for c in (ch_ids[int(g.integers(0, n))] for _ in range(6))
                      if world.cardholders[c].pool == seed_pool]
        members = [seed_cid] + candidates[: int(g.integers(1, 4))]
        shared = world.cardholders[seed_cid].devices[0]
        for cid in members:
            ch = world.cardholders[cid]
            if shared not in ch.devices:
                ch.devices.append(shared)
            _tag(cid, "household_shared_device")
            world.devices[shared].shared_with.append(cid)

    # Joint accounts: two cardholders on one instrument.
    n_joint = int(n * float(gcfg["joint_account_share"]) / 2)
    for _ in range(max(0, n_joint)):
        a, b = ch_ids[int(g.integers(0, n))], ch_ids[int(g.integers(0, n))]
        if a == b or world.cardholders[a].pool != world.cardholders[b].pool:
            continue
        world.cardholders[b].pan_canonical = world.cardholders[a].pan_canonical
        world.cardholders[b].bin_prefix = world.cardholders[a].bin_prefix
        _tag(a, "joint_account")
        _tag(b, "joint_account")

    # Gig-worker fan-in: one legitimate receiver paid by many unrelated payers. This is an
    # EXACT description of a mule, and it is why HARD-BENIGN-B exists at all.
    n_gig = int(n * float(gcfg["gig_worker_fanin_share"]))
    for i in range(max(0, n_gig)):
        cid = ch_ids[int(g.integers(0, n))]
        _tag(cid, "gig_worker_fanin")

    # Marketplace sellers: high payer diversity, legitimately.
    n_mkt = int(n * float(gcfg["marketplace_seller_share"]))
    for _ in range(max(0, n_mkt)):
        _tag(ch_ids[int(g.integers(0, n))], "marketplace_seller")

    # NRI remittance corridors: foreign inbound into an Indian account, legitimately.
    n_nri = int(n * float(gcfg["nri_corridor_share"]))
    for _ in range(max(0, n_nri)):
        _tag(ch_ids[int(g.integers(0, n))], "nri_corridor")

    # A small population of genuinely implausible device bundles that are NOT attacks: broken
    # SDKs, privacy browsers, corporate proxies. Without them, "impossible attribute
    # combination" is a perfect signal and ATK-G5 is free.
    dev_ids = list(world.devices.keys())
    for _ in range(max(1, len(dev_ids) // 300)):
        world.devices[dev_ids[int(g.integers(0, len(dev_ids)))]].cloned_bundle = True


def _build_benign_onboarding(world: World, g: np.random.Generator, cfg: Config, days: int) -> None:
    """Benign onboarding batches: the negative class for the cohort-statistics scorer."""
    ocfg = cfg.scenario["onboarding"]
    n_batches = int(ocfg["benign_batches"])
    lam = float(ocfg["benign_batch_size_lambda"])
    ben_ids = list(world.beneficiaries.keys())
    if not ben_ids:
        return
    for b in range(n_batches):
        bid = f"OB{b:05d}"
        day = int(g.integers(0, max(1, days)))
        size = max(1, int(g.poisson(lam)))
        picked = [ben_ids[int(g.integers(0, len(ben_ids)))] for _ in range(size)]
        batch = OnboardingBatch(
            id=bid,
            day=day,
            beneficiary_ids=picked,
            # A benign batch has HIGH device/OS entropy and diverse ASNs — the attack cohort's
            # signature is the collapse of exactly these, so the benign side must have them.
            device_models=[_DEVICE_MODELS[int(g.integers(0, len(_DEVICE_MODELS)))] for _ in picked],
            asns=[_ASN_POOL[int(g.integers(0, len(_ASN_POOL)))] for _ in picked],
            is_attack_cohort=False,
        )
        world.onboarding_batches[bid] = batch
        for pid in picked:
            world.beneficiaries[pid].onboarding_batch_id = bid


def quasi_cash_mccs() -> frozenset[str]:
    return _QUASI_CASH_MCC


def device_model_pool() -> tuple[str, ...]:
    return _DEVICE_MODELS


def asn_pool() -> tuple[str, ...]:
    return _ASN_POOL
