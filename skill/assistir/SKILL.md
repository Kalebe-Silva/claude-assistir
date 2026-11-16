---
name: assistir
description: Assiste a um vídeo (YouTube, outros sites ou arquivo local) e responde sobre ele. Use quando o usuário mandar um link de vídeo, pedir resumo, explicação ou perguntar o que aparece ou é dito num vídeo.
---

# Assistir a um vídeo

O comando `assistir` baixa o vídeo, tira quadros sem repetição e pega a fala (legenda do vídeo ou transcrição local com o whisper). Nada é enviado para serviços de IA externos.

## Passos

1. Rode em segundo plano (vídeo longo demora: a transcrição local leva ~0,7× a duração do vídeo):
   `assistir "<url ou arquivo>" [--idioma pt] [--inicio mm:ss --fim mm:ss] [--quadros 40]`
   - Vídeo longo e a pergunta é sobre um trecho: use `--inicio/--fim`.
   - Pergunta só sobre a fala: `--quadros 5`. Pergunta sobre a tela (passo a passo, configuração): `--quadros 60`.
   - `--modelo medium` transcreve melhor e é ~3× mais lento; use só se a fala sair ruim.
2. A última linha da saída é o caminho do `roteiro.md`. Leia o roteiro: ele traz título, canal, duração e a linha do tempo com cada quadro e a fala daquele trecho.
3. Abra com Read os quadros relevantes para a pergunta (todos, se for um resumo de vídeo curto). Não invente o que não viu: se a pergunta depende de um momento sem quadro, rode de novo com `--inicio/--fim` naquele trecho.
4. Responda citando os tempos (ex.: "em 02:28 ele mostra...").

## Observações

- A transcrição automática erra nomes próprios (ex.: "Cloud" no lugar de "Claude"); corrija pelo contexto.
- A saída fica em `~/Analises Claude/videos-assistidos/<data>-<título>/` (roteiro.md, transcricao.txt, quadros/).
- Se o YouTube recusar a legenda (429), o comando transcreve o áudio sozinho.
