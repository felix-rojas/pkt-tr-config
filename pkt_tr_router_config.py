import pandas as pd
from router import Router
from pkt_tr_utils import get_wildcard_mask
from pkt_tr_base_config import generate_basic_config


def generate_router_commands(r: Router, vlsm_df: pd.DataFrame) -> str:
    """Generates the Cisco IOS configuration string for a single router."""
    lines = []
    lines.append(f"!\n! ========================================")
    lines.append(f"! Configuration for Router {r.router_name}")
    lines.append(f"! ========================================\n!")

    # Inject baseline configuration from PDF
    lines.append(generate_basic_config(r.router_name, "router"))

    # Gather all Ethernet interfaces
    all_eth_interfaces = {}
    all_eth_interfaces.update(r.fast_interfaces)
    all_eth_interfaces.update(r.gigabyte_interfaces)

    physical_ports_to_enable = set()
    ospf_networks = []
    dhcp_pools = []

    # First pass: Identify and enable physical trunk ports before sub-interfaces
    for port, data in all_eth_interfaces.items():
        if data:
            if data['hosts'] == 0:
                physical_ports_to_enable.add(port)
            elif "." in port:
                physical_port = port.split(".")[0]
                physical_ports_to_enable.add(physical_port)

    for phys_port in physical_ports_to_enable:
        lines.append(f"interface {phys_port}")
        lines.append(f" description This is interface {phys_port}")
        lines.append(" no shutdown")
        lines.append(" exit\n!")

    # Second pass: Configure IPs and sub-interfaces
    for port, data in all_eth_interfaces.items():
        if data and data['hosts'] > 0:
            subnet_label = data['name'] if data['name'] else port
            expected_name = f"{r.router_name}_{subnet_label}"

            row = vlsm_df[vlsm_df['Subnet Name'] == expected_name]
            if not row.empty:
                ip = row.iloc[0]['First Valid IP']
                mask = row.iloc[0]['Subnet Mask']
                network_id = row.iloc[0]['Network ID']

                ospf_networks.append((network_id, get_wildcard_mask(mask)))
                dhcp_pools.append((expected_name, network_id, mask, ip))

                if "." in port:  # Sub-interface (VLAN)
                    vlan_id = port.split(".")[1]
                    lines.append(f"interface {port}")
                    lines.append(
                        f" description This is interface {port} for VLAN {vlan_id}")
                    lines.append(f" encapsulation dot1Q {vlan_id}")
                    lines.append(f" ip address {ip} {mask}")
                    lines.append(" exit\n!")
                else:  # Normal interface
                    lines.append(f"interface {port}")
                    lines.append(f" description This is interface {port}")
                    lines.append(f" ip address {ip} {mask}")
                    lines.append(" no shutdown")
                    lines.append(" exit\n!")

    # Serial interfaces (Router to Router Links)
    for port, remote_name in r.serial_interfaces.items():
        if remote_name:
            link_name_1 = f"zzLink_{r.router_name}_{remote_name}"
            link_name_2 = f"zzLink_{remote_name}_{r.router_name}"

            row = vlsm_df[(vlsm_df['Subnet Name'] == link_name_1)
                          | (vlsm_df['Subnet Name'] == link_name_2)]

            if not row.empty:
                mask = row.iloc[0]['Subnet Mask']
                link_name = row.iloc[0]['Subnet Name']
                network_id = row.iloc[0]['Network ID']
                parts = link_name.split("_")
                router_a = parts[1]

                ospf_networks.append((network_id, get_wildcard_mask(mask)))

                if r.router_name == router_a:
                    ip = row.iloc[0]['First Valid IP']
                else:
                    ip = row.iloc[0]['Last Valid IP']

                lines.append(f"interface {port}")
                lines.append(
                    f" description This is interface {port} hacia {remote_name}")
                lines.append(f" ip address {ip} {mask}")
                lines.append(
                    f" ! Note: If this is the DCE side of the connection, uncomment the next line:")
                lines.append(f" ! clock rate 64000")
                lines.append(" no shutdown")
                lines.append(" exit\n!")

    # DHCP Pools Configuration
    for pool_name, net_id, mask, def_router in dhcp_pools:
        lines.append(f"ip dhcp pool POOL_{pool_name}")
        lines.append(f" network {net_id} {mask}")
        lines.append(f" default-router {def_router}")
        lines.append(" dns-server 8.8.8.8")
        lines.append(" exit\n!")

    # OSPF Configuration
    if ospf_networks:
        lines.append("router ospf 1")
        for net_id, wildcard in ospf_networks:
            lines.append(f" network {net_id} {wildcard} area 0")
        lines.append(" exit\n!")

    # Custom Commands
    custom_commands = getattr(r, 'custom_commands', [])
    if custom_commands:
        lines.append("! Custom User Commands")
        for cmd in custom_commands:
            lines.append(cmd)
        lines.append("!\n")

    lines.append("end")
    # Using 'copy running-config startup-config' as per the PDF
    lines.append("copy running-config startup-config\n\n")

    return "\n".join(lines)
