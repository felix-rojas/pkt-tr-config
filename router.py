from typing import Optional

from pkt_tr_utils import build_interface_map, normalize_interface_name, normalize_port_type


class Switch:
    def __init__(self, name):
        self.name = name
        self.vlans = []
        # list of trunk ports on this switch (can connect to router or other switches)
        self.trunk_ports = [normalize_interface_name("GigabitEthernet0/1")]
        # record of connected switches (name -> port mapping)
        self.connected_switches = []

    def add_vlan(self, vlan_id, hosts, name=None, ports=None):
        vlan = {
            "id": vlan_id,
            "hosts": hosts,
            "name": name if name else f"VLAN{vlan_id}"
        }
        if ports:
            vlan["ports"] = [normalize_interface_name(p) for p in ports]
        self.vlans.append(vlan)

    def connect_switch(self, other_switch: "Switch", port: str = "GigabitEthernet0/1", other_port: str = "GigabitEthernet0/1"):
        """Create a trunk link between two switches by adding trunk ports on both sides."""
        port = normalize_interface_name(port)
        other_port = normalize_interface_name(other_port)

        if port not in self.trunk_ports:
            self.trunk_ports.append(port)
        if other_port not in other_switch.trunk_ports:
            other_switch.trunk_ports.append(other_port)

        self.connected_switches.append({"peer": other_switch.name, "port": port, "peer_port": other_port})
        other_switch.connected_switches.append({"peer": self.name, "port": other_port, "peer_port": port})


