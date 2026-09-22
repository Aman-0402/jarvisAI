# Multilingual Voice (Hindi/English/Hinglish) + One-Click Installer

## Context

Jarvis's voice pipeline (wake word → STT → LLM → TTS) is currently English-only:
STT is hardcoded to `language="en"`, the LLM system prompt has no language
guidance, and TTS always uses the single cached English voice/pipeline.
The user wants full Hindi / English / Hinglish (code-mixed) support end to
end, and wants the Ollama LLM runtime folded into `install.bat` so a fresh
Windows machine needs no manual steps.

## Goals

1. Understand spoken Hindi, English, and Hinglish input.
2. Reply in the same language/script the user spoke in.
3. Speak the reply back in the matching voice (Hindi voice for Devanagari
   replies, English voice otherwise).
4. `install.bat` installs and configures Ollama + pulls the default model
   automatically, project-scoped, idempotently.

## Non-goals

- No new STT/TTS engines. Whisper (multilingual) and Kokoro (has native
  Hindi voices) already cover this.
- No per-user language preference setting — language is inferred per
  utterance, not configured globally.
- No support for languages beyond Hindi/English/Hinglish in this pass.

## Design

### 1. STT — auto language detection

`jarvis/stt.py`: `transcribe_audio()` currently calls
`model.transcribe(audio, beam_size=5, language="en")` in two places (primary
path and CPU-fallback retry path). Change both to `language=None`, letting
faster-whisper auto-detect the spoken language per utterance. The `small`
Whisper model is multilingual and handles Hindi (Devanagari transcription)
and code-switched Hinglish reasonably without a model swap.

### 2. LLM — mirror input language

`jarvis/main.py`: `_system_prompt()` gets an added instruction block telling
the model to reply in the same language and script the user just used —
Devanagari when the user spoke Hindi, Roman script when the user spoke
English or Hinglish. Existing conciseness/tone instructions are unchanged.

### 3. TTS — script-based voice/pipeline switch

`jarvis/tts.py` currently has one global `_pipeline` (Kokoro `KPipeline`,
`lang_code="a"`) and one global `_voice_tensor` (English voice from
`config.yaml`). This becomes per-language-code caching:

- `_pipelines: dict[str, KPipeline]` keyed by `lang_code` (`"a"` English,
  `"h"` Hindi), replacing the single `_pipeline` global.
- `_voice_tensors: dict[str, Tensor]` keyed by voice name, replacing the
  single `_voice_tensor` global.
- New helper `_is_devanagari(text: str) -> bool`: returns True if the text
  contains any character in the Devanagari Unicode block (`ऀ`–`ॿ`).
- New helper `_select_lang_and_voice(text: str) -> tuple[str, str]`: returns
  `("h", cfg["tts"]["voice_hi"])` if `_is_devanagari(text)`, else
  `("a", cfg["tts"]["voice"])`.
- `speak_to_bytes()` and `speak_streamed()` call `_select_lang_and_voice()`
  on the text before synthesis and use the returned lang_code/voice to fetch
  the right cached pipeline/voice tensor.
- Hinglish (Roman-script code-mixed replies) rides the English pipeline —
  Kokoro's Hindi G2P is tuned for Devanagari input and would mishandle
  romanized text, so script presence (not language) drives the switch.
- `speak_streamed()` splits into sentences and speaks each with its own
  detected language — a reply that mixes a Devanagari sentence and a Roman
  one will correctly switch voices mid-reply.

### 4. Config

`config.yaml`: add `tts.voice_hi: hf_alpha` (Hindi female voice, matching
the existing `tts.voice: af_heart` English female default). No other config
changes.

### 5. Installer — bundle Ollama setup into install.bat

`install.bat` gets a new step after wake-word model download:

1. Check `.\ollama\app\ollama.exe` exists — skip download/install if so
   (idempotent).
2. If missing: download `https://ollama.com/download/OllamaSetup.exe` to
   `.\ollama\OllamaSetup.exe`, silent-install
   (`/VERYSILENT /NORESTART /DIR=".\ollama\app"`) so it's project-scoped
   and gitignored, not a system-wide install.
3. Set user-level env var `OLLAMA_MODELS` to `.\ollama-models` (absolute
   path resolved at install time) via `setx`, so model weights land in the
   project folder, not `%USERPROFILE%\.ollama`.
4. Start `.\ollama\app\ollama.exe serve` in the background if not already
   listening on `11434`.
5. Run `.\ollama\app\ollama.exe pull qwen3:8b` — skip if `ollama list`
   already shows it (idempotent, avoids re-downloading ~5GB on reinstall).

`.gitignore` already covers `ollama/` and `ollama-models/`? No — needs two
new entries: `ollama/` and `ollama-models/`.

## Testing

- `tests/test_stt.py` (or equivalent): update any test asserting
  `language="en"` is passed to `model.transcribe` — now asserts
  `language=None`.
- New unit tests for `_is_devanagari()`: Devanagari string → True, pure
  English/Hinglish (Roman script) → False, empty string → False.
- New unit tests for `_select_lang_and_voice()`: Devanagari text → `("h",
  "hf_alpha")`; Roman/English/Hinglish text → `("a", "af_heart")` (reading
  from config).
- Existing TTS tests updated for the pipeline/voice caches now being dicts
  keyed by lang_code/voice name instead of single globals.
- Installer changes are manual/integration-tested (Windows batch script,
  not unit-testable in pytest) — verified by running `install.bat` fresh
  and confirming `ollama\app\ollama.exe`, `ollama-models\`, and the pulled
  model exist afterward.

## Error handling

- STT: unchanged fallback-to-CPU-on-CUDA-failure behavior; language
  auto-detect doesn't change error paths.
- TTS: if Devanagari detected but `voice_hi` fails to load (e.g. offline,
  not yet cached), falls back to the English voice/pipeline rather than
  crashing the speak call — mirrors the existing local-cache-first pattern
  in `_get_voice()`.
- Installer: each step checks for prior completion before acting (idempotent
  reruns), and download/install failures print an error and exit
  non-zero, matching the existing `install.bat` error-handling style.
