from router import Switch
from pkt_tr_base_config import generate_basic_config
from pkt_tr_utils import render_interface_name, render_interface_range, normalize_interface_name

def generate_switch_commands(
    s: Switch,
    banner_text: str | None = None,
) -> str:
    """Generates the Cisco IOS configuration string for a single switch."""
    lines = []
    lines.append("! ====================")
    lines.append(f"! ===== {s.name} =====")
    lines.append("! ====================\n")
    
    # Inject baseline configuration from PDF
    lines.append(generate_basic_config(s.name, "switch", banner_text=banner_text))

    # Create user VLANs
    skip_vlan_1 = getattr(s, "skip_vlan_1", False)
    lines.append("! -------VLAN database-------")
    for vlan in s.vlans:
        if skip_vlan_1 and vlan['id'] == 1:
            continue
        lines.append(f"vlan {vlan['id']}")
        lines.append(f" name {vlan['name']}")
        lines.append(" exit\n!")
    
    # Get normalized trunk ports to ensure accurate comparisons
    trunk_ports_raw = getattr(s, 'trunk_ports', ['GigabitEthernet0/1'])
    trunk_ports_normalized = [normalize_interface_name(tp) for tp in trunk_ports_raw]
    trunk_ports_rendered = [render_interface_name(tp) for tp in trunk_ports_normalized]

    lines.append("! -------Trunk ports-------")
    for tp in trunk_ports_rendered:
        lines.append(f"interface {tp}")
        lines.append(" switchport mode trunk")
        lines.append(" no shut")
        lines.append("")
    
    lines.append("! -------Access ports-------")
    
    # 1. Process explicitly defined bulk access ranges
    access_ranges = getattr(s, "access_ranges", [])
    if access_ranges:
        for access in access_ranges:
            vlan_id = access["vlan_id"]
            range_str = render_interface_range(access["range"])
            lines.append(f"interface range {range_str}")
            lines.append(" switchport mode access")
            lines.append(f" switchport access vlan {vlan_id}")
            lines.append("")

    # 2. Process dynamically assigned device ports or fallback logic
    port_counter = 1
    for vlan in s.vlans:
        assigned_ports = vlan.get('ports', [])
        
        # If no specific ports and no ranges are provided, auto-assign one free port
        if not assigned_ports and not access_ranges:
            while True:
                candidate_port = f"FastEthernet0/{port_counter}"
                if normalize_interface_name(candidate_port) not in trunk_ports_normalized:
                    assigned_ports = [candidate_port]
                    port_counter += 1
                    break
                port_counter += 1

        # Apply configuration for the specific ports (including endpoint devices)
        for port in assigned_ports:
            port_rendered = render_interface_name(port)
            lines.append(f"interface {port_rendered}")
            lines.append(" switchport mode access")
            lines.append(f" switchport access vlan {vlan['id']}")
            lines.append("")

    management = getattr(s, "management", None)
    if management:
        vlan_id = management.get("vlan", 1)
        ip = management.get("ip")
        mask = management.get("mask")
        gateway = management.get("default_gateway")
        lines.append("! -------Management SVI-------")
        lines.append(f"int vlan {vlan_id}")
        if ip and mask:
            lines.append(f"ip address {ip} {mask}")
        lines.append("no shut")
        if gateway:
            lines.append(f"ip default-gateway {gateway}")
        lines.append("")
        
    lines.append("end")
    #lines.append("copy running-config startup-config\n\n")
    
    return "\n".join(lines)
