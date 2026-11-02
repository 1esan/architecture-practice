import pathlib,sqlite3,tempfile,unittest
from unittest.mock import patch
import server

class DatabaseLifecycleTests(unittest.TestCase):
 def test_connection_commits_and_closes_on_exit(self):
  with tempfile.TemporaryDirectory() as temp,patch.object(server,'DB',pathlib.Path(temp)/'state.sqlite3'):
   with server.connect() as db:
    db.execute('CREATE TABLE example(value TEXT)')
    db.execute('INSERT INTO example VALUES(?)',('saved',))
   with self.assertRaises(sqlite3.ProgrammingError):db.execute('SELECT 1')
   with server.connect() as check:self.assertEqual(check.execute('SELECT value FROM example').fetchone()[0],'saved')
   server.DB.unlink()
 def test_exception_rolls_back_and_closes(self):
  with tempfile.TemporaryDirectory() as temp,patch.object(server,'DB',pathlib.Path(temp)/'state.sqlite3'):
   with server.connect() as db:db.execute('CREATE TABLE example(value TEXT)')
   with self.assertRaisesRegex(RuntimeError,'rollback'):
    with server.connect() as failed:
     failed.execute('INSERT INTO example VALUES(?)',('discard',))
     raise RuntimeError('rollback')
   with self.assertRaises(sqlite3.ProgrammingError):failed.execute('SELECT 1')
   with server.connect() as check:self.assertEqual(check.execute('SELECT COUNT(*) FROM example').fetchone()[0],0)
   server.DB.unlink()
