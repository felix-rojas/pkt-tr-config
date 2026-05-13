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
        {"name": "SW2", "vlans": [{"id": 99, "hosts": 1200, "name": "Management"}]},
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
    "output": {"commands": "packet_tracer_commands.txt", "answers": "answers.csv"},
}

generate_from_config(config)
