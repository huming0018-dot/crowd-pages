"""Same expected URL against baseline and candidate; transport is synthetic."""
import importlib.util,inspect,json,os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
path=Path(os.environ.get('DEPENDENCY_SOURCE',str(Path(__file__).parent/'participant/prepare-pro-dependencies.py')))
s=importlib.util.spec_from_file_location('deps_url',path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Response:
 status=200
 def __enter__(self):return self
 def __exit__(self,*a):pass
 def read(self,n):return b'{"isok":true,"biz_code":0,"data":{"message":"pong"}}'
calls=[]
with patch.object(m.urllib.request,'build_opener',return_value=SimpleNamespace(open=lambda url,**kw:(calls.append(url)or Response()))):
 if len(inspect.signature(m.signer_health).parameters):m.signer_health('http://127.0.0.1:8990')
 else:m.signer_health()
assert calls==['http://127.0.0.1:8990/signsrv/pong'],calls
print('exact original binding URL preserved; no real HTTP')
