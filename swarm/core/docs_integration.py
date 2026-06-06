from __future__ import annotations


DOC_SOURCES = {
    "next.js": ("Next.js docs", "https://nextjs.org/docs", ("app router", "routing", "server actions")),
    "nextjs": ("Next.js docs", "https://nextjs.org/docs", ("app router", "routing", "server actions")),
    "react": ("React docs", "https://react.dev", ("components", "hooks", "rendering")),
    "tailwind": ("Tailwind CSS docs", "https://tailwindcss.com/docs", ("utility css", "responsive design")),
    "supabase": ("Supabase docs", "https://supabase.com/docs", ("database", "auth", "storage", "rls")),
    "stripe": ("Stripe docs", "https://docs.stripe.com", ("payments", "checkout", "webhooks")),
    "figma": ("Figma docs", "https://www.figma.com/developers/api", ("design", "plugins", "handoff")),
    "vercel": ("Vercel docs", "https://vercel.com/docs", ("deployments", "edge", "environment")),
    "cloudflare": ("Cloudflare docs", "https://developers.cloudflare.com", ("workers", "kv", "r2")),
    "three.js": ("Three.js docs", "https://threejs.org/docs", ("3d", "webgl", "viewer")),
    "elevenlabs": ("ElevenLabs docs", "https://elevenlabs.io/docs", ("speech", "voice", "audio")),
    "manus": ("Manus provider docs", "provider-configured", ("agent workflows", "automation")),
}


def plan_docs_for_task(task: str) -> dict:
    lower = task.lower()
    selected = []
    for key, (name, url, topics) in DOC_SOURCES.items():
        if key in lower or any(topic in lower for topic in topics):
            selected.append({"name": name, "url": url, "topics": list(topics)})
    return {
        "task": task,
        "sources": selected,
        "policy": (
            "When sources are listed, consult the current docs before generating code. "
            "Use docs for API shape, framework conventions, and version-sensitive behavior."
        ),
        "fallback": "If no source matches, inspect local package files and existing project patterns first.",
    }
