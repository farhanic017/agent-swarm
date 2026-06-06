from __future__ import annotations

import math
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
MP4 = EXAMPLES / "agent_swarm_live_demo.mp4"
GIF = EXAMPLES / "agent_swarm_live_demo.gif"
POSTER = EXAMPLES / "agent_swarm_live_demo_poster.png"

WIDTH = 1280
HEIGHT = 720
FPS = 15
DURATION = 60
TOTAL_FRAMES = FPS * DURATION

BG = (8, 13, 23)
PANEL = (17, 24, 39)
PANEL_2 = (24, 35, 54)
TEXT = (240, 247, 255)
MUTED = (148, 163, 184)
GREEN = (34, 197, 94)
BLUE = (56, 189, 248)
AMBER = (251, 191, 36)
PINK = (244, 114, 182)
PURPLE = (167, 139, 250)
RED = (248, 113, 113)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


F_TITLE = font(52, True)
F_H1 = font(38, True)
F_H2 = font(26, True)
F_BODY = font(21)
F_SMALL = font(17)
F_MONO = font(19)
F_TINY = font(14)


AGENTS = [
    ("triage", "act", AMBER),
    ("hermes", "act", PURPLE),
    ("coder", "code", GREEN),
    ("security", "code", RED),
    ("testing", "code", BLUE),
    ("researcher", "see", BLUE),
    ("analytics", "see", GREEN),
    ("frontend_ui", "design", PINK),
    ("backend_maker", "code", GREEN),
    ("web_scraper", "see", BLUE),
    ("job_finder", "act", AMBER),
    ("building_designer", "design", PINK),
    ("animator", "design", PURPLE),
    ("hallucination_guard", "act", RED),
    ("n8n_workflow", "act", GREEN),
    ("game_developer", "code", BLUE),
    ("social_manager", "act", AMBER),
    ("photo_editor", "see", PINK),
    ("video_editor", "see", PURPLE),
    ("voice_transcriber", "see", BLUE),
    ("voice_generator", "design", GREEN),
    ("legal", "act", AMBER),
    ("finance", "act", GREEN),
    ("council_master", "act", PURPLE),
]

FEATURES = [
    "20+ agents", "4 pillars", "always-on council", "A/B voting", "real-time dashboard",
    "live code typing", "sub-agents", "provider fallback", "local/MCP/cloud", "OpenCode/Qwen/Mistral/Kimi",
    "browser control", "web scraper", "job applier", "app builder", "backend maker", "app tester",
    "image/video generation", "Google Flow", "Omni", "Veo", "Recraft", "Kling", "NVIDIA", "Zyphra", "Hugging Face", "Alibaba", "Perplexity", "Microsoft",
    "photo/video editors", "voice STT/TTS", "Figma + Blender", "heavy 3D models", "mockup video",
    "building design", "temporary vision", "benchmark charts", "temporary skills", "MCP marketplace", "Graphify", "Obsidian",
    "scoped file security", "AI reviewer", "XSS checks", "/compact memory", "hallucination recovery", "n8n workflows",
    "game developer", "social poster/manager", "Hermes self-evolution",
]


def ease(value: float) -> float:
    return 0.5 - math.cos(max(0.0, min(1.0, value)) * math.pi) / 2


def draw_round(draw: ImageDraw.ImageDraw, xy, radius: int, fill, outline=None, width: int = 1):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def draw_text(draw: ImageDraw.ImageDraw, xy, text: str, fill=TEXT, fnt=F_BODY, anchor=None):
    draw.text(xy, text, fill=fill, font=fnt, anchor=anchor)


def fit_text(draw: ImageDraw.ImageDraw, text: str, max_width: int, fnt=F_BODY) -> str:
    words = text.split()
    lines: list[str] = []
    line = ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=fnt)[2] <= max_width:
            line = candidate
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return "\n".join(lines)


def base_frame(frame: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)
    for x in range(0, WIDTH, 64):
        shade = 18 + int(8 * math.sin((frame + x) / 70))
        draw.line((x, 0, x, HEIGHT), fill=(shade, shade + 6, shade + 16))
    for y in range(0, HEIGHT, 64):
        draw.line((0, y, WIDTH, y), fill=(15, 23, 38))
    draw.rectangle((0, 0, WIDTH, 72), fill=(10, 16, 28))
    draw_text(draw, (34, 20), "Agent Swarm v8", fnt=F_H2)
    draw_text(draw, (1110, 23), "16:9 live demo", fill=MUTED, fnt=F_SMALL)
    return img, draw


