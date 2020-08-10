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
This file contains the Interface DOM metrics collector supporing the Arista EOS
devices using the eAPI.
"""

# -----------------------------------------------------------------------------
# System Imports
# -----------------------------------------------------------------------------

from typing import Optional, List

# -----------------------------------------------------------------------------
# Public Imports
# -----------------------------------------------------------------------------

from netpaca import Metric, MetricTimestamp
from netpaca.collectors.executor import CollectorExecutor
from netpaca.drivers.eapi import Device

# -----------------------------------------------------------------------------
# Private Imports
# -----------------------------------------------------------------------------

import netpaca_optics as ifdom

# -----------------------------------------------------------------------------
# Exports (none)
# -----------------------------------------------------------------------------

__all__ = []


# -----------------------------------------------------------------------------
#
#                                 CODE BEGINS
#
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
#
#                     Register Arista Device to Colletor Type
#
# -----------------------------------------------------------------------------


@ifdom.register
async def start(
    device: Device, executor: CollectorExecutor, spec: ifdom.CollectorModel,
):
    """
    The IF DOM collector start coroutine for Arista EOS devices.  The purpose of this
    coroutine is to start the collector task.  Nothing fancy.

    Parameters
    ----------
    device:
        The device driver instance for the Arista device

    executor:
        The executor that is used to start one or more collector tasks. In this
        instance, there is only one collector task started per device.

    spec:
        The collector model instance that contains information about the
        collector; for example the collector configuration values.
    """
    device.log.info(f"{device.name}: Starting Arista EOS Interface DOM collection")
    executor.start(
        # required args
        spec=spec,
        coro=get_dom_metrics,
        device=device,
        # kwargs to collector coroutine:
        config=spec.config,
    )

# -----------------------------------------------------------------------------
#
#                             Collector Coroutine
#
# -----------------------------------------------------------------------------


async def get_dom_metrics(
    device: Device, timestamp: MetricTimestamp, config: ifdom.IFdomCollectorConfig
) -> Optional[List[Metric]]:
    """
    This coroutine will be executed as a asyncio Task on a periodic basis, the
    purpose is to collect data from the device and return the list of Interface
    DOM metrics.

    Parameters
    ----------
    device:
        The Arisa EOS device driver instance for this device.

    timestamp: MetricTimestamp
        The timestamp now in milliseconds

    config:
        The collector configuration options

    Returns
    -------
    Option list of Metic items.
    """

    # Execute the required "show" commands to colelct the interface information
    # needed to produce the Metrics

    if_dom_res, if_desc_res = await device.eapi.exec(
        ["show interfaces transceiver detail", "show interfaces description"]
    )

    if not if_dom_res.ok:
        device.log.error(
            f"{device.name}: failed to collect DOM information: {if_dom_res.output}, aborting."
        )
        return

    # both ifs_desc and ifs_dom are dict[<if_name>]

    ifs_desc = if_desc_res.output["interfaceDescriptions"]
    ifs_dom = if_dom_res.output["interfaces"]

    def __ok_process_if(if_name):

        # if the interface name does not exist in the interface description data
        # it likely means that the interface name is an unused transciever lane;
        # and if so then it would be the same data as the "first lane".  In this
        # case we don't need to record a duplicate metric.

        if not (if_desc := ifs_desc.get(if_name)):
            return False

        # examine the interface state vs. what the collector is configured to do.

        if_status = if_desc["interfaceStatus"]

        if if_status == "adminDown":
            return False

        # if the collector is configure to include interfaces even if the link
        # is not up, then return True now.

        if config.include_linkdown:
            return True

        # otherwise only allow interface that are in the link-up condition
        return if_status == "up"

    metrics = [
        measurement
        for if_name, if_dom_data in ifs_dom.items()
        if if_dom_data and __ok_process_if(if_name)
        for measurement in _make_if_metrics(
            ts=timestamp,
            if_name=if_name,
            if_dom_data=if_dom_data,
            if_desc=ifs_desc[if_name]["description"],
        )
    ]

    return metrics


# -----------------------------------------------------------------------------
#
#                            PRIVATE FUNCTIONS
#
# -----------------------------------------------------------------------------


def _make_if_metrics(
    ts: MetricTimestamp, if_name: str, if_dom_data: dict, if_desc: str
):
    """
    This function is used to create the specific IFdom Metrics for a specific
    interface.

    Parameters
    ----------
    ts: int
        The timestamp

    if_name:
        The interface name

    if_dom_data:
        The interface transceiver details as retrieved via the EAPI

    if_desc:
        The interface description value

    Yields
    ------
    A collection of IFdom specific Metrics.
    """

    c_tags = {
        "if_name": if_name,
        "if_desc": if_desc or "MISSING-DESCRIPTION",
        "media": if_dom_data["mediaType"],
    }

    m_txpow = ifdom.IFdomTxPowerMetric(value=if_dom_data["txPower"], tags=c_tags, ts=ts)
    m_rxpow = ifdom.IFdomRxPowerMetric(value=if_dom_data["rxPower"], tags=c_tags, ts=ts)
    m_temp = ifdom.IFdomTempMetric(value=if_dom_data["temperature"], tags=c_tags, ts=ts)
    m_volt = ifdom.IFdomVoltageMetric(value=if_dom_data["voltage"], tags=c_tags, ts=ts)

    yield from [m_txpow, m_rxpow, m_temp, m_volt]

    thresholds = if_dom_data["details"]

    yield ifdom.IFdomRxPowerStatusMetric(
        value=_threshold_outside(value=m_rxpow.value, thresholds=thresholds["rxPower"]),
        tags=c_tags,
        ts=ts,
    )

    yield ifdom.IFdomTxPowerStatusMetric(
        value=_threshold_outside(value=m_txpow.value, thresholds=thresholds["txPower"]),
        tags=c_tags,
        ts=ts,
    )

    yield ifdom.IFdomTempStatusMetric(
        value=_threshold_outside(
            value=m_temp.value, thresholds=thresholds["temperature"]
        ),
        tags=c_tags,
        ts=ts,
    )

    yield ifdom.IFdomVoltageStatusMetric(
        value=_threshold_outside(value=m_volt.value, thresholds=thresholds["voltage"]),
        tags=c_tags,
        ts=ts,
    )


def _threshold_outside(value: float, thresholds: dict) -> int:
    """
    This function determines a given metric "status" by comparing the IFdom value against
    the IFdom measurement; which are obtained from the interface transceiver details.
    The status is encoded as (0=ok, 1=warn, 2=alert)

    Parameters
    ----------
    value:
        The interface DOM value is always a floating point number

    thresholds:
        The dictionary containing the threshold values
    """
    if value <= thresholds["lowAlarm"] or value >= thresholds["highAlarm"]:
        return 2

    if value <= thresholds["lowWarn"] or value >= thresholds["highWarn"]:
        return 1

    return 0
