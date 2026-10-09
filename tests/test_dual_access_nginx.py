from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]


def test_ip_and_domain_have_separate_nginx_hosts():
    domain=(ROOT/"nginx/makia-vps-manager.conf").read_text()
    fallback=(ROOT/"nginx/makia-ip-fallback.conf").read_text()
    assert "listen 80 default_server;" not in domain
    assert "listen [::]:80 default_server;" not in domain
    assert "server_name makia.invalid;" in domain
    assert "listen 80 default_server;" in fallback
    assert "listen [::]:80 default_server;" in fallback
    assert "server_name _;" in fallback
    assert "proxy_pass http://127.0.0.1:8787;" in fallback
    assert "server_name _;" not in domain


def test_clean_install_enables_both_sites_and_keeps_port_80_nonguessing():
    installer=(ROOT/"scripts/install.sh").read_text()
    assert 'nginx/makia-ip-fallback.conf' in installer
    assert 'sites-enabled/makia-ip-fallback' in installer
    assert 'nginx -t' in installer
    assert 'makia-enable-ip-panel' in installer
    assert 'MAKIA_PUBLIC_IPV4' in installer
    assert 'ip.is_global' in installer


def test_update_preserves_existing_tls_config_and_only_stages_migration():
    updater=(ROOT/"scripts/update.sh").read_text()
    assert "Preserving active Makia Nginx/Certbot configuration" in updater
    assert 'install_verified_shell "$SRC/scripts/enable-ip-panel.sh"' in updater
    assert 'etc/nginx/sites-available/makia-ip-fallback' in updater
    assert not re.search(r"(?m)^\s*(?:sudo\s+)?makia-enable-ip-panel\s*$",updater)


def test_manual_migration_has_rollback_and_does_not_change_tls():
    code=(ROOT/"scripts/enable-ip-panel.sh").read_text()
    assert "trap restore ERR" in code
    assert 'cp -a "$backup/makia-vps-manager" "$DOMAIN"' in code
    assert 'nginx -t' in code and "systemctl reload nginx" in code
    assert "http://127.0.0.1/healthz" in code
    assert "(?:80|\\[::\\]:80)" in code
    assert "letsencrypt" not in code.lower()
    assert not re.search(r"(?m)^\\s*(?:certbot\\s|\\$\\{?CERTBOT\\}?)",code)
