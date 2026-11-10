# Serving the Danish/Nordic open models

`llm.py` treats the three Nordic rows as OpenAI-compatible endpoints at `LOCAL_VLLM_BASE_URL`
(set in `.env`). `litellm_model` is `openai/<hf repo id>`, so the served model name must be the
Hugging Face repo id. The models are run one at a time against the same base URL; run
`danews generate --models <id>` per model.

## Option A — vLLM on a Nebius GPU instance (Munin 7B, DanskGPT v4 12B)

```bash
pip install vllm
# Munin 7B (Mistral-7B-v0.1 base, Apache-2.0)
vllm serve danish-foundation-models/munin-7b-alpha --dtype bfloat16 --max-model-len 8192 --port 8000
# DanskGPT v4 12B (Gemma-4-12B-it fine-tune, CC-BY-4.0 + Gemma terms)
vllm serve syvai/danskgpt-v4-12b --dtype bfloat16 --max-model-len 8192 --port 8000
```

Then on the laptop: `ssh -L 8000:localhost:8000 <instance>` and `LOCAL_VLLM_BASE_URL=http://localhost:8000/v1`.

Cost per 1,000 T1 tasks for self-hosted rows = GPU hourly price ÷ measured T1 throughput
(tasks per hour), recorded in `DECISIONS.md` when the run happens. Latencies are labelled
"(lokal)" in the dependency table.

## Option B — local 4-bit (Mimir v1.5; Munin/DanskGPT if RAM allows)

Mimir v1.5 is a 1.8 B HRM-Text model that needs a recent Transformers/vLLM with
`HrmTextForCausalLM`; the `-GGUF` repo runs on llama.cpp:

```bash
llama-server -hf danish-foundation-models/DFM-Mimir-v1.5-GGUF --alias danish-foundation-models/DFM-Mimir-v1.5 --port 8000 -c 4096
```

For Munin/DanskGPT locally, use the Q4_K_M GGUF quantisations with llama.cpp and the same
`--alias <hf repo id>` trick so the served name matches `models.yaml`.

Open item: decide whether Munin and DanskGPT run locally (4-bit) or on a Nebius GPU hour, based on laptop RAM (58 GB RAM available, no NVIDIA GPU detected on 2026-11-09 — 4-bit CPU inference will be slow; a GPU hour is the realistic choice).
