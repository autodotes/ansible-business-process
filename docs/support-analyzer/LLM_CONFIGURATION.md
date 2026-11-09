# LLM Configuration Guide

## Overview

The support case analyzer workflow (`playbooks/pb_analyze_support_cases.yml`, via the
`zjleblanc.rh_case_mgmt.llm_summarize` module) supports **any OpenAI-compatible LLM API**, including:

- **vLLM** — High-performance LLM serving (local or remote)
- **Ollama** — Local LLM deployment
- **LocalAI** — Self-hosted OpenAI alternative
- **OpenAI** — Cloud-based GPT models
- **Azure OpenAI** — Enterprise OpenAI deployment
- Any other service with an OpenAI-compatible `/v1/chat/completions` endpoint

## Quick start

### Option 1: Local vLLM (recommended for privacy)

```bash
# 1. Install vLLM
pip install vllm

# 2. Start vLLM server with your model
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-2-70b-chat-hf \
  --host 0.0.0.0 \
  --port 8000
```

Set in `vault.yml`:

```yaml
redhat_offline_token: "your-redhat-token"
llm_api_key: "EMPTY"
llm_api_base_url: "http://localhost:8000/v1"
llm_model: "meta-llama/Llama-2-70b-chat-hf"
```

```bash
ansible-navigator run playbooks/pb_analyze_support_cases.yml -e @vault.yml -e @my_accounts.yml
```

### Option 2: Ollama

```bash
# 1. Install and start Ollama
ollama serve

# 2. Pull a model
ollama pull llama2
```

Set in `vault.yml`:

```yaml
llm_api_key: "EMPTY"
llm_api_base_url: "http://localhost:11434/v1"
llm_model: "llama2"
```

### Option 3: OpenAI

Set in `vault.yml`:

```yaml
llm_api_key: "sk-your-openai-api-key"
llm_api_base_url: "https://api.openai.com/v1"
llm_model: "gpt-4"
```

## Configuration options

### Required vault / extra vars

| Variable | Description | Example |
|----------|-------------|---------|
| `llm_api_key` | API key (use `"EMPTY"` for local deployments without auth) | `"EMPTY"` or `"sk-..."` |
| `llm_api_base_url` | Base URL for LLM API | `"http://localhost:8000/v1"` |
| `llm_model` | Model name | `"meta-llama/Llama-2-70b-chat-hf"` |

### Additional parameters

Defaulted in `playbooks/pb_analyze_support_cases.yml`'s `vars:` section — override with `-e` if
needed:

```yaml
llm_temperature: 0.7   # Creativity (0.0-1.0)
llm_max_tokens: 2048   # Maximum response length
llm_timeout: 120       # Request timeout in seconds
```

## vLLM deployment guide

### Local deployment

#### Prerequisites

- NVIDIA GPU (recommended: A100, H100, or multiple V100s)
- CUDA 11.8+
- Python 3.8+
- 40GB+ VRAM for 70B models, 20GB+ for 13B models

#### Installation

```bash
# Install vLLM
pip install vllm

# Or with specific CUDA version
pip install vllm --extra-index-url https://download.pytorch.org/whl/cu118
```

#### Start server

**Basic:**

```bash
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-2-70b-chat-hf \
  --host 0.0.0.0 \
  --port 8000
```

**With tensor parallelism (multiple GPUs):**

```bash
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-2-70b-chat-hf \
  --tensor-parallel-size 4 \
  --host 0.0.0.0 \
  --port 8000
```

**With quantization (lower memory):**

```bash
python -m vllm.entrypoints.openai.api_server \
  --model TheBloke/Llama-2-70B-chat-AWQ \
  --quantization awq \
  --host 0.0.0.0 \
  --port 8000
```

### Remote vLLM deployment

If running vLLM on a remote server:

```bash
# On remote server
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-2-70b-chat-hf \
  --host 0.0.0.0 \
  --port 8000
```

Set `llm_api_base_url: "http://your-server:8000/v1"` in `vault.yml` on the control node.

### Docker deployment

```bash
# Pull vLLM image
docker pull vllm/vllm-openai:latest

# Run with GPU support
docker run --gpus all \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  -p 8000:8000 \
  vllm/vllm-openai:latest \
  --model meta-llama/Llama-2-70b-chat-hf
```

## Recommended models

### For support case analysis

| Model | Size | VRAM | Quality | Speed | Use case |
|-------|------|------|---------|-------|----------|
| Llama-2-70B-chat | 70B | 140GB | Excellent | Slow | Best quality, production |
| Llama-2-13B-chat | 13B | 26GB | Good | Fast | Development, testing |
| Mistral-7B-Instruct | 7B | 14GB | Good | Very Fast | Quick analysis |
| GPT-4 (OpenAI) | - | N/A | Excellent | Medium | Cloud-based option |
| GPT-3.5-turbo (OpenAI) | - | N/A | Good | Fast | Cost-effective cloud |

### Model selection guide

**For production (high quality):**

