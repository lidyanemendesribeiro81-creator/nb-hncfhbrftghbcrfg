import discord
from discord.ext import commands
import asyncio
import aiohttp
from datetime import datetime, timedelta
import random
import string

# ══════════════════════════════════════════
#   CONFIGURAÇÃO — edite antes de rodar
# ══════════════════════════════════════════
BOT_TOKEN   = "MTU3NTI1NTA2NzkxMTUyODUwOA.GTX6cJ.CYFp5MlcPmAjzyLWmjXW50FLnTsIfIwqDKtMFI	"          # Token do bot no Discord Developer Portal
BRAWL_API   = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiIsImtpZCI6IjI4YTMxOGY3LTAwMDAtYTFlYi03ZmExLTJjNzQzM2M2Y2NhNSJ9.eyJpc3MiOiJzdXBlcmNlbGwiLCJhdWQiOiJzdXBlcmNlbGw6Z2FtZWFwaSIsImp0aSI6ImMwNWYxM2Y1LWMxNDgtNDkyNi1iZWEwLTk5YTg0ZTkyNTYzZSIsImlhdCI6MTc5NTY0MTY5Nywic3ViIjoiZGV2ZWxvcGVyLzMxZDFhOTMyLTdmNGQtNGI5NS04MzE1LTg3NWE0YTljNzUwYiIsInNjb3BlcyI6WyJicmF3bHN0YXJzIl0sImxpbWl0cyI6W3sidGllciI6ImRldmVsb3Blci9zaWx2ZXIiLCJ0eXBlIjoidGhyb3R0bGluZyJ9LHsiY2lkcnMiOlsiNDUuMTY5LjY3LjIzNCJdLCJ0eXBlIjoiY2xpZW50In1dfQ.6Vr0x-j0aJv3iBmucaMNpezRllUyllEmjgSJyj_xBNlCwvO8CjciGEH83LPMTVhM4dZNVZO9tMqH7tj0j_yE4w"  # brawlapi.com ou API oficial
CATEGORY_ID = 1521924917417869402# ID da categoria onde criar canais temporários
# ══════════════════════════════════════════

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=".", intents=intents, help_command=None)

# ──────────────── ESTADO EM MEMÓRIA ────────────────
filas    = {}   # canal_id → {modo, jogadores, time1, time2, ...}
salas    = {}   # canal_temporario_id → {fila_info}
perfis   = {}   # user_id → brawl_tag
mvp_data = {}   # canal_id → {candidato, time_adversario_ids, votos}

# ──────────────── CONSTANTES DOS MODOS ────────────────
MODOS = {
    "futbrawl"    : {"nome": "⚽ Fut Brawl",    "jogadores": 6, "times": True},
    "3x3"         : {"nome": "🏆 3v3 Padrão",   "jogadores": 6, "times": True},
    "amistoso1x1" : {"nome": "⚔️  Amistoso 1x1","jogadores": 2, "times": False},
    "amistoso3x3" : {"nome": "🤝 Amistoso 3v3", "jogadores": 6, "times": True},
    "duelo"       : {"nome": "🗡️  Duelo",        "jogadores": 4, "times": True},
    "knockout"    : {"nome": "💀 Knockout",      "jogadores": 6, "times": True},
    "caçatesouro" : {"nome": "💎 Caça Tesouro",  "jogadores": 6, "times": True},
    "hotzone"     : {"nome": "🔥 Hot Zone",      "jogadores": 6, "times": True},
    "heist"       : {"nome": "🏦 Heist",         "jogadores": 6, "times": True},
    "bounty"      : {"nome": "🎯 Bounty",        "jogadores": 6, "times": True},
    "5x5"         : {"nome": "🎮 5v5 Especial",  "jogadores": 10,"times": True},
}

BRAWL_EMOJI = "🎮"

# ════════════════════════════════════════════════════
#   HELPERS
# ════════════════════════════════════════════════════
def gerar_codigo():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

