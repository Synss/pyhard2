#!/usr/bin/env python
# This file is part of
# pyhard2 - An object-oriented framework for the development of
# instrument drivers
# Copyright (C) 2012, Mathias Laurin, GPLv3

"""
pyhard2.pid
===========

Proportional-integral-derivative control algorithm and PID ramping
helper functions.

Notes
-----
See `pyfuzzy <http://pyfuzzy.sourceforge.net/>`_ for fuzzy logic in Python.

"""


import time


class PidController(object):
    """A software PID controller.

    Parameters
    ----------
    proportional, integral, derivative : float
        `Kp`, `Kd`, `Ki` in the ideal form.
    vmin, vmax : float
        Minimum and maximum values for the output.

    Attributes
    ----------
    setpoint : float
    proportional, integral, derivative : float
        Ideal form, as gains.
    proportional, integral_time, derivative_time : float
        Standard form, as times.
    anti_windup : float
        Soft integrator, 1.0 to disable, recommended range [0.005-0.25].
    proportional_on_pv : bool
        Computes proportional gain based on the process variable.

    Methods
    -------
    reset()
        Reset time now.
    compute_output(measure[, now])
        Compute output `now`.

    Notes
    -----
    Ideal or standard PID form.

    The controller follows either

    .. math::
        \\text{ideal form}& u(t) =& K_p e(t) + K_i \\int_0^t e(t)dt
            + K_d \\frac{d}{dt}e(t), \\\\
        \\text{standard form}& u(t) =& K_p \\left(
            e(t) + \\frac{1}{T_i} \\int_0^t e(t)dt
            + T_d \\frac{d}{dt} e(t) \\right)

    References
    ----------
    - http://en.wikipedia.org/wiki/PID_controller
    - http://www.mstarlabs.com/apeng/techniques/pidsoftw.html
    """

    def __init__(self,
                 proportional=2.0, integral_time=0.0, derivative_time=0.0,
                 vmin=0.0, vmax=100.0):
        self.proportional = proportional
        self.integral_time = integral_time
        self.derivative_time = derivative_time
        self.vmin = vmin
        self.vmax = vmax
        self.setpoint = 0.0
        self.anti_windup = 0.25
        self.proportional_on_pv = False

        self._old_input = 0.0
        self._integral = 0.0
        self._prev_time = time.time()

    def __repr__(self):
        return "".join(
            ["%s(",
             "proportional=%r, integral_time=%r, derivative_time=%r, ",
             "vmin=%r, vmax=%r)"]) % \
                (self.__class__.__name__,
                 self.proportional, self.integral_time, self.derivative_time,
                 self.vmin, self.vmax)

    @property
    def integral_time(self):
        """Integral time (s) :math:`T_i = K_p/K_i`."""
        return (0.0 if self.integral == 0.0
                else self.proportional / self.integral)

    @integral_time.setter
    def integral_time(self, integral_time):
        self.integral = (0.0 if integral_time == 0.0
                         else self.proportional / integral_time)

    @property
    def derivative_time(self):
        """Derivative time (s) :math:`T_d = K_d / K_p`."""
        return self.derivative / self.proportional

    @derivative_time.setter
    def derivative_time(self, derivative_time):
        self.derivative = self.proportional * derivative_time

    def reset(self):
        """Reset time to now."""
        self._prev_time = time.time()

    def compute_output(self, measure, now=None):
        """Compute next output.

        Parameters
        ----------
        measure : float
            Process value.
        now : float, optional
            Time in s, time.time() is called if value is omitted.

        Returns
        -------
        output : float
        """
        error = self.setpoint - measure
        if now is None:
            now = time.time()
        dt = now - self._prev_time

        p = self.proportional * (measure if self.proportional_on_pv else error)
        if dt > 0.0:
            i = self.integral * self._integral * dt
            d = self.derivative * (measure - self._old_input) / dt
        else:
            i = d = 0.0

        self._prev_time = now
        self._old_input = measure

        u = p + i + d
        if u > self.vmax:
            u = self.vmax
            self._integral += self.anti_windup * error
        elif u < self.vmin:
            u = self.vmin
            self._integral += self.anti_windup * error
        else:
            self._integral += error
        return u


class Profile(object):
    """Make profile ramps.
    
    Parameters
    ----------
    profile : iterable
        A list of (time, setpoint) tuples, time in s.

    Notes
    -----
    A :math:`t_0` point is created by default.  Overwrite by adding a
    value at :math:`t_0 = 0` in the profile.
    """

    TIME, SP = 0, 1

    def __init__(self, profile):
        profile.sort()
        # make sure we have a starting point
        profile.insert(0, (-0.001, 0.0))
        self.profile = profile
        self.start_time = 0.0

    def __repr__(self):
        return "%s(profile=%r)" % (self.__class__.__name__, self.profile)

    def setpoint(self, now):
        """Return setpoint value.

        Parameters
        ----------
        now : float
            In seconds.

        Returns
        -------
        setpoint : float
            Value at time `now`.
        """
        if now >= self.profile[-1][Profile.TIME]:
            return self.profile[-1][Profile.SP]
        # find current element in profile // binary search would be + efficient
        index = len(filter(lambda point:
                           point[Profile.TIME] <= now, self.profile))
        point, next_point = self.profile[index - 1], self.profile[index]
        return (point[Profile.SP] + 
                (next_point[Profile.SP] - point[Profile.SP]) /
                (next_point[Profile.TIME] - point[Profile.TIME]) *
                (now - point[Profile.TIME]))

    def ramp(self):
        """Generate setpoint values.

        Returns
        -------
        setpoint : generator

        Examples
        --------
        >>> from time import sleep
        >>> profile = Profile([(5, 10.0), (10, -20.0), (15, -20)])
        >>> for setpoint in profile.ramp():
                print setpoint
                sleep(2)
        """
        self.start_time = time.time()
        elapsed_time = 0.0
        while elapsed_time < self.profile[-1][Profile.TIME]:
            yield self.setpoint(time.time() - self.start_time)
            elapsed_time = time.time() - self.start_time
        else:
            raise StopIteration


def test_ramp():
    """Test ramping algorithms."""
    profile = Profile([(5, 10.0), (10, -20.0), (15, -20), (20, -7)])
    times = np.arange(0, 21, 0.1)
    fig = plt.figure()
    ax = fig.add_subplot(111)
    l, = ax.plot(times, [profile.setpoint(time) for time in times])
    plt.show()

def test_system():
    """Test PID algorithm."""
    import scipy.signal as sig
    # transfer function in s-space describes sys
    tf = sig.tf2ss([10], [100, 10])
    times = np.arange(1, 200, 5.0)
    #step = 1 * np.ones(len(times))
    # initialize PID
    pid = PidController(2.0, 10.0, 0.0)
    pid.anti_windup = 0.2
    pid.vmin, pid.vmax = -200.0, 200.0
    pid.setpoint = 50.0
    pid._prev_time = 0.0
    sysout = [0.0]
    pidout = [0.0]
    real_time = [0.0]
    for time in times:
        real_time.append(time)
        pidout.append(pid.compute_output(sysout[-1], real_time[-1]))
        t, sysout, xout = sig.lsim(tf, pidout, real_time)

    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.plot(real_time, sysout, 'r', real_time, pidout, 'b--')
    plt.show()


if __name__ == "__main__":
    import matplotlib.pyplot as plt
    import numpy as np
    test_system()


