"""Collect installed dependency notices next to a local portable build."""
import importlib.metadata as metadata
import json
from pathlib import Path
import shutil
import sys

out=Path('dist/licenses');out.mkdir(parents=True,exist_ok=True)
manifest=[]
for dist in metadata.distributions():
 name=dist.metadata.get('Name','unknown')
 if name=='pip':continue
 dest=out/name
 count=0
 for file in dist.files or []:
  if any(part.lower().startswith(('license','copying','notice','authors')) for part in file.parts):
   source=Path(dist.locate_file(file))
   if source.is_file():
    dest.mkdir(parents=True,exist_ok=True)
    target=dest/('-'.join(file.parts[-3:]))
    shutil.copyfile(source,target);count+=1
 manifest.append({'name':name,'version':dist.version,'notice_files':count,
                  'license':dist.metadata.get('License-Expression') or dist.metadata.get('License','See included notices')})
base=Path(sys.base_prefix)
for source,name in [(base/'LICENSE.txt','Python-LICENSE.txt'),(base/'tcl/tk8.6/license.terms','TclTk-license.terms')]:
 if source.exists():shutil.copyfile(source,out/name)
shutil.copyfile('computer_connect/assets/SpaceMono-OFL.txt',out/'SpaceMono-OFL.txt')
Path('dist/dependencies.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
for file in ('README.md','LICENSE','THIRD_PARTY.md'):
 shutil.copyfile(file,Path('dist')/file)
