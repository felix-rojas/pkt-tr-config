from cisco_pkt import generate_from_config

config = {
    "base_ip": "192.168.1.0",
    "routers": [
        {"name": "ISP", "interfaces": {"fast": 0, "gigabit": 0, "serial": 1}},
        {
            "name": "RFrontera",
            "interfaces": {"fast": 1, "gigabit": 1, "serial": 1},
            "static_routes": [
                {
                    "dest": "0.0.0.0",
                    "mask": "0.0.0.0",
                    "out_interface": "Serial0/0/0",
                }
            ],
        },
    ],
    "switches": [
        {
            "name": "SOeste",
            "vlans": [
                {"id": 1, "hosts": 6, "name": "Administration"},
                {"id": 10, "hosts": 10, "name": "Managers"},
                {"id": 20, "hosts": 120, "name": "Users"},
                {"id": 30, "hosts": 5, "name": "Services"},
            ],
            "skip_vlan_1": True,
            "access_ranges": [
                {"vlan_id": 10, "range": "FastEthernet0/2-6"},
                {"vlan_id": 20, "range": "FastEthernet0/7-19"},
                {"vlan_id": 30, "range": "FastEthernet0/20-24"},
            ],
            "management": {
                "vlan": 1,
                "ip": "192.168.1.153",
                "mask": "255.255.255.248",
                "default_gateway": "192.168.1.158",
            },
        },
        {
            "name": "SEste",
            "vlans": [
                {"id": 1, "hosts": 6, "name": "Administration"},
                {"id": 10, "hosts": 10, "name": "Managers"},
                {"id": 20, "hosts": 120, "name": "Users"},
                {"id": 30, "hosts": 5, "name": "Services"},
            ],
            "skip_vlan_1": True,
            "access_ranges": [
                {"vlan_id": 10, "range": "FastEthernet0/2-6"},
                {"vlan_id": 20, "range": "FastEthernet0/7-19"},
                {"vlan_id": 30, "range": "FastEthernet0/20-24"},
            ],
            "management": {
                "vlan": 1,
                "ip": "192.168.1.155",
                "mask": "255.255.255.248",
                "default_gateway": "192.168.1.158",
            },
        },
        {
            "name": "SCompany",
            "vlans": [
                {"id": 1, "hosts": 6, "name": "Administration"},
                {"id": 10, "hosts": 10, "name": "Managers"},
                {"id": 20, "hosts": 120, "name": "Users"},
                {"id": 30, "hosts": 5, "name": "Services"},
            ],
            "skip_vlan_1": True,
            "trunk_ports": [
                "GigabitEthernet0/1",
                "FastEthernet0/1",
                "FastEthernet0/2",
            ],
            "management": {
                "vlan": 1,
                "ip": "192.168.1.153",
                "mask": "255.255.255.248",
                "default_gateway": "192.168.1.158",
            },
        },
    ],
    "subnets": [],
    "links": [
        {
            "type": "serial",
            "a": "ISP",
            "a_port": "Serial0/0/0",
            "b": "RFrontera",
            "b_port": "Serial0/0/0",
            "network_ip": "65.255.255.252/30",
        },
        {
            "type": "trunk",
            "router": "RFrontera",
            "router_port": "GigabitEthernet0/0/0",
            "switch": "SCompany",
            "switch_port": "GigabitEthernet0/1",
        },
        {
            "type": "switch",
            "a": "SOeste",
            "a_port": "FastEthernet0/1",
            "b": "SCompany",
            "b_port": "FastEthernet0/1",
        },
        {
            "type": "switch",
            "a": "SEste",
            "a_port": "FastEthernet0/1",
            "b": "SCompany",
            "b_port": "FastEthernet0/2",
        },
    ],
    "routing": {"auto_static": True, "auto_static_out_interface": True, "ospf": False},
    "dhcp": {"enabled": False, "dns_enabled": False, "dns_server": "8.8.8.8"},
    "output": {
        "commands": "packet_tracer_commands.txt",
        "answers": "answers.csv",
        "banner": "Unauthorized access is strictly prohibited.",
    },
}

generate_from_config(config)
