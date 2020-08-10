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
Collector: Interface Optic Monitoring
Device: Cisco IOS via SSH

For details on the async SSH device driver, refer to the scrapli
project: https://github.com/carlmontanari/scrapli

"""
# -----------------------------------------------------------------------------
# System Imports
# -----------------------------------------------------------------------------

from typing import Optional, List
from itertools import chain

# -----------------------------------------------------------------------------
# Public Imports
# -----------------------------------------------------------------------------

from netpaca import Metric, MetricTimestamp
from netpaca.collectors.executor import CollectorExecutor
from netpaca import log
from netpaca.drivers.nxos_ssh import Device
from netpaca.drivers.nxos_ssh import (
    parse_show_interfaces_status,
    parse_show_interface_transceiver,
)

# -----------------------------------------------------------------------------
# Private Imports
# -----------------------------------------------------------------------------

import netpaca_optics as ifdom
from netpaca_optics.cisco_helpers import from_ifdomflag_to_status

# -----------------------------------------------------------------------------
# Exports (none)
# -----------------------------------------------------------------------------

__all__ = []


# -----------------------------------------------------------------------------
#
#                                CODE BEGINS
#
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
#
#                  Register Cisc Device SSH to Colletor Type
#
# -----------------------------------------------------------------------------


@ifdom.register
async def start(
    device: Device, executor: CollectorExecutor, spec: ifdom.CollectorModel
):
    """
    The IF DOM collector start coroutine for Cisco NXOS SSH devices.  The
    purpose of this coroutine is to start the collector task.  Nothing fancy.

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
    log.get_logger().info(
        f"{device.name}: Starting Cisco NXOS SSH Interface DOM collection"
    )
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

    timestamp:
        The current timestamp

    config:
        The collector configuration options

    Returns
    -------
    Option list of Metic items.
    """
    device.log.debug(f"{device.name}: Getting DOM information")

    # Execute the required "show" commands to colelct the interface information
    # needed to produce the Metrics

    cli_show_ifs_st, cli_show_ifs_optics = await device.driver.send_commands(
        ["show interface status", "show interface transceiver details"]
    )

    ifs_status_data = parse_show_interfaces_status(cli_show_ifs_st.result)
    ifs_dom_data = parse_show_interface_transceiver(cli_show_ifs_optics.result)

    if not ifs_dom_data:
        device.log.debug(f"{device.name}: no optics found")
        return

    def _allow_interface(if_status):
        if if_status == "disabled":
            # if administratively disabled skip this interface
            return False

        if config.include_linkdown:
            # if the collector config allows link-down interfaces,
            # then return True now
            return True

        return if_status == "connected"

    # find the set of interface names to create metrics.  This will be the
    # intersection of the interface names in the optics output (since this
    # output shows only avaialble interfaces with optics) and the set of
    # interfaces that match the link status criteria as identified in the
    # collector configuration.

    # first we need to normalize the Eth -> Ethernet so that the
    # lookup between the two dictionaries work.  We only care about
    # Ethernet ports.

    ifs_status_data = {
        if_name.replace("Eth", "Ethernet"): val
        for if_name, val in ifs_status_data.items()
        if if_name.startswith("Eth")
    }

    ok_ifs = set(
        if_name
        for if_name, if_st in ifs_status_data.items()
        if _allow_interface(if_st["if_status"])
    )

    metrics = (
        generate_if_metrics(
            if_name,
            if_st_data=ifs_status_data[if_name],
            if_dom_data=ifs_dom_data[if_name],
            ts=timestamp,
        )
        for if_name in ok_ifs & set(ifs_dom_data)
    )

    return list(chain.from_iterable(metrics))


def generate_if_metrics(if_name, if_st_data, if_dom_data, ts):
    """
    This generator creates the IFdom metrics for a specific interface.

    Parameters
    ----------
    if_name : str
        The interface name

    if_st_data
    if_dom_data
    ts

    Returns
    -------

    """
    # all metrics use the same tags:

    if_tags = dict(
        if_name=if_name, if_desc=if_st_data["if_desc"], media=if_st_data["if_type"]
    )

    # create the value metrics

    yield ifdom.IFdomRxPowerMetric(value=if_dom_data["rxpower"], tags=if_tags, ts=ts)
    yield ifdom.IFdomTxPowerMetric(value=if_dom_data["txpower"], tags=if_tags, ts=ts)
    yield ifdom.IFdomTempMetric(value=if_dom_data["temp"], tags=if_tags, ts=ts)
    yield ifdom.IFdomVoltageMetric(value=if_dom_data["voltage"], tags=if_tags, ts=ts)

    # create the status metrics

    yield ifdom.IFdomRxPowerStatusMetric(
        value=from_ifdomflag_to_status(if_dom_data["rxpower_flag"]), tags=if_tags, ts=ts
    )
    yield ifdom.IFdomTxPowerStatusMetric(
        value=from_ifdomflag_to_status(if_dom_data["txpower_flag"]), tags=if_tags, ts=ts
    )
    yield ifdom.IFdomTempStatusMetric(
        value=from_ifdomflag_to_status(if_dom_data["temp_flag"]), tags=if_tags, ts=ts
    )
    yield ifdom.IFdomVoltageStatusMetric(
        value=from_ifdomflag_to_status(if_dom_data["voltage_flag"]), tags=if_tags, ts=ts
    )
