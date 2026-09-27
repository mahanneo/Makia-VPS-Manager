import pytest

from app import panel_ops
from app.panel_ops import validate_domain, PanelOperationError


def test_valid_domain_normalized():
    assert validate_domain("Panel.Example.COM.") == "panel.example.com"


@pytest.mark.parametrize("value", ["localhost", "bad_domain.com", "http://example.com", ""])
def test_invalid_domain_rejected(value):
    with pytest.raises(PanelOperationError):
        validate_domain(value)


def test_apply_domain_updates_all_makia_server_blocks(monkeypatch,tmp_path):
    site=tmp_path/"makia-vps-manager"
    site.write_text(
        "server {\n    listen 80;\n    server_name old.example.com;\n}\n"
        "server {\n    listen 443 ssl;\n    server_name old.example.com;\n}\n",
        encoding="utf-8",
    )
    calls=[]
    monkeypatch.setattr(panel_ops,"NGINX_SITE",site)
    monkeypatch.setattr(panel_ops,"_run",lambda args,timeout=120:calls.append(list(args)) or "")
    monkeypatch.setattr(panel_ops,"domain_status",lambda domain:{"domain":domain})
    result=panel_ops.apply_domain("Panel.Example.com")
    text=site.read_text(encoding="utf-8")
    assert text.count("server_name panel.example.com;")==2
    assert ["nginx","-t"] in calls
    assert ["systemctl","reload","nginx"] in calls
    assert result["domain"]=="panel.example.com"


def test_issue_certificate_rejects_dns_mismatch_before_certbot(monkeypatch,tmp_path):
    site=tmp_path/"makia-vps-manager"
    site.write_text("server { server_name _; }\n",encoding="utf-8")
    monkeypatch.setattr(panel_ops,"NGINX_SITE",site)
    monkeypatch.setattr(panel_ops,"domain_status",lambda domain:{
        "resolved_ipv4":["203.0.113.20"],"local_ipv4":["198.51.100.10"],"dns_matches_server":False,
    })
    monkeypatch.setattr(panel_ops,"_run",lambda *args,**kwargs:pytest.fail("no command should run on DNS mismatch"))
    with pytest.raises(PanelOperationError,match="does not point"):
        panel_ops.issue_certificate("panel.example.com","admin@example.com")


def test_issue_certificate_applies_domain_and_verifies_https(monkeypatch,tmp_path):
    site=tmp_path/"makia-vps-manager"
    site.write_text("server {\n    listen 80;\n    server_name _;\n}\n",encoding="utf-8")
    monkeypatch.setattr(panel_ops,"NGINX_SITE",site)
    calls=[]
    monkeypatch.setattr(panel_ops,"_run",lambda args,timeout=120:calls.append(list(args)) or "")
    monkeypatch.setattr(panel_ops.shutil,"which",lambda name:f"/usr/bin/{name}")
    states=iter([
        {"resolved_ipv4":["198.51.100.10"],"local_ipv4":["198.51.100.10"],"dns_matches_server":True},
        {"domain":"panel.example.com"},
        {"resolved_ipv4":["198.51.100.10"],"local_ipv4":["198.51.100.10"],"dns_matches_server":True,
         "certificate":True,"https_listener":True,"certificate_days_left":89},
    ])
    monkeypatch.setattr(panel_ops,"domain_status",lambda domain:next(states))
    result=panel_ops.issue_certificate("panel.example.com","admin@example.com")
    assert "server_name panel.example.com;" in site.read_text(encoding="utf-8")
    certbot=[x for x in calls if x and x[0]=="certbot"]
    assert certbot and "--redirect" in certbot[0]
    assert result["certificate"] is True
    assert result["https_listener"] is True


def test_issue_certificate_rolls_back_nginx_on_certbot_failure(monkeypatch,tmp_path):
    site=tmp_path/"makia-vps-manager"
    original="server {\n    listen 80;\n    server_name old.example.com;\n}\n"
    site.write_text(original,encoding="utf-8")
    monkeypatch.setattr(panel_ops,"NGINX_SITE",site)
    monkeypatch.setattr(panel_ops.shutil,"which",lambda name:f"/usr/bin/{name}")
    monkeypatch.setattr(panel_ops,"domain_status",lambda domain:{
        "resolved_ipv4":["198.51.100.10"],"local_ipv4":["198.51.100.10"],"dns_matches_server":True,
    })
    def run(args,timeout=120):
        if args and args[0]=="certbot":
            raise PanelOperationError("challenge failed")
        return ""
    monkeypatch.setattr(panel_ops,"_run",run)
    with pytest.raises(PanelOperationError,match="challenge failed"):
        panel_ops.issue_certificate("panel.example.com","admin@example.com")
    assert site.read_text(encoding="utf-8")==original
