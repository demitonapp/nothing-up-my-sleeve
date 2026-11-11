"""The Labs page's list (thorp.labs): ten distinct houses, each a lab the leaderboard knows, and the new
families matched to the house that makes them. The payload itself reads the store and is covered by the
lab page's own use; this pins the list and the matching, which the dashboard's cards depend on."""

from thorp import labs


def test_the_labs_page_has_ten_distinct_houses() -> None:
    assert len(labs.HOUSES) == 10
    assert len(set(labs.HOUSES)) == 10
    known = {lab.key for lab in labs.LABS}
    assert set(labs.HOUSES) <= known


def test_a_house_is_a_lab_and_its_profile_is_complete() -> None:
    for key in labs.HOUSES:
        lab = labs.get(key)
        assert lab is not None
        assert lab.short and lab.country and lab.hq and lab.blurb and lab.flagship
        assert lab.door.startswith("http")


def test_the_new_families_find_their_house() -> None:
    # the ten houses the Reach had not named before 12 November, matched by family rather than by repo owner
    assert labs.lab_of("Ling-3.2-flash").key == "antgroup"
    assert labs.lab_of("gpt-oss-20b").key == "openai"
    assert labs.lab_of("DeepSeek-V4-Pro").key == "deepseek"
    assert labs.lab_of("Claude-Opus-5.5").key == "anthropic"
    assert labs.lab_of("Grok-4.6").key == "xai"
    assert labs.lab_of("Mistral-OCR-4").key == "mistral"
    # and the old mappings still hold
    assert labs.lab_of("mlx-community/Qwen3-4B-4bit").key == "alibaba"
    assert labs.lab_of("mlx-community/Phi-4-mini-instruct-4bit").key == "microsoft"
    assert labs.lab_of("mlx-community/gemma-3-text-4b-pt-4bit").key == "google"
    assert labs.lab_of("mlx-community/Llama-3.2-3B-bf16").key == "meta"
    assert labs.lab_of("EleutherAI/pythia-70m").key == "eleutherai"
    assert labs.lab_of("HuggingFaceTB/SmolLM2-360M").key == "huggingface"


def test_an_unrelated_model_belongs_to_no_house() -> None:
    assert labs.lab_of("Maincode/Maincoder-1B") is None
