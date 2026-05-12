from router import Switch
from pkt_tr_base_config import generate_basic_config

def generate_switch_commands(s: Switch) -> str:
    """Generates the Cisco IOS configuration string for a single switch."""
    lines = []
    lines.append(f"!\n! ========================================")
    lines.append(f"! Configuration for Switch {s.name}")
    lines.append(f"! ========================================\n!")
    
    # Inject baseline configuration from PDF
    lines.append(generate_basic_config(s.name, "switch"))
    
    # Create Native VLAN (Security Best Practice)
    native_vlan_id = getattr(s, 'native_vlan', 999)
    lines.append(f"vlan {native_vlan_id}")
    lines.append(" name Native_Blackhole")
    lines.append(" exit\n!")

    # Create user VLANs
    for vlan in s.vlans:
        lines.append(f"vlan {vlan['id']}")
        lines.append(f" name {vlan['name']}")
        lines.append(" exit\n!")
    
    # Assign trunk port (defaults to GigabitEthernet0/1 if switch.trunk_port is not set)
    trunk_port = getattr(s, 'trunk_port', 'GigabitEthernet0/1')
    lines.append(f"interface {trunk_port}")
    lines.append(f" description Trunk Link from {s.name}")
    lines.append(" switchport mode trunk")
    lines.append(f" switchport trunk native vlan {native_vlan_id}")
    lines.append(" exit\n!")
    
    # Assign access ports sequentially or based on vlan config
    port_counter = 1
    used_fast_ports = []
    
    for vlan in s.vlans:
        # check if the user defined specific ports for this vlan, otherwise use FastEthernet0/X
        assigned_ports = vlan.get('ports', [f"FastEthernet0/{port_counter}"])
        for port in assigned_ports:
            lines.append(f"interface {port}")
            lines.append(f" description Access Port for VLAN {vlan['id']} ({vlan['name']})")
            lines.append(" switchport mode access")
            lines.append(f" switchport access vlan {vlan['id']}")
            lines.append(" exit\n!")
            
            # Keep track of FastEthernet ports used for the shutdown range later
            if port.startswith("FastEthernet0/"):
                try:
                    used_fast_ports.append(int(port.split("/")[1]))
                except ValueError:
                    pass
                    
        port_counter += len(assigned_ports)
    
    # Security: Shutdown unused FastEthernet ports (assuming standard 24-port switch)
    if used_fast_ports:
        max_used = max(used_fast_ports)
        if max_used < 24:
            lines.append(f"interface range FastEthernet0/{max_used + 1} - 24")
            lines.append(" shutdown")
            lines.append(" exit\n!")
        
    lines.append("end")
    # Using 'copy running-config startup-config' as per the PDF
    lines.append("copy running-config startup-config\n\n")
    
    return "\n".join(lines)