def embed_base(titulo, cor=0xFFD700):
    e = discord.Embed(title=f"{BRAWL_EMOJI} {titulo}", color=cor)
    e.set_footer(text="Brawl Stars Queue Bot • Use .ajuda para ver comandos")
    return e

def formatar_jogadores(lista):
    return "\n".join(f"• {m.mention}" for m in lista) if lista else "_Nenhum ainda_"

async def buscar_perfil(tag: str):
    """Consulta a API do Brawl Stars para pegar dados do jogador."""
    tag_fmt = tag.upper().replace("#", "%23")
    url = f"https://api.brawlstars.com/v1/players/{tag_fmt}"
    headers = {"Authorization": f"Bearer {BRAWL_API}"}
    async with aiohttp.ClientSession() as s:
        async with s.get(url, headers=headers) as r:
            if r.status == 200:
                return await r.json()
            return None

def montar_embed_perfil(dados: dict, member: discord.Member):
    """Monta embed rico com tudo do perfil."""
    brawlers       = dados.get("brawlers", [])
    total_trofeus  = dados.get("trophies", 0)
    max_trofeus    = dados.get("highestTrophies", 0)
    gemas          = dados.get("gems", 0)
    ouro           = dados.get("gold", 0)
    exp            = dados.get("expLevel", 0)
    exp_pts        = dados.get("expPoints", 0)
    clube          = dados.get("club", {}).get("name", "Sem clube")
    victorias_3x3  = dados.get("3vs3Victories", 0)
    victorias_solo = dados.get("soloVictories", 0)
    victorias_duo  = dados.get("duoVictories", 0)
    nome           = dados.get("name", "?")
    tag            = dados.get("tag", "?")

    # Top 5 brawlers por troféus
    top_brawlers = sorted(brawlers, key=lambda x: x.get("trophies", 0), reverse=True)[:5]
    top_txt = "\n".join(
        f"`{i+1}.` **{b['name']}** — 🏆 {b['trophies']} | ⭐ Rank {b.get('rank',0)}"
        for i, b in enumerate(top_brawlers)
    ) or "_Nenhum_"

    # Brawlers desbloqueados vs total
    total_brawlers = len(brawlers)

    e = embed_base(f"Perfil de {nome}", cor=0x00C8FF)
    e.set_thumbnail(url=member.display_avatar.url)
    e.add_field(name="🏷️ Tag",           value=f"`{tag}`",           inline=True)
    e.add_field(name="⚡ Nível",          value=f"{exp} ({exp_pts} XP)", inline=True)
    e.add_field(name="🏛️ Clube",          value=clube,                inline=True)
    e.add_field(name="🏆 Troféus Atuais", value=f"{total_trofeus:,}", inline=True)
    e.add_field(name="🥇 Recorde",        value=f"{max_trofeus:,}",   inline=True)
    e.add_field(name="🎯 Brawlers",       value=f"{total_brawlers} desbloqueados", inline=True)
    e.add_field(name="💎 Gemas",          value=f"{gemas:,}",         inline=True)
    e.add_field(name="🪙 Ouro",           value=f"{ouro:,}",          inline=True)
    e.add_field(name="🎮 Vitórias",
                value=f"3v3: {victorias_3x3:,} | Solo: {victorias_solo:,} | Duo: {victorias_duo:,}",
                inline=False)
    e.add_field(name="🌟 Top 5 Brawlers", value=top_txt, inline=False)
    return e

# ════════════════════════════════════════════════════
#   EVENTOS
# ════════════════════════════════════════════════════
@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user} ({bot.user.id})")
    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.playing,
                                  name="Brawl Stars | .ajuda"))

