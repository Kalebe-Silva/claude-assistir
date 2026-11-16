---
name: assistir
description: Assiste a um vídeo (YouTube, outros sites ou arquivo local) e responde sobre ele. Use quando o usuário mandar um link de vídeo, pedir resumo, explicação ou perguntar o que aparece ou é dito num vídeo.
---

# Assistir a um vídeo

O script `assistir.py` (nesta pasta) baixa o vídeo, tira quadros sem repetição e pega a fala: usa a legenda do vídeo ou transcreve o áudio no próprio computador com o whisper. Nenhum áudio ou vídeo vai para serviços de IA externos.

## Passos

1. Rode o script em segundo plano (`run_in_background`), porque vídeo longo demora:

   ```
   python "${CLAUDE_SKILL_DIR}/assistir.py" "<url ou arquivo>" [--idioma pt] [--inicio mm:ss --fim mm:ss] [--quadros 40]
   ```

   - No Windows, se `python` não existir, tente `py -3`. Se nenhum funcionar, peça ao usuário para instalar o Python 3.12 (`winget install Python.Python.3.12`) e abrir um terminal novo.
   - Na primeira execução o script instala as dependências sozinho em `~/.assistir` (uns 800 MB, alguns minutos) e baixa o modelo do whisper (~500 MB). Avise o usuário.
   - Vídeo longo e pergunta sobre um trecho: use `--inicio/--fim`.
   - Pergunta só sobre a fala: `--quadros 5`. Pergunta sobre a tela (passo a passo, configuração): `--quadros 60`.
   - Vídeo que pede login (Instagram, stories, LinkedIn Learning, vídeo privado do Facebook, gravação do Teams/SharePoint): acrescente `--navegador <nome>` com o navegador em que o usuário está logado no site (`firefox`, `edge`, `chrome`...). Se o script avisar que o site pediu login, pergunte ao usuário qual navegador ele usa e rode de novo com a opção. No Windows, o Chrome e o Edge só liberam os cookies com o navegador totalmente fechado; o Firefox funciona aberto. Outra saída é `--cookies cookies.txt`, um arquivo exportado do navegador por extensão.
   - `--modelo medium` transcreve melhor e é cerca de 3× mais lento; use só se a fala sair ruim.
2. A última linha da saída é o caminho do `roteiro.md`. Leia o roteiro: ele traz título, canal, duração e a linha do tempo com cada quadro e a fala daquele trecho.
3. Abra com Read os quadros relevantes para a pergunta (todos, se for resumo de vídeo curto). Não invente o que não viu: se a pergunta depende de um momento sem quadro, rode de novo com `--inicio/--fim` naquele trecho.
4. Responda citando os tempos (ex.: "em 02:28 ele mostra...").

## Observações

- A transcrição automática erra nomes próprios (ex.: "Cloud" no lugar de "Claude"); corrija pelo contexto.
- A saída fica em `~/Videos/assistidos/<data>-<título>/` (`roteiro.md`, `transcricao.txt`, `quadros/`). A variável `ASSISTIR_SAIDA` troca a pasta.
- Sites suportados: YouTube, LinkedIn, TikTok, X/Twitter, Facebook, Instagram, Vimeo, Reddit, Twitch, Loom, Globo e mais de 1.700 outros (os do yt-dlp).
- Se o YouTube recusar a legenda (erro 429), o script transcreve o áudio sozinho. Isso é normal.
- Transcrição local em CPU leva perto de 0,7× a duração do vídeo (14 min de vídeo ≈ 10 min).
