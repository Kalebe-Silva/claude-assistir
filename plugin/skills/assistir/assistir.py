#!/usr/bin/env python3
"""assistir: prepara um vídeo para o Claude "assistir".

Baixa o vídeo (YouTube e outros sites suportados pelo yt-dlp) ou usa um arquivo local,
tira quadros sem repetição, pega a legenda ou transcreve o áudio localmente (faster-whisper)
e grava um roteiro.md que junta quadros e falas na linha do tempo.

Tudo roda na máquina de quem usa: nada de áudio ou vídeo vai para serviços de IA externos.
Na primeira vez, instala em ~/.assistir (pip --target) o yt-dlp,
faster-whisper, ffmpeg (imageio-ffmpeg) e deno (exigido pelo YouTube).

Uso:
  assistir <url|arquivo> [--inicio mm:ss] [--fim mm:ss] [--quadros 40]
           [--modelo small|medium] [--idioma pt] [--sem-legenda] [--manter-video] [--saida DIR]
           [--navegador firefox|edge|chrome[:perfil]] [--cookies cookies.txt]
"""
import argparse, datetime, json, os, re, shutil, subprocess, sys, tempfile, unicodedata
from pathlib import Path

for _s in (sys.stdout, sys.stderr):  # console do Windows não é UTF-8 por padrão
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HOME = Path.home()
# instalações "vendoradas" do servidor da Tecadi; em outras máquinas não existem e são ignoradas
for _v in (os.environ.get("ASSISTIR_WHISPER", HOME / ".local/opt/whisper"),
           os.environ.get("ASSISTIR_YTDLP", HOME / ".local/opt/ytdlp")):
    if Path(_v).is_dir():
        sys.path.insert(0, str(_v))
PACOTES = ["yt-dlp[default]", "faster-whisper", "imageio-ffmpeg", "deno"]
LIBS = Path(os.environ.get("ASSISTIR_LIBS", HOME / ".assistir" / f"libs-py{sys.version_info[0]}{sys.version_info[1]}"))
_videos = HOME / "Videos"
SAIDA_PADRAO = Path(os.environ.get("ASSISTIR_SAIDA") or ((_videos if _videos.is_dir() else HOME) / "assistidos"))
LARGURA = 768  # largura dos quadros: legível para o Claude e barato em tokens


def garantir_dependencias():
    """Usa o que já está instalado; se faltar algo, instala uma vez em ~/.assistir (pip --target)."""
    if LIBS.is_dir():
        sys.path.insert(0, str(LIBS))
    try:
        import yt_dlp, faster_whisper, numpy  # noqa: F401
        return
    except ImportError:
        pass
    pip = [sys.executable, os.environ["ASSISTIR_PIP"]] if os.environ.get("ASSISTIR_PIP") else [sys.executable, "-m", "pip"]
    log(f"primeira execução: instalando dependências em {LIBS} (alguns minutos, ~800 MB)...")
    LIBS.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([*pip, "install", "-q", "--disable-pip-version-check", "--upgrade", "--target", str(LIBS), *PACOTES])
    if r.returncode:
        raise SystemExit("[assistir] não consegui instalar as dependências com o pip. "
                         "Confira se o Python 3.10+ está instalado com o pip (python -m pip --version).")
    import importlib
    importlib.invalidate_caches()
    if str(LIBS) not in sys.path:
        sys.path.insert(0, str(LIBS))
    import yt_dlp, faster_whisper, numpy  # noqa: F401


def achar_ffmpeg():
    if os.environ.get("ASSISTIR_FFMPEG"):
        return os.environ["ASSISTIR_FFMPEG"]
    if shutil.which("ffmpeg"):
        return shutil.which("ffmpeg")
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    fixo = HOME / ".local/opt/pyvideo/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2"
    if fixo.exists():
        return str(fixo)
    raise SystemExit("[assistir] ffmpeg não encontrado.")


def achar_js():
    """Runtime JavaScript que o yt-dlp usa para o YouTube: deno, bun ou node."""
    for nome in ("deno", "bun", "node"):
        caminho = os.environ.get(f"ASSISTIR_{nome.upper()}") or shutil.which(nome)
        if not caminho and nome == "bun" and (HOME / ".bun/bin/bun").exists():
            caminho = str(HOME / ".bun/bin/bun")
        if caminho:
            return {nome: {"path": caminho}}
    try:
        import deno
        return {"deno": {"path": deno.find_deno_bin()}}
    except Exception:
        return None


FFMPEG = None  # definido em main(), depois de garantir as dependências


def log(msg):
    print(f"[assistir] {msg}", file=sys.stderr, flush=True)


