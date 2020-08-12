# Sample Deployment

This document describes the process to use the netpaca-optics monitoring in a
full stack that includes [InfluxDB](https://www.influxdata.com/) as the time
series database and [Grafana](https://grafana.com/) for dashboard visualization.

# Before You Begin

You will need a server with [Docker](https://docs.docker.com/get-docker/) and
[Docker-Compose](https://docs.docker.com/compose/install/) installed.  This
sample deployment uses docker-compose v3.7 format, so make sure you are using a
version that supports it.   At the time of this writing these versions were
used:

```shell
$ docker --version
Docker version 19.03.12, build 48a66213fe

$ docker-compose --version
docker-compose version 1.26.2, build eefe0d31
```

## Read over `netpaca.toml` Configuration File

Please read through the [netpaca.toml](netpaca.toml) configuration file.  You
will notice a number of envrioment varaibles being referenced.  The
[docker-compose.yml](docker-compose.yml) file will configure some of these.

## Credentials
The credentials are provided via a [credentials.env](credentials.env). You
**MUST** edit the credentials.env file and set the values to your actual
credentials.

## Inventory
You will need to provide an inventory CSV file that defines the `host`,
`ipaddr`, and `os_name` columns at a minimum.  You can add additional columns
and they will present as metric tag-values. For example, if you define a column
called `site`, then your metrics will include the tag `site=<value>`.

This sample creates two monitoring collector containers using a `role` column as
a filter. One container will monitor devices with role = "core" and the other
will monitor all other devices.  If you are using Netbox for example, this is
the device role value. If you do not have a role (or similar), or do not want to
create multiple collector containers based on role, then you do not need the
role column.

You are responsible for building this inventory file.  If you use Netbox, you
can find a python script
[here](https://github.com/netpaca/netpaca/blob/master/examples/netbox_inventory.py).
Otherwise you will need to DIY a script to generate the inventory file that you
want to use.

## Setup your InfluxDB instance

Install InfluxDB from DockerHub:

```
docker pull influxdb
```

The `netpaca.toml` file is configured to use a database with the name `optics`.  When you
setup your InfluxDB system, make sure you create this database.  You should also
set a database retention size so you do not fillup your server filesystem.

The InfluxDB command to set a 3 day retention, for example from within
the influxdb container, run the `influx` command, and then:

```
CREATE RETENTION POLICY three_days ON optics DURATION 72h REPLICATION 1 DEFAULT
```

## Setup your Grafana instance

Install the grafana docker instance from DockerHub:

```
docker pull grafana/grafana
```

Once you've logged into the system you will need to first configure a Datasource to use
the InfluxDB system.  Your settings should look like this:

![Grafana Data Source](grafana-influxdb-source.png)

The next step is to import the Dashboard from the [optics-dashboard.json](optics-dashboard.json) file.

## Customize the `docker-compose.yml` file

As noted above the docker compose file defines two collector services that use
the inventory column `role` to select core verse non-core devices.  You can edit
this file and customize the number of collector containers in a way that is
suitable for your environment. 

If you have a small inventory, you could just have one collector container, and you
would only have this service defined.

```yaml
  optics-all:
    << : *default-netpaca
    command: netpaca -C /etc/netpaca/netpaca.toml --log-level debug
```

# The `netpaca` command

The `netpaca` command is executed in the container image to perform the metric
collection and export process.  For details on this command, please refer to the
[netpaca](https://github.com/netpaca/netpaca) repository documents.
