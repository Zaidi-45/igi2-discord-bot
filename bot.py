import socket
import os
import requests
from datetime import datetime, timezone

# --- CONFIGURATION ---
SERVERS = [
    {"ip": "16.24.95.100", "port": 26001, "name": "DON CLAN IGI2"}
]

# Discord URLs from GitHub Secrets
STATUS_WEBHOOK = os.getenv('STATUS_WEBHOOK')
HYPE_WEBHOOK = os.getenv('HYPE_WEBHOOK')

# State Files
MSG_ID_FILE = 'discord_msg_id.txt'
ALERT_STATE_FILE = 'discord_alert_state.txt'

# --- MAP IMAGES ---
MAP_IMAGES = {
    "sandstorm": "https://raw.githubusercontent.com/Zaidi-45/igi2-status/refs/heads/main/sandstorm.png", 
    "redstone": "https://filker.weebly.com/uploads/3/9/4/3/39435999/2235265_orig.png", 
    "timberland": "https://filker.weebly.com/uploads/3/9/4/3/39435999/7201890_orig.png", 
    "forestraid": "https://filker.weebly.com/uploads/3/9/4/3/39435999/7950290_orig.png", 
    "chinese temple": "https://filker.weebly.com/uploads/3/9/4/3/39435999/7534426_orig.png", 
    "dark hills": "https://iili.io/f4w2IJR.png", 
    "default": "https://raw.githubusercontent.com/Zaidi-45/igi2-status/refs/heads/main/default.png"
}

def read_state(filepath, default=""):
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return f.read().strip()
    return default

def write_state(filepath, content):
    with open(filepath, 'w') as f:
        f.write(str(content))

def parse_igi2_response(raw_data):
    decoded = raw_data.decode('latin-1', errors='replace')
    parts = decoded.split('\\')
    data_map = {parts[i]: parts[i+1] for i in range(1, len(parts)-1, 2)}

    server_info = {
        "hostname": data_map.get("hostname", "Unknown"),
        "mapname": data_map.get("mapname", "Unknown"),
        "players_count": f"{data_map.get('numplayers', 0)}/{data_map.get('maxplayers', 0)}",
        "timeleft": data_map.get("timeleft", "00:00"),
        "score_igi": data_map.get("score_t0", "0"),
        "score_con": data_map.get("score_t1", "0"),
        "team_igi_players": [],
        "team_con_players": []
    }

    for key, name in data_map.items():
        if key.startswith("player_"):
            pid = key.split("_")[1]
            p_stats = {
                "id": pid,
                "name": name,
                "frags": data_map.get(f"frags_{pid}", "0"),
                "deaths": data_map.get(f"deaths_{pid}", "0"),
                "ping": data_map.get(f"ping_{pid}", "0"),
                "team": data_map.get(f"team_{pid}", "0")
            }
            if p_stats["team"] == "0":
                server_info["team_igi_players"].append(p_stats)
            else:
                server_info["team_con_players"].append(p_stats)
    return server_info

def check_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(3.0)
    srv = SERVERS[0]
    
    try:
        sock.sendto(b'\\status\\', (srv["ip"], srv["port"]))
        data, _ = sock.recvfrom(8192)
        parsed_data = parse_igi2_response(data)
        parsed_data["status"] = "Online"
    except:
        parsed_data = {"hostname": srv["name"], "status": "Offline"}
    
    sock.close()
    return parsed_data

def run_discord_bot():
    if not STATUS_WEBHOOK or not HYPE_WEBHOOK:
        print("Error: Webhook secrets are missing.")
        return

    srv = check_server()
    
    try:
        current_players = int(str(srv.get('players_count', '0/0')).split('/')[0])
    except:
        current_players = 0

    # --- 1. THE MULTI-TIER HYPE ENGINE (Uses HYPE_WEBHOOK) ---
    try:
        current_state = int(read_state(ALERT_STATE_FILE, "0"))
    except ValueError:
        current_state = 0

    new_state = current_state
    hype_msg = ""

    if current_players >= 24 and current_state < 3:
        hype_msg = f"🚨 @here **MAXIMUM CARNAGE!** {current_players}/32 operatives! The server is practically full! Get in! 🚨"
        new_state = 3
    elif current_players >= 16 and current_state < 2:
        hype_msg = f"💥 @here **WARZONE DEPLOYED!** Server is half-full with {current_players}/32 operatives. Drop in now! 💥"
        new_state = 2
    elif current_players >= 8 and current_state < 1:
        hype_msg = f"🔥 @here **SERVER IS ON FIRE!** We have {current_players}/32 operatives deployed. Join to ignite more! 🔥"
        new_state = 1
    elif current_players <= 3:
        new_state = 0

    if hype_msg:
        requests.post(HYPE_WEBHOOK, json={"content": hype_msg})
        write_state(ALERT_STATE_FILE, str(new_state))

    # --- 2. THE LIVE DASHBOARD (Uses STATUS_WEBHOOK) ---
    if srv.get('status') == 'Offline':
        embed = {"title": f"🔴 {srv.get('hostname', 'Server')} is OFFLINE", "color": 16711680}
    else:
        # ASCII Table Formatter (COMPACT MOBILE-SAFE EDITION)
        def format_team(players, team_name, score):
            if not players: return f"```text\n[{team_name}] {score} Score\n* NO AGENTS DEPLOYED *\n```"
            
            lines = [
                f"[{team_name}] {score} Score",
                "ID | Name            | K/D    | Ping",
                "---+-----------------+--------+-----"
            ]
            for p in players:
                pid = str(p.get('id', '0')).ljust(2)
                
                # Truncate at 15 chars (Fits 'IGI 2 Pakistani' perfectly)
                name_str = str(p.get('name', 'Unknown'))[:15] 
                name = name_str.ljust(15)
                
                kd = f"{p.get('frags', 0)}/{p.get('deaths', 0)}".ljust(6)
                ping = f"{p.get('ping', '0')}ms".ljust(4)
                lines.append(f"{pid} | {name} | {kd} | {ping}")
            
            return "```text\n" + "\n".join(lines) + "\n```"

        map_name_lower = srv.get('mapname', '').lower()
        map_img = MAP_IMAGES.get(map_name_lower, MAP_IMAGES['default'])

        embed = {
            "title": f"**{srv.get('hostname')}**",
            "color": 2278750,
            "description": f"**SERVER CONFIG**\n```text\n> Map Name : '{srv.get('mapname')}'\n> Map Time : {srv.get('timeleft')}\n> Players  : {srv.get('players_count')}\n> Status   : ONLINE\n```\n**IN-GAME PLAYERS**",
            "fields": [
                {"name": "", "value": format_team(srv.get('team_igi_players', []), "IGI OPERATIVE", srv.get('score_igi')), "inline": False},
                {"name": "v/s", "value": format_team(srv.get('team_con_players', []), "CONSPIRACY", srv.get('score_con')), "inline": False}
            ],
            "image": {"url": map_img},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "footer": {"text": "DON CLAN Satellite Uplink"}
        }

    payload = {"embeds": [embed]}
    msg_id = read_state(MSG_ID_FILE)

    if msg_id:
        res = requests.patch(f"{STATUS_WEBHOOK}/messages/{msg_id}", json=payload)
        if res.status_code == 404:
            msg_id = "" # Reset if deleted

    if not msg_id:
        res = requests.post(f"{STATUS_WEBHOOK}?wait=true", json=payload)
        if res.status_code in (200, 201):
            write_state(MSG_ID_FILE, res.json().get('id'))

if __name__ == "__main__":
    run_discord_bot()
# System wake-up commit
