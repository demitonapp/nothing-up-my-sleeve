"""The house's Hub list (thorp.lab_models): NVIDIA's organisation also hosts other houses' NVFP4
conversions, so its page keeps NVIDIA's own families and drops a repo named for another house."""

from thorp.lab_models import _keep, _row, _variant


def test_nvidia_keeps_nemotron_and_drops_other_houses_conversions() -> None:
    assert _keep("nvidia", "NVIDIA-Nemotron-3-Nano-4B-BF16")
    assert _keep("nvidia", "llama-nemotron-embed-1b-v2")
    assert _keep("nvidia", "Cosmos-Reason2-2B")
    assert _keep("nvidia", "parakeet-tdt-0.6b-v3")
    assert not _keep("nvidia", "Qwen3.6-35B-A3B-NVFP4")
    assert not _keep("nvidia", "Gemma-4-26B-A4B-NVFP4")
    assert not _keep("nvidia", "GLM-5.3-NVFP4")
    assert not _keep("nvidia", "Kimi-K2-Thinking-NVFP4")


def test_the_other_orgs_are_not_filtered() -> None:
    assert _keep("google", "gemma-4-31B-it")
    assert _keep("microsoft", "Phi-4-mini-instruct")
    assert _keep("alibaba", "Qwen3.8-27B")


def test_a_gguf_name_supplies_the_size_when_safetensors_does_not() -> None:
    row = _row({"id": "arcee-ai/AFM-4.5B-GGUF", "tags": ["gguf"]})
    assert row["params"] == 4.5e9
    assert row["size_inferred"] is True
    assert row["mac"] is True


def test_a_model_is_named_by_its_tuning_not_only_its_size() -> None:
    assert _variant("Falcon3-7B-Base", "text-generation") == "base"
    assert _variant("Falcon3-7B-Instruct", "text-generation") == "instruct"
    assert _variant("Trinity-Large-Thinking", "text-generation") == "reasoning"
    assert _variant("Falcon-OCR", "image-to-text") == "other"
    assert _variant("falcon-7b", "text-generation") == "general"
