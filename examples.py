from router import Router, Switch
from vlsm import calculate_vlsm_from_routers
from cisco_pkt import generate_cisco_ios_commands

router_a = Router("RA", fast_count=0, gigabyte_count=1, serial_count=1)
router_b = Router("RB", fast_count=0, gigabyte_count=2, serial_count=2)
router_c = Router("RC", fast_count=0, gigabyte_count=1, serial_count=2)
router_d = Router("RD", fast_count=0, gigabyte_count=1, serial_count=1)

network_routers = [router_a, router_b, router_c, router_d]

# Create a switch with multiple VLANs
switch_1 = Switch("SW1")
switch_1.add_vlan(vlan_id=10, hosts=1000, name="Sales")
switch_1.add_vlan(vlan_id=20, hosts=250, name="Engineering")

switch_2 = Switch("SW2")
switch_2.add_vlan(vlan_id=99, hosts=1200, name="Management")

# Connect the switches to the routers using explicit ports
router_a.connect_switch(switch_1, port="G0/0")

# You can also fall back to automatic assignment if the port isn't specified
router_d.connect_switch(switch_2, port_type="G")

# Standard subnets specifying the exact port to utilize
router_b.add_subnet(hosts=500,  port="G0/0")
router_b.add_subnet(hosts=2400, port="G0/1")
router_c.add_subnet(hosts=8,    port="G0/0")

# Connect routers together using serial links
# Utilizing local_port and remote_port specifications
router_a.connect_router(router_b, local_port="S0/0/0", remote_port="S0/0/0")
router_b.connect_router(router_c, local_port="S0/0/1", remote_port="S0/0/0")
router_c.connect_router(router_d, local_port="S0/0/1", remote_port="S0/0/0")

# the base IP can be provided without a prefix
# the program calculates the smallest prefix that can accommodate all subnets
exercise_df = calculate_vlsm_from_routers("140.7.32.0/19", network_routers)

name_sorted = exercise_df.sort_values(by='Subnet Name')
name_sorted['Order'] = name_sorted.index + 1

result = name_sorted[['Subnet Name', 'Total IPs', 'Host Bits', 'Net Suffix',
                      'Subnet Mask', 'Order', 'Network ID', 'First Valid IP', 'Last Valid IP', 'Broadcast IP']]

print(result.to_string())
result.to_csv("answers.csv", index=False)

# Generate the configuration commands for Packet Tracer
generate_cisco_ios_commands(
    network_routers, exercise_df, switches=[switch_1, switch_2])