def seg(txt):
    """'90', '1:30' ou '01:01:30' -> segundos."""
    if txt is None:
        return None
    p = [float(x) for x in str(txt).split(":")]
    s = 0.0
    for x in p:
        s = s * 60 + x
    return s


def hms(s):
    s = int(s)
    h, m, ss = s // 3600, s % 3600 // 60, s % 60
    return f"{h:02d}:{m:02d}:{ss:02d}" if h else f"{m:02d}:{ss:02d}"


def slug(txt, n=50):
    t = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode()
    t = re.sub(r"[^A-Za-z0-9]+", "-", t).strip("-").lower()
    return t[:n].strip("-") or "video"


def duracao(arq):
    r = subprocess.run([FFMPEG, "-hide_banner", "-i", str(arq)], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.?\d*)", r.stderr)
    if not m:
        raise SystemExit(f"Não consegui ler a duração de {arq}")
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])


# ---------------------------------------------------------------- download
def baixar(url, pasta, idioma, com_legenda, navegador=None, cookies=None):
    import yt_dlp

    # legenda manual no idioma pedido ou a automática no idioma original (-orig);
    # evita "pt-en" e afins, que são traduções automáticas ruins
    langs = [idioma, f"{idioma}-BR", f"{idioma}-orig"] if idioma else ["pt", "pt-BR", "en", ".*-orig"]
    opts = {
        "outtmpl": str(pasta / "video.%(ext)s"),
        "format": "bv*[height<=720]+ba/b[height<=720]/b",
        "merge_output_format": "mp4",
        "ffmpeg_location": FFMPEG,
        "quiet": True, "no_warnings": True, "noprogress": True,
        "noplaylist": True,
        "writesubtitles": com_legenda, "writeautomaticsub": com_legenda,
        "subtitleslangs": langs, "subtitlesformat": "vtt",
    }
    js = achar_js()
    if js:
        opts["js_runtimes"] = js
    if navegador:
        # "firefox", "edge", "chrome" ou "firefox:NomeDoPerfil": usa a sessão já aberta no navegador
        nome, _, perfil = navegador.partition(":")
        opts["cookiesfrombrowser"] = (nome.lower(), perfil or None, None, None)
    if cookies:
        opts["cookiefile"] = str(Path(cookies).expanduser())
    try:
        with yt_dlp.YoutubeDL(opts) as y:
            info = y.extract_info(url, download=True)
    except yt_dlp.utils.DownloadError as e:
        msg = str(e)
        if re.search(r"(?i)could not find .*cookies database|unsupported browser", msg):
            raise SystemExit(f"[assistir] não achei o navegador '{navegador}' neste computador. "
                             "Use um navegador instalado e com login feito no site (firefox, edge, chrome...).")
        if re.search(r"(?i)could not (copy|decrypt).*cookie|failed to decrypt|cookie database", msg):
            raise SystemExit("[assistir] não consegui ler os cookies do navegador. No Windows, o Chrome e o Edge "
                             "bloqueiam a leitura com o navegador aberto: feche-o por completo e tente de novo, "
                             "ou use --navegador firefox.")
        if re.search(r"(?i)log ?in|sign in|cookies|private|authenticat|registered users|not available", msg) \
                and "subtitle" not in msg.lower():
            dica = ("Tente de novo com --navegador firefox (ou edge/chrome), logado no site."
                    if not (navegador or cookies) else
                    "Confira se a conta logada nesse navegador tem acesso ao vídeo.")
            raise SystemExit("[assistir] o site pediu login para este vídeo. " + dica)
        if not com_legenda or "subtitle" not in msg.lower():
            raise
        # o YouTube costuma recusar legenda com 429; segue sem ela e transcreve local
        log("legenda indisponível (" + str(e).split(":")[-1].strip() + "); vou transcrever o áudio")
        for p in pasta.glob("video*"):
            p.unlink()
        return baixar(url, pasta, idioma, False, navegador, cookies)
    video = next(pasta.glob("video.mp4"), None) or next(
        (p for p in pasta.glob("video.*") if p.suffix not in (".vtt",)), None)
    legendas = sorted(pasta.glob("video*.vtt"))
    # legenda manual vem antes da automática quando as duas existem
    manuais = set((info.get("subtitles") or {}).keys())
    legendas.sort(key=lambda p: 0 if p.suffixes[-2].lstrip(".") in manuais else 1)
    meta = {k: info.get(k) for k in ("title", "uploader", "upload_date", "duration", "webpage_url", "language")}
    return video, (legendas[0] if legendas else None), meta


