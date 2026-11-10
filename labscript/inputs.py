#####################################################################
#                                                                   #
# /inputs.py                                                        #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of the program labscript, in the labscript      #
# suite (see http://labscriptsuite.org), and is licensed under the  #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################

"""Classes for device channels that are inputs"""

import math

from .base import Device
from .utils import LabscriptError, set_passed_properties


class AnalogIn(Device):
    """Analog Input for use with all devices that have an analog input."""
    description = "Analog Input"

    @set_passed_properties(property_names={})
    def __init__(
        self, name, parent_device, connection, scale_factor=1.0, units="Volts", **kwargs
    ):
        """Instantiates an Analog Input.

        Args:
            name (str): python variable to assign this input to.
            parent_device (:obj:`IntermediateDevice`): Device input is connected to.
            scale_factor (float, optional): Factor to scale the recorded values by.
            units (str, optional): Units of the input.
            **kwargs: Keyword arguments passed to :func:`Device.__init__`.
        """
        self.acquisitions = []
        self.scale_factor = scale_factor
        self.units=units
        Device.__init__(self, name, parent_device, connection, **kwargs)

    def acquire(
        self, label, start_time, end_time, wait_label="", scale_factor=None, units=None
    ):
        """Command an acquisition for this input.

        Args:
            label (str): Unique label for the acquisition. Used to identify the saved trace.
            start_time (float): Time, in seconds, when the acquisition should start.
            end_time (float): Time, in seconds, when the acquisition should end.
            wait_label (str, optional): 
            scale_factor (float): Factor to scale the saved values by.
            units: Units of the input, consistent with the unit conversion class.

        Returns:
            float: Duration of the acquistion, equivalent to `end_time - start_time`.
        """
        if scale_factor is None:
            scale_factor = self.scale_factor
        if units is None:
            units = self.units
        self.acquisitions.append(
            {
                "start_time": start_time,
                "end_time": end_time,
                "label": label,
                "wait_label": wait_label,
                "scale_factor": scale_factor,
                "units": units,
            }
        )
        return end_time - start_time


class Counter(Device):
    """Counter Input for edge counting over timed gate windows."""
    description = "Counter Input"

    manual_acquisition_defaults = {
        "enabled": True,
        "sample_clock": "connection_table",
        "rate": 10.0,
        "buffer_size": 1024,
        "polling_interval": 0.1,
    }

    def __init__(self, name, parent_device, connection, edge_terminal, gate_terminal=None, sample_terminal=None, *, monitor=None, **kwargs):
        """Counter device

        Args:
            name (str): python variable to assign this device to.
            parent_device (:obj:`IntermediateDevice`): Device this counter is attached to. (e.g. NI_***)
            connection (str): Connection name on the parent device. (e.g. /NI_***/ctr0)
            edge_terminal (str): Terminal on the parent device for edge counting. (e.g. PFI0)
            gate_terminal (str): Terminal on the parent device for gate. High for enabled. (e.g. PFI1)
            sample_terminal (str): Terminal on the parent device for accepting ticks for sampling. High at tick. (e.g. PFI2)
            monitor: Optional ChannelMonitor for manual and buffered streaming.
            **kwargs: Passed to :func:`Device.__init__`.
        """
        from pythonlib.online_monitor import ChannelMonitor
        if monitor is not None and not isinstance(monitor, ChannelMonitor):
            raise LabscriptError("Counter monitor must be a ChannelMonitor")
        self.monitor = monitor.to_dict() if monitor is not None else None
        self.acquisitions = []
        self.edge_terminal = edge_terminal
        self.gate_terminal = gate_terminal
        self.sample_terminal = sample_terminal
        Device.__init__(self, name, parent_device, connection, **kwargs)
        self.set_property("monitor", self.monitor, "connection_table_properties")

    def acquire(self, label, max_sampling_rate=None, buffer_size=None, polling_interval=None):
        """Schedule a counter acquisition

        Args:
            label (str): Unique label for the acquisition.
            max_sampling_rate (float): Estimated maximum sampling rate in Hz. Only necessary in sampling mode.
            buffer_size (int): Length of buffer storing sampled data. Only necessary in sampling mode.
            polling_interval (float): Polling interval to read data from buffer in seconds. Only necessary in sampling mode.
        """

        self.acquisitions.append(
            {
                "label": label,
                "max_sampling_rate": max_sampling_rate,
                "buffer_size": buffer_size,
                "polling_interval": polling_interval,
            }
        )

        return

    def configure_manual_acquisition(
        self,
        *,
        enabled=True,
        sample_clock="connection_table",
        rate=10.0,
        buffer_size=1024,
        polling_interval=0.1,
        **legacy,
    ):
        """Configure manual acquisition timing; sinks belong in Counter(monitor=...).

        ``sample_clock`` is ``connection_table`` for an external sample terminal,
        or ``ctr<N>`` to generate a sample clock at ``rate`` Hz. ``buffer_size``
        sets the read buffer length; ``polling_interval`` is the read interval in
        seconds (overridden by FastMonitor.poll_s when configured, minimum 20 ms).
        ``enabled=False`` hides the channel's manual controls.
        """
        if legacy:
            raise LabscriptError(
                "Legacy manual counter settings are unsupported: %s. "
                "Use Counter(monitor=ChannelMonitor(...)); apply averaging and "
                "multiplication at the receiver." % ", ".join(sorted(legacy))
            )
        sample_clock = str(sample_clock).strip()
        sample_clock_lower = sample_clock.lower()
        if sample_clock_lower == "connection_table":
            sample_clock = "connection_table"
        else:
            try:
                prefix = sample_clock_lower[:3]
                ctr = int(sample_clock_lower[3:])
            except (TypeError, ValueError):
                raise LabscriptError(
                    "Counter manual acquisition sample_clock must be "
                    "'connection_table' or 'ctr<N>', not %r" % sample_clock
                )
            if prefix != "ctr":
                raise LabscriptError(
                    "Counter manual acquisition sample_clock must be "
                    "'connection_table' or 'ctr<N>', not %r" % sample_clock
                )
            if ctr < 0:
                raise LabscriptError(
                    "Counter manual acquisition sample_clock must not be negative"
                )
            sample_clock = "ctr%d" % ctr

        try:
            rate = float(rate)
            polling_interval = float(polling_interval)
        except (TypeError, ValueError):
            raise LabscriptError(
                "Counter manual acquisition rate and polling_interval must be numeric"
            )
        if not math.isfinite(rate) or rate <= 0:
            raise LabscriptError(
                "Counter manual acquisition rate must be a finite positive number"
            )
        if not math.isfinite(polling_interval) or polling_interval < 0.02:
            raise LabscriptError(
                "Counter manual acquisition polling_interval must be at least 0.02 s"
            )
        try:
            buffer_size = int(buffer_size)
        except (TypeError, ValueError):
            raise LabscriptError("Counter buffer_size must be an integer")
        if buffer_size < 1:
            raise LabscriptError("Counter buffer_size must be at least 1")

        config = {
            "enabled": bool(enabled),
            "sample_clock": sample_clock,
            "rate": rate,
            "buffer_size": buffer_size,
            "polling_interval": polling_interval,
        }
        self.set_property(
            "manual_acquisition",
            config,
            "connection_table_properties",
            overwrite=True,
        )
        return config