class Router:
    def __init__(self, router_name, fast_count, gigabyte_count, serial_count):
        self.router_name = router_name
        self.fast_interfaces = build_interface_map("FastEthernet", fast_count)
        self.gigabyte_interfaces = build_interface_map("GigabitEthernet", gigabyte_count)
        self.serial_interfaces = build_interface_map("Serial", serial_count)
        # Structured static route declarations will be stored here as dicts
        # Each route should include: 'dest', 'mask', and exactly one of
        # 'next_hop' or 'out_interface'. Example:
        # {"dest": "10.0.0.0", "mask": "255.255.255.0", "next_hop": "192.168.1.1"}
        self.static_routes = []

    def add_subnet(self, hosts, name=None, port_type="FastEthernet", port=None):
        if port:
            port = normalize_interface_name(port)
            if port in self.fast_interfaces:
                if self.fast_interfaces[port] is None:
                    self.fast_interfaces[port] = {"name": name, "hosts": hosts}
                    return
                print(f"Port {port} on {self.router_name} is already in use.")
                return

            if port in self.gigabyte_interfaces:
                if self.gigabyte_interfaces[port] is None:
                    self.gigabyte_interfaces[port] = {
                        "name": name, "hosts": hosts}
                    return
                print(f"Port {port} on {self.router_name} is already in use.")
                return

            print(f"Port {port} does not exist on {self.router_name}")
            return

        # Fallback to automatic assignment if no specific port is provided
        normalized_type = normalize_port_type(port_type)
        if normalized_type == "FastEthernet":
            interfaces = self.fast_interfaces
        elif normalized_type == "GigabitEthernet":
            interfaces = self.gigabyte_interfaces
        else:
            print(f"Invalid port type: {port_type}")
            return

        for p, val in interfaces.items():
            if "." not in p and val is None:
                interfaces[p] = {"name": name,
                                 "hosts": hosts}
                return
        print(f"No available {normalized_type} ports on {self.router_name}")

    def connect_switch(self, switch: Switch, port_type="GigabitEthernet", port=None, switch_port: str = "GigabitEthernet0/1"):
        available_port = None
        target_interfaces = None

        if port:
            port = normalize_interface_name(port)
            if port in self.fast_interfaces:
                # allow reuse of an existing trunk port (hosts == 0)
                if self.fast_interfaces[port] is None:
                    available_port = port
                    target_interfaces = self.fast_interfaces
                elif isinstance(self.fast_interfaces[port], dict) and self.fast_interfaces[port].get('hosts') == 0:
                    available_port = port
                    target_interfaces = self.fast_interfaces
                else:
                    print(f"Port {port} on {self.router_name} is already in use.")
                    return
            elif port in self.gigabyte_interfaces:
                if self.gigabyte_interfaces[port] is None:
                    available_port = port
                    target_interfaces = self.gigabyte_interfaces
                elif isinstance(self.gigabyte_interfaces[port], dict) and self.gigabyte_interfaces[port].get('hosts') == 0:
                    available_port = port
                    target_interfaces = self.gigabyte_interfaces
                else:
                    print(f"Port {port} on {self.router_name} is already in use.")
                    return
            else:
                print(f"Port {port} does not exist on {self.router_name}")
                return
        else:
            # Fallback to automatic assignment if no specific port is provided
            normalized_type = normalize_port_type(port_type)
            if normalized_type == "FastEthernet":
                target_interfaces = self.fast_interfaces
            elif normalized_type == "GigabitEthernet":
                target_interfaces = self.gigabyte_interfaces
            else:
                print(f"Invalid port type: {port_type}")
                return

            for p, val in list(target_interfaces.items()):
                if "." not in p and val is None:
                    available_port = p
                    break

        if available_port is None:
            print(
                f"No available {normalize_port_type(port_type)} ports on {self.router_name} for switch {switch.name}")
            return

        # Mark the physical port as occupied by a trunk link (requires 0 hosts for the physical link itself)
        if target_interfaces.get(available_port) is None:
            target_interfaces[available_port] = {"name": f"Trunk_{switch.name}", "hosts": 0}

        # Ensure the switch knows which trunk port is used to connect to this router
        switch_port = normalize_interface_name(switch_port)
        if hasattr(switch, 'trunk_ports'):
            if switch_port not in switch.trunk_ports:
                switch.trunk_ports.append(switch_port)
        else:
            setattr(switch, 'trunk_ports', [switch_port])

        # Create sub-interfaces for each VLAN (e.g., GigabitEthernet0/0/0.10)
        for vlan in switch.vlans:
            sub_interface = f"{available_port}.{vlan['id']}"
            # only create the sub-interface if it doesn't already exist
            if target_interfaces.get(sub_interface) is None:
                target_interfaces[sub_interface] = {
                    "name": f"{switch.name}_{vlan['name']}",
                    "hosts": vlan['hosts']
                }

    def connect_router(self, other_router: "Router", local_port=None, remote_port=None, _is_backlink=False):
        if local_port:
            local_port = normalize_interface_name(local_port)
            if local_port not in self.serial_interfaces:
                print(
                    f"Port {local_port} does not exist on {self.router_name}")
                return
            if self.serial_interfaces[local_port] is not None:
                print(
                    f"Port {local_port} on {self.router_name} is already in use.")
                return
            actual_local_port = local_port
        else:
            # Find the first available serial port
            actual_local_port = next(
                (p for p, v in self.serial_interfaces.items() if v is None), None)

            if actual_local_port is None:
                print(f"No available serial ports on {self.router_name}")
                return

        self.serial_interfaces[actual_local_port] = other_router.router_name

        if not _is_backlink:
            # Create the reciprocal connection on the other router
            normalized_remote = normalize_interface_name(remote_port) if remote_port else None
            other_router.connect_router(
                self, local_port=normalized_remote, remote_port=actual_local_port, _is_backlink=True)

    def add_static_route(
        self,
        dest: str,
        mask: str,
        next_hop: Optional[str] = None,
        out_interface: Optional[str] = None,
        next_hop_router: Optional[str] = None,
    ):
        """Add a structured static route to this router.

        Provide either:
        - `next_hop` (optionally with `out_interface`), or
        - `out_interface` only, or
        - `next_hop_router` (to auto-resolve a serial next-hop).
        """
        if next_hop_router and (next_hop or out_interface):
            raise ValueError(
                "add_static_route cannot mix next_hop_router with next_hop or out_interface")

        if not next_hop and not out_interface and not next_hop_router:
            raise ValueError(
                "add_static_route requires next_hop, out_interface, or next_hop_router")

        route = {"dest": dest, "mask": mask}
        if next_hop_router:
            route["next_hop_router"] = next_hop_router
        else:
            if next_hop:
                route["next_hop"] = next_hop
            if out_interface:
                route["out_interface"] = normalize_interface_name(out_interface)

        self.static_routes.append(route)
