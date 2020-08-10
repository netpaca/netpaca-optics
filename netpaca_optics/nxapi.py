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
Device: Cisco NX-OS via NXAPI
"""

# -----------------------------------------------------------------------------
# System Imports
# -----------------------------------------------------------------------------

from typing import Optional, List

# -----------------------------------------------------------------------------
# Public Imports
# -----------------------------------------------------------------------------

from lxml.etree import Element

from netpaca import Metric, MetricTimestamp
from netpaca.collectors.executor import CollectorExecutor
from netpaca.drivers.nxapi import Device

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
#                                   CODE BEGINS
#
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
#
#                 Register Cisco Device NXAPI to Colletor Type
#
# -----------------------------------------------------------------------------


@ifdom.register
async def start(
    device: Device, executor: CollectorExecutor, spec: ifdom.CollectorModel
):
    """
    The IF DOM collector start coroutine for Cisco NX-API enabled devices.  The
    purpose of this coroutine is to start the collector task.  Nothing fancy.

    Parameters
    ----------
    device:
        The device driver instance for the Cisco device

    executor:
        The executor that is used to start one or more collector tasks. In this
        instance, there is only one collector task started per device.

    spec:
        The collector model instance that contains information about the
        collector; for example the collector configuration values.
    """
    device.log.info(f"{device.name}: Starting Cisco NXAPI Interface DOM collection")

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
        The Cisco device driver instance for this device.

    timestamp: MetricTimestamp
        The current timestamp

    config:
        The collector configuration options

    Returns
    -------
    Option list of Metic items.
    """

    device.log.debug(f"{device.name}: Process DOM metrics")

    ifs_dom_res, ifs_status_res = await device.nxapi.exec(
        ["show interface transceiver details", "show interface status"]
    )

    # find all interfaces that have a transceiver present, and the transceiver
    # has a temperature value - guard against non-optical transceivers.

    ifs_dom_data = [
        _row_to_dict(ele)
        for ele in ifs_dom_res.output.xpath(
            './/ROW_interface[sfp="present" and temperature]'
        )
    ]

    def _allow_interface(if_status):
        if if_status == "disabled":
            # if administratively disabled skip this interface
            return False

        if config.include_linkdown:
            # if the collector config allows link-down interfaces,
            # then return True now
            return True

        return if_status == "connected"

    # noinspection PyArgumentList
    def generate_metrics():

        for if_dom_item in ifs_dom_data:
            if_name = if_dom_item["interface"]

            # for the given interface, if it not in a connected state (up), then do not report

            # if_status = ifs_status_res.output.xpath(
            #     f'TABLE_interface/ROW_interface[interface="{if_name}" and state!="disabled"]'
            # )

            if_status = ifs_status_res.output.xpath(
                f'TABLE_interface/ROW_interface[interface="{if_name}"]'
            )[0]

            if not _allow_interface(if_status.findtext("state")):
                continue

            # obtain the interface description value; handle case if there is none configured.

            if_desc = (if_status.findtext("name") or "").strip()
            if_media = (if_dom_item["type"] or if_dom_item["partnum"]).strip()

            # all of the metrics will share the same interface tags

            if_tags = {
                "if_name": if_name,
                "if_desc": if_desc,
                "media": if_media,
            }

            for nx_field, metric_cls in _METRIC_VALUE_MAP.items():
                if metric_value := if_dom_item.get(nx_field):
                    yield metric_cls(value=metric_value, tags=if_tags, ts=timestamp)

            for nx_field, metric_cls in _METRIC_STATUS_MAP.items():
                if metric_value := if_dom_item.get(nx_field):
                    yield metric_cls(
                        value=from_ifdomflag_to_status(metric_value),
                        tags=if_tags,
                        ts=timestamp,
                    )

    return list(generate_metrics())


# -----------------------------------------------------------------------------
#
#                            PRIVATE FUNCTIONS
#
# -----------------------------------------------------------------------------

_METRIC_VALUE_MAP = {
    "voltage": ifdom.IFdomVoltageMetric,
    "tx_pwr": ifdom.IFdomTxPowerMetric,
    "rx_pwr": ifdom.IFdomRxPowerMetric,
    "temperature": ifdom.IFdomTempMetric,
}


_METRIC_STATUS_MAP = {
    "rx_pwr_flag": ifdom.IFdomRxPowerStatusMetric,
    "tx_pwr_flag": ifdom.IFdomTxPowerStatusMetric,
    "volt_flag": ifdom.IFdomVoltageStatusMetric,
    "temp_flag": ifdom.IFdomTempStatusMetric,
}


def _row_to_dict(row: Element):
    """ helper function to convert XML elements into a dict obj. """
    return {ele.tag: ele.text for ele in row.iterchildren()}
