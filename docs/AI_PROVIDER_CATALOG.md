# AI Provider Catalog (2026-07-29)

Operator-configurable LLM providers for BRIEFR (Phase E). Catalog entries use OpenAI-compatible chat completions unless noted. **Custom slot** accepts any validated base URL + model name.

> Research date: 2026-07-29. Re-verify provider docs before changing defaults.

## Built-in catalog

| Provider ID | Display name | Base URL (OpenAI-compatible) | Default model | Env key |
|-------------|--------------|------------------------------|---------------|---------|
| `openai` | OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` | `OPENAI_API_KEY` |
| `anthropic` | Anthropic (via OpenRouter or proxy) | `https://api.anthropic.com` | `claude-sonnet-4-6` | `ANTHROPIC_API_KEY` |
| `gemini` | Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-2.5-flash-lite` | `GEMINI_API_KEY` |
| `deepseek` | DeepSeek | `https://api.deepseek.com` | `deepseek-v4-flash` | `DEEPSEEK_API_KEY` |
| `kimi` | Kimi / Moonshot | `https://api.moonshot.ai/v1` | `kimi-k2.6` | `KIMI_API_KEY` / `MOONSHOT_API_KEY` |

### DeepSeek notes (2026-07)

- Legacy IDs `deepseek-chat` and `deepseek-reasoner` were retired **2026-07-24**. Use `deepseek-v4-pro` or `deepseek-v4-flash`.
- OpenAI-compatible base: `https://api.deepseek.com` (no `/v1` suffix required).
- Anthropic-compatible surface exists at `https://api.deepseek.com/anthropic` but maps Claude model names server-side — prefer OpenAI surface for explicit model pinning.

### Kimi / Moonshot notes

- Global API: `https://api.moonshot.ai/v1`
- China API: `https://api.moonshot.cn/v1` (operator selects via config if needed)
- Models: `kimi-k2.6`, `kimi-k2.5`, `moonshot-v1-*` family

### Gemini notes

- OpenAI-compatible: `https://generativelanguage.googleapis.com/v1beta/openai`
- Native SDK default: `https://generativelanguage.googleapis.com`

## Custom OpenAI-compatible slot

| Field | Config key | Validation |
|-------|------------|------------|
| Base URL | `CUSTOM_LLM_BASE_URL` | HTTPS URL, no trailing slash required |
| API key | `CUSTOM_LLM_API_KEY` | Secret, stored encrypted in `app_settings` |
| Model | `CUSTOM_LLM_MODEL` | `^[a-zA-Z0-9][a-zA-Z0-9._:/-]{0,127}$` |

## Existing scheduler chain (unchanged defaults)

Groq → Cerebras → OpenRouter → Gemini — catalog providers extend failover when keys are configured.

## Cost guards (instance-wide)

| Setting | Default | Purpose |
|---------|---------|---------|
| `AI_DAILY_REQUEST_CAP` | 200 | Max LLM requests per UTC day |
| `AI_PER_MINUTE_CAP` | 10 | Burst limit |
| UI debounce | 5s | Prevent double-click hammering |

## References

- [Kimi Code CLI providers](https://moonshotai.github.io/kimi-code/en/configuration/providers.html)
- [DeepSeek API SDK compatibility](https://deepseekai.guide/api/deepseek-api-sdk/)
- [Google Gemini OpenAI compatibility](https://ai.google.dev/gemini-api/docs/openai)