def draw_progress(draw: ImageDraw.ImageDraw, frame: int):
    pct = frame / max(1, TOTAL_FRAMES - 1)
    draw_round(draw, (34, 675, 1246, 690), 7, (15, 23, 42))
    draw_round(draw, (34, 675, 34 + int(1212 * pct), 690), 7, BLUE)
    draw_text(draw, (34, 648), "council -> agents -> providers -> dashboard -> tools -> review -> Hermes memory", fill=MUTED, fnt=F_SMALL)


def draw_chips(draw: ImageDraw.ImageDraw, frame: int):
    offset = int((frame * 3) % 420)
    x = 38 - offset
    y = 606
    for idx, feature in enumerate(FEATURES + FEATURES[:8]):
        w = 18 + draw.textbbox((0, 0), feature, font=F_TINY)[2]
        color = [GREEN, BLUE, AMBER, PINK, PURPLE][idx % 5]
        if 34 <= x and x + w <= WIDTH - 34:
            draw_round(draw, (x, y, x + w, y + 28), 14, (18, 27, 45), color)
            draw_text(draw, (x + 9, y + 6), feature, fill=TEXT, fnt=F_TINY)
        x += w + 10


def panel(draw, xy, title: str, body: list[str], accent=BLUE):
    x1, y1, x2, y2 = xy
    draw_round(draw, xy, 14, PANEL, (50, 65, 90), 1)
    draw.rectangle((x1, y1, x1 + 6, y2), fill=accent)
    draw_text(draw, (x1 + 22, y1 + 18), title, fnt=F_H2)
    y = y1 + 58
    for line in body:
        draw_text(draw, (x1 + 24, y), line, fill=MUTED if line.startswith("-") else TEXT, fnt=F_SMALL)
        y += 28


def scene_intro(draw, local: int):
    alpha = ease(local / (5 * FPS))
    draw_text(draw, (70, 138), "Multi-agent work, visible end to end", fnt=F_TITLE)
    draw_text(draw, (74, 212), "Every request runs council review, smart routing, sub-agents, live dashboards, security checks, and Hermes skill evolution.", fill=MUTED, fnt=F_BODY)
    for i, (label, color) in enumerate([("CODE", GREEN), ("SEE", BLUE), ("DESIGN", PINK), ("ACT", AMBER)]):
        x = 84 + i * 288
        draw_round(draw, (x, 330, x + 230, 438), 18, PANEL_2, color, 2)
        draw_text(draw, (x + 34, 362), label, fill=color, fnt=F_H1)
        draw_text(draw, (x + 34, 406), "pillar online", fill=MUTED, fnt=F_SMALL)
    draw_text(draw, (458, 502), f"loading swarm graph {int(alpha * 100)}%", fill=BLUE, fnt=F_H2)


def scene_architecture(draw, local: int):
    panel(draw, (52, 112, 388, 520), "Architecture", [
        "User request",
        "-> Triage",
        "-> Council meeting",
        "-> Specialist agents",
        "-> Master integration review",
    ], BLUE)
    centers = [(590, 180), (780, 180), (970, 180), (690, 360), (900, 360)]
    labels = ["Triage", "Council", "Master", "Agents", "Artifacts"]
    colors = [AMBER, PURPLE, GREEN, BLUE, PINK]
    for idx, ((x, y), label) in enumerate(zip(centers, labels)):
        pulse = 8 * math.sin((local + idx * 8) / 10)
        draw.ellipse((x - 56 - pulse, y - 56 - pulse, x + 56 + pulse, y + 56 + pulse), fill=(17, 25, 42), outline=colors[idx], width=3)
        draw_text(draw, (x, y - 10), label, fnt=F_SMALL, anchor="mm")
    for a, b in [(0, 1), (1, 2), (1, 3), (3, 4), (2, 4)]:
        draw.line((*centers[a], *centers[b]), fill=(80, 96, 130), width=2)


