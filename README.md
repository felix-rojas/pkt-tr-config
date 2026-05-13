# pkt-tr-config

An automated tool that creates **Cisco Packet Tracer** base configurations, calculates **VLSM** (Variable Length Subnet Masking) requirements, and automatically assigns IP addresses to devices across a topology to prevent conflicts.

---

## Quick Start (CSV Topology)

The recommended way to generate configurations is using the minimal parameter-based CSV format. The script parses the CSV, calculates the necessary subnets in memory, sequentially assigns management IPs and default gateways to your switches, and outputs the final Cisco IOS commands.

Run the generator using:

```bash
python main.py topology_input.csv

```

### CSV Format Overview

The CSV uses a flexible `Category, Name/ID, Parameters...` layout. Parameters are defined as `Key=Value` pairs and can be provided in any order.

#### Example Topology (topology_input.csv)

```csv
# Format: Category, Name/LinkType, Params (Key=Value)...
Global, Base, BaseIP=140.7.32.0/19, AutoStatic=False, OSPF=True, DhcpEnabled=True, DnsEnabled=True, DnsServer=8.8.8.8, Commands=packet_tracer_commands.txt, Answers=subnetting.csv, Banner=Unauthorized access is strictly prohibited.

# Routers
Router, RA, Fast=0, Gigabit=1, Serial=1
Router, RB, Fast=0, Gigabit=2, Serial=2
Router, RC, Fast=0, Gigabit=1, Serial=2
Router, RD, Fast=0, Gigabit=1, Serial=1

# Switches
Switch, SW1, MgmtVlan=99
Switch, SW2, MgmtVlan=99

# VLAN definitions (Category, SwitchName, VlanID, VlanName, Hosts)
VLAN, SW1, 10, Sales, 1000
VLAN, SW1, 20, Engineering, 250
VLAN, SW2, 99, Management, 1200

# Subnets (Category, RouterName, Hosts=X, Port=Y)
Subnet, RB, Hosts=500, Port=GigabitEthernet0/0/0
Subnet, RB, Hosts=2400, Port=GigabitEthernet0/0/1
Subnet, RC, Hosts=8, Port=GigabitEthernet0/0/0

# Links (Category, Type, SrcName, SrcPort, DestName, DestPort, [Optional Parameters])
Link, Trunk, RA, GigabitEthernet0/0/0, SW1, GigabitEthernet0/1
Link, Trunk, RD, GigabitEthernet0/0/0, SW2, GigabitEthernet0/1
Link, Serial, RA, Serial0/0/0, RB, Serial0/0/0
Link, Serial, RB, Serial0/0/1, RC, Serial0/0/0
Link, Serial, RC, Serial0/0/1, RD, Serial0/0/0

```

---

## Auto IP Assignment

When using the CSV builder, the script utilizes an internal hash map to track allocated IP addresses for each broadcast domain.

* **Switch Management IPs:** Assigned sequentially from the **First Valid IP** of their respective subnet.
* **Router Sub-interfaces:** Automatically take the **Last Valid IP** (acting as the default gateway).

This ensures zero IP conflicts across the topology without manual subnet tracking.

---

## Declarative Config API (Python)

Alternatively, you can bypass the CSV parser and use a Python dictionary (or JSON/YAML file) to describe the topology directly, then generate the outputs.

This is tedious but it might be useful if you come up with an easier way to config the initial setup.

```python
from cisco_pkt import generate_from_config

config = {
    "base_ip": "140.7.32.0/19",
    "routers": [
        {"name": "RA", "interfaces": {"fast": 0, "gigabit": 1, "serial": 1}},
        {"name": "RB", "interfaces": {"fast": 0, "gigabit": 2, "serial": 2}},
        {"name": "RC", "interfaces": {"fast": 0, "gigabit": 1, "serial": 2}},
        {"name": "RD", "interfaces": {"fast": 0, "gigabit": 1, "serial": 1}},
    ],
    "switches": [
        {
            "name": "SW1",
            "vlans": [
                {"id": 10, "hosts": 1000, "name": "Sales"},
                {"id": 20, "hosts": 250, "name": "Engineering"},
            ],
        },
        {
            "name": "SW2", 
            "vlans": [{"id": 99, "hosts": 1200, "name": "Management"}]
        },
    ],
    "subnets": [
        {"router": "RB", "hosts": 500, "port": "GigabitEthernet0/0/0"},
        {"router": "RB", "hosts": 2400, "port": "GigabitEthernet0/0/1"},
        {"router": "RC", "hosts": 8, "port": "GigabitEthernet0/0/0"},
    ],
    "links": [
        {"type": "trunk", "router": "RA", "router_port": "GigabitEthernet0/0/0", "switch": "SW1"},
        {"type": "trunk", "router": "RD", "router_port": "GigabitEthernet0/0/0", "switch": "SW2"},
        {"type": "serial", "a": "RA", "a_port": "Serial0/0/0", "b": "RB", "b_port": "Serial0/0/0"},
        {"type": "serial", "a": "RB", "a_port": "Serial0/0/1", "b": "RC", "b_port": "Serial0/0/0"},
        {"type": "serial", "a": "RC", "a_port": "Serial0/0/1", "b": "RD", "b_port": "Serial0/0/0"},
    ],
    "routing": {"auto_static": False, "ospf": True},
    "dhcp": {"enabled": True, "dns_enabled": True, "dns_server": "8.8.8.8"},
    "output": {
        "commands": "packet_tracer_commands.txt", 
        "answers": "subnetting.csv", 
        "banner": "Unauthorized access is strictly prohibited."
    },
}

generate_from_config(config)

```

---

## Additional Specifications

### Interface Naming

All interfaces are normalized to their full canonical names (e.g., `GigabitEthernet0/0/0`). Aliases like `Gi0/0/0`, `Fa0/1`, and `S0/0/0` are accepted as input and automatically normalized by the parser.

### ISP Serial Link Network

For a serial link involving an ISP router, you can set `Network=65.255.255.252/30` (in CSV) or `links[].network_ip` (in Python API) to force a specific /30 network for that link. If omitted, the link subnet is allocated dynamically from the base IP space.