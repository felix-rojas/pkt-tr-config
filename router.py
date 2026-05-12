class Switch:
    def __init__(self, name):
        self.name = name
        self.vlans = []

    def add_vlan(self, vlan_id, hosts, name=None):
        self.vlans.append({
            "id": vlan_id,
            "hosts": hosts,
            "name": name if name else f"VLAN{vlan_id}"
        })


class Router:
    def __init__(self, router_name, fast_count, gigabyte_count, serial_count):
        self.router_name = router_name
        self.fast_interfaces = {
            f"FastEthernet0/0/{i}": None for i in range(fast_count)}
        self.gigabyte_interfaces = {
            f"GigabitEthernet0/0/{i}": None for i in range(gigabyte_count)}
        self.serial_interfaces = {
            f"Serial0/0/{i}": None for i in range(serial_count)}

    def add_subnet(self, hosts, name=None, port_type="F", port=None):
        if port:
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
        if port_type == "F":
            interfaces = self.fast_interfaces
        elif port_type == "G":
            interfaces = self.gigabyte_interfaces
        else:
            print(f"Invalid port type: {port_type}")
            return

        for p, val in interfaces.items():
            if "." not in p and val is None:
                interfaces[p] = {"name": name,
                                 "hosts": hosts}
                return
        print(f"No available {port_type} ports on {self.router_name}")

    def connect_switch(self, switch: Switch, port_type="G", port=None):
        available_port = None
        target_interfaces = None

        if port:
            if port in self.fast_interfaces:
                if self.fast_interfaces[port] is None:
                    available_port = port
                    target_interfaces = self.fast_interfaces
                else:
                    print(
                        f"Port {port} on {self.router_name} is already in use.")
                    return
            elif port in self.gigabyte_interfaces:
                if self.gigabyte_interfaces[port] is None:
                    available_port = port
                    target_interfaces = self.gigabyte_interfaces
                else:
                    print(
                        f"Port {port} on {self.router_name} is already in use.")
                    return
            else:
                print(f"Port {port} does not exist on {self.router_name}")
                return
        else:
            # Fallback to automatic assignment if no specific port is provided
            if port_type == "F":
                target_interfaces = self.fast_interfaces
            elif port_type == "G":
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
                f"No available {port_type} ports on {self.router_name} for switch {switch.name}")
            return

        # Mark the physical port as occupied by a trunk link (requires 0 hosts for the physical link itself)
        target_interfaces[available_port] = {
            "name": f"Trunk_{switch.name}", "hosts": 0}

        # Create sub-interfaces for each VLAN (e.g., GigabitEthernet0/0/0.10)
        for vlan in switch.vlans:
            sub_interface = f"{available_port}.{vlan['id']}"
            target_interfaces[sub_interface] = {
                "name": f"{switch.name}_{vlan['name']}",
                "hosts": vlan['hosts']
            }

    def connect_router(self, other_router: "Router", local_port=None, remote_port=None, _is_backlink=False):
        if local_port:
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
            other_router.connect_router(
                self, local_port=remote_port, remote_port=actual_local_port, _is_backlink=True)