# ════════════════════════════════════════════════════
#   COMANDO: .ajuda  /  .tutorial
# ════════════════════════════════════════════════════
@bot.command(name="ajuda", aliases=["tutorial", "help"])
async def ajuda(ctx):
    e = embed_base("Central de Ajuda — Brawl Stars Queue", cor=0xAA00FF)
    e.description = (
        "Bem-vindo ao bot de filas de Brawl Stars!\n"
        "Abaixo estão todos os comandos disponíveis."
    )
    e.add_field(name="📋 Modos Disponíveis",
        value=(
            "`.futbrawl` `.3x3` `.amistoso1x1` `.amistoso3x3`\n"
            "`.duelo` `.knockout` `.caçatesouro` `.hotzone`\n"
            "`.heist` `.bounty` `.5x5`"
        ), inline=False)

    e.add_field(name="🎮 Fluxo de Jogo",
        value=(
            "**1.** Use um comando de modo para abrir fila\n"
            "**2.** Jogadores usam `.entrar` para entrar\n"
            "**3.** Fila cheia → use `.go` para confirmar\n"
            "**4.** Use `.criar` no canal privado para gerar código da sala\n"
            "**5.** Use `.win Time1` ou `.win Time2` ao terminar\n"
            "**6.** Vote no MVP → sala fecha automaticamente"
        ), inline=False)

    e.add_field(name="⚙️ Comandos de Fila",
        value=(
            "`.entrar` — Entrar na fila aberta\n"
            "`.sair` — Sair da fila\n"
            "`.fila` — Ver status da fila atual\n"
            "`.cancelar` — Cancelar fila (quem criou)\n"
            "`.go` — Confirmar fila e criar sala privada"
        ), inline=False)

    e.add_field(name="🏠 Comandos da Sala",
        value=(
            "`.criar` — Gerar código da sala Brawl Stars\n"
            "`.win @time` — Declarar vencedor\n"
            "`.encerrar` — Fechar sala manualmente"
        ), inline=False)

    e.add_field(name="👤 Perfil",
        value=(
            "`.perfil #TAG` — Ver perfil completo\n"
            "`.vincular #TAG` — Vincular sua tag ao Discord\n"
            "`.meu` — Ver seu perfil vinculado"
        ), inline=False)

    e.add_field(name="ℹ️ Outros",
        value="`.ping` `.ajuda` `.tutorial`", inline=False)
    await ctx.send(embed=e)

# ════════════════════════════════════════════════════
#   COMANDO: .ping
# ════════════════════════════════════════════════════
@bot.command()
async def ping(ctx):
    ms = round(bot.latency * 1000)
    await ctx.send(embed=embed_base(f"🏓 Pong! `{ms}ms`", cor=0x00FF88))

# ════════════════════════════════════════════════════
#   CRIAR FILA — fábrica de comandos por modo
# ════════════════════════════════════════════════════
def criar_comando_modo(chave: str):
    @bot.command(name=chave)
    async def _cmd(ctx):
        cid = ctx.channel.id
        if cid in filas:
            fila = filas[cid]
            await ctx.send(embed=embed_base(
                f"Já existe uma fila de **{fila['modo_nome']}** aqui!\n"
                f"Use `.fila` para ver ou `.cancelar` para encerrar.",
                cor=0xFF4444))
            return

        info = MODOS[chave]
        filas[cid] = {
            "modo"       : chave,
            "modo_nome"  : info["nome"],
            "max"        : info["jogadores"],
            "times"      : info["times"],
            "jogadores"  : [],
            "criador"    : ctx.author,
            "criado_em"  : datetime.utcnow(),
        }

        e = embed_base(f"Fila Aberta — {info['nome']}", cor=0x00FF88)
        e.description = (
            f"**Capacidade:** {info['jogadores']} jogadores\n"
            f"**Criada por:** {ctx.author.mention}\n\n"
            f"Use **`.entrar`** para participar!\n"
            f"Use **`.fila`** para ver o status."
        )
        e.add_field(name="Jogadores (0/{})".format(info["jogadores"]),
                    value="_Nenhum ainda_")
        await ctx.send(embed=e)

    _cmd.__name__ = f"modo_{chave}"
    return _cmd

# Registra um comando por modo
for _chave in MODOS:
    criar_comando_modo(_chave)

