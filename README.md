# A10 Networks OpenStack Octavia Driver

## Table of Contents
1. [Overview](#Overview)

2. [System Requirements](#System-Requirements)

3. [Setup and Installation](#Setup-and-Installation)

    1. [For use with vThunders](#For-use-with-vThunders)

    2. [For use with hardware devices](#For-use-with-hardware-devices)

4. [Setting Object Defaults](#Setting-Object-Defaults)

5. [Contribution](#Contribution)

6. [Issues and Inquiries](#Issues-and-Inquiries)

# Overview

**This is currently in beta stage with limited support.**

A10 Networks Octavia Driver for Thunder, vThunder and AX Series Appliances 
supported releases:

* OpenStack: Stein Release
* Octavia version: >=4.1.1, <5.0.0.0rc1 (Stein versions)
* ACOS versions: ACOS 4.1.4 GR1 P2
* AXAPI versions: 3.0

**Note: Following Configurations should be done as an OpenStack admin user**

# Installation

This guide assumes that Openstack has already been deployed and Octavia has already been configured.

## Install from PyPi

```shell
pip install a10-octavia
```

# Setup And Configuration

## Enable A10 provider driver in Octavia config file

Add `a10` driver to the `enabled_provider_drivers` list in the `api-settings` section of `/etc/octavia/octavia.conf`.
Change `default_provider_driver` to `a10`

```shell
enabled_provider_drivers = a10: 'The A10 Octavia driver.'

default_provider_driver = a10
```

## Restart Openstack Octavia services

#### For devstack development environment
`sudo systemctl restart devstack@o-api.service devstack@o-cw.service devstack@o-hk.service devstack@o-hm.service`

#### For other OpenStack environments
Use `systemctl` or similar function to restart Octavia controller and health services.

### Add A10 Octavia config file
Create a `a10-octavia.conf` file at /etc/a10/ location with proper permissions including following configuration sections.

## For use with vThunders

### Upload vThunder image and create a nova flavor for amphorae devices

Upload a vThunder image (QCOW2) and create nova flavor with required resources.
Minimum recommendation for vThunder instance is 8 vCPUs, 8GB RAM and 30GB disk.

```shell
openstack image create --disk-format qcow2 --container-format bare --public --file vThunder410.qcow2 vThunder.qcow2

openstack flavor create --vcpu 8 --ram 8196 --disk 30 vThunder_flavor
```

Note down the `image ID` and `flavor ID` of created resources.

### vThunder sample config
```shell
[VTHUNDER]
DEFAULT_VTHUNDER_USERNAME = "admin"
DEFAULT_VTHUNDER_PASSWORD = "a10"
DEFAULT_AXAPI_VERSION = "30"

[a10_controller_worker]
amp_image_owner_id = <admin_project_id>
amp_secgroup_list = <security_group_to_apply>
amp_flavor_id = <flavor_id_for_amphorae>
amp_boot_network_list = <netword_id_to_boot_amphorae_in_admin_project>
amp_ssh_key_name = <ssh_key_for_amphorae>
network_driver = a10_octavia_neutron_driver
workers = 2
amp_active_retries = 100
amp_active_wait_sec = 2
amp_image_id = <vthunder_amphorae_image_id>
loadbalancer_topology = <SINGLE or ACTIVE_STANDBY>

[a10_health_manager]
udp_server_ip_address = <server_ip_address_for_health_monitor>
bind_port = 5550
bind_ip = <controller_ip_configured_to_listen_for_udp_health_packets>
heartbeat_interval = 5
heartbeat_key = insecure
heartbeat_timeout = 90
health_check_interval = 3
failover_timeout = 600
health_check_timeout = 3
health_check_max_retries = 5
```

#### Housekeeper sample config
```shell
[a10_house_keeping]
load_balancer_expiry_age = 3600
amphorae_expiry_age = 3600
```

## Update security group to access vThunder AXAPIs

Update security group `lb-mgmt-sec-grp` (or custom security group configured in a10-octavia.conf file) and allow `TCP PORT 80` and `TCP PORT 443` ingress traffic to allow AXAPI communication with vThunder instances. Also update security group `lb-health-mgr-sec-grp` to allow `UDP PORT 5550` ingress traffic to allow UDP packets from vThunder instances.

## For use with hardware devices

### Hardware sample config

```shell
[a10_controller_worker]
amp_secgroup_list = <security_group_to_apply> 
amp_boot_network_list = <netword_id_to_boot_amphorae_in_admin_project>
amp_ssh_key_name = <ssh_key_for_amphorae>
network_driver = a10_octavia_neutron_driver
workers = 2
amp_active_retries = 100
amp_active_wait_sec = 2
loadbalancer_topology = SINGLE

[RACK_VTHUNDER]
devices = """[
                    {
                     "project_id":"<project_id>",
                     "ip_address":"10.0.0.4",
                     "undercloud":"True",
                     "username":"<username>",
                     "password":"<password>",
                     "device_name":"<device_name>",
                     "axapi_version":"30"
                     },
                     {
                     "project_id":"<another_project_id>",
                     "ip_address":"10.0.0.5",
                     "undercloud":"True",
                     "username":"<username>",
                     "password":"<password>",
                     "device_name":"<device_name>",
                     "axapi_version":"30",
                     }
             ]
       """
```


## Run database migrations

from `a10-octavia/a10_octavia/db/migration` folder run 

```shell
alembic upgrade head
```

If versioning error occurs, delete all entries in the `alembic_version` table from `octavia` database and re-run the above command.

```shell
mysql> use octavia;
mysql> DELETE FROM alembic_version;
```

*Note: Octavia verisons less than 4.1.1 have the `alembic_migrations` table instead*

## STEP 7: Restart Related Octavia Services

#### For devstack development environment
`sudo systemctl restart devstack@o-api.service devstack@o-cw.service devstack@o-hk.service devstack@o-hm.service`

#### For other OpenStack environments
Use `systemctl` or similar function to restart Octavia controller and health services. 

## STEP 8: [FOR ROCKY AND STEIN RELEASE] Create a10-octavia services
```
This will install systemd services with names - `a10-controller-worker`, `a10-health-manager.service` and `a10-housekeeper-manager.service`. Make sure the services are up and running.
You can start/stop the services using systemctl/service commands.
You may check logs of the services using `journalctl` commands. For example:
```shell
journalctl -af --unit a10-controller-worker.service
journalctl -af --unit a10-health-manager.service
journalctl -af --unit a10-housekeeper-manager.service
```

# Setting Object Defaults

# Contribution

### Fork the a10-octavia repository

[How To Fork](https://help.github.com/en/github/getting-started-with-github/fork-a-repo)

### Clone the repo from your fork

```shell
git clone https://git@github.com:<username>/a10-octavia.git
```

### Checkout to a new branch

```shell
git checkout -b feature/<branch_name>
```

### Register the A10 provider driver and controller worker plugin

```shell
sudo pip install -e /path/to/a10-octavia
```

# Issues and Inquiries
For all issues, please send an email to support@a10networks.com 

For general inquiries, please send an email to opensource@a10networks.com
