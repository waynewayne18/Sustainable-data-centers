"""Exclusions, normalisation and pillar scoring over raster layers.

Two distinct ideas, kept separate on purpose:

  exclusions  binary. The cell is unavailable, full stop. Flood zone 3,
              an SSSI. No score, removed from consideration.

  criteria    continuous. More or less desirable along some axis. Always
              normalised to 0-1 where 1 is better, with the raw array
              retained so any result can be traced back.
"""

import numpy as np

PILLARS = ("energy", "land", "water", "community")


class Model:
    """Accumulates exclusions and scored criteria over one Grid."""

    def __init__(self, grid):
        self.grid = grid
        self.exclusions = {}
        self.criteria = {}      # (pillar, name) -> normalised array
        self.raw = {}           # (pillar, name) -> pre-normalisation array

    # -- exclusions -------------------------------------------------

    def exclude(self, name, arr):
        """Register a boolean exclusion mask."""
        arr = np.asarray(arr).astype(bool)
        if arr.shape != self.grid.shape:
            raise ValueError(f"{name}: shape {arr.shape} != grid {self.grid.shape}")
        self.exclusions[name] = arr
        return self

    @property
    def excluded(self):
        out = np.zeros(self.grid.shape, dtype=bool)
        for a in self.exclusions.values():
            out |= a
        return out

    @property
    def available(self):
        """Land, and not excluded. The cells actually in play."""
        return self.grid.land & ~self.excluded

    # -- criteria ---------------------------------------------------

    def add(self, name, arr, pillar, higher_is_better):
        """Normalise a raw layer to 0-1 where 1 is always the good end.

        `higher_is_better` is mandatory and has no default, deliberately.
        An inverted layer produces a confident, completely wrong map and
        raises nothing anywhere. The direction is stated at every call
        site so it is visible in review rather than buried in a config.

        Normalisation uses only available cells, so excluded areas cannot
        stretch the range and flatten the contrast everywhere else.
        """
        if pillar not in PILLARS:
            raise ValueError(f"unknown pillar {pillar!r}")

        arr = np.asarray(arr, dtype="float32")
        if arr.shape != self.grid.shape:
            raise ValueError(f"{name}: shape {arr.shape} != grid {self.grid.shape}")

        sel = self.available & np.isfinite(arr)
        if not sel.any():
            raise ValueError(f"{name}: no finite values in available cells")

        lo, hi = float(arr[sel].min()), float(arr[sel].max())

        norm = self.grid.empty()
        if hi == lo:
            norm[sel] = 0.5
        else:
            scaled = (arr[sel] - lo) / (hi - lo)
            norm[sel] = scaled if higher_is_better else 1 - scaled

        self.raw[(pillar, name)] = arr
        self.criteria[(pillar, name)] = norm
        return self

    # -- scoring ----------------------------------------------------

    def pillar(self, name, weights=None):
        """Weighted mean of one pillar's criteria. NaN outside available."""
        items = [(n, a) for (p, n), a in self.criteria.items() if p == name]
        if not items:
            raise ValueError(f"no criteria registered for pillar {name!r}")

        weights = weights or {}
        stack = np.stack([a for _, a in items])
        w = np.array([weights.get(n, 1.0) for n, _ in items], dtype="float32")

        out = np.nansum(stack * w[:, None, None], axis=0) / w.sum()
        out[~self.available] = np.nan
        return out

    def score(self, pillar_weights=None):
        """Combine pillar scores into one surface.

        Pillars are combined last on purpose: each stays inspectable on
        its own, which is what lets you show trade-offs instead of one
        opaque ranking nobody can interrogate.
        """
        names = sorted({p for p, _ in self.criteria})
        if not names:
            raise ValueError("no criteria registered")

        pillar_weights = pillar_weights or {}
        stack = np.stack([self.pillar(p) for p in names])
        w = np.array([pillar_weights.get(p, 1.0) for p in names], dtype="float32")

        out = np.nansum(stack * w[:, None, None], axis=0) / w.sum()
        out[~self.available] = np.nan
        return out

    def report(self):
        excl = int((self.excluded & self.grid.land).sum())
        return (
            f"land {self.grid.n_land:,} cells | "
            f"excluded {excl:,} | available {int(self.available.sum()):,} | "
            f"criteria {len(self.criteria)} across {len({p for p,_ in self.criteria})} pillars"
        )
