import pandas as pd
from router import Router
from pkt_tr_utils import get_wildcard_mask, render_interface_name
from pkt_tr_base_config import generate_basic_config


def generate_router_commands(
    r: Router,
    vlsm_df: pd.DataFrame,
    banner_text: str | None = None,
) -> str:
    """Generates the Cisco IOS configuration string for a single router."""
    lines = []
    lines.append("! ===========================")
    lines.append(f"! ======== {r.router_name} ========")
    lines.append("! ===========================\n")

    # Inject baseline configuration from PDF
    lines.append(generate_basic_config(r.router_name, "router", banner_text=banner_text))

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

                port = render_interface_name(port)
                lines.append(f"int {port}")
                lines.append(f"desc Interface that connects to {remote_name}")
                lines.append(f"ip address {ip} {mask}")
                lines.append("no shut")
                lines.append("")

    # Second pass: Configure IPs and sub-interfaces
    if any(data for data in all_eth_interfaces.values() if data and data['hosts'] > 0):
        lines.append("! -------------Subinterface declarations-------------")
        lines.append("")
    for port, data in all_eth_interfaces.items():
        if data and data['hosts'] > 0:
            subnet_label = data['name'] if data['name'] else port
            expected_name = f"{r.router_name}_{subnet_label}"

            row = vlsm_df[vlsm_df['Subnet Name'] == expected_name]
            if not row.empty:
                mask = row.iloc[0]['Subnet Mask']
                network_id = row.iloc[0]['Network ID']

                if "." in port:  # Sub-interface (VLAN)
                    ip = row.iloc[0]['Last Valid IP']
                else:  # Normal interface
                    ip = row.iloc[0]['First Valid IP']

                ospf_networks.append((network_id, get_wildcard_mask(mask)))
                dhcp_pools.append((expected_name, network_id, mask, ip))

                normalized_port = render_interface_name(port)
                if "." in port:  # Sub-interface (VLAN)
                    vlan_id = port.split(".")[1]
                    vlan_name = subnet_label.split("_", 1)[-1]
                    lines.append(f"int {normalized_port}")
                    lines.append(f"desc {vlan_name}")
                    lines.append(f"encapsulation dot1q {vlan_id}")
                    lines.append(f"ip add {ip} {mask}")
                    lines.append("")
                else:  # Normal interface
                    lines.append(f"int {normalized_port}")
                    lines.append(f"ip add {ip} {mask}")
                    lines.append("no shut")
                    lines.append("")

    if physical_ports_to_enable:
        for phys_port in sorted(physical_ports_to_enable):
            phys_port = render_interface_name(phys_port)
            lines.append(f"int {phys_port}")
            lines.append("no shut")
            lines.append("")

    # DHCP Pools Configuration (skip if router disables DHCP)
    if not getattr(r, 'disable_dhcp', False):
        for pool_name, net_id, mask, def_router in dhcp_pools:
            lines.append(f"ip dhcp pool POOL_{pool_name}")
            lines.append(f" network {net_id} {mask}")
            lines.append(f" default-router {def_router}")
            dns_server = getattr(r, 'dns_server', "8.8.8.8")
            if dns_server and not getattr(r, 'disable_dns', False):
                lines.append(f" dns-server {dns_server}")
            lines.append(" exit\n!")

    # OSPF Configuration (skip if router disables OSPF)
    if ospf_networks and not getattr(r, 'disable_ospf', False):
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

    # Static Routes (structured)
    static_routes = getattr(r, 'static_routes', [])
    if static_routes:
        lines.append("! -------Default route for Internet traffic-------")
        for rt in static_routes:
            dest = rt.get('dest')
            mask = rt.get('mask')
            next_hop = rt.get('next_hop')
            out_if = rt.get('out_interface')
            nh_router = rt.get('next_hop_router')
            if next_hop and out_if:
                out_if = render_interface_name(out_if)
                lines.append(f"ip route {dest} {mask} {out_if} {next_hop}")
            elif next_hop:
                lines.append(f"ip route {dest} {mask} {next_hop}")
            elif out_if:
                out_if = render_interface_name(out_if)
                lines.append(f"ip route {dest} {mask} {out_if}")
            elif nh_router:
                # Try to determine serial link subnet between this router and the named neighbor
                link_name_1 = f"zzLink_{r.router_name}_{nh_router}"
                link_name_2 = f"zzLink_{nh_router}_{r.router_name}"
                row = vlsm_df[(vlsm_df['Subnet Name'] == link_name_1) | (vlsm_df['Subnet Name'] == link_name_2)]
                if not row.empty:
                    link_name = row.iloc[0]['Subnet Name']
                    parts = link_name.split("_")
                    router_a = parts[1]
                    # neighbor's IP is the opposite end of the link
                    if r.router_name == router_a:
                        neighbor_ip = row.iloc[0]['Last Valid IP']
                    else:
                        neighbor_ip = row.iloc[0]['First Valid IP']
                    lines.append(f"ip route {dest} {mask} {neighbor_ip}")
                else:
                    lines.append(f"! Warning: could not determine next-hop IP for route to {dest}; missing link subnet for {nh_router}")
        lines.append("\n")

    lines.append("end")
    # Using 'copy running-config startup-config' as per the PDF
    # lines.append("copy running-config startup-config\n\n")

    return "\n".join(lines)