def scene_council(draw, local: int):
    panel(draw, (54, 106, 1226, 542), "Council Meeting - always happens", [
        "Question: build a feature?",
        "Researcher: demand checked",
        "Security: no critical risk",
        "Testing: edge cases covered",
        "Analytics: impact measured",
        "Hermes: reusable lesson captured",
    ], PURPLE)
    yes = min(6, int(local / 14) + 1)
    for i in range(6):
        x = 600 + (i % 3) * 185
        y = 205 + (i // 3) * 110
        color = GREEN if i < yes else (51, 65, 85)
        draw_round(draw, (x, y, x + 150, y + 70), 12, (20, 32, 50), color, 2)
        draw_text(draw, (x + 22, y + 18), f"Agent {i + 1}", fnt=F_SMALL)
        draw_text(draw, (x + 22, y + 43), "YES" if i < yes else "waiting", fill=color, fnt=F_SMALL)
    draw_text(draw, (822, 456), f"Vote: {yes}/6 YES    Confidence: {70 + yes * 4}%", fill=GREEN, fnt=F_H2, anchor="mm")


def scene_agents(draw, local: int):
    draw_text(draw, (58, 110), "Specialists and sub-agents work in parallel", fnt=F_H1)
    for idx, (name, pillar, color) in enumerate(AGENTS):
        row = idx % 6
        col = idx // 6
        x = 56 + col * 300
        y = 166 + row * 54
        active = (local // 8 + idx) % 3 == 0
        draw_round(draw, (x, y, x + 270, y + 35), 8, PANEL, color if active else (45, 55, 75))
        draw_text(draw, (x + 14, y + 8), name, fnt=F_TINY)
        draw_text(draw, (x + 220, y + 8), pillar, fill=color, fnt=F_TINY)
    draw_text(draw, (413, 565), "spawn_agent lets any specialist delegate focused work", fill=MUTED, fnt=F_BODY)


def scene_connected_graph(draw, local: int):
    draw_text(draw, (58, 104), "Live graph: agents verify, connect, then publish", fnt=F_H1)
    draw_text(draw, (62, 145), "Every specialist verifies its slice, connects artifacts, then passes evidence to master review and publish.", fill=MUTED, fnt=F_SMALL)
    graph_agents = [
        ("coder", "kimi", 90, 205, GREEN),
        ("reviewer", "openrouter", 90, 285, GREEN),
        ("security", "fireworks", 90, 365, RED),
        ("testing", "groq", 90, 445, BLUE),
        ("debugging", "qwen", 90, 525, GREEN),
        ("researcher", "microsoft", 340, 205, BLUE),
        ("analytics", "alibaba", 340, 300, GREEN),
        ("ux_research", "cloudflare", 340, 395, BLUE),
        ("photo_editor", "recraft", 340, 490, PINK),
        ("writer", "claude", 620, 205, PURPLE),
        ("localization", "mistral", 620, 290, PURPLE),
        ("design", "gemini", 620, 375, PURPLE),
        ("figma_controller", "browser", 620, 460, PINK),
        ("marketing", "perplexity", 930, 205, AMBER),
        ("finance", "nvidia", 930, 285, AMBER),
        ("trading", "mcp", 930, 365, AMBER),
        ("product_manager", "huggingface", 930, 445, AMBER),
        ("master_review", "verify", 930, 525, GREEN),
        ("n8n_workflow", "nodes", 1160, 205, GREEN),
        ("game_developer", "kling", 1160, 285, BLUE),
        ("publish", "release", 1160, 365, BLUE),
        ("social_manager", "queue", 1160, 445, AMBER),
    ]
    label_map = {
        "ux_research": "ux",
        "photo_editor": "photo",
        "figma_controller": "figma",
        "product_manager": "product",
        "master_review": "master",
        "n8n_workflow": "n8n",
        "game_developer": "game",
        "social_manager": "social",
    }
    positions = {name: (x, y) for name, _, x, y, _ in graph_agents}
    edges = [
        ("coder", "researcher"), ("coder", "design"), ("reviewer", "analytics"), ("security", "design"),
        ("testing", "ux_research"), ("debugging", "figma_controller"), ("researcher", "writer"),
        ("researcher", "design"), ("analytics", "localization"), ("analytics", "marketing"),
        ("ux_research", "design"), ("photo_editor", "design"), ("writer", "marketing"),
        ("writer", "product_manager"), ("localization", "finance"), ("design", "marketing"),
        ("design", "finance"), ("design", "trading"), ("design", "product_manager"),
        ("figma_controller", "master_review"), ("security", "master_review"), ("testing", "master_review"),
        ("product_manager", "master_review"), ("master_review", "publish"),
        ("hermes", "design"), ("n8n_workflow", "master_review"), ("game_developer", "master_review"),
        ("social_manager", "master_review"), ("design", "game_developer"), ("marketing", "social_manager"),
    ]
    positions["hermes"] = (632, 535)
    for idx, (source, target) in enumerate(edges):
        if source not in positions or target not in positions:
            continue
        x1, y1 = positions[source]
        x2, y2 = positions[target]
        color = (34, 197, 142) if idx % 3 == 0 else (52, 65, 88)
        draw.line((x1, y1, x2, y2), fill=color, width=2 if idx % 3 == 0 else 1)
        phase = ((local * 0.018) + idx * 0.071) % 1.0
        px = x1 + (x2 - x1) * phase
        py = y1 + (y2 - y1) * phase
        draw.ellipse((px - 5, py - 5, px + 5, py + 5), fill=GREEN if idx % 2 == 0 else BLUE)
    for name, provider, x, y, color in graph_agents:
        active = (local // 9 + len(name)) % 4 != 0
        radius = 18 + (5 * math.sin((local + x + y) / 13) if active else 0)
        if name == "design":
            radius += 6
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(18, 28, 44), outline=color, width=3)
        draw.ellipse((x + 22, y - 22, x + 32, y - 12), fill=GREEN if active else MUTED)
        label = label_map.get(name, name)
        label_y = y + radius + 14
        provider_y = label_y + 15
        draw_round(draw, (x - 45, label_y - 3, x + 45, provider_y + 13), 7, (8, 13, 23))
        draw_text(draw, (x, label_y), label, fill=TEXT, fnt=F_TINY, anchor="mm")
        draw_text(draw, (x, provider_y), provider, fill=MUTED, fnt=F_TINY, anchor="mm")
    hx, hy = positions["hermes"]
    draw.ellipse((hx - 18, hy - 18, hx + 18, hy + 18), fill=(18, 28, 44), outline=PURPLE, width=3)
    draw_text(draw, (hx, hy + 33), "hermes", fill=TEXT, fnt=F_TINY, anchor="mm")
    draw_text(draw, (hx, hy + 51), "skills", fill=MUTED, fnt=F_TINY, anchor="mm")


def scene_routing(draw, local: int):
    panel(draw, (54, 108, 462, 542), "Smart AI Selection", [
        "coding -> Codestral/Qwen/Kimi/local",
        "reasoning -> Opus/GPT/Hermes/NVIDIA",
        "vision -> Gemini/vision bridge",
        "voice -> ElevenLabs/Zyphra/STT/TTS",
        "media -> Recraft/Kling/HF",
        "fallback keeps memory once",
    ], GREEN)
    routes = [
        ("Master", "cloud reasoning", PURPLE),
        ("Coder", "coding model", GREEN),
        ("Browser", "MCP + browser", BLUE),
        ("Media", "Recraft/Kling", PINK),
        ("Cheap checks", "local model", AMBER),
    ]
    for idx, (role, model, color) in enumerate(routes):
        x = 560
        y = 135 + idx * 78
        draw_round(draw, (x, y, 1174, y + 54), 14, PANEL_2, color, 2)
        fill = color if idx <= (local // 16) % len(routes) else MUTED
        draw_text(draw, (x + 24, y + 14), role, fill=fill, fnt=F_SMALL)
        draw_text(draw, (x + 300, y + 14), model, fill=TEXT, fnt=F_SMALL)
        draw_text(draw, (x + 510, y + 14), "ready", fill=GREEN, fnt=F_SMALL)


def scene_dashboard(draw, local: int):
    draw_text(draw, (58, 104), "Real-time dashboard: graph, code, file growth", fnt=F_H1)
    draw_round(draw, (58, 160, 430, 554), 12, PANEL, BLUE)
    for idx, (name, _, color) in enumerate(AGENTS[:9]):
        y = 184 + idx * 38
        active = idx == (local // 18) % 9
        draw_round(draw, (82, y, 400, y + 28), 8, PANEL_2 if active else (13, 20, 34), color if active else (40, 52, 75))
        draw_text(draw, (98, y + 6), f"{name}  {'typing...' if active else 'watching'}", fill=TEXT if active else MUTED, fnt=F_TINY)
    draw_round(draw, (470, 160, 1200, 554), 12, (3, 7, 18), (50, 65, 90))
    code = [
        "def build_feature(request):",
        "    council = run_council_vote(request)",
        "    agents = route_specialists(request)",
        "    result = integrate_outputs(agents)",
        "    review = master_review(result)",
        "    hermes.learn_if_reusable(review)",
        "    return result",
    ]
    chars = min(sum(len(line) + 1 for line in code), int(local * 2.4))
    remaining = chars
    y = 190
    for line in code:
        visible = line[: max(0, min(len(line), remaining))]
        draw_text(draw, (500, y), visible, fill=GREEN, fnt=F_MONO)
        remaining -= len(line) + 1
        y += 42
    draw_round(draw, (500, 500, 500 + min(650, chars * 4), 524), 12, BLUE)


def scene_tools(draw, local: int):
    groups = [
        ("Browser", ["open", "snapshot", "click", "title", "stop"], BLUE),
        ("MCP", ["Supabase", "Figma", "Drive", "Stripe", "Obsidian"], PURPLE),
        ("CLI", ["OpenCode", "Qwen", "Mistral", "Aider", "Windsurf"], GREEN),
        ("Workflow", ["scrape", "apply jobs", "build app", "test app", "backend"], AMBER),
        ("Automation", ["n8n nodes", "dry-run JSON", "game build", "social queue", "approval"], RED),
    ]
    for idx, (title, items, color) in enumerate(groups):
        x = 56 + (idx % 3) * 410
        y = 112 + (idx // 3) * 218
        panel(draw, (x, y, x + 370, y + 198), title, [f"- {item}" for item in items], color)
    draw_text(draw, (330, 560), "Plan mode asks detailed questions only when vision/context is missing", fill=MUTED, fnt=F_BODY)


def scene_media(draw, local: int):
    draw_text(draw, (58, 106), "Creative stack: image, video, voice, design, 3D", fnt=F_H1)
    items = [
        ("Image generation", "Recraft / Omni / HF / Flow", PINK),
        ("Video generation", "Kling / Google Flow / Veo", PURPLE),
        ("Voice", "STT + TTS + Zyphra", GREEN),
        ("Figma", "layouts + prototype checks", BLUE),
        ("Blender + model APIs", "heavy 3D + Kimi/NVIDIA", AMBER),
        ("Animator", "mockups + Alibaba/Microsoft", RED),
    ]
    for idx, (title, sub, color) in enumerate(items):
        x = 80 + (idx % 3) * 390
        y = 180 + (idx // 3) * 165
        draw_round(draw, (x, y, x + 330, y + 110), 16, PANEL, color, 2)
        draw_text(draw, (x + 22, y + 24), title, fill=color, fnt=F_H2)
        draw_text(draw, (x + 22, y + 65), sub, fill=MUTED, fnt=F_SMALL)


def scene_security(draw, local: int):
    panel(draw, (62, 112, 558, 552), "Security and Cost Control", [
        "AI reviewer checks each agent",
        "XSS and logic-risk detection",
        "Scoped file access blocks secrets",
        "Hallucination guard verifies facts",
        "/compact preserves architecture",
        "Token budget limits overhead",
        "Temporary skills clean up",
    ], RED)
    checks = ["security", "performance", "logic", "hallucination", "secrets", "tests"]
    for idx, check in enumerate(checks):
        x = 660 + (idx % 2) * 230
        y = 155 + (idx // 2) * 105
        draw.ellipse((x, y, x + 70, y + 70), fill=(20, 32, 50), outline=GREEN, width=4)
        draw.line((x + 18, y + 38, x + 31, y + 52, x + 54, y + 20), fill=GREEN, width=5)
        draw_text(draw, (x + 86, y + 24), check, fnt=F_SMALL)


def scene_hermes(draw, local: int):
    draw_text(draw, (58, 104), "Hermes self-evolution: skills get smarter over time", fnt=F_H1)
    steps = [
        ("observe", "successful work + failures"),
        ("compress", "turn pattern into skill draft"),
        ("validate", "safety, reuse, size gates"),
        ("version", "JSON manifest + SKILL.md"),
        ("reuse", "future agents load approved skill"),
    ]
    for idx, (title, sub) in enumerate(steps):
        x = 86 + idx * 230
        y = 255 + int(18 * math.sin((local + idx * 12) / 18))
        color = [BLUE, PURPLE, GREEN, AMBER, PINK][idx]
        draw.ellipse((x, y, x + 112, y + 112), fill=PANEL, outline=color, width=4)
        draw_text(draw, (x + 56, y + 43), title, fill=color, fnt=F_SMALL, anchor="mm")
        draw_text(draw, (x + 56, y + 75), str(idx + 1), fill=TEXT, fnt=F_H2, anchor="mm")
        draw_text(draw, (x - 30, y + 138), fit_text(draw, sub, 165, F_TINY), fill=MUTED, fnt=F_TINY)
        if idx < len(steps) - 1:
            draw.line((x + 120, y + 56, x + 210, y + 56), fill=(80, 96, 130), width=3)
    draw_text(draw, (367, 548), "Guardrails: no credential skills, no unreviewed execution, master review before reuse", fill=MUTED, fnt=F_BODY)


def scene_finish(draw, local: int):
    draw_text(draw, (96, 128), "Aggressive verification", fnt=F_TITLE)
    cards = [
        ("pytest", "319 passed", GREEN),
        ("warnings", "clean", GREEN),
        ("all CLIs", "shown", BLUE),
        ("feature benchmark", "16/16 passed", PURPLE),
        ("OpenCode", "6/6", AMBER),
        ("Qwen + Aider", "OK", PINK),
        ("Codex", "OK", GREEN),
        ("Gemini", "version OK", BLUE),
        ("n8n/game/social", "OK", AMBER),
        ("charts", "generated", GREEN),
    ]
    for idx, (title, value, color) in enumerate(cards):
        x = 88 + (idx % 3) * 382
        y = 198 + (idx // 3) * 90
        draw_round(draw, (x, y, x + 320, y + 66), 14, PANEL, color, 2)
        draw_text(draw, (x + 20, y + 10), title, fill=MUTED, fnt=F_SMALL)
        draw_text(draw, (x + 20, y + 34), value, fill=color, fnt=F_SMALL if len(value) > 12 else F_H2)


SCENES = [
    (0, 4, scene_intro),
    (4, 9, scene_architecture),
    (9, 14, scene_council),
    (14, 19, scene_agents),
    (19, 25, scene_connected_graph),
    (25, 30, scene_routing),
    (30, 36, scene_dashboard),
    (36, 42, scene_tools),
    (42, 48, scene_media),
    (48, 53, scene_security),
    (53, 58, scene_hermes),
    (58, 60, scene_finish),
]


def draw_frame(frame: int) -> Image.Image:
    img, draw = base_frame(frame)
    second = frame / FPS
    for start, end, fn in SCENES:
        if start <= second < end:
            fn(draw, frame - start * FPS)
            break
    draw_chips(draw, frame)
    draw_progress(draw, frame)
    return img


def render_mp4():
    EXAMPLES.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-f",
        "rawvideo",
        "-vcodec",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{WIDTH}x{HEIGHT}",
        "-r",
        str(FPS),
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "24",
        "-pix_fmt",
        "yuv420p",
        str(MP4),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    assert process.stdin is not None
    for frame in range(TOTAL_FRAMES):
        process.stdin.write(draw_frame(frame).tobytes())
    process.stdin.close()
    if process.wait() != 0:
        raise RuntimeError("ffmpeg failed while rendering mp4")
    draw_frame(0).save(POSTER)


def render_gif():
    with tempfile.TemporaryDirectory() as tmp:
        palette = Path(tmp) / "palette.png"
        filters = "fps=10,scale=960:-1:flags=lanczos"
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(MP4), "-vf", f"{filters},palettegen=stats_mode=diff", str(palette)],
            check=True,
        )
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(MP4), "-i", str(palette), "-lavfi", f"{filters} [x]; [x][1:v] paletteuse=dither=bayer:bayer_scale=5", str(GIF)],
            check=True,
        )


def main():
    render_mp4()
    render_gif()
    print({"mp4": str(MP4), "gif": str(GIF), "poster": str(POSTER)})


if __name__ == "__main__":
    main()
