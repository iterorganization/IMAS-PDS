"""
MUSCLE3 TORAX actor whose poloidal flux follows the received equilibrium.

The stock `torax_muscle3.torax_actor` takes only TORAX's geometry from a received
equilibrium. With `numerics.evolve_current = False` TORAX then holds psi at
`profile_conditions.psi`, which the stock actor fills from the F_INIT core_profiles (the
inverse_convergence TORAX psi in evolutive_controller): q, magnetic shear, bootstrap, ohmic
power, j_total (hence FF') and the core_profiles grid.psi on which NICE evo_rd maps TORAX's
pressure, conductivity and j_non_inductive onto its own flux surfaces would follow the
inverse instead of NICE. This runner overwrites `profile_conditions.psi` with the received
equilibrium's profiles_1d.psi versus rho_tor_norm after every receive (F_INIT: every valid
slice; S: the last valid slice just received, held until the next one), so the current
diffusion is done by the peer alone.

On S the profile goes in as `(rho_norm, values)`, i.e. constant in time under the fixed key
0.0: TimeVaryingArray flattens its `{time: (rho, values)}` dict into the step function's
pytree, so a new time key on every exchange would retrace and recompile TORAX every step.

Setting `psi_from_equilibrium` (bool, default False): off, this is the stock actor. Use it
with `numerics.evolve_current = False` in the TORAX config; with evolve_current = True
only TORAX's initial psi changes.

A power-only 'ec' core_sources source is handled by the stock actor (TORAX-MUSCLE3 39a33db).
"""

import logging
from typing import Optional

import numpy as np
from imas.ids_toplevel import IDSToplevel
from torax.experimental import RuntimeParamsProvider
from torax_muscle3.torax_actor import ToraxMuscleRunner
from torax_muscle3.utils import get_setting_optional

logger = logging.getLogger()

RHO_NORM = np.linspace(0.0, 1.0, 101)
"""Common rho_tor_norm grid for the equilibrium psi (TORAX re-interpolates linearly onto its
own, which is accurate on this spacing)."""

PsiInput = tuple[np.ndarray, ...]


def valid_slices(equilibrium: IDSToplevel):
    """(time, time_slice) of the slices not flagged output_flag = -1."""
    flags = np.asarray(equilibrium.code.output_flag)
    for k, ts in enumerate(equilibrium.time_slice):
        if k < flags.size and flags[k] == -1:
            continue
        yield (float(equilibrium.time[k]) if k < len(equilibrium.time) else float(ts.time)), ts


def psi_from_equilibrium(equilibrium: IDSToplevel) -> Optional[PsiInput]:
    """`profile_conditions.psi` input (times, rho_norm, values) from an equilibrium IDS.

    Slices flagged output_flag = -1 or without a usable psi(rho_tor_norm) are skipped;
    returns None if none is left. psi stays in the IDS convention, as the stock actor
    already passes core_profiles grid.psi (profile_conditions_from_IMAS).
    """
    times, values = [], []
    for t, ts in valid_slices(equilibrium):
        rho = np.asarray(ts.profiles_1d.rho_tor_norm, dtype=float)
        psi = np.asarray(ts.profiles_1d.psi, dtype=float)
        if (
            rho.size < 2
            or rho.size != psi.size
            or not (np.all(np.isfinite(psi)) and np.all(np.abs(psi) < 1e30))
            or not np.all(np.diff(rho) > 0)
        ):
            continue
        times.append(t)
        # Linear in rho^2, not rho: psi - psi_axis ~ rho^2 near the axis, where NICE's grid
        # (uniform in psi_N) is coarse in rho (0, 0.066, 0.094, ...). Linear in rho there
        # gave TORAX a spurious j_total bump (+26 % at rho 0.06, dip at 0.02) and a wrong
        # q(rho < 0.1), i.e. extra central ohmic heating (105084 run of 2026-10-12 21:44).
        x = rho / rho[-1]
        values.append(np.interp(RHO_NORM**2, x**2, psi))
    if not times:
        return None
    return np.asarray(times), RHO_NORM, np.asarray(values)


class PsiFromEquilibriumRunner(ToraxMuscleRunner):
    """ToraxMuscleRunner that also sets profile_conditions.psi from each received equilibrium."""

    use_equilibrium_psi: bool = False
    """Value of the `psi_from_equilibrium` setting, read in run_prep"""
    psi_input: Optional[PsiInput] = None
    """profile_conditions.psi built from the last valid equilibrium received"""
    psi_received: bool = False
    """Whether the receive in progress delivered a new psi_input"""

    def run_prep(self, torax_config=None) -> None:
        super().run_prep(torax_config)
        self.use_equilibrium_psi = bool(
            get_setting_optional(self.instance, "psi_from_equilibrium", False)
        )
        if self.use_equilibrium_psi:
            evolve_current = self.torax_config.numerics.evolve_current
            logger.info(
                "psi_from_equilibrium: TORAX psi follows the received equilibrium "
                "(numerics.evolve_current = %s)",
                evolve_current,
            )
            if evolve_current:
                logger.warning(
                    "psi_from_equilibrium with numerics.evolve_current = True: only the "
                    "initial psi follows the equilibrium, TORAX still evolves its current"
                )

    def receive_ids_data(self, ids_name: str, port_name: str):
        ids_data = super().receive_ids_data(ids_name, port_name)
        if ids_name == "equilibrium" and ids_data is not None and self.use_equilibrium_psi:
            psi = psi_from_equilibrium(ids_data[0])
            if psi is None:
                logger.warning(
                    "equilibrium_%s: no usable profiles_1d.psi at t=%g, keeping the previous psi",
                    port_name,
                    ids_data[1],
                )
            else:
                # F_INIT: time-dependent over every slice; S: the last slice, constant
                # under a fixed key (see the module docstring).
                self.psi_input = psi if port_name == "in_f" else (psi[1], psi[2][-1])
                self.psi_received = True
        return ids_data

    def receive_equilibrium(self, port_name: str) -> None:
        self.psi_received = False
        super().receive_equilibrium(port_name)
        if self.psi_received:
            self.apply_equilibrium_psi()

    def receive_core_profiles(self, port_name: str) -> None:
        # The stock receive rebuilds profile_conditions from core_profiles (psi included)
        # and then the runtime params provider: put the equilibrium psi back on top.
        provider = self.runtime_params_provider
        super().receive_core_profiles(port_name)
        if self.runtime_params_provider is not provider:
            self.apply_equilibrium_psi()

    def apply_equilibrium_psi(self) -> None:
        if not self.use_equilibrium_psi or self.psi_input is None:
            return
        self.torax_config.update_fields({"profile_conditions.psi": self.psi_input})
        self.runtime_params_provider = RuntimeParamsProvider.from_config(self.torax_config)


def main() -> None:
    """Create the TORAX instance and enter the submodel execution loop"""
    logger.info("Starting TORAX actor (psi from the received equilibrium)")
    PsiFromEquilibriumRunner().run_sim()


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    main()
