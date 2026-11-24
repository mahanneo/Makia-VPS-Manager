from contextlib import ExitStack
from unittest.mock import patch,Mock
from fastapi import HTTPException
import app.main as m

def run(fail=False):
 with ExitStack() as s:
  def p(obj,name,value):return s.enter_context(patch.object(obj,name,value))
  p(m,'require_mutation',lambda request:'admin');p(m,'require_local_admin',lambda request:'admin')
  p(m,'audit',Mock());p(m,'ip',lambda request:'local')
  p(m.client_store,'account_by_username',lambda n:None)
  p(m.client_store,'create_account',Mock(return_value=222))
  deleted=p(m.client_store,'delete_account',Mock())
  bindp=p(m.client_store,'bind_protocol_client',Mock())
  binda=p(m.client_store,'bind_access_artifact',Mock())
  p(m.client_store,'account_admin_snapshot',lambda n:{'id':n})
  p(m.protocol_ops,'openvpn_policy_status',lambda:{'ready':True})
  p(m.integration_ops,'outline_status',lambda:{'api_ok':True,'keys':[]})
  p(m.integration_ops,'outline_transfer_metrics',lambda:{})
  p(m,'_unified_xray_targets',lambda:{'ws443':'vless443','iran_xhttp':'iran2053','vless':'v','vmess':'m','trojan':'t'})
  p(m.protocol_ops,'vmess_public_443_link',lambda link,host:link)
  p(m.protocol_ops,'trojan_grpc_public_443_link',lambda link,host:link)
  p(m,'get_setting',lambda k,d='':'example.test' if k=='panel_domain' else d)
  p(m.protocol_ops,'validate_endpoint_selection',lambda x,*args,**kw:x)
  p(m,'get_profile',lambda n:None)
  p(m,'get_access_artifact_by_key',lambda k,n:None)
  p(m,'list_protocol_clients',lambda:[])
  p(m.protocol_ops,'list_wireguard_peers',lambda:[])
  batchcalls=[]
  def batch(entries,endpoint='',remove=False):
   batchcalls.append(('remove' if remove else 'create',len(entries)))
   if remove:return [{'removed':True}]
   return [dict(x,protocol=protocol,credential='safecredential',share_link='test://link',port=20000+i,transport='tcp',security='tls') for i,(x,protocol) in enumerate(zip(entries,('vless','vless','vless','vmess','trojan')))]
  p(m.protocol_ops,'batch_xray_client_change',batch)
  count=[0]
  def createpc(*args):count[0]+=1;return count[0]
  p(m,'create_protocol_client',createpc)
  p(m,'get_protocol_client',lambda ident:{'subscription_id':'subtest'})
  p(m,'operator_settings_snapshot',lambda:{'subscription':{'enabled':True,'client_page_enabled':True,'default_format':'base64'}})
  p(m,'artifact_save',lambda *args,**kw:111)
  p(m,'public_origin',lambda req:'https://example.test')
  p(m,'wireguard_peer_create',lambda *args:{'artifact_id':222,'public_key':'mock-key'})
  p(m,'openvpn_client_create',lambda *args:{'artifact_id':333})
  ports=[]
  def create_outline(payload,request):
   ports.append(payload.port)
   return {'id':str(len(ports)),'client_id':440+len(ports),'artifact_id':450+len(ports)}
  p(m,'outline_key_create',create_outline)
  p(m,'create_account',Mock(side_effect=RuntimeError('injected final SSH failure')) if fail else Mock(return_value={'artifact_id':555}))
  p(m,'delete_access_artifact_by_key',Mock());p(m,'delete_protocol_client',Mock())
  p(m.protocol_ops,'remove_wireguard_peer',Mock())
  p(m.protocol_ops,'revoke_openvpn_client',Mock())
  p(m.integration_ops,'outline_delete_key',Mock())
  p(m.system_ops,'delete_user',Mock());p(m.system_ops,'lock_user',Mock());p(m,'delete_profile',Mock())
  try:
   out=m.unified_client_provision(m.UnifiedClientProvision(username='testbatch',quota_gb=10,expire_days=20),Mock())
   assert not fail
   assert len(out['protocols'])==12 and bindp.call_count==9 and binda.call_count==3
   assert batchcalls==[('create',5)] and ports==[0,2083,2096,1080]
   print('PASS full success: 12 accesses, all three additional SS ports, one Xray batch')
  except HTTPException as e:
   assert fail and e.status_code==500
   assert deleted.called and batchcalls==[('create',5),('remove',5)]
   assert m.integration_ops.outline_delete_key.call_count==4
   print('PASS late failure: single Xray rollback batch')
run();run(True)
