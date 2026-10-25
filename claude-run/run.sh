#!/usr/bin/env bash
# One run of the name keychain lab (SolidCraft for Beginners #10) = ONE fresh headless Claude Code session against SolidCraft
# 0.22.1, in a NEW empty folder, with the prompt below.
#   bash claude-run/run.sh RUN_ID
# Claude Code --stdio--> docker run -i ... [mcp_log_proxy.py --stdio--> solidcraft-cli mcp]; every JSON-RPC line is in
# transcript.jsonl, Claude Code's own stream in session.jsonl. Sealed like the three-way lab: no session persistence,
# auto memory off, CLAUDE.md files outside the folder excluded, user settings not loaded, only the solidcraft tools,
# no built-in tools, tool search off; prerun-files.txt + instructions-loaded.jsonl record it. Host paths -> $LAB.
set -euo pipefail
RUN=$1
cd "$(dirname "$0")/.."
LAB="$(pwd -W 2>/dev/null || pwd)"
S=out/runs/run-$RUN; W="$S/work"
LEDGER="${LEDGER:-$LAB/../ai-cad-set-BUDGET.tsv}"
MODEL="${MODEL:-claude-sonnet-5-5}"
BUDGET="${BUDGET:-1.00}"
[ -e "$S/meta.json" ] && { echo "refusing to overwrite $S"; exit 3; }
python claude-run/budget.py check "$LEDGER" "$BUDGET" || { echo "BUDGET STOP"; exit 2; }
mkdir -p "$W"
true
python claude-run/prerun.py "$W" > "$S/prerun-files.txt" 2>&1 || true
PROMPT="Use the solidcraft MCP tools. Make a keychain tag 50 x 20 mm with the name ALEX and a smaller second row of text, GYM BAG, for a printer with a 0.4 mm nozzle. Save the design to /lab/work/tag.solidcraft."
printf '%s\n' "$PROMPT" > "$S/prompt.txt"
NAME="nametag-$RUN-$$"
cat > "$S/mcp-config.json" <<JSON
{"mcpServers": {"solidcraft": {"command": "docker", "args": ["run", "-i", "--rm", "--name", "$NAME", "-v", "$LAB/proxy:/proxy:ro", "-v", "$LAB/$W:/lab/work", "-v", "$LAB/$S:/lab/log", "solidcraft-nametag-lab:0.22.1", "python3", "/proxy/mcp_log_proxy.py", "--log", "/lab/log/transcript.jsonl", "--png-dir", "/lab/log", "--watchdog", "300", "--", "solidcraft-cli", "mcp", "--allow-path", "/lab/work"]}}}
JSON
HOOKLOG="$LAB/$S/instructions-loaded.jsonl"
SETTINGS=$(python - "$HOOKLOG" <<'PY'
import json, sys
log = sys.argv[1].replace(chr(92), '/')
print(json.dumps({"claudeMdExcludes": ["**/.claude/CLAUDE.md"],
                  "autoMemoryEnabled": False,
                  "hooks": {"InstructionsLoaded": [{"hooks": [{"type": "command",
                            "command": f"python -c \"import sys; open(r'{log}', 'a').write(sys.stdin.read() + chr(10))\""}]}]}}))
PY
)
T0=$(date +%s)
set +e
( cd "$W" && MSYS_NO_PATHCONV=1 CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 ENABLE_TOOL_SEARCH=false timeout 1200 \
    "${CLAUDE:-claude}" -p "$PROMPT" --model "$MODEL" \
    --mcp-config "$LAB/$S/mcp-config.json" --strict-mcp-config \
    --tools "" --allowedTools "mcp__solidcraft__*" --permission-mode dontAsk \
    --max-budget-usd "$BUDGET" --no-session-persistence \
    --setting-sources project,local --settings "$SETTINGS" \
    --output-format stream-json --verbose < /dev/null > "$LAB/$S/session.jsonl" )
RC=$?
set -e
docker kill "$NAME" >/dev/null 2>&1 || true
COST=$(python -c "import json,sys
c=''
for l in open(sys.argv[1], encoding='utf-8'):
    try: d=json.loads(l)
    except Exception: continue
    if d.get('type')=='result': c=d.get('total_cost_usd','')
print(c)" "$S/session.jsonl")
python claude-run/budget.py record "$LEDGER" "nametag-run-$RUN" "$COST" "$BUDGET" go25-nametag
echo "{\"run\": \"$RUN\", \"exit\": $RC, \"wall_s\": $(( $(date +%s) - T0 )), \"cost\": \"${COST:-killed}\", \"model\": \"$MODEL\", \"claude_version\": \"$(${CLAUDE:-claude} --version | head -1)\", \"solidcraft\": \"0.22.1\"}" > "$S/meta.json"
python claude-run/scrub.py "$S"
cat "$S/meta.json"