# ---------------------------------------------------------------- transcrição
def ler_vtt(arq):
    """Converte VTT em [(ini, fim, texto)], tirando as repetições da legenda automática."""
    blocos, cur = [], None
    for linha in arq.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = re.match(r"(\d+:)?(\d+):(\d+\.\d+) --> (\d+:)?(\d+):(\d+\.\d+)", linha)
        if m:
            ini = seg((m[1] or "0:") + m[2] + ":" + m[3])
            fim = seg((m[4] or "0:") + m[5] + ":" + m[6])
            cur = [ini, fim, []]
            blocos.append(cur)
        elif cur is not None and linha.strip():
            t = re.sub(r"<[^>]+>", "", linha).strip()
            if t:
                cur[2].append(t)
    saida, ultima = [], ""
    for ini, fim, linhas in blocos:
        for orig in linhas:
            orig = re.sub(r"\s+", " ", orig)
            if not orig or orig == ultima or ultima.endswith(orig):
                continue
            # legenda automática repete a linha anterior como prefixo
            t = orig[len(ultima):].strip() if ultima and orig.startswith(ultima) else orig
            ultima = orig
            if t:
                saida.append((ini, fim, t))
    return saida


def transcrever(video, idioma, modelo, ini, fim, dica=None):
    import numpy as np
    from faster_whisper import WhisperModel

    cmd = [FFMPEG, "-v", "error"]
    if ini:
        cmd += ["-ss", str(ini)]
    if fim:
        cmd += ["-to", str(fim)]
    cmd += ["-i", str(video), "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"]
    pcm = subprocess.run(cmd, capture_output=True, check=True).stdout
    if not pcm:
        return []
    log(f"transcrevendo {len(pcm) / 32000:.0f}s de áudio com o whisper {modelo} (local)...")
    m = WhisperModel(modelo, device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 4)
    segs, _ = m.transcribe(np.frombuffer(pcm, np.int16).astype(np.float32) / 32768,
                           language=idioma or None, vad_filter=True,
                           initial_prompt=dica or None)  # título ajuda com nomes próprios
    base = ini or 0
    return [(base + s.start, base + s.end, s.text.strip()) for s in segs if s.text.strip()]


# ---------------------------------------------------------------- quadros
def quadros(video, pasta, ini, fim, maximo):
    import numpy as np  # vem junto com o faster-whisper
    total = duracao(video)
    a, b = ini or 0, min(fim or total, total)
    trecho = max(b - a, 1)
    # candidatos: ~4 por quadro final, no mínimo 1 a cada 0,5 s e no máximo 1 a cada 10 s
    passo = min(max(trecho / (maximo * 4), 0.5), 10)
    fps = 1 / passo
    base = [FFMPEG, "-v", "error", "-ss", str(a), "-to", str(b), "-i", str(video)]
    # passada 1: miniaturas 16x16 em cinza para medir o quanto cada candidato muda
    raw = subprocess.run(base + ["-vf", f"fps={fps},scale=16:16,format=gray", "-f", "rawvideo", "-"],
                         capture_output=True, check=True).stdout
    mini = np.frombuffer(raw, np.uint8).reshape(-1, 256).astype(np.int16)
    if len(mini) == 0:
        return []
    tempos = [a + i * passo for i in range(len(mini))]
    # quadro novo quando a cena muda (slide, corte) e já passou um tempo mínimo do anterior
    gap_min = max(trecho / (maximo * 2), 1.0)
    # cena parada por muito tempo: garante um quadro de tempos em tempos
    gap_max = max(2 * trecho / maximo, 20.0)
    escolhidos, ref = [0], mini[0]
    for i in range(1, len(mini)):
        dt = tempos[i] - tempos[escolhidos[-1]]
        mudou = np.abs(mini[i] - ref).mean() > 12
        if (mudou and dt >= gap_min) or dt >= gap_max:
            escolhidos.append(i)
            ref = mini[i]
    if len(escolhidos) > maximo:  # mantém espalhado na linha do tempo
        idx = np.linspace(0, len(escolhidos) - 1, maximo).round().astype(int)
        escolhidos = [escolhidos[i] for i in sorted(set(idx))]
    # passada 2: salva só os escolhidos, na largura final
    pq = pasta / "quadros"
    pq.mkdir(exist_ok=True)
    saida = []
    for n, i in enumerate(escolhidos, 1):
        t = tempos[i]
        nome = f"q{n:03d}-{hms(t).replace(':', 'm', 1).replace(':', 'm')}s.jpg"
        subprocess.run([FFMPEG, "-v", "error", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1",
                        "-vf", f"scale='min({LARGURA},iw)':-2", "-q:v", "4", "-y", str(pq / nome)], check=True)
        saida.append((t, nome))
    return saida


