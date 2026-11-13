"""The Labs page's list (thorp.labs): the distinct houses, each a lab the leaderboard knows, and the new
families matched to the house that makes them. The payload itself reads the store and is covered by the
lab page's own use; this pins the list and the matching, which the dashboard's cards depend on."""

from thorp import labs


def test_the_labs_page_has_distinct_houses() -> None:
    listed = labs.listed()
    assert len(listed) == 46  # 13 November: four Aboriginal language archives joined Australia's research houses
    assert len({lab.key for lab in listed}) == 46
    known = {lab.key for lab in labs.all()}
    assert {lab.key for lab in listed} <= known
    # Hugging Face is the one leaderboard-only row left; EleutherAI is a research house now
    assert {"huggingface"} <= known - {lab.key for lab in listed}
    assert "eleutherai" in {lab.key for lab in listed}


def test_a_house_is_a_lab_and_its_profile_is_complete() -> None:
    for key in (lab.key for lab in labs.listed()):
        lab = labs.get(key)
        assert lab is not None
        assert lab.short and lab.country and lab.hq and lab.blurb
        assert lab.category in ("lab", "research") and lab.kind
        assert lab.door.startswith("http")
        if lab.category == "lab":  # a research infrastructure may name no model
            assert lab.flagship


def test_the_new_families_find_their_house() -> None:
    # the houses the Reach had not named before 12 November, matched by family rather than by repo owner
    assert labs.lab_of("Ling-3.2-flash").key == "antgroup"
    assert labs.lab_of("gpt-oss-20b").key == "openai"
    assert labs.lab_of("DeepSeek-V4-Pro").key == "deepseek"
    assert labs.lab_of("Claude-Opus-5.5").key == "anthropic"
    assert labs.lab_of("Grok-4.6").key == "xai"
    assert labs.lab_of("Mistral-OCR-4").key == "mistral"
    assert labs.lab_of("Moonshot-Kimi-K3.1-Pro").key == "moonshot"
    assert labs.lab_of("GLM-5.3-Flash").key == "zai"
    assert labs.lab_of("MiniMax-M2.5").key == "minimax"
    assert labs.lab_of("Command-A").key == "cohere"
    assert labs.lab_of("Nemotron-3").key == "nvidia"
    assert labs.lab_of("Step-5").key == "stepfun"
    assert labs.lab_of("Seed-OSS-36B").key == "bytedance"
    assert labs.lab_of("Inkling").key == "thinkingmachines"
    assert labs.lab_of("Falcon-3").key == "tii"
    assert labs.lab_of("SWE-1.5").key == "cognition"
    assert labs.lab_of("Arcee-Fusion").key == "arcee"
    assert labs.lab_of("MolmoWeb-8B").key == "ai2"
    assert labs.lab_of("allenai/OLMo-3-7B").key == "ai2"
    assert labs.lab_of("Holo2-8B").key == "hcompany"
    # Maincode's ship was already in the Reach before its house had a page
    assert labs.lab_of("Maincode/Maincoder-1B").key == "maincode"
    assert labs.lab_of("Maincoder-1B").key == "maincode"
    # the three regional houses (12 November): the UK, South Africa and South America
    assert labs.lab_of("GAIA-2").key == "wayve"
    assert labs.lab_of("LINGO-2").key == "wayve"
    assert labs.lab_of("InkubaLM-0.4B").key == "lelapa"
    assert labs.lab_of("Vulavula").key == "lelapa"
    assert labs.lab_of("S5").key == "maritaca"
    assert labs.lab_of("S5-nano").key == "maritaca"
    assert labs.lab_of("Sabiá 4").key == "maritaca"
    # the UK, South African and Australian houses that joined on the same day
    assert labs.lab_of("Lizzy-7B").key == "flower"
    assert labs.lab_of("Stable Diffusion").key == "stability"
    assert labs.lab_of("MzansiLM-125M").key == "uctnlp"
    assert labs.lab_of("MasakhaNER-2.0").key == "masakhane"
    assert labs.lab_of("Ginan").key == "sovereign-au"
    assert labs.lab_of("Australis").key == "sovereign-au"
    # the research houses by country
    assert labs.lab_of("Pythia-410m").key == "eleutherai"
    assert labs.lab_of("InternLM-3").key == "shanghai-ai"
    assert labs.lab_of("InternVL-3").key == "shanghai-ai"
    assert labs.lab_of("Aquila-7B").key == "baai"
    assert labs.lab_of("JoeyLLM").key == "southern-cross"
    assert labs.lab_of("Moshi").key == "kyutai"
    assert labs.lab_of("Tucano-1b1").key == "nilc"
    # and the old mappings still hold
    assert labs.lab_of("mlx-community/Qwen3-4B-4bit").key == "alibaba"
    assert labs.lab_of("mlx-community/Phi-4-mini-instruct-4bit").key == "microsoft"
    assert labs.lab_of("mlx-community/gemma-3-text-4b-pt-4bit").key == "google"
    assert labs.lab_of("mlx-community/Llama-3.2-3B-bf16").key == "meta"
    assert labs.lab_of("EleutherAI/pythia-70m").key == "eleutherai"
    assert labs.lab_of("HuggingFaceTB/SmolLM2-360M").key == "huggingface"


def test_an_unrelated_model_belongs_to_no_house() -> None:
    assert labs.lab_of("some-lab/Orion-7B") is None


def test_the_frontend_house_routes_match_the_store() -> None:
    """frontend/src/data/labs.json is the route list the Astro pages pre-render; it is written from the
    store, so a house added to s4.labs must be exported (`python -m thorp.dash.lab_keys`) before a build."""
    import json

    from thorp import paths

    data = json.loads((paths.FRONTEND / "src" / "data" / "labs.json").read_text())
    listed = labs.listed()
    assert [list(x) for x in data["houses"]] == [[lab.country, lab.key] for lab in listed]
    assert data["keys"] == [lab.key for lab in listed]
