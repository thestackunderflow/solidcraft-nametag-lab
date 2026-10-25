"""SolidCraft 0.22.1 model renders of the probe tags for the video (headless, software GPU). No AI.
    docker run --rm -v "$PWD:/work" -w /work solidcraft-nametag-lab:0.22.1 python3 video/renders.py"""
import json
import os
import sys

LAB = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, LAB)
from mcp_client import McpClient  # noqa: E402

OUT = os.path.join(LAB, 'video', 'renders')
CAMS = {'top': {'target': [0, 0, 3], 'yaw': -1.5708, 'pitch': 1.5, 'distance': 75},
        'tilt': {'target': [0, 0, 3], 'yaw': -1.25, 'pitch': 0.55, 'distance': 80}}
m = McpClient(['solidcraft-cli', 'mcp', '--allow-path', LAB], timeout_s=240)
m.start()
log = []
try:
    for case in ('raised-h2', 'raised-h3', 'engraved-h2', 'engraved-h3'):
        r = m.call_tool('open', {'path': f'{LAB}/out/{case}/tag.solidcraft'})
        for name, cam in CAMS.items():
            p = f'{OUT}/{case}-{name}.png'
            r = m.call_tool('screenshot', {'path': p, 'width': 1600, 'height': 1000, 'grid': False, 'axes': False, 'camera': cam})
            log.append({'png': os.path.basename(p), 'isError': r.get('isError', False)})
finally:
    m.close()
json.dump(log, open(f'{OUT}/renders.json', 'w'), indent=1)
print(log)
