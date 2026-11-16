# assistir

Faz o Claude "assistir" a um vídeo: baixa (YouTube e outros sites, via yt-dlp) ou usa um arquivo local, tira quadros sem repetição, pega a legenda ou transcreve o áudio localmente (faster-whisper) e grava um `roteiro.md` com quadros e falas na linha do tempo. Nada vai para serviços de IA externos.

    assistir <url|arquivo> [--idioma pt] [--inicio mm:ss] [--fim mm:ss] [--quadros 40] [--modelo small|medium]

- É um plugin do Claude Code: marketplace `tecadi-ti` (`.claude-plugin/marketplace.json`), plugin em `plugin/`, skill e script em `plugin/skills/assistir/`.
- No servidor: atalho `bin/assistir` (link em `~/.local/bin`, saída em `~/Analises Claude/videos-assistidos`) e skill linkada em `~/.claude/skills/assistir`.
- Em outro PC, a primeira execução instala as dependências em `~/.assistir` (pip --target, ~800 MB) e baixa o modelo do whisper (~500 MB). Precisa do Python 3.10+ com pip.

## Instalar no Claude Code (PC dos colegas)

    /plugin marketplace add <owner>/<repo>
    /plugin install assistir@tecadi-ti

Depois é só mandar um link de vídeo e pedir o resumo.
- Dependências no servidor: yt-dlp em `~/.local/opt/ytdlp`, faster-whisper em `~/.local/opt/whisper`, ffmpeg do imageio, bun como runtime JS do YouTube. Caminhos trocáveis por `ASSISTIR_YTDLP`, `ASSISTIR_WHISPER`, `ASSISTIR_FFMPEG`, `ASSISTIR_BUN`, `ASSISTIR_SAIDA`.
- Desempenho (4 CPUs): vídeo de 14 min sem legenda levou ~9,5 min (whisper small).
