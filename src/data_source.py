"""
Torque data sources.

``TorqueDataSource`` is the interface the calibration sequence talks to.
``SimulatedTorqueSource`` produces a continuous virtual sensor signal.
``HardwareTorqueSource`` is an extension point for a real torque measuring
device; it deliberately contains no communication code and cannot be used to
acquire data in this version (Simulation Mode only).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import numpy as np

from .config import SimulationSettings

# Signal phases (section 7.2)
PHASE_ZERO = "Zero"
PHASE_INCREASING = "Torque Increasing"
PHASE_APPROACHING = "Approaching Target"
PHASE_APPLIED = "Torque Applied"
PHASE_CAPTURED = "Measurement Captured"
PHASE_RELEASING = "Torque Released"
PHASE_IDLE = "Idle"

ALL_PHASES = (PHASE_ZERO, PHASE_INCREASING, PHASE_APPROACHING, PHASE_APPLIED,
              PHASE_CAPTURED, PHASE_RELEASING)


@dataclass
class TorqueSample:
    t: float                    # s since the start of the current application
    torque: float               # N·m
    phase: str
    captured: Optional[float] = None  # set on the single capture sample


class TorqueDataSource(ABC):
    """Interface between the calibration sequence and a torque signal provider."""

    #: Human readable name shown in the GUI / logs
    name: str = "Torque data source"

    @property
    @abstractmethod
    def is_simulated(self) -> bool: ...

    @abstractmethod
    def connect(self) -> bool: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def reset_run(self) -> None:
        """Called once at the start of every calibration run."""

    @abstractmethod
    def begin_application(self, target: float) -> None:
        """Start one torque application (preload or measurement) towards target."""

    @abstractmethod
    def read_sample(self, dt: float) -> TorqueSample:
        """Return the next sample, ``dt`` seconds after the previous one."""

    @property
    @abstractmethod
    def application_done(self) -> bool: ...

    def abort_application(self) -> None:
        """Abort the current application (Stop button)."""

    def idle_sample(self, dt: float) -> float:
        """Signal between applications (unloaded transducer)."""
        return 0.0


class SimulatedTorqueSource(TorqueDataSource):
    """Virtual torque measuring device.

    The indicated value of each application is drawn from ``value_rng`` when the
    application begins; display noise uses a separate ``noise_rng``. Timing
    settings (ramp speed, hold time, speed factor, sampling interval) therefore
    never change the captured values: with the same seed, every speed preset
    yields identical results.
    """

    name = "Simulated Torque Measuring Device (virtual)"
    ZERO_TIME = 0.25            # s of zero signal before loading
    APPROACH_FRACTION = 0.88    # switch to slow approach at 88 % of target
    APPROACH_RATE = 0.30        # approach speed relative to ramp speed
    RELEASE_RATE = 2.0          # release speed relative to ramp speed

    def __init__(self, sim: SimulationSettings, resolution: float = 0.01):
        self.sim = sim
        self.resolution = resolution
        self._value_rng = np.random.default_rng(sim.seed)
        noise_seed = None if sim.seed is None else int(sim.seed) + 7919
        self._noise_rng = np.random.default_rng(noise_seed)
        self.bias_fraction = 0.0
        self._reset_application()

    # -- interface ---------------------------------------------------------
    @property
    def is_simulated(self) -> bool:
        return True

    def connect(self) -> bool:
        return True

    def disconnect(self) -> None:
        pass

    def reset_run(self) -> None:
        self._value_rng = np.random.default_rng(self.sim.seed)
        noise_seed = None if self.sim.seed is None else int(self.sim.seed) + 7919
        self._noise_rng = np.random.default_rng(noise_seed)
        b = self.sim.systematic_error_pct / 100.0
        self.bias_fraction = float(self._value_rng.uniform(-b, b)) if b > 0 else 0.0
        self._reset_application()

    def draw_indication(self, target: float) -> float:
        """Indicated value for one application (bias + random error), rounded."""
        r = self.sim.random_error_pct / 100.0
        rnd = float(self._value_rng.uniform(-r, r)) if r > 0 else 0.0
        value = target * (1.0 + self.bias_fraction + rnd)
        return self._round(value)

    def begin_application(self, target: float) -> None:
        self._reset_application()
        self.target = float(target)
        self.final_value = self.draw_indication(target)
        self.phase = PHASE_ZERO
        self.active = True

    def read_sample(self, dt: float) -> TorqueSample:
        if not self.active:
            return TorqueSample(self.t, 0.0, PHASE_IDLE)
        self.t += dt
        self.phase_t += dt
        ramp = self.sim.ramp_speed
        captured = None

        if self.phase == PHASE_ZERO:
            self.level = 0.0
            if self.phase_t >= self.ZERO_TIME:
                self._enter(PHASE_INCREASING)
        elif self.phase == PHASE_INCREASING:
            self.level += ramp * dt
            if self.level >= self.APPROACH_FRACTION * self.final_value:
                self.level = self.APPROACH_FRACTION * self.final_value
                self._enter(PHASE_APPROACHING)
        elif self.phase == PHASE_APPROACHING:
            self.level += ramp * self.APPROACH_RATE * dt
            if self.level >= self.final_value:
                self.level = self.final_value
                self._enter(PHASE_APPLIED)
        elif self.phase == PHASE_APPLIED:
            self.level = self.final_value
            if self.phase_t >= self.sim.hold_time:
                self._enter(PHASE_CAPTURED)
                captured = self.final_value
                self.captured_value = captured
                # The capture sample shows the filtered (captured) value exactly.
                return TorqueSample(self.t, self.final_value, PHASE_CAPTURED, captured)
        elif self.phase == PHASE_CAPTURED:
            self._enter(PHASE_RELEASING)
            self.level = max(0.0, self.level - ramp * self.RELEASE_RATE * dt)
        elif self.phase == PHASE_RELEASING:
            self.level = max(0.0, self.level - ramp * self.RELEASE_RATE * dt)
            if self.level <= 0.0:
                self.active = False
                self.done = True
                return TorqueSample(self.t, 0.0, PHASE_RELEASING)

        return TorqueSample(self.t, self._noisy(self.level), self.phase, captured)

    @property
    def application_done(self) -> bool:
        return self.done

    def abort_application(self) -> None:
        self._reset_application()

    def idle_sample(self, dt: float) -> float:
        return self._noisy(0.0)

    # -- helpers -----------------------------------------------------------
    def _reset_application(self):
        self.target = 0.0
        self.final_value = 0.0
        self.captured_value: Optional[float] = None
        self.level = 0.0
        self.t = 0.0
        self.phase_t = 0.0
        self.phase = PHASE_IDLE
        self.active = False
        self.done = False

    def _enter(self, phase: str):
        self.phase = phase
        self.phase_t = 0.0

    def _noisy(self, level: float) -> float:
        sd = self.sim.noise_level
        if sd <= 0:
            return round(level, 2)
        n = float(np.clip(self._noise_rng.normal(0.0, sd), -3 * sd, 3 * sd))
        if level <= 0.0:
            n = abs(n) * 0.3   # an unloaded transducer shows tiny positive drift
        return round(max(0.0, level + n), 2)

    def _round(self, value: float) -> float:
        res = self.resolution if self.resolution > 0 else 0.01
        return round(round(value / res) * res, 6)


class HardwareTorqueSource(TorqueDataSource):
    """Extension point for a real torque measuring device (not implemented).

    A future implementation would open a serial / USB / Ethernet connection
    (e.g. pyserial or a vendor SDK), stream readings in ``read_sample`` and
    detect the peak / capture event. In this version every acquisition method
    raises ``NotImplementedError`` and ``connect()`` returns ``False`` so the
    program can only run in Simulation Mode.
    """

    name = "Hardware Torque Measuring Device (interface only - not available)"

    def __init__(self, port: str = "", baudrate: int = 9600):
        self.port = port
        self.baudrate = baudrate

    @property
    def is_simulated(self) -> bool:
        return False

    def connect(self) -> bool:
        return False

    def disconnect(self) -> None:
        pass

    def reset_run(self) -> None:
        raise NotImplementedError("Hardware acquisition is not implemented (Simulation Mode only).")

    def begin_application(self, target: float) -> None:
        raise NotImplementedError("Hardware acquisition is not implemented (Simulation Mode only).")

    def read_sample(self, dt: float) -> TorqueSample:
        raise NotImplementedError("Hardware acquisition is not implemented (Simulation Mode only).")

    @property
    def application_done(self) -> bool:
        return False
