from router import Switch
from pkt_tr_base_config import generate_basic_config
from pkt_tr_utils import render_interface_name, render_interface_range

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
    
    # Create Native VLAN (Security Best Practice)
    # native_vlan_id = getattr(s, 'native_vlan', 999)
    # lines.append(f"vlan {native_vlan_id}")
    # lines.append(" name Native_Blackhole")
    # lines.append(" exit\n!")

    # Create user VLANs
    skip_vlan_1 = getattr(s, "skip_vlan_1", False)
    lines.append("! -------VLAN database-------")
    for vlan in s.vlans:
        if skip_vlan_1 and vlan['id'] == 1:
            continue
        lines.append(f"vlan {vlan['id']}")
        lines.append(f" name {vlan['name']}")
        lines.append(" exit\n!")
    
    # Assign trunk ports (defaults to GigabitEthernet0/1 if switch.trunk_ports not set)
    trunk_ports = [render_interface_name(tp) for tp in getattr(s, 'trunk_ports', ['GigabitEthernet0/1'])]
    lines.append("! -------Trunk ports-------")
    for tp in trunk_ports:
        lines.append(f"interface {tp}")
        lines.append(" switchport mode trunk")
        lines.append(" no shut")
        lines.append("")
    
    # Assign access ports sequentially or based on vlan config
    port_counter = 1
    used_fast_ports = []
    access_ranges = getattr(s, "access_ranges", [])

    lines.append("! -------Access ports-------")
    if access_ranges:
        for access in access_ranges:
            vlan_id = access["vlan_id"]
            range_str = render_interface_range(access["range"])
            lines.append(f"interface range {range_str}")
            lines.append(" switchport mode access")
            lines.append(f" switchport access vlan {vlan_id}")
            lines.append("")
    else:
        for vlan in s.vlans:
            assigned_ports = vlan.get('ports', [f"FastEthernet0/{port_counter}"])
            for port in [render_interface_name(p) for p in assigned_ports]:
                lines.append(f"interface {port}")
                lines.append(" switchport mode access")
                lines.append(f" switchport access vlan {vlan['id']}")
                lines.append("")
            port_counter += len(assigned_ports)

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
    # Using 'copy running-config startup-config' as per the PDF
    # lines.append("copy running-config startup-config\n\n")
    
    return "\n".join(lines)