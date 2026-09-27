from fastapi import HTTPException
from starlette.requests import Request
from app import main as main_app

def request(method="GET",path="/api/protocols"):
    return Request({"type":"http","method":method,"path":path,"headers":[(b"x-makia-request",b"1")],"query_string":b"","scheme":"https","server":("panel.example",443),"client":("203.0.113.1",1234)})

def test_open_capabilities_still_require_login(monkeypatch):
    monkeypatch.setattr(main_app,"require_user",lambda _: (_ for _ in ()).throw(HTTPException(401,"login required")))
    for capability in ("xray","wireguard","openvpn","nodes","protected_delivery"):
        try: main_app.require_capability(request(),capability)
        except HTTPException as exc: assert exc.status_code==401
        else: raise AssertionError("authentication bypassed")

def test_open_capabilities_use_normal_mutation_protection(monkeypatch):
    monkeypatch.setattr(main_app,"require_mutation",lambda _: (_ for _ in ()).throw(HTTPException(403,"CSRF")))
    for capability in ("xray","wireguard","openvpn","nodes"):
        try: main_app.require_capability(request("POST"),capability,mutation=True)
        except HTTPException as exc: assert exc.status_code==403
        else: raise AssertionError("mutation protection bypassed")

def test_all_capabilities_available_to_local_admin(monkeypatch):
    monkeypatch.setattr(main_app,"require_user",lambda _:"admin")
    for capability in ("xray","wireguard","openvpn","nodes","protected_delivery"):
        assert main_app.require_capability(request(),capability)=="admin"
