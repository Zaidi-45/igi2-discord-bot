import socket
import os
import requests

# --- CONFIGURATION ---
SERVERS = [
    {"ip": "16.24.95.100", "port": 26001, "name": "DON CLAN IGI2"}
]

# Discord Hype Thresholds
FIRE_THRESHOLD = 8
COOLDOWN_THRESHOLD = 3

# State Files (so the bot remembers what it did)
MSG_ID_FILE = 'discord_msg_id.txt'
ALERT_STATE_FILE = 'discord_alert_state.txt'

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
    WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK')
    if not WEBHOOK_URL:
        print("Error: DISCORD_WEBHOOK secret is missing.")
        return

    srv = check_server()
    
    try:
        current_players = int(str(srv.get('players_count', '0/0')).split('/')[0])
    except:
        current_players = 0

    # --- 1. THE HYPE ALERT ---
    alert_triggered = read_state(ALERT_STATE_FILE, "False") == "True"

    if current_players >= FIRE_THRESHOLD and not alert_triggered:
        hype_msg = f"🔥 @here **SERVER IS ON FIRE!** We have {current_players} operatives deployed. Join to ignite more! 🔥"
        requests.post(WEBHOOK_URL, json={"content": hype_msg})
        write_state(ALERT_STATE_FILE, "True")
    elif current_players <= COOLDOWN_THRESHOLD and alert_triggered:
        write_state(ALERT_STATE_FILE, "False")

    # --- 2. THE LIVE DASHBOARD ---
    if srv.get('status') == 'Offline':
        embed = {"title": f"🔴 {srv.get('hostname', 'Server')} is OFFLINE", "color": 16711680}
    else:
        def format_team(players):
            if not players: return "*NO AGENTS DEPLOYED*"
            lines = ["NAME             K/D    PING", "-"*28]
            for p in players:
                name = str(p.get('name', 'Unknown'))[:14].ljust(15)
                kd = f"{p.get('frags', 0)}/{p.get('deaths', 0)}".ljust(6)
                ping = str(p.get('ping', 'N/A')).ljust(4)
                lines.append(f"{name} {kd} {ping}")
            return "```text\n" + "\n".join(lines) + "\n```"

        embed = {
            "title": f"🟢 {srv.get('hostname')} is ONLINE",
            "color": 2278750,
            "description": f"**Map:** {srv.get('mapname')} | **Time:** {srv.get('timeleft')} | **Players:** {srv.get('players_count')}\n**Score:** IGI ({srv.get('score_igi')}) - Conspiracy ({srv.get('score_con')})",
            "fields": [
                {"name": "🟦 IGI OPERATIVES", "value": format_team(srv.get('team_igi_players', [])), "inline": False},
                {"name": "🟥 CONSPIRACY", "value": format_team(srv.get('team_con_players', [])), "inline": False}
            ],
            "footer": {"text": "Live Uplink • Auto-updates every 5 mins"}
        }

    payload = {"embeds": [embed]}
    msg_id = read_state(MSG_ID_FILE)

    if msg_id:
        res = requests.patch(f"{WEBHOOK_URL}/messages/{msg_id}", json=payload)
        if res.status_code == 404:
            msg_id = "" # Message deleted, reset

    if not msg_id:
        res = requests.post(f"{WEBHOOK_URL}?wait=true", json=payload)
        if res.status_code in (200, 201):
            write_state(MSG_ID_FILE, res.json().get('id'))

if __name__ == "__main__":
    run_discord_bot()
