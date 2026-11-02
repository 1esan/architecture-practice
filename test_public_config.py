"""Publication config is portable and does not depend on a private adapter setup."""
import os,pathlib,subprocess,sys,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parent
class PublicConfigTests(unittest.TestCase):
 def run_server_import(self,**values):
  env=dict(os.environ);env.update(values)
  return subprocess.run([sys.executable,'-B','-c','import server; print(server.ADAPTER_URL); print(server.MODEL); print(server.KEY)'],cwd=ROOT,env=env,capture_output=True,text=True)
 def test_configured_local_adapter_and_key_path(self):
  with tempfile.TemporaryDirectory() as temp:
   key=pathlib.Path(temp)/'adapter-key'
   r=self.run_server_import(TRAINER_ADAPTER_URL='http://127.0.0.1:9999/',TRAINER_MODEL='example-model',TRAINER_ADAPTER_KEY_FILE=str(key))
   self.assertEqual(r.returncode,0,r.stderr);self.assertIn('http://127.0.0.1:9999',r.stdout);self.assertIn('example-model',r.stdout);self.assertIn(str(key),r.stdout)
 def test_external_or_credentialed_adapter_is_rejected(self):
  for url in ['https://example.com','http://user:password@localhost:8766','http://localhost:8766/path','http://localhost:8766/?key=test']:
   with self.subTest(url=url):self.assertNotEqual(self.run_server_import(TRAINER_ADAPTER_URL=url).returncode,0)
 def test_no_private_desktop_key_default(self):
  r=self.run_server_import(TRAINER_ADAPTER_URL='http://127.0.0.1:8766')
  self.assertEqual(r.returncode,0,r.stderr)
  if 'TRAINER_ADAPTER_KEY_FILE' not in os.environ:self.assertIn(str(ROOT/'.state/adapter-key'),r.stdout)
