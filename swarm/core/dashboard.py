from __future__ import annotations

import html
import json
from pathlib import Path
from textwrap import dedent

from swarm.core.agent import Agent
from swarm.core.council import CouncilDecision
from swarm.core.provider_assignment import ProviderAssignment


DEMO_CODE = {
    "coder": "def build_feature(request):\n    validate_request(request)\n    return implement(request)\n",
    "testing": "def test_feature_edge_cases():\n    assert feature_handles_empty_input()\n    assert feature_is_accessible()\n",
    "security": "def audit_change(change):\n    assert no_secrets_leaked(change)\n    assert permissions_are_minimal(change)\n",
    "design": "function renderDarkModeToggle() {\n  return segmentedControl(['Light', 'Dark', 'System']);\n}\n",
    "analytics": "track('feature_decision', { vote: 'proceed', confidence: 96 });\n",
}


def build_dashboard_payload(
    agents: list[Agent],
    council_decision: CouncilDecision | None = None,
    provider_assignments: list[ProviderAssignment] | None = None,
    ab_test: dict | None = None,
) -> dict:
    assignment_by_agent = {}
    for assignment in provider_assignments or []:
        assignment_by_agent.setdefault(assignment.agent_name, assignment)
    return {
        "agents": [
            {
                "name": agent.name,
                "pillar": agent.pillar,
                "category": agent.category,
                "model": (
                    assignment_by_agent[agent.name].model_ref
                    if agent.name in assignment_by_agent
                    else agent.model or "auto-selected"
                ),
                "model_preference": agent.model_preference,
                "provider": assignment_by_agent[agent.name].provider if agent.name in assignment_by_agent else "auto",
                "route_type": assignment_by_agent[agent.name].route_type if agent.name in assignment_by_agent else "auto",
                "selection_rationale": assignment_by_agent[agent.name].rationale if agent.name in assignment_by_agent else "auto-selected",
                "description": agent.description,
                "sub_agent_roles": list(agent.sub_agent_roles),
                "code": DEMO_CODE.get(
                    agent.name,
                    f"# {agent.name}\nreview('{agent.pillar}', '{agent.category}')\n",
                ),
            }
            for agent in agents
        ],
        "provider_assignments": [assignment.to_dict() for assignment in provider_assignments or []],
        "council": _decision_to_payload(council_decision),
        "ab_test": ab_test,
    }


def _decision_to_payload(decision: CouncilDecision | None) -> dict | None:
    if decision is None:
        return None
    return {
        "question": decision.question,
        "verdict": decision.verdict,
        "yes_votes": decision.yes_votes,
        "no_votes": decision.no_votes,
        "confidence": decision.confidence,
        "summary": decision.summary,
        "opinions": [
            {
                "agent": opinion.agent_name,
                "pillar": opinion.pillar,
                "stance": opinion.stance,
                "confidence": opinion.confidence,
                "reasoning": opinion.reasoning,
                "evidence": list(opinion.evidence),
                "risks": list(opinion.risks),
            }
            for opinion in decision.opinions
        ],
    }


