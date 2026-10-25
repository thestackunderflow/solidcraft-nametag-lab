"""Record SolidCraft 0.22.0's own docs for the commands this probe uses (list_commands), to out/p4-commands.json.

    docker run --rm -v <probe>:/w -v <probe>/out:/lab/out -w /w solidcraft-tipping-lab:0.22.0 python3 explore_cmds.py"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcp_client import McpClient  # noqa: E402

WANT = ('sketch.text', 'sketch.edit_text', 'solid.emboss', 'solid.hole', 'solid.box', 'sketch.edit', 'sketch.finish')
m = McpClient(['solidcraft-cli', 'mcp', '--allow-path', '/lab/out'], timeout_s=120)
m.start()
r = m.call_tool('list_commands', {})
t = '\n'.join(b.get('text', '') for b in r.get('content', []) if b.get('type') == 'text')
cmds = json.loads(t)
lst = cmds if isinstance(cmds, list) else cmds.get('commands', [])
keep = {c['id']: c for c in lst if c.get('id') in WANT}
out = {'server': m.init_result.get('serverInfo'), 'n_commands': len(lst), 'commands': keep}
with open('/lab/out/p4-commands.json', 'w', encoding='utf-8', newline='\n') as f:
    json.dump(out, f, indent=1)
print(json.dumps(out, indent=1))
m.close()
