from __future__ import annotations


USER_OWNED_SIGNALS = (
    "my design",
    "my sketch",
    "my drawing",
    "my building",
    "my house",
    "my product",
    "my logo",
    "client design",
    "original design",
    "prototype",
    "floor plan",
    "blueprint",
    "cad",
    "reference photo",
)

THIRD_PARTY_SIGNALS = (
    "same to same",
    "exact copy",
    "identical",
    "1:1",
    "clone",
    "mewtwo",
    "pokemon",
    "mario",
    "sonic",
    "disney",
    "marvel",
    "dc comics",
)


def classify_3d_design_request(prompt: str) -> dict:
    lower = prompt.lower()
    user_owned = any(signal in lower for signal in USER_OWNED_SIGNALS)
    third_party_exact = any(signal in lower for signal in THIRD_PARTY_SIGNALS) and any(
        token in lower for token in ("same", "exact", "identical", "1:1", "clone")
    )
    if user_owned:
        decision = "allow_direct_3d_build"
        guidance = "The swarm should build the requested 3D version directly from the user's supplied design/reference."
    elif third_party_exact:
        decision = "transform_to_original_variant"
        guidance = "Do not create an exact third-party character/brand clone; make an original variant instead."
    else:
        decision = "allow_with_reference_check"
        guidance = "Proceed with 3D modeling and ask for ownership/rights only if the request clearly targets a protected third-party design."
    return {
        "decision": decision,
        "user_owned_design_allowed": user_owned or not third_party_exact,
        "third_party_exact_clone": third_party_exact,
        "guidance": guidance,
        "examples_allowed": [
            "turn my building sketch into a 3D model",
            "make my product design as a Blender mockup",
            "convert my original character concept into a 3D creature",
            "make a 3D view of my floor plan or architecture reference",
        ],
        "retained_boundary": "Exact copying of third-party protected characters, mascots, or brand assets requires rights; otherwise create an original variant.",
    }


def build_3d_design_workflow(prompt: str, app: str = "Blender") -> dict:
    policy = classify_3d_design_request(prompt)
    return {
        "prompt": prompt,
        "selected_app": app,
        "policy": policy,
        "steps": [
            "read the supplied sketch, image, blueprint, CAD note, or written design brief",
            "block out the main 3D proportions and camera views",
            "model primary forms, structural details, materials, and scale cues",
            "add lighting, camera, preview render, and export formats",
            "run visual QA for framing, missing parts, material errors, and file validity",
        ],
        "outputs": ["blend", "glb_or_obj_when_requested", "preview_png", "generation_script_when_procedural"],
        "quality_bar": {
            "user_owned_designs": "match the user's design as closely as possible",
            "buildings_and_products": "prioritize faithful geometry, scale, materials, and usable inspection angles",
            "original_characters": "preserve the user's concept, pose, colors, silhouette, and notable details",
            "third_party_references": "preserve only high-level vibe unless the user has rights",
        },
    }