# ════════════════════════════════════════════════════
#   .entrar
# ════════════════════════════════════════════════════
@bot.command()
async def entrar(ctx):
    cid = ctx.channel.id
    if cid not in filas:
        await ctx.send(embed=embed_base("Não há fila aberta neste canal.", cor=0xFF4444))
        return

    fila = filas[cid]
    if ctx.author in fila["jogadores"]:
        await ctx.send(embed=embed_base("Você já está na fila!", cor=0xFFAA00))
        return
    if len(fila["jogadores"]) >= fila["max"]:
        await ctx.send(embed=embed_base("A fila está cheia!", cor=0xFF4444))
        return

    fila["jogadores"].append(ctx.author)
    n = len(fila["jogadores"])
    maximo = fila["max"]

    e = embed_base(f"{ctx.author.display_name} entrou na fila!", cor=0x00C8FF)
    e.add_field(name=f"Jogadores ({n}/{maximo})",
                value=formatar_jogadores(fila["jogadores"]))

    if n == maximo:
        e.description = "✅ **Fila completa!** Use **`.go`** para criar a sala."
        e.color = 0x00FF88

    await ctx.send(embed=e)

# ════════════════════════════════════════════════════
#   .sair
# ════════════════════════════════════════════════════
@bot.command()
async def sair(ctx):
    cid = ctx.channel.id
    if cid not in filas or ctx.author not in filas[cid]["jogadores"]:
        await ctx.send(embed=embed_base("Você não está em nenhuma fila aqui.", cor=0xFF4444))
        return
    filas[cid]["jogadores"].remove(ctx.author)
    n = len(filas[cid]["jogadores"])
    e = embed_base(f"{ctx.author.display_name} saiu da fila.", cor=0xFFAA00)
    e.add_field(name=f"Jogadores ({n}/{filas[cid]['max']})",
                value=formatar_jogadores(filas[cid]["jogadores"]))
    await ctx.send(embed=e)

# ════════════════════════════════════════════════════
#   .fila
# ════════════════════════════════════════════════════
@bot.command()
async def fila(ctx):
    cid = ctx.channel.id
    if cid not in filas:
        await ctx.send(embed=embed_base("Não há fila aberta neste canal.", cor=0xFF4444))
        return
    f = filas[cid]
    n, mx = len(f["jogadores"]), f["max"]
    e = embed_base(f"Fila — {f['modo_nome']}", cor=0x00C8FF)
    e.add_field(name=f"Jogadores ({n}/{mx})",
                value=formatar_jogadores(f["jogadores"]))
    e.add_field(name="Criada por", value=f["criador"].mention, inline=True)
    delta = datetime.utcnow() - f["criado_em"]
    e.add_field(name="Há quanto tempo",
                value=f"{int(delta.total_seconds()//60)}m {int(delta.total_seconds()%60)}s",
                inline=True)
    if n == mx:
        e.set_footer(text="✅ Fila cheia! Use .go para criar a sala.")
    await ctx.send(embed=e)

# ════════════════════════════════════════════════════
#   .cancelar
# ════════════════════════════════════════════════════
@bot.command()
async def cancelar(ctx):
    cid = ctx.channel.id
    if cid not in filas:
        await ctx.send(embed=embed_base("Não há fila para cancelar.", cor=0xFF4444))
        return
    if filas[cid]["criador"] != ctx.author and not ctx.author.guild_permissions.administrator:
        await ctx.send(embed=embed_base("Apenas quem criou a fila pode cancelá-la.", cor=0xFF4444))
        return
    del filas[cid]
    await ctx.send(embed=embed_base("Fila cancelada.", cor=0xFFAA00))

