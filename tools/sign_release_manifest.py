#!/usr/bin/env python3
"""Offline project attestation over FINAL signed installer bytes. Never publishes."""
import argparse,base64,hashlib,importlib.util,json,re
from pathlib import Path
from cryptography.hazmat.primitives import serialization
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('agent',root/'agent/win/couchsided-win.py')
agent=importlib.util.module_from_spec(spec);spec.loader.exec_module(agent)
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--installer',type=Path,required=True)
 p.add_argument('--version',required=True,help='Stable Windows version, e.g. 0.4.16-win')
 p.add_argument('--key',type=Path,required=True,help='Local Ed25519 PEM. Never upload to CI/repository.')
 p.add_argument('--out',type=Path,required=True)
 args=p.parse_args()
 if agent._release_version(args.version) is None:p.error('stable version required')
 if args.installer.name!='CouchsideSetup.exe':p.error('expected final CouchsideSetup.exe')
 key=serialization.load_pem_private_key(args.key.read_bytes(),password=None)
 public=key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw).hex()
 if public!=agent._UPDATE_RELEASE_PUBLIC_KEY:p.error('private key does not match pinned project public key')
 h=hashlib.sha256()
 with args.installer.open('rb') as f:
  for chunk in iter(lambda:f.read(65536),b''):h.update(chunk)
 digest=h.hexdigest();tag='v'+args.version
 payload={'schema':1,'repository':'emerytech/couchside-windows','tag':tag,'version':args.version,'asset':'CouchsideSetup.exe','sha256':digest}
 raw=json.dumps(payload,sort_keys=True,separators=(',',':')).encode('ascii')+b'\n'
 sig=base64.b64encode(key.sign(raw))+b'\n'
 agent._verify_release_manifest(raw,sig,tag,args.version,digest)
 args.out.mkdir(parents=True,exist_ok=True)
 # Never overwrite an earlier attestation accidentally.
 for name,data in [('CouchsideRelease.json',raw),('CouchsideRelease.json.sig',sig)]:
  with (args.out/name).open('xb') as f:f.write(data)
 print('Created local project attestation. This does not verify Authenticode, approve signing, or publish a release.')
if __name__=='__main__':main()
