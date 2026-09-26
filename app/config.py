from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("MAKIA_DATA_DIR", os.getenv("DRAGON_DATA_DIR", BASE_DIR / "data")))
DB_PATH = Path(os.getenv("MAKIA_DB_PATH", os.getenv("DRAGON_DB_PATH", DATA_DIR / "makia.db")))
SECRET_PATH = Path(os.getenv("MAKIA_SECRET_PATH", os.getenv("DRAGON_SECRET_PATH", DATA_DIR / ".secret")))
COOKIE_NAME = "makia_session"
SESSION_TTL_SECONDS = 60 * 60 * 12
APP_NAME = "Makia VPS Manager"
VERSION = "0.17.0-rc2"
ALLOWED_SERVICES = {
    "ssh": "OpenSSH",
    "nginx": "Nginx",
    "stunnel4": "Stunnel",
    "fail2ban": "Fail2ban",
    "xray": "Xray",
    "openvpn-server@server": "OpenVPN",
    "wg-quick@wg0": "WireGuard",
    "makia-policy-enforcer": "Policy Enforcer",
    "makia-metrics-sampler": "Metrics Sampler",
    "makia-protocol-traffic": "Protocol Traffic Collector",
}