# ════════════════════════════════════════════════════
#   .go — confirma fila e cria canal privado
# ════════════════════════════════════════════════════
@bot.command()
async def go(ctx):
    cid = ctx.channel.id
    if cid not in filas:
        await ctx.send(embed=embed_base("Não há fila aberta aqui.", cor=0xFF4444))
        return

    f = filas[cid]
    n, mx = len(f["jogadores"]), f["max"]
    if n < mx:
        await ctx.send(embed=embed_base(
            f"A fila ainda não está cheia! ({n}/{mx})", cor=0xFF4444))
        return

    guild = ctx.guild
    categoria = guild.get_channel(CATEGORY_ID) if CATEGORY_ID else None

    # Permissões: apenas os jogadores veem o canal
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
    }
    for membro in f["jogadores"]:
        overwrites[membro] = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True)

    nome_canal = f"sala-{f['modo']}-{gerar_codigo().lower()}"
    canal = await guild.create_text_channel(
        nome_canal, category=categoria, overwrites=overwrites,
        topic=f"Sala privada — {f['modo_nome']}")

    # Sorteia times se necessário
    jogadores = f["jogadores"][:]
    random.shuffle(jogadores)
    info_times = ""

    if f["times"] and mx >= 4:
        meio = mx // 2
        time1 = jogadores[:meio]
        time2 = jogadores[meio:]
        salas[canal.id] = {**f, "canal_original": cid,
                           "time1": time1, "time2": time2, "codigo": None}

        t1_txt = formatar_jogadores(time1)
        t2_txt = formatar_jogadores(time2)
        info_times = (
            f"\n\n🔵 **Time 1:**\n{t1_txt}\n\n"
            f"🔴 **Time 2:**\n{t2_txt}"
        )
    else:
        salas[canal.id] = {**f, "canal_original": cid,
                           "time1": jogadores, "time2": [], "codigo": None}
        info_times = f"\n\n👥 **Jogadores:**\n{formatar_jogadores(jogadores)}"

    # Mensagem no canal original
    e_orig = embed_base("✅ Sala criada!", cor=0x00FF88)
    e_orig.description = f"Canal privado criado: {canal.mention}\nUsem **`.criar`** lá dentro para gerar o código da sala."
    await ctx.send(embed=e_orig)

    # Mensagem dentro do canal privado
    e_sala = embed_base(f"Bem-vindos — {f['modo_nome']}", cor=0x7B2FBE)
    e_sala.description = (
        f"Canal privado criado com sucesso!{info_times}\n\n"
        f"Use **`.criar`** para gerar o código da sala no jogo.\n"
        f"Ao terminar: **`.win Time1`** ou **`.win Time2`**"
    )
    await canal.send(
        content=" ".join(m.mention for m in f["jogadores"]),
        embed=e_sala)

    del filas[cid]

# ════════════════════════════════════════════════════
#   .criar — gera código da sala
# ════════════════════════════════════════════════════
@bot.command()
async def criar(ctx):
    cid = ctx.channel.id
    if cid not in salas:
        await ctx.send(embed=embed_base(
            "Este comando só funciona dentro de uma sala privada.", cor=0xFF4444))
        return

    if salas[cid]["codigo"]:
        await ctx.send(embed=embed_base(
            f"Código já gerado: `{salas[cid]['codigo']}`", cor=0xFFAA00))
        return

    codigo = gerar_codigo()
    salas[cid]["codigo"] = codigo

    e = embed_base("🎮 Código da Sala Gerado!", cor=0x00FF88)
    e.description = (
        f"**Código:** `{codigo}`\n\n"
        f"📌 Passos para criar a sala no jogo:\n"
        f"1. Abra Brawl Stars\n"
        f"2. Vá em **Jogo Amistoso** → **Criar Sala**\n"
        f"3. Compartilhe o código com os jogadores\n\n"
        f"Quando terminar: **`.win Time1`** ou **`.win Time2`**"
    )
    await ctx.send(embed=e)

