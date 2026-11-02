"""Check the publishable file set without printing potentially sensitive matches."""
from pathlib import Path
import re,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
r=subprocess.run(['git','ls-files','-z'],cwd=ROOT,capture_output=True)
if r.returncode==0 and r.stdout:
 files=[ROOT/p for p in r.stdout.decode().split('\0') if p]
else:
 files=[p for p in ROOT.rglob('*') if p.is_file() and not any(x in {'.git','.state','__pycache__','node_modules','.venv'} for x in p.relative_to(ROOT).parts)]
patterns={
 'GitHub credential':re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9_]{25,}|github_pat_[A-Za-z0-9_]{25,})'),
 'API credential':re.compile(r'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{25,}'),
 'AWS credential':re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
 'private key':re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'),
 'personal absolute path':re.compile(r'/(?:Users|home)/[A-Za-z0-9_.-]+/'),
}
problems=[]
for path in files:
 rel=path.relative_to(ROOT);parts=rel.parts
 if any(x in {'.state','backups','secrets','exports'} for x in parts) or path.suffix in {'.sqlite','.sqlite3','.db','.log','.pem','.key'} or (path.name.startswith('.env') and path.name!='.env.example') or path.name=='adapter-key':
  problems.append((str(rel),'runtime data or secret file'));continue
 try:text=path.read_text(encoding='utf-8')
 except (UnicodeError,OSError):continue
 for label,pattern in patterns.items():
  if pattern.search(text):problems.append((str(rel),label))
if problems:
 for file,label in problems:print(f'{file}: {label}',file=sys.stderr)
 raise SystemExit(1)
print(f'Release hygiene: {len(files)} files checked; no forbidden runtime files, known key patterns or personal paths')
