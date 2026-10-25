"""Before a session: list the session folder and every CLAUDE.md / CLAUDE.local.md / AGENTS.md in it, above it, and in
the user's ~/.claude (excluded by claudeMdExcludes, listed so the log shows it was there and not loaded).
    python claude-run/prerun.py WORKDIR"""
import os, sys
w = os.path.abspath(sys.argv[1])
print('folder:', sorted(os.listdir(w)))
names = {'claude.md', 'claude.local.md', 'agents.md'}
d = w
found = []
while True:
    for f in os.listdir(d):
        if f.lower() in names:
            found.append(os.path.join(d, f).replace(os.path.expanduser('~'), '~'))
    p = os.path.dirname(d)
    if p == d:
        break
    d = p
u = os.path.join(os.path.expanduser('~'), '.claude')
if os.path.isdir(u):
    found += ['~/.claude/' + f + ' (user level: excluded by claudeMdExcludes)' for f in os.listdir(u) if f.lower() in names]
print('instruction files found:', found)
