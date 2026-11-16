# assistir

Faz o Claude "assistir" a um vídeo: baixa (YouTube e outros sites, via yt-dlp) ou usa um arquivo local, tira quadros sem repetição, pega a legenda ou transcreve o áudio localmente (faster-whisper) e grava um `roteiro.md` com quadros e falas na linha do tempo. Nada vai para serviços de IA externos.

    assistir <url|arquivo> [--idioma pt] [--inicio mm:ss] [--fim mm:ss] [--quadros 40] [--modelo small|medium]

- Código: `assistir.py`; atalho: `bin/assistir` (link em `~/.local/bin`).
- Skill do Claude Code: `skill/assistir/SKILL.md` (link em `~/.claude/skills/assistir`).
- Dependências no servidor: yt-dlp em `~/.local/opt/ytdlp`, faster-whisper em `~/.local/opt/whisper`, ffmpeg do imageio, bun como runtime JS do YouTube. Caminhos trocáveis por `ASSISTIR_YTDLP`, `ASSISTIR_WHISPER`, `ASSISTIR_FFMPEG`, `ASSISTIR_BUN`, `ASSISTIR_SAIDA`.
- Desempenho (4 CPUs): vídeo de 14 min sem legenda levou ~9,5 min (whisper small).
