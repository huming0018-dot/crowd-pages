import importlib.util
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile

BASE=Path(__file__).resolve().parent
PAGES=BASE


class Builder(unittest.TestCase):
    def test_real_builder_packages_helpers_with_integrity_list_not_sdk(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); tree=root/'v4'; (tree/'participant').mkdir(parents=True)
            for item in (PAGES/'participant').iterdir():
                if item.is_file():shutil.copyfile(item,tree/'participant'/item.name)
            for name in ['prepare-pro-dependencies.py','prepare-and-configure-pro.py','install.command']:
                shutil.copyfile(BASE/'participant'/name,tree/'participant'/name)
            shutil.copyfile(BASE/'build_participant.py',tree/'build_participant.py')
            spec=importlib.util.spec_from_file_location('candidate_builder',tree/'build_participant.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            extension_input=Path(os.environ['CROWD_PARTICIPANT_EXTENSION'])
            helper_input=Path(os.environ['CROWD_PARTICIPANT_HELPER'])
            ext=root/'extension.zip'
            shutil.copyfile(extension_input,ext)
            helper=root/'helper';shutil.copyfile(helper_input,helper);helper.chmod(0o700)
            runtime=root/'runtime';runtime.mkdir();(runtime/'participant_pro_native.py').write_bytes(b'fixture own adapter')
            (runtime/'portable_node.py').write_bytes((BASE/'participant/portable_node.py').read_bytes())
            (runtime/'PRO-RUNTIME.json').write_text(json.dumps({'schema':'crowd-participant-pro-runtime-v1','files':{name:hashlib.sha256((runtime/name).read_bytes()).hexdigest() for name in ('participant_pro_native.py','portable_node.py')}}))
            output=root/'installer.zip';module.build(ext,helper,output,runtime)
            with zipfile.ZipFile(output) as archive:
                for name in ['prepare-pro-dependencies.py','prepare-and-configure-pro.py']:
                    key='.crowd-support/'+name
                    self.assertEqual(archive.read(key),(BASE/'participant'/name).read_bytes())
                    self.assertIn(name,archive.read('.crowd-support/INSTALL-SHA256.txt').decode())
                self.assertFalse(any('uv.lock' in n or 'pyvenv.cfg' in n or 'browser_data' in n for n in archive.namelist()))


if __name__=='__main__':unittest.main()