- Llama-2-70B-chat-hf
- GPT-4 (if using OpenAI)

**For development/testing:**

- Llama-2-13B-chat-hf
- Mistral-7B-Instruct-v0.2

**For budget/speed:**

- Llama-2-7B-chat-hf
- GPT-3.5-turbo (if using OpenAI)

## Performance tuning

### vLLM optimization

```bash
# Increase batch size for better throughput
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-2-70b-chat-hf \
  --max-num-seqs 32 \
  --host 0.0.0.0 \
  --port 8000

# Use PagedAttention for better memory efficiency
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-2-70b-chat-hf \
  --block-size 16 \
  --host 0.0.0.0 \
  --port 8000
```

### Playbook optimization

Adjust `llm_timeout` in `playbooks/pb_analyze_support_cases.yml`'s `vars:` section (or via `-e`)
for slower models:

```yaml
llm_timeout: 300  # 5 minutes for large models
```

## Troubleshooting

### Connection issues

**Error: "Connection refused"**

```bash
# Check if vLLM is running
curl http://localhost:8000/v1/models

# Expected response
{"object":"list","data":[{"id":"meta-llama/Llama-2-70b-chat-hf",...}]}
```

**Error: "Request timeout"**

Increase `llm_timeout` via `-e llm_timeout=300` or in `vault.yml`.

### Model issues

**Error: "Model not found"**

Check available models:

```bash
curl http://localhost:8000/v1/models
```

Use the exact model name from the response.

**Error: "Out of memory"**

Options:

1. Use a quantized model (AWQ, GPTQ)
2. Reduce batch size
3. Use a smaller model
4. Add more GPUs with tensor parallelism

### Authentication issues

**Local vLLM** doesn't require authentication:

```yaml
llm_api_key: "EMPTY"
```

**OpenAI** requires a valid API key:

```yaml
llm_api_key: "sk-..."
```

## Security considerations

### Local deployment (vLLM, Ollama)

**Advantages:**

- Data never leaves your network
- No API rate limits
- No per-request costs
- Full control over models

**Security:**

- Ensure the vLLM server is not exposed to the internet
- Use firewall rules to restrict access
- Consider a VPN for remote access

### Cloud deployment (OpenAI, etc.)

**Considerations:**

- Data sent to a third-party API
- Subject to terms of service
- Potential compliance concerns
- No infrastructure maintenance required
- Always up-to-date models

**Mitigation:**

- Review data sensitivity
- Check compliance requirements (GDPR, HIPAA, etc.)
- Consider data anonymization
- Use Azure OpenAI for enterprise compliance

## Example configurations

### Configuration 1: High-performance local

```yaml
# vault.yml
llm_api_key: "EMPTY"
llm_api_base_url: "http://localhost:8000/v1"
llm_model: "meta-llama/Llama-2-70b-chat-hf"
llm_temperature: 0.7
llm_max_tokens: 2048
llm_timeout: 180
```

### Configuration 2: Fast local development

```yaml
# vault.yml
llm_api_key: "EMPTY"
llm_api_base_url: "http://localhost:8000/v1"
llm_model: "mistralai/Mistral-7B-Instruct-v0.2"
llm_temperature: 0.7
llm_max_tokens: 1500
llm_timeout: 60
```

### Configuration 3: OpenAI cloud

```yaml
# vault.yml
llm_api_key: "sk-your-api-key"
llm_api_base_url: "https://api.openai.com/v1"
llm_model: "gpt-4"
llm_temperature: 0.7
llm_max_tokens: 2048
llm_timeout: 120
```

### Configuration 4: Azure OpenAI enterprise

```yaml
# vault.yml
llm_api_key: "your-azure-api-key"
llm_api_base_url: "https://your-resource.openai.azure.com/openai/deployments/your-deployment"
llm_model: "gpt-4"
llm_temperature: 0.7
llm_max_tokens: 2048
llm_timeout: 120
```

## Testing your configuration

### Test vLLM server

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "meta-llama/Llama-2-70b-chat-hf",
    "messages": [{"role": "user", "content": "Hello!"}],
    "max_tokens": 50
  }'
```

### Test with the playbook

```bash
ansible-navigator run playbooks/pb_analyze_support_cases.yml \
  -e @vault.yml -e @my_accounts.yml \
  -- --tags ai -vvv
```

## Resources

### Documentation

- [vLLM Documentation](https://vllm.readthedocs.io/)
- [Ollama Documentation](https://ollama.ai/docs)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
- [HuggingFace Models](https://huggingface.co/models)

### Model repositories

- [Llama 2 Models](https://huggingface.co/meta-llama)
- [Mistral Models](https://huggingface.co/mistralai)
- [Quantized Models by TheBloke](https://huggingface.co/TheBloke)

### Tools

- [vLLM GitHub](https://github.com/vllm-project/vllm)
- [Ollama GitHub](https://github.com/jmorganca/ollama)
- [LM Studio](https://lmstudio.ai/) — GUI for local LLMs
