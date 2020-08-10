#  Copyright (C) 2020  Jeremy Schulman
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.


"""

This file contains the Interface Digital Optical Measurement (DOM) collection
definition.

"""

from typing import Optional
from pydantic.dataclasses import dataclass
from pydantic import conint, Field

from netpaca import Metric
from netpaca.collectors import CollectorType, CollectorConfigModel
from netpaca.config_model import CollectorModel  # noqa

# -----------------------------------------------------------------------------
#
#                              Collector Config
# -----------------------------------------------------------------------------
# Define the collector configuraiton options that the User can set in their
# configuration file.
# -----------------------------------------------------------------------------


class IFdomCollectorConfig(CollectorConfigModel):
    include_linkdown: Optional[bool] = Field(
        default=False,
        description="""
Controls whether or not to report on interfaces when the link is down.  When
False (default), only interfaces that are link-up are included.  When True, all
interfaces with optics installed will be included, even if they are link-down.
""",
    )


# -----------------------------------------------------------------------------
#
#                              Metrics
#
# -----------------------------------------------------------------------------
# This section defines the Metric types supported by the IF DOM collector
# -----------------------------------------------------------------------------

# the status values will be encoded in the metric to mean 0=OK, 1=WARN, 2=ALERT

_IFdomStatusValue = conint(ge=0, le=2)


@dataclass
class IFdomTempMetric(Metric):
    value: float
    name: str = "ifdom_temp"


@dataclass
class IFdomTempStatusMetric(Metric):
    value: _IFdomStatusValue
    name: str = "ifdom_temp_status"


@dataclass
class IFdomRxPowerMetric(Metric):
    value: float
    name: str = "ifdom_rxpower"


@dataclass
class IFdomRxPowerStatusMetric(Metric):
    value: _IFdomStatusValue
    name: str = "ifdom_rxpower_status"


@dataclass
class IFdomTxPowerMetric(Metric):
    value: float
    name: str = "ifdom_txpower"


@dataclass
class IFdomTxPowerStatusMetric(Metric):
    value: _IFdomStatusValue
    name: str = "ifdom_txpower_status"


@dataclass
class IFdomVoltageMetric(Metric):
    value: float
    name: str = "ifdom_voltage"


@dataclass
class IFdomVoltageStatusMetric(Metric):
    value: _IFdomStatusValue
    name: str = "ifdom_voltag_status"


# -----------------------------------------------------------------------------
#
#                              Collector Definition
#
# -----------------------------------------------------------------------------


class IFdomCollector(CollectorType):
    """
    This class defines the Interface DOM Collector specification.  This class is
    "registered" with the "netpaca.collectors" entry_point group via the
    `setup.py` file.  As a result of this registration, a User of the netpaca
    tool can setup their configuration file with the "use" statement.

    Examples (Configuration File)
    -----------------------------
    [collectors.ifdom]
        use = "netpaca.collectors:ifdom"
    """

    name = "interface-dom"
    description = """
Used to collect interface transceiver optic metrics values and status indicators
"""
    config = IFdomCollectorConfig

    metrics = [
        # float value metrics
        IFdomRxPowerMetric,
        IFdomTxPowerMetric,
        IFdomTempMetric,
        IFdomVoltageMetric,
        # enumerated status metrics
        IFdomRxPowerStatusMetric,
        IFdomTxPowerStatusMetric,
        IFdomTempStatusMetric,
        IFdomVoltageStatusMetric,
    ]


# create an "alias" variable so that the device specific collector packages
# can register their start functions.

register = IFdomCollector.start.register
