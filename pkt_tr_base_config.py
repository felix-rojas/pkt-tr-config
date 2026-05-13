from datetime import datetime

dt = datetime.now()

# format like "17:00:00 Aug 12 2020"
formatted_date = dt.strftime("%H:%M:%S %b %d %Y")

def generate_basic_config(hostname: str, device_type: str = "router",
                          enable_password: str = "class",
                          enable_secret: str = "class",
                          console_password: str = "cisco",
                          vty_password: str = "cisco",
                          debug: bool = False,
                          banner_text: str | None = None) -> str:
    """
    Generates the baseline configuration for a switch/router.
    Includes clock settings, passwords, console/vty settings, encryption, and banners.
    """
    lines = []

    lines.append("ena")
    lines.append("conf t")
    lines.append(f"hostname {hostname}")
    lines.append("no ip domain-lookup")
    lines.append("service password-encryption")
    lines.append(f"enable password {enable_password}")
    lines.append(f"enable secret {enable_secret}")

    # console config
    lines.append("line con 0")
    lines.append(f" password {console_password}")
    lines.append(" login")
    lines.append(" logging synchronous")
    lines.append(" exit")

    # vty config
    if device_type == "switch":
        lines.append("line vty 0 15")
    else:
        lines.append("line vty 0 4")
    lines.append(f" password {vty_password}")
    lines.append(" login")
    lines.append(" logging synchronous")
    lines.append(" exit")

    # banner
    device_label = "router" if device_type == "router" else "switch"
    if banner_text is None:
        banner_text = "Unauthorized access is strictly prohibited."

    # debug banner with all password info
    if debug:
        banner_text += f"\n[DEBUG INFO] Enable PW: {enable_password} | Secret: {enable_secret} | Console: {console_password} | VTY: {vty_password}"

    lines.append(f"banner motd #{banner_text}#")

    return "\n".join(lines)