# ════════════════════════════════════════════════════
#   .win — declarar vencedor
# ════════════════════════════════════════════════════
@bot.command()
async def win(ctx, *, time_vencedor: str = None):
    cid = ctx.channel.id
    if cid not in salas:
        await ctx.send(embed=embed_base(
            "Este comando só funciona dentro de uma sala privada.", cor=0xFF4444))
        return
    if not time_vencedor:
        await ctx.send(embed=embed_base(
            "Use `.win Time1` ou `.win Time2`", cor=0xFF4444))
        return

    sala = salas[cid]
    tv = time_vencedor.strip().lower()

    if tv in ("time1", "time 1", "t1", "azul"):
        venc = sala["time1"]
        adv  = sala["time2"]
        nome_venc = "🔵 Time 1"
    elif tv in ("time2", "time 2", "t2", "vermelho"):
        venc = sala["time2"]
        adv  = sala["time1"]
        nome_venc = "🔴 Time 2"
    else:
        await ctx.send(embed=embed_base(
            "Time inválido. Use `.win Time1` ou `.win Time2`", cor=0xFF4444))
        return

    e = embed_base(f"🏆 {nome_venc} Venceu!", cor=0xFFD700)
    e.description = (
        f"**Vencedores:**\n{formatar_jogadores(venc)}\n\n"
        f"Agora escolha o **MVP** da partida!\n"
        f"**Mencione o jogador:** `.mvp @jogador`\n"
        f"O time adversário confirma a escolha."
    )
    salas[cid]["vencedor"] = venc
    salas[cid]["adversario"] = adv
    salas[cid]["nome_venc"] = nome_venc
    await ctx.send(embed=e)

# ════════════════════════════════════════════════════
#   .mvp — votar no MVP
# ════════════════════════════════════════════════════
@bot.command()
async def mvp(ctx, candidato: discord.Member = None):
    cid = ctx.channel.id
    if cid not in salas or "vencedor" not in salas[cid]:
        await ctx.send(embed=embed_base(
            "Use `.mvp` apenas após declarar o vencedor com `.win`.", cor=0xFF4444))
        return
    if not candidato:
        await ctx.send(embed=embed_base("Mencione o jogador: `.mvp @jogador`", cor=0xFF4444))
        return

    sala = salas[cid]
    todos = (sala.get("time1", []) + sala.get("time2", []))
    if candidato not in todos:
        await ctx.send(embed=embed_base("Esse jogador não está nesta sala.", cor=0xFF4444))
        return

    adv = sala.get("adversario", [])
    mvp_data[cid] = {
        "candidato" : candidato,
        "adv_ids"   : [m.id for m in adv],
        "confirmados": set(),
    }

    e = embed_base(f"⭐ Candidato a MVP: {candidato.display_name}", cor=0xFFD700)
    e.description = (
        f"{candidato.mention} foi indicado como MVP!\n\n"
        f"**Time adversário**, reaja com ✅ para confirmar ou ❌ para negar.\n"
        f"Precisamos que **todos do time adversário** votem."
    )
    adv_mentions = " ".join(m.mention for m in adv) if adv else ""
    msg = await ctx.send(content=adv_mentions, embed=e)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    mvp_data[cid]["msg_id"] = msg.id

@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return
    cid = reaction.message.channel.id
    if cid not in mvp_data:
        return
    dados = mvp_data[cid]
    if reaction.message.id != dados["msg_id"]:
        return
    if user.id not in dados["adv_ids"]:
        return

    if str(reaction.emoji) == "❌":
        await reaction.message.channel.send(embed=embed_base(
            f"{user.display_name} negou o MVP. Indique outro com `.mvp @jogador`",
            cor=0xFF4444))
        del mvp_data[cid]
        return

    if str(reaction.emoji) == "✅":
        dados["confirmados"].add(user.id)
        restam = set(dados["adv_ids"]) - dados["confirmados"]
        if not restam:
            # Todos confirmaram — fechar sala
            canal = reaction.message.channel
            await fechar_sala(canal, dados["candidato"])

async def fechar_sala(canal: discord.TextChannel, mvp_membro: discord.Member):
    cid = canal.id
    sala = salas.get(cid, {})

    e = embed_base("🎉 Partida Encerrada!", cor=0x00FF88)
    e.description = (
        f"**MVP:** ⭐ {mvp_membro.mention} — parabéns!\n\n"
        f"**Resultado:** {sala.get('nome_venc','')}\n\n"
        f"Este canal será deletado em **10 segundos**."
    )
    await canal.send(embed=e)
    if cid in salas:   del salas[cid]
    if cid in mvp_data: del mvp_data[cid]
    await asyncio.sleep(10)
    try:
        await canal.delete()
    except Exception:
        pass

