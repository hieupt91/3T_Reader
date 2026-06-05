# ADR 005 - AI Provider Abstraction

## Status

Accepted.

## Decision

AI features use a multi-provider abstraction with provider preference and fallback behavior configured through AI settings.

## Rationale

- Different deployments may use OpenAI, Anthropic, Gemini, OpenRouter, Groq, HuggingFace, or local Ollama.
- Provider fallback keeps user workflows available when one provider is unavailable.
- Secure config storage avoids writing API keys in plain text.

## Consequences

- New AI actions should go through the provider layer rather than calling a provider SDK directly.
- Settings UI must preserve backward compatibility with existing environment/config keys.