def render_dashboard_html(payload: dict) -> str:
    data = json.dumps(payload, ensure_ascii=True)
    return dedent(
        f"""\
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <title>Agent Swarm Real-Time Dashboard</title>
          <style>
            :root {{
              --bg: #101114;
              --panel: #181a20;
              --panel-2: #20232b;
              --line: #343946;
              --text: #f4f6fb;
              --muted: #aab1c0;
              --green: #3ddc97;
              --yellow: #ffd166;
              --red: #ff6b6b;
              --blue: #67b7ff;
              --violet: #b695ff;
            }}
            * {{ box-sizing: border-box; }}
            body {{
              margin: 0;
              min-height: 100vh;
              font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
              background: var(--bg);
              color: var(--text);
            }}
            .shell {{
              display: grid;
              grid-template-columns: 300px minmax(0, 1fr) 360px;
              grid-template-rows: 60px minmax(0, 1fr);
              height: 100vh;
            }}
            header {{
              grid-column: 1 / -1;
              display: flex;
              align-items: center;
              justify-content: space-between;
              padding: 0 20px;
              border-bottom: 1px solid var(--line);
              background: var(--panel);
            }}
            h1 {{ font-size: 18px; margin: 0; letter-spacing: 0; }}
            .metrics {{ display: flex; gap: 18px; color: var(--muted); font-size: 13px; }}
            aside, main, section {{ min-height: 0; overflow: auto; }}
            aside {{ border-right: 1px solid var(--line); background: var(--panel); padding: 12px; }}
            main {{ padding: 16px; }}
            section {{ border-left: 1px solid var(--line); background: var(--panel); padding: 12px; }}
            .pillars {{ display: grid; gap: 10px; }}
            .pillar {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel-2); padding: 10px; }}
            .pillar h2 {{ font-size: 12px; color: var(--muted); text-transform: uppercase; margin: 0 0 8px; letter-spacing: .08em; }}
            .agent {{
              width: 100%;
              display: grid;
              grid-template-columns: 1fr auto;
              gap: 4px;
              border: 1px solid transparent;
              border-radius: 7px;
              padding: 8px;
              margin-top: 6px;
              color: var(--text);
              background: #14161b;
              text-align: left;
              cursor: pointer;
            }}
            .agent:hover, .agent.active {{ border-color: var(--blue); }}
            .agent small {{ color: var(--muted); }}
            .live-graph {{
              position: relative;
              height: 360px;
              border: 1px solid var(--line);
              border-radius: 8px;
              background: #0b0d10;
              overflow: hidden;
              margin-bottom: 12px;
            }}
            #agentGraph {{ width: 100%; height: 100%; display: block; }}
            .graph-toolbar {{
              position: absolute;
              top: 10px;
              left: 10px;
              display: flex;
              gap: 8px;
              z-index: 2;
            }}
            .graph-toolbar button {{
              border: 1px solid var(--line);
              border-radius: 7px;
              background: var(--panel-2);
              color: var(--text);
              padding: 7px 10px;
              cursor: pointer;
            }}
            .graph-toolbar button:hover {{ border-color: var(--blue); }}
            .board {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }}
            .lane {{ min-height: 180px; border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 12px; }}
            .lane h2, section h2 {{ margin: 0 0 10px; font-size: 14px; }}
            .event {{ border-left: 3px solid var(--blue); padding: 8px 10px; margin: 8px 0; background: var(--panel-2); border-radius: 6px; font-size: 13px; }}
            .event.done {{ border-color: var(--green); }}
            .event.vote {{ border-color: var(--yellow); }}
            pre {{
              margin: 12px 0 0;
              min-height: 260px;
              white-space: pre-wrap;
              border: 1px solid var(--line);
              border-radius: 8px;
              padding: 12px;
              background: #0b0d10;
              color: #d8f3dc;
              font: 13px/1.55 "JetBrains Mono", Consolas, monospace;
            }}
            .cursor {{ display: inline-block; width: 7px; height: 15px; background: var(--green); vertical-align: -2px; animation: blink .8s steps(2) infinite; }}
            @keyframes blink {{ 50% {{ opacity: 0; }} }}
            .vote-row {{ border: 1px solid var(--line); border-radius: 7px; padding: 9px; margin: 8px 0; background: var(--panel-2); }}
            .vote-row strong {{ color: var(--green); }}
            .risk {{ color: var(--red); }}
            @media (max-width: 1000px) {{
              .shell {{ grid-template-columns: 1fr; grid-template-rows: auto auto auto auto; height: auto; }}
              header, aside, main, section {{ grid-column: auto; border: 0; }}
              .board {{ grid-template-columns: 1fr; }}
            }}
          </style>
        </head>
        <body>
          <div class="shell">
            <header>
              <h1>Agent Swarm Real-Time Dashboard</h1>
              <div class="metrics">
                <span id="agentCount"></span>
                <span id="modelCount"></span>
                <span id="confidence"></span>
              </div>
            </header>
            <aside>
              <div class="pillars" id="pillars"></div>
            </aside>
            <main>
              <div class="live-graph">
                <div class="graph-toolbar">
                  <button id="playGraph" type="button">Live demo</button>
                  <button id="pauseGraph" type="button">Pause</button>
                </div>
                <canvas id="agentGraph"></canvas>
              </div>
              <div class="board">
                <div class="lane"><h2>Live Work</h2><div id="work"></div></div>
                <div class="lane"><h2>Logic Flow</h2><div id="logic"></div></div>
                <div class="lane"><h2>File Growth</h2><div id="growth"></div></div>
              </div>
              <pre id="code"></pre>
            </main>
            <section>
              <h2>Council Meeting</h2>
              <div id="council"></div>
              <h2>A/B Selection</h2>
              <div id="abTest"></div>
            </section>
          </div>
          <script>
            const payload = {data};
            const pillars = ['code', 'see', 'design', 'act'];
            const byPillar = Object.fromEntries(pillars.map(p => [p, []]));
            payload.agents.forEach(agent => byPillar[agent.pillar].push(agent));
            agentCount.textContent = `${{payload.agents.length}} agents`;
            modelCount.textContent = `${{new Set(payload.agents.map(a => a.model_preference)).size}} model type(s)`;
            confidence.textContent = payload.council ? `${{payload.council.confidence}}% confidence` : 'council ready';

            function renderAgents() {{
              pillars.forEach(pillar => {{
                const box = document.createElement('div');
                box.className = 'pillar';
                box.innerHTML = `<h2>${{pillar}}</h2>`;
                byPillar[pillar].forEach(agent => {{
                  const button = document.createElement('button');
                  button.className = 'agent';
                  button.innerHTML = `<span>${{agent.name}}</span><small>${{agent.model_preference}}</small><small>${{agent.category}}</small>`;
                  button.onclick = () => selectAgent(agent, button);
                  box.appendChild(button);
                }});
                document.getElementById('pillars').appendChild(box);
              }});
            }}

            function selectAgent(agent, button) {{
              document.querySelectorAll('.agent').forEach(el => el.classList.remove('active'));
              button.classList.add('active');
              work.innerHTML = `<div class="event">${{agent.name}} is working on ${{agent.description}}</div>`;
              logic.innerHTML = `<div class="event">pillar: ${{agent.pillar}}</div><div class="event">model type: ${{agent.model_preference}}</div><div class="event">route: ${{agent.route_type}}</div><div class="event">why this AI: ${{agent.selection_rationale}}</div><div class="event">sub-agents: ${{(agent.sub_agent_roles || []).join(', ') || 'none'}}</div>`;
              focusGraphAgent(agent.name);
              typeCode(agent.code);
            }}

            function typeCode(text) {{
              code.textContent = '';
              growth.innerHTML = '<div class="event">0 bytes written</div>';
              let i = 0;
              const timer = setInterval(() => {{
                i += 2;
                code.textContent = text.slice(0, i);
                code.innerHTML = escapeHtml(code.textContent) + '<span class="cursor"></span>';
                growth.innerHTML = `<div class="event done">${{Math.min(i, text.length)}} bytes written</div>`;
                if (i >= text.length) clearInterval(timer);
              }}, 28);
            }}

            function escapeHtml(value) {{
              return value.replace(/[&<>"']/g, char => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[char]));
            }}

            function renderCouncil() {{
              if (!payload.council) {{
                council.innerHTML = '<div class="event">No council decision loaded.</div>';
                return;
              }}
              council.innerHTML = `<div class="event vote">${{payload.council.summary}}</div>`;
              payload.council.opinions.forEach(opinion => {{
                const row = document.createElement('div');
                row.className = 'vote-row';
                const risks = opinion.risks.length ? `<div class="risk">Risks: ${{opinion.risks.join('; ')}}</div>` : '';
                row.innerHTML = `<strong>${{opinion.agent}}</strong> voted ${{opinion.stance}} (${{opinion.confidence}}%)<br>${{opinion.reasoning}}${{risks}}`;
                council.appendChild(row);
              }});
            }}

            function renderABTest() {{
              if (!payload.ab_test) {{
                abTest.innerHTML = '<div class="event">No A/B result loaded.</div>';
                return;
              }}
              abTest.innerHTML = `<div class="event vote">${{payload.ab_test.summary}}</div>`;
              payload.ab_test.candidates.forEach(candidate => {{
                const row = document.createElement('div');
                row.className = 'vote-row';
                const label = candidate.id === payload.ab_test.winner_id ? 'COUNCIL PICK' : 'OTHER VERSION';
                row.innerHTML = `<strong>${{label}} ${{candidate.id}}: ${{candidate.name}}</strong><br>${{candidate.strategy}}<br>Score: ${{candidate.score}}`;
                abTest.appendChild(row);
              }});
            }}

            const graphCanvas = document.getElementById('agentGraph');
            const graphCtx = graphCanvas.getContext('2d');
            const graphState = {{
              nodes: [],
              edges: [],
              activeAgent: '',
              running: true,
              tick: 0,
            }};
            const colors = {{
              code: '#3ddc97',
              see: '#67b7ff',
              design: '#b695ff',
              act: '#ffd166',
            }};

            function resizeGraph() {{
              const rect = graphCanvas.parentElement.getBoundingClientRect();
              graphCanvas.width = Math.max(300, Math.floor(rect.width));
              graphCanvas.height = Math.max(260, Math.floor(rect.height));
              layoutGraph();
            }}

            function layoutGraph() {{
              const w = graphCanvas.width;
              const h = graphCanvas.height;
              if (!w || !h) return;
              const groups = Object.fromEntries(pillars.map(p => [p, payload.agents.filter(a => a.pillar === p)]));
              graphState.nodes = [];
              pillars.forEach((pillar, column) => {{
                const agents = groups[pillar];
                agents.forEach((agent, row) => {{
                  graphState.nodes.push({{
                    agent,
                    x: 95 + column * ((w - 190) / Math.max(1, pillars.length - 1)),
                    y: 74 + row * Math.min(44, (h - 120) / Math.max(1, agents.length)),
                    pulse: 0,
                  }});
                }});
              }});
              const byName = Object.fromEntries(graphState.nodes.map(node => [node.agent.name, node]));
              graphState.edges = [];
              payload.agents.forEach(agent => {{
                (agent.sub_agent_roles || []).forEach(role => {{
                  if (byName[agent.name] && byName[role]) {{
                    graphState.edges.push({{ from: agent.name, to: role, pulse: Math.random() }});
                  }}
                }});
              }});
            }}

            function focusGraphAgent(name) {{
              graphState.activeAgent = name;
              const agent = payload.agents.find(item => item.name === name);
              if (agent) {{
                const provider = agent.provider && agent.provider !== 'auto' ? agent.provider : 'auto provider';
                work.innerHTML += `<div class="event done">provider: ${{provider}} | model: ${{agent.model}}</div>`;
              }}
            }}

            function drawGraph() {{
              const w = graphCanvas.width;
              const h = graphCanvas.height;
              graphCtx.clearRect(0, 0, w, h);
              graphCtx.fillStyle = '#0b0d10';
              graphCtx.fillRect(0, 0, w, h);
              graphCtx.font = '12px Inter, sans-serif';
              graphCtx.fillStyle = '#aab1c0';
              graphCtx.fillText('interactive live agent graph: click an agent or run the live demo', 16, h - 16);
              const byName = Object.fromEntries(graphState.nodes.map(node => [node.agent.name, node]));
              graphState.edges.forEach(edge => {{
                const a = byName[edge.from];
                const b = byName[edge.to];
                if (!a || !b) return;
                const active = edge.from === graphState.activeAgent || edge.to === graphState.activeAgent;
                graphCtx.strokeStyle = active ? 'rgba(61, 220, 151, .75)' : 'rgba(170, 177, 192, .18)';
                graphCtx.lineWidth = active ? 2 : 1;
                graphCtx.beginPath();
                graphCtx.moveTo(a.x, a.y);
                graphCtx.lineTo(b.x, b.y);
                graphCtx.stroke();
                if (active || graphState.running) {{
                  edge.pulse = (edge.pulse + .01) % 1;
                  const px = a.x + (b.x - a.x) * edge.pulse;
                  const py = a.y + (b.y - a.y) * edge.pulse;
                  graphCtx.fillStyle = '#3ddc97';
                  graphCtx.beginPath();
                  graphCtx.arc(px, py, 3.5, 0, Math.PI * 2);
                  graphCtx.fill();
                }}
              }});
              graphState.nodes.forEach(node => {{
                const active = node.agent.name === graphState.activeAgent;
                const radius = active ? 15 + Math.sin(graphState.tick / 10) * 2 : 10;
                graphCtx.fillStyle = colors[node.agent.pillar] || '#aab1c0';
                graphCtx.globalAlpha = active ? 1 : .72;
                graphCtx.beginPath();
                graphCtx.arc(node.x, node.y, radius, 0, Math.PI * 2);
                graphCtx.fill();
                graphCtx.globalAlpha = 1;
                graphCtx.strokeStyle = active ? '#ffffff' : '#343946';
                graphCtx.lineWidth = active ? 2 : 1;
                graphCtx.stroke();
                graphCtx.fillStyle = active ? '#ffffff' : '#d5dae6';
                graphCtx.font = active ? '700 11px Inter, sans-serif' : '10px Inter, sans-serif';
                graphCtx.textAlign = 'center';
                graphCtx.fillText(node.agent.name, node.x, node.y + 27);
                graphCtx.fillStyle = '#aab1c0';
                graphCtx.font = '9px Inter, sans-serif';
                graphCtx.fillText(node.agent.provider || node.agent.model_preference, node.x, node.y + 39);
              }});
              graphState.tick += 1;
              requestAnimationFrame(drawGraph);
            }}

            function advanceLiveDemo() {{
              if (!graphState.running) return;
              const index = graphState.tick % payload.agents.length;
              const agent = payload.agents[index];
              graphState.activeAgent = agent.name;
              work.innerHTML = `<div class="event">${{agent.name}} working via ${{agent.provider}} / ${{agent.model_preference}}</div>`;
              logic.innerHTML = `<div class="event">model: ${{agent.model}}</div><div class="event">route: ${{agent.route_type}}</div><div class="event">why: ${{agent.selection_rationale}}</div><div class="event">sub-agents: ${{(agent.sub_agent_roles || []).join(', ') || 'none'}}</div>`;
              if (index % 4 === 0) typeCode(agent.code);
            }}

            playGraph.onclick = () => {{ graphState.running = true; }};
            pauseGraph.onclick = () => {{ graphState.running = false; }};
            window.addEventListener('resize', resizeGraph);

            renderAgents();
            renderCouncil();
            renderABTest();
            resizeGraph();
            drawGraph();
            setInterval(advanceLiveDemo, 900);
            const first = document.querySelector('.agent');
            if (first) first.click();
          </script>
        </body>
        </html>
        """
    )


def write_dashboard(
    path: str | Path,
    agents: list[Agent],
    council_decision: CouncilDecision | None = None,
    provider_assignments: list[ProviderAssignment] | None = None,
    ab_test: dict | None = None,
) -> Path:
    payload = build_dashboard_payload(agents, council_decision, provider_assignments, ab_test)
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_dashboard_html(payload), encoding="utf-8")
    return output
