"""Replace host paths and the host user name in a session's text logs (they are committed; the lab may be published).
    python claude-run/scrub.py SESSION_DIR
The lab folder becomes $LAB; any other path under the user's home becomes ~ ; the user name itself becomes 'you'."""
import os
import re
import sys

BS = chr(92)   # a backslash, spelled out so no shell or editor can eat it

d = sys.argv[1]
lab = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
home = os.path.expanduser('~')
user = os.path.basename(home)
forms = []
for p, rep in ((lab, '$LAB'), (home, '~')):
    for q in {p, p.replace(BS, '/'), p.replace('/', BS)}:
        forms += [(q.replace(BS, BS + BS), rep), (q, rep)]
forms.sort(key=lambda x: -len(x[0]))
n = 0
for root, _, files in os.walk(d):
    for f in files:
        if not f.endswith(('.json', '.jsonl', '.txt', '.log')):
            continue
        fp = os.path.join(root, f)
        s = open(fp, encoding='utf-8', errors='surrogateescape').read()
        t = s
        for a, b in forms:
            t = re.sub(re.escape(a), lambda _m: b, t, flags=re.IGNORECASE)
        t = re.sub(r'(?i)\b' + re.escape(user) + r'\b', 'you', t)
        if t != s:
            open(fp, 'w', encoding='utf-8', errors='surrogateescape', newline='').write(t)
            n += 1
print(f'scrubbed {n} files in {d}')