# ════════════════════════════════════════════════════
#   .encerrar — fechar sala manualmente
# ════════════════════════════════════════════════════
@bot.command()
async def encerrar(ctx):
    cid = ctx.channel.id
    if cid not in salas:
        await ctx.send(embed=embed_base(
            "Este canal não é uma sala ativa.", cor=0xFF4444))
        return
    sala = salas[cid]
    todos = sala.get("time1", []) + sala.get("time2", [])
    if ctx.author not in todos and not ctx.author.guild_permissions.administrator:
        await ctx.send(embed=embed_base("Você não faz parte desta sala.", cor=0xFF4444))
        return

    e = embed_base("⚠️ Sala encerrada manualmente.", cor=0xFFAA00)
    e.description = "Canal será deletado em 5 segundos."
    await ctx.send(embed=e)
    if cid in salas:    del salas[cid]
    if cid in mvp_data: del mvp_data[cid]
    await asyncio.sleep(5)
    try:
        await ctx.channel.delete()
    except Exception:
        pass

# ════════════════════════════════════════════════════
#   .vincular — salvar tag Brawl Stars
# ════════════════════════════════════════════════════
@bot.command()
async def vincular(ctx, tag: str = None):
    if not tag:
        await ctx.send(embed=embed_base("Use: `.vincular #SUA_TAG`", cor=0xFF4444))
        return
    if not tag.startswith("#"):
        tag = "#" + tag
    perfis[ctx.author.id] = tag.upper()
    e = embed_base("✅ Tag vinculada com sucesso!", cor=0x00FF88)
    e.description = f"Sua tag `{tag.upper()}` foi salva!\nUse **`.meu`** para ver seu perfil."
    await ctx.send(embed=e)

# ════════════════════════════════════════════════════
#   .meu — perfil vinculado
# ════════════════════════════════════════════════════
@bot.command()
async def meu(ctx):
    tag = perfis.get(ctx.author.id)
    if not tag:
        await ctx.send(embed=embed_base(
            "Você não tem tag vinculada. Use `.vincular #TAG`", cor=0xFF4444))
        return
    await _mostrar_perfil(ctx, tag, ctx.author)

# ════════════════════════════════════════════════════
#   .perfil #TAG  — perfil por tag
# ════════════════════════════════════════════════════
@bot.command()
async def perfil(ctx, tag: str = None):
    if not tag:
        # Tenta usar o vinculado
        tag = perfis.get(ctx.author.id)
        if not tag:
            await ctx.send(embed=embed_base(
                "Use: `.perfil #TAG` ou vincule com `.vincular #TAG`", cor=0xFF4444))
            return
    if not tag.startswith("#"):
        tag = "#" + tag
    await _mostrar_perfil(ctx, tag.upper(), ctx.author)

async def _mostrar_perfil(ctx, tag: str, member: discord.Member):
    msg_wait = await ctx.send(embed=embed_base("🔍 Buscando perfil...", cor=0x888888))
    dados = await buscar_perfil(tag)
    if not dados:
        await msg_wait.edit(embed=embed_base(
            f"Perfil `{tag}` não encontrado.\nVerifique a tag ou tente novamente mais tarde.",
            cor=0xFF4444))
        return
    e = montar_embed_perfil(dados, member)
    await msg_wait.edit(embed=e)

# ════════════════════════════════════════════════════
#   HANDLER DE ERROS
# ════════════════════════════════════════════════════
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return  # ignora comandos desconhecidos silenciosamente
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(embed=embed_base(
            f"Argumento faltando. Use `.ajuda` para ver o uso correto.", cor=0xFF4444))
        return
    if isinstance(error, commands.BadArgument):
        await ctx.send(embed=embed_base(
            "Argumento inválido. Mencione um membro válido.", cor=0xFF4444))
        return
    # Erros não tratados
    await ctx.send(embed=embed_base(f"Erro: `{error}`", cor=0xFF0000))
    raise error

# ════════════════════════════════════════════════════
#   RODAR
# ════════════════════════════════════════════════════
if __name__ == "__main__":
    bot.run(BOT_TOKEN)
