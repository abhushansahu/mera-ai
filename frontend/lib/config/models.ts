export const PROVIDER_OPTIONS = [
  { value: 'openrouter', label: 'OpenRouter (cloud)' },
  { value: 'lmstudio', label: 'LM Studio (local)' },
  { value: 'cursor-local', label: 'Cursor Local Agent' },
];

export const MODELS_BY_PROVIDER: Record<string, string[]> = {
  openrouter: [
    'openai/gpt-4o-mini',
    'openai/gpt-4o',
    'anthropic/claude-3.5-sonnet',
    'google/gemini-2.0-flash-exp',
  ],
  lmstudio: ['google/gemma-3-4b-it', 'google/gemma-3-12b-it', 'meta-llama/llama-3.2-3b-instruct'],
  'cursor-local': ['gemma3:4b', 'qwen2.5-coder:7b', 'llama3.2:3b'],
};