# ---------------------------------------------------------------- roteiro
def roteiro(pasta, meta, falas, qs, fonte_fala, ini, fim):
    L = [f"# {meta.get('title') or 'Vídeo'}", ""]
    for rot, k in (("Canal", "uploader"), ("Link", "webpage_url"), ("Arquivo", "arquivo")):
        if meta.get(k):
            L.append(f"- {rot}: {meta[k]}")
    if meta.get("duration"):
        L.append(f"- Duração: {hms(meta['duration'])}")
    if ini or fim:
        L.append(f"- Trecho analisado: {hms(ini or 0)} a {hms(fim) if fim else 'fim'}")
    L.append(f"- Fala: {fonte_fala}")
    L.append(f"- Quadros: {len(qs)} em `quadros/` (abra com a ferramenta Read para ver)")
    L += ["", "## Linha do tempo", ""]
    falas = [f for f in falas if (not ini or f[1] >= ini) and (not fim or f[0] <= fim)]
    eventos = [(t, 0, n) for t, n in qs] + [(i, 1, txt) for i, _, txt in falas]
    eventos.sort(key=lambda e: (e[0], e[1]))
    buf = []
    for t, tipo, x in eventos:
        if tipo == 0:
            if buf:
                L.append(" ".join(buf)); L.append(""); buf = []
            L.append(f"### {hms(t)} · quadro `quadros/{x}`")
            L.append("")
        else:
            buf.append(f"[{hms(t)}] {x}")
    if buf:
        L.append(" ".join(buf))
    (pasta / "roteiro.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    (pasta / "transcricao.txt").write_text(
        "\n".join(f"[{hms(i)}] {t}" for i, _, t in falas) + "\n", encoding="utf-8")


def main():
    global FFMPEG
    garantir_dependencias()
    FFMPEG = achar_ffmpeg()
    ap = argparse.ArgumentParser(description="Prepara um vídeo para o Claude assistir (quadros + fala).")
    ap.add_argument("fonte", help="URL do vídeo ou caminho de um arquivo local")
    ap.add_argument("--inicio"), ap.add_argument("--fim")
    ap.add_argument("--quadros", type=int, default=40, help="máximo de quadros (padrão 40)")
    ap.add_argument("--modelo", default="small", help="modelo do whisper: small (rápido) ou medium (melhor)")
    ap.add_argument("--idioma", default=None, help="idioma da fala, ex.: pt, en (padrão: detectar)")
    ap.add_argument("--sem-legenda", action="store_true", help="ignora a legenda e transcreve o áudio")
    ap.add_argument("--manter-video", action="store_true", help="não apaga o vídeo baixado")
    ap.add_argument("--saida", help=f"pasta base (padrão {SAIDA_PADRAO})")
    ap.add_argument("--navegador", help="usa o login do navegador para vídeos que pedem conta: "
                    "firefox, edge, chrome, brave... (opcional :perfil, ex.: firefox:default-release)")
    ap.add_argument("--cookies", help="arquivo cookies.txt (formato Netscape) exportado do navegador")
    a = ap.parse_args()
    ini, fim = seg(a.inicio), seg(a.fim)

    local = Path(a.fonte).expanduser()
    tmp = Path(tempfile.mkdtemp(prefix="assistir-"))
    try:
        if local.exists():
            video, leg, meta = local, None, {"title": local.stem, "arquivo": str(local)}
        else:
            log("baixando...")
            video, leg, meta = baixar(a.fonte, tmp, a.idioma, not a.sem_legenda, a.navegador, a.cookies)
            if not video:
                raise SystemExit("O download não gerou arquivo de vídeo.")
        meta.setdefault("duration", duracao(video))
        data = datetime.date.today().isoformat()
        pasta = Path(a.saida or SAIDA_PADRAO) / f"{data}-{slug(meta.get('title') or 'video')}"
        pasta.mkdir(parents=True, exist_ok=True)

        log("tirando quadros...")
        qs = quadros(video, pasta, ini, fim, max(a.quadros, 1))

        if leg:
            falas, fonte_fala = ler_vtt(leg), f"legenda do vídeo ({leg.suffixes[-2].lstrip('.')})"
        else:
            falas = transcrever(video, a.idioma, a.modelo, ini, fim, meta.get("title"))
            fonte_fala = f"transcrição local (whisper {a.modelo})" if falas else "sem fala detectada"

        roteiro(pasta, meta, falas, qs, fonte_fala, ini, fim)
        if a.manter_video and not local.exists():
            shutil.copy2(video, pasta / f"video{video.suffix}")
        (pasta / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        log(f"pronto: {len(qs)} quadros, {len(falas)} trechos de fala")
        print(pasta / "roteiro.md")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
