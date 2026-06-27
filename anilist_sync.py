# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CÉLULA 1 — Instalar dependências
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
!pip install -q requests gspread google-auth
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CÉLULA 2 — Login com sua conta Google
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from google.colab import auth
auth.authenticate_user()
print("Autenticado!")
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CÉLULA 3 — Anti-desconexão do Colab
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from IPython.display import display, Javascript
display(Javascript('''
  function clickConnect() {
    try {
      document.querySelector("#top-toolbar > colab-connect-button")
        .shadowRoot.querySelector("#connect").click();
    } catch(e) {}
  }
  setInterval(clickConnect, 60000);
'''))
print("Keep-alive ativo!")
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CÉLULA 4 — Script principal (cole tudo daqui pra baixo)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

import os, time, hashlib, json, requests, gspread
from google.auth import default
from google.oauth2.service_account import Credentials
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo

# ─────────────────────────────────────────────
# FUSO HORÁRIO
# ─────────────────────────────────────────────

TZ = ZoneInfo("America/Sao_Paulo")

def now_br(fmt="%d/%m/%Y  %H:%M"):
    return datetime.now(TZ).strftime(fmt)

def next_check_br(seconds):
    return datetime.fromtimestamp(time.time() + seconds, TZ).strftime("%H:%M:%S")

# ─────────────────────────────────────────────
# CONFIGURAÇÕES
# ─────────────────────────────────────────────

ANILIST_API_URL  = "https://graphql.anilist.co"
SPREADSHEET_NAME = "planoha animes armário - (python fucking good bro)"
SYNC_INTERVAL    = 300   # segundos entre verificações (300 = 5 min)

USERNAMES = [
    "CianBrz", "BingoRTv", "Dioo", "Gumya",
    "Jotalhos", "niccname", "ViniAxd", "SleepyGT",
]

STATUS_MAP = {
    "COMPLETED": "Assistido",
    "DROPPED":   "Dropado",
    "PAUSED":    "Pausado",
    "CURRENT":   "Assistindo",
    "PLANNING":  "Planejando",
}

# Cores RGB 0-1 para fundo das células de status
STATUS_BG = {
    "Assistido":  {"red": 0.204, "green": 0.659, "blue": 0.325},
    "Dropado":    {"red": 0.898, "green": 0.224, "blue": 0.208},
    "Pausado":    {"red": 0.984, "green": 0.737, "blue": 0.020},
    "Assistindo": {"red": 0.259, "green": 0.522, "blue": 0.957},
    "Planejando": {"red": 0.612, "green": 0.153, "blue": 0.690},
    "-":          {"red": 0.930, "green": 0.930, "blue": 0.930},
}

STATUS_FG = {
    "Assistido":  {"red": 1,    "green": 1,    "blue": 1},
    "Dropado":    {"red": 1,    "green": 1,    "blue": 1},
    "Pausado":    {"red": 0.18, "green": 0.14, "blue": 0.02},
    "Assistindo": {"red": 1,    "green": 1,    "blue": 1},
    "Planejando": {"red": 1,    "green": 1,    "blue": 1},
    "-":          {"red": 0.60, "green": 0.60, "blue": 0.60},
}

# Paleta de cores para gráfico de barras de usuário (Assistido/Assistindo/Planejando/Dropado)
BAR_COLORS = {
    "Assistido":  {"red": 0.204, "green": 0.659, "blue": 0.325},
    "Assistindo": {"red": 0.259, "green": 0.522, "blue": 0.957},
    "Planejando": {"red": 0.612, "green": 0.153, "blue": 0.690},
    "Dropado":    {"red": 0.898, "green": 0.224, "blue": 0.208},
    "Pausado":    {"red": 0.984, "green": 0.737, "blue": 0.020},
}

WHITE    = {"red": 1,    "green": 1,    "blue": 1}
BLACK    = {"red": 0.08, "green": 0.08, "blue": 0.08}
DARK_HDR = {"red": 0.09, "green": 0.13, "blue": 0.24}   # azul bem escuro
GRAY_ALT = {"red": 0.97, "green": 0.97, "blue": 0.98}
GRAY_HDR = {"red": 0.20, "green": 0.20, "blue": 0.22}
ACCENT   = {"red": 0.16, "green": 0.44, "blue": 0.86}
LIGHT_BLUE = {"red": 0.90, "green": 0.94, "blue": 1.00}
GOLD     = {"red": 0.80, "green": 0.60, "blue": 0.00}
SILVER   = {"red": 0.55, "green": 0.55, "blue": 0.58}
BRONZE   = {"red": 0.60, "green": 0.36, "blue": 0.17}

# Cores de avatar por usuário (cicladas)
AVATAR_COLORS = [
    ({"red": 0.18, "green": 0.39, "blue": 0.78}, WHITE),
    ({"red": 0.61, "green": 0.15, "blue": 0.69}, WHITE),
    ({"red": 0.20, "green": 0.66, "blue": 0.33}, WHITE),
    ({"red": 0.90, "green": 0.35, "blue": 0.13}, WHITE),
    ({"red": 0.00, "green": 0.59, "blue": 0.53}, WHITE),
    ({"red": 0.76, "green": 0.19, "blue": 0.39}, WHITE),
    ({"red": 0.20, "green": 0.52, "blue": 0.74}, WHITE),
    ({"red": 0.48, "green": 0.35, "blue": 0.72}, WHITE),
]

# ─────────────────────────────────────────────
# QUERY GRAPHQL
# ─────────────────────────────────────────────

MEDIA_LIST_QUERY = """
query ($username: String) {
  MediaListCollection(userName: $username, type: ANIME) {
    lists {
      entries {
        status
        media {
          id
          title { romaji english }
        }
      }
    }
  }
}
"""

# ─────────────────────────────────────────────
# ANILIST — busca e estruturação
# ─────────────────────────────────────────────

def fetch_user_anime_list(username):
    r = requests.post(
        ANILIST_API_URL,
        json={"query": MEDIA_LIST_QUERY, "variables": {"username": username}},
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        timeout=30,
    )
    if r.status_code == 429:
        wait = int(r.headers.get("Retry-After", 60))
        print(f"  Rate limit! Aguardando {wait}s...")
        time.sleep(wait)
        return fetch_user_anime_list(username)
    r.raise_for_status()
    data = r.json()
    if "errors" in data:
        print(f"  Erro para '{username}': {data['errors']}")
        return {}
    anime_map = {}
    for lst in data["data"]["MediaListCollection"]["lists"]:
        for entry in lst["entries"]:
            media = entry["media"]
            mid   = media["id"]
            title = media["title"]["english"] or media["title"]["romaji"] or f"ID:{mid}"
            anime_map[mid] = {"title": title, "status": STATUS_MAP.get(entry["status"], "-")}
    return anime_map


def fetch_all_users(verbose=True):
    all_data = {}
    for u in USERNAMES:
        if verbose:
            print(f"  -> {u}...", end=" ", flush=True)
        all_data[u] = fetch_user_anime_list(u)
        if verbose:
            print(f"{len(all_data[u])} animes")
        time.sleep(1)
    return all_data


def build_master_list(all_data):
    master, grid = {}, {}
    for u, anime_map in all_data.items():
        for mid, info in anime_map.items():
            if mid not in master:
                master[mid] = info["title"]
                grid[mid]   = {}
            grid[mid][u] = info["status"]
    for mid in grid:
        for u in USERNAMES:
            grid[mid].setdefault(u, "-")
    return master, grid


def compute_hash(all_data):
    snap = {
        u: sorted([(mid, info["status"]) for mid, info in am.items()], key=lambda x: x[0])
        for u, am in sorted(all_data.items())
    }
    return hashlib.md5(json.dumps(snap, sort_keys=True).encode()).hexdigest()

# ─────────────────────────────────────────────
# ANALYTICS
# ─────────────────────────────────────────────

def build_analytics(master, grid):
    N = len(USERNAMES)
    watched_count = {
        mid: sum(1 for u in USERNAMES if grid[mid].get(u) == "Assistido")
        for mid in master
    }
    top_watched = sorted(
        [(mid, c) for mid, c in watched_count.items() if c > 0],
        key=lambda x: -x[1]
    )[:10]
    least_watched = sorted(
        [(mid, c) for mid, c in watched_count.items() if 0 < c < N],
        key=lambda x: x[1]
    )[:5]

    all_watched_by_all = sum(1 for c in watched_count.values() if c == N)

    user_stats = {}
    for u in USERNAMES:
        counts = Counter(grid[mid].get(u, "-") for mid in master)
        user_stats[u] = {s: counts.get(s, 0) for s in list(STATUS_MAP.values()) + ["-"]}
        user_stats[u]["total"] = sum(
            user_stats[u].get(s, 0) for s in STATUS_MAP.values()
        )

    most_watched_user = max(USERNAMES, key=lambda u: user_stats[u]["Assistido"])
    most_dropped_user = max(USERNAMES, key=lambda u: user_stats[u]["Dropado"])
    biggest_list_user = max(USERNAMES, key=lambda u: user_stats[u]["total"])

    return {
        "top_watched":       top_watched,
        "least_watched":     least_watched,
        "user_stats":        user_stats,
        "most_watched_user": most_watched_user,
        "most_dropped_user": most_dropped_user,
        "biggest_list_user": biggest_list_user,
        "watched_count":     watched_count,
        "all_watched_by_all": all_watched_by_all,
        "total_unique":      len(master),
    }

# ─────────────────────────────────────────────
# HELPERS DE FORMATAÇÃO
# ─────────────────────────────────────────────

def cell_fmt(bg, fg=None, bold=False, size=10, align="CENTER",
             wrap="CLIP", italic=False, strikethrough=False):
    return {
        "backgroundColor": bg,
        "horizontalAlignment": align,
        "verticalAlignment": "MIDDLE",
        "wrapStrategy": wrap,
        "textFormat": {
            "bold": bold, "italic": italic,
            "strikethrough": strikethrough,
            "fontSize": size,
            "foregroundColor": fg or BLACK,
        },
    }

def repeat_cell(sid, r1, r2, c1, c2, fmt):
    return {"repeatCell": {
        "range": {"sheetId": sid,
                  "startRowIndex": r1, "endRowIndex": r2,
                  "startColumnIndex": c1, "endColumnIndex": c2},
        "cell": {"userEnteredFormat": fmt},
        "fields": "userEnteredFormat(backgroundColor,horizontalAlignment,"
                  "verticalAlignment,wrapStrategy,textFormat)",
    }}

def border_req(sid, r1, r2, c1, c2,
               style="SOLID", width=1, color=None, inner=True):
    color = color or {"red": 0.82, "green": 0.82, "blue": 0.85}
    b = {"style": style, "width": width, "color": color}
    req = {"updateBorders": {
        "range": {"sheetId": sid,
                  "startRowIndex": r1, "endRowIndex": r2,
                  "startColumnIndex": c1, "endColumnIndex": c2},
        "top": b, "bottom": b, "left": b, "right": b,
    }}
    if inner:
        req["updateBorders"]["innerHorizontal"] = b
        req["updateBorders"]["innerVertical"]   = b
    return req

def outer_border(sid, r1, r2, c1, c2, color=None, width=2):
    color = color or DARK_HDR
    b = {"style": "SOLID", "width": width, "color": color}
    thin = {"style": "SOLID", "width": 1,
            "color": {"red": 0.82, "green": 0.82, "blue": 0.85}}
    return {"updateBorders": {
        "range": {"sheetId": sid,
                  "startRowIndex": r1, "endRowIndex": r2,
                  "startColumnIndex": c1, "endColumnIndex": c2},
        "top": b, "bottom": b, "left": b, "right": b,
        "innerHorizontal": thin, "innerVertical": thin,
    }}

def row_height(sid, r1, r2, px):
    return {"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "ROWS",
                  "startIndex": r1, "endIndex": r2},
        "properties": {"pixelSize": px},
        "fields": "pixelSize",
    }}

def col_width(sid, c1, c2, px):
    return {"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "COLUMNS",
                  "startIndex": c1, "endIndex": c2},
        "properties": {"pixelSize": px},
        "fields": "pixelSize",
    }}

def unmerge_all(sid):
    return {"unmergeCells": {
        "range": {"sheetId": sid}
    }}

def merge_cells(sid, r1, r2, c1, c2):
    return {"mergeCells": {
        "range": {"sheetId": sid,
                  "startRowIndex": r1, "endRowIndex": r2,
                  "startColumnIndex": c1, "endColumnIndex": c2},
        "mergeType": "MERGE_ALL",
    }}

def freeze(sid, rows=1, cols=0):
    return {"updateSheetProperties": {
        "properties": {"sheetId": sid,
                       "gridProperties": {"frozenRowCount": rows,
                                          "frozenColumnCount": cols}},
        "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount",
    }}

def auto_resize(sid, c1, c2):
    return {"autoResizeDimensions": {
        "dimensions": {"sheetId": sid, "dimension": "COLUMNS",
                       "startIndex": c1, "endIndex": c2}
    }}

# ─────────────────────────────────────────────
# ABA 1 — SYNC
# ─────────────────────────────────────────────

def write_sync_sheet(ws, master, grid, analytics, last_updated):
    sid = ws.id
    N   = len(USERNAMES)
    sorted_ids = sorted(master, key=lambda m: master[m].lower())
    n   = len(sorted_ids)

    # Layout da aba principal:
    # linha 0 = título bonitinho
    # linha 1 = legenda de status + data de atualização
    # linha 2 = cabeçalho da tabela
    # linha 3+ = dados
    TITLE_ROW  = 0
    LEGEND_ROW = 1
    HEADER_ROW = 2
    DATA_START = 3
    total_cols = N + 1

    rows = []

    title_row = ["ARMÁRIO DOS ANIMES"] + [""] * (total_cols - 1)
    rows.append(title_row)

    # A legenda agora usa todas as colunas visíveis e não fica com textos sumidos.
    legend_row = [
        "LEGENDA",
        "Assistido",
        "Assistindo",
        "Planejando",
        "Pausado",
        "Dropado",
        "Sem registro",
        "",
        f"Atualizado: {last_updated}",
    ]
    legend_row = legend_row[:total_cols]
    while len(legend_row) < total_cols:
        legend_row.append("")
    rows.append(legend_row)

    rows.append(["Nome do anime"] + USERNAMES)

    for mid in sorted_ids:
        rows.append([master[mid]] + [grid[mid].get(u, "-") for u in USERNAMES])

    ws.clear()
    ws.update(range_name="A1", values=rows)

    reqs = []
    reqs.append(unmerge_all(sid))
    # IMPORTANTE: remove congelamento de colunas ANTES de qualquer merge.
    # O Google Sheets dá erro se tentar mesclar coluna congelada com não congelada.
    reqs.append(freeze(sid, rows=0, cols=0))

    # Limpa filtro antigo, se existir, para recriar sem conflito.
    reqs.append({"clearBasicFilter": {"sheetId": sid}})

    # Fundo base
    reqs.append(repeat_cell(sid, 0, len(rows), 0, total_cols,
        cell_fmt(WHITE, BLACK, size=10, align="CENTER", wrap="CLIP")))

    # Título
    reqs.append(merge_cells(sid, TITLE_ROW, TITLE_ROW + 1, 0, total_cols))
    reqs.append(repeat_cell(sid, TITLE_ROW, TITLE_ROW + 1, 0, total_cols,
        cell_fmt(DARK_HDR, WHITE, bold=True, size=14, align="LEFT", wrap="CLIP")))
    reqs.append(row_height(sid, TITLE_ROW, TITLE_ROW + 1, 38))

    # Legenda
    reqs.append(repeat_cell(sid, LEGEND_ROW, LEGEND_ROW + 1, 0, total_cols,
        cell_fmt(GRAY_HDR, WHITE, bold=True, size=9, align="CENTER", wrap="CLIP")))
    reqs.append(repeat_cell(sid, LEGEND_ROW, LEGEND_ROW + 1, 0, 1,
        cell_fmt(DARK_HDR, WHITE, bold=True, size=9, align="LEFT", wrap="CLIP")))

    legend_items = [
        (1, "Assistido"),
        (2, "Assistindo"),
        (3, "Planejando"),
        (4, "Pausado"),
        (5, "Dropado"),
        (6, "-"),
    ]
    for col, st in legend_items:
        if col < total_cols:
            reqs.append(repeat_cell(sid, LEGEND_ROW, LEGEND_ROW + 1, col, col + 1,
                cell_fmt(STATUS_BG[st], STATUS_FG[st], bold=True, size=9, align="CENTER", wrap="CLIP")))

    # Célula de atualização, discreta e alinhada à direita.
    if total_cols >= 9:
        reqs.append(repeat_cell(sid, LEGEND_ROW, LEGEND_ROW + 1, 7, total_cols,
            cell_fmt(GRAY_HDR, {"red": 0.86, "green": 0.86, "blue": 0.90},
                     bold=False, size=9, align="RIGHT", wrap="CLIP")))
    reqs.append(row_height(sid, LEGEND_ROW, LEGEND_ROW + 1, 28))

    # Cabeçalho principal
    reqs.append(repeat_cell(sid, HEADER_ROW, HEADER_ROW + 1, 0, total_cols,
        cell_fmt(DARK_HDR, WHITE, bold=True, size=10, align="CENTER", wrap="CLIP")))
    reqs.append(repeat_cell(sid, HEADER_ROW, HEADER_ROW + 1, 0, 1,
        cell_fmt(DARK_HDR, WHITE, bold=True, size=10, align="LEFT", wrap="CLIP")))

    for i, (bg, fg) in enumerate(AVATAR_COLORS[:N]):
        reqs.append(repeat_cell(sid, HEADER_ROW, HEADER_ROW + 1, i + 1, i + 2,
            cell_fmt(bg, fg, bold=True, size=10, align="CENTER", wrap="CLIP")))

    reqs.append(row_height(sid, HEADER_ROW, HEADER_ROW + 1, 34))

    # Linhas de dados
    for i, mid in enumerate(sorted_ids):
        r = DATA_START + i
        bg = GRAY_ALT if i % 2 == 0 else WHITE

        reqs.append(repeat_cell(sid, r, r + 1, 0, 1,
            cell_fmt(bg, BLACK, size=10, align="LEFT", wrap="CLIP")))

        for col_i, u in enumerate(USERNAMES):
            st = grid[mid].get(u, "-")
            reqs.append(repeat_cell(sid, r, r + 1, col_i + 1, col_i + 2,
                cell_fmt(
                    STATUS_BG.get(st, STATUS_BG["-"]),
                    STATUS_FG.get(st, STATUS_FG["-"]),
                    bold=(st != "-"),
                    size=10,
                    align="CENTER",
                    wrap="CLIP"
                )
            ))

    reqs.append(row_height(sid, DATA_START, DATA_START + n, 24))

    # Bordas e congelamento
    reqs.append(outer_border(sid, 0, len(rows), 0, total_cols))
    reqs.append(border_req(sid, LEGEND_ROW, HEADER_ROW + 1, 0, total_cols,
                           color={"red": 0.58, "green": 0.62, "blue": 0.70}, inner=True))
    reqs.append(border_req(sid, DATA_START, len(rows), 0, total_cols,
                           color={"red": 0.82, "green": 0.84, "blue": 0.88}, inner=True))
    reqs.append(freeze(sid, rows=DATA_START, cols=0))

    # Filtro no cabeçalho da tabela, sem pegar a legenda.
    reqs.append({
        "setBasicFilter": {
            "filter": {
                "range": {
                    "sheetId": sid,
                    "startRowIndex": HEADER_ROW,
                    "endRowIndex": len(rows),
                    "startColumnIndex": 0,
                    "endColumnIndex": total_cols
                }
            }
        }
    })

    # Larguras
    reqs.append(col_width(sid, 0, 1, 390))
    for i in range(1, total_cols):
        reqs.append(col_width(sid, i, i + 1, 128))

    return reqs, sorted_ids

# ─────────────────────────────────────────────
# ABA 2 — RESUMO
# ─────────────────────────────────────────────

def write_stats_sheet(ws, master, grid, analytics):
    sid  = ws.id
    N    = len(USERNAMES)
    top  = analytics["top_watched"]
    least = analytics["least_watched"]
    us   = analytics["user_stats"]
    wc   = analytics["watched_count"]
    mwu  = analytics["most_watched_user"]
    mdu  = analytics["most_dropped_user"]
    blu  = analytics["biggest_list_user"]
    all8 = analytics["all_watched_by_all"]
    total_unique = analytics["total_unique"]

    NCOLS = 15
    data = []

    def blank_row():
        return [""] * NCOLS

    # Título
    row = blank_row()
    row[0] = "RESUMO DO GRUPO"
    data.append(row)
    data.append(blank_row())

    # Cards principais — sem seção duplicada de destaques.
    # O card de drops aparece uma vez aqui e também existe a coluna Dropado no ranking detalhado.
    row = blank_row()
    row[0] = "Total de animes únicos"
    row[3] = "Assistidos por todos"
    row[6] = "Maratonista do grupo"
    row[9] = "Maior biblioteca"
    row[12] = "Quem mais dropou"
    data.append(row)

    row = blank_row()
    row[0] = str(total_unique)
    row[3] = f"{all8} animes"
    row[6] = f"{mwu} ({us[mwu]['Assistido']} concluídos)"
    row[9] = f"{blu} ({us[blu]['total']} na lista)"
    row[12] = f"{mdu} ({us[mdu]['Dropado']} dropados)"
    data.append(row)

    data.append(blank_row())

    # Top 10
    row = blank_row()
    row[0] = "TOP 10 — ANIMES MAIS ASSISTIDOS"
    data.append(row)

    row = blank_row()
    row[0] = "Anime"
    row[1] = "Popularidade"
    row[2] = "Assistido por"
    row[3] = "% do grupo"
    row[4] = "Quem assistiu"
    data.append(row)

    medals = [f"{i}." for i in range(1, 11)]
    for i, (mid, count) in enumerate(top):
        row = blank_row()
        pct  = f"{round(count / N * 100)}%"
        pips = "●" * count + "○" * (N - count)
        watchers = [u for u in USERNAMES if grid[mid].get(u) == "Assistido"]
        row[0] = f"{medals[i]} {master[mid]}"
        row[1] = pips
        row[2] = f"{count} de {N}"
        row[3] = pct
        row[4] = ", ".join(watchers)
        data.append(row)

    data.append(blank_row())

    # Menos vistos
    row = blank_row()
    row[0] = "ANIMES MENOS VISTOS"
    data.append(row)

    row = blank_row()
    row[0] = "Anime"
    row[1] = "Quem assistiu"
    row[2] = "Assistido por"
    data.append(row)

    for mid, count in least:
        row = blank_row()
        watchers = [u for u in USERNAMES if grid[mid].get(u) == "Assistido"]
        row[0] = master[mid]
        row[1] = ", ".join(watchers) if watchers else "-"
        row[2] = f"{count} pessoa{'s' if count != 1 else ''}"
        data.append(row)

    data.append(blank_row())

    # Ranking usuários
    row = blank_row()
    row[0] = "RANKING POR USUÁRIO"
    data.append(row)

    row = blank_row()
    row[0] = "Usuário"
    row[1] = "Assistido"
    row[2] = "Assistindo"
    row[3] = "Planejando"
    row[4] = "Dropado"
    row[5] = "Pausado"
    row[6] = "Total"
    data.append(row)

    sorted_users = sorted(USERNAMES, key=lambda u: -us[u]["Assistido"])
    for pos, u in enumerate(sorted_users, 1):
        s = us[u]
        row = blank_row()
        row[0] = f"{pos}. {u}"
        row[1] = s["Assistido"]
        row[2] = s["Assistindo"]
        row[3] = s["Planejando"]
        row[4] = s["Dropado"]
        row[5] = s["Pausado"]
        row[6] = s["total"]
        data.append(row)

    ws.clear()
    ws.update(range_name="A1", values=data)

    reqs = []
    reqs.append(unmerge_all(sid))
    # IMPORTANTE: remove congelamento de colunas ANTES de qualquer merge.
    reqs.append(freeze(sid, rows=0, cols=0))
    nrows = len(data)

    # Fundo base
    reqs.append(repeat_cell(sid, 0, nrows, 0, NCOLS,
        cell_fmt(WHITE, BLACK, size=10, align="LEFT", wrap="CLIP")))

    # Título
    reqs.append(merge_cells(sid, 0, 1, 0, NCOLS))
    reqs.append(repeat_cell(sid, 0, 1, 0, NCOLS,
        cell_fmt(DARK_HDR, WHITE, bold=True, size=14, align="LEFT", wrap="CLIP")))
    reqs.append(row_height(sid, 0, 1, 38))

    # Cards principais
    card_spans = [(0, 3), (3, 6), (6, 9), (9, 12), (12, 15)]
    card_bgs = [
        LIGHT_BLUE,
        {"red": 0.97, "green": 0.91, "blue": 0.97},
        {"red": 1.00, "green": 0.96, "blue": 0.82},
        {"red": 0.90, "green": 0.97, "blue": 0.91},
        {"red": 1.00, "green": 0.90, "blue": 0.88},
    ]
    card_fgs = [
        {"red": 0.09, "green": 0.13, "blue": 0.24},
        {"red": 0.30, "green": 0.08, "blue": 0.34},
        GOLD,
        {"red": 0.10, "green": 0.35, "blue": 0.12},
        {"red": 0.65, "green": 0.12, "blue": 0.10},
    ]

    for i, (c1, c2) in enumerate(card_spans):
        reqs.append(merge_cells(sid, 2, 3, c1, c2))
        reqs.append(merge_cells(sid, 3, 4, c1, c2))
        reqs.append(repeat_cell(sid, 2, 3, c1, c2,
            cell_fmt(card_bgs[i], card_fgs[i], bold=False, size=9, align="CENTER", wrap="CLIP")))
        reqs.append(repeat_cell(sid, 3, 4, c1, c2,
            cell_fmt(card_bgs[i], card_fgs[i], bold=True, size=12, align="CENTER", wrap="WRAP")))
        reqs.append(outer_border(sid, 2, 4, c1, c2, color=card_fgs[i], width=1))

    reqs.append(row_height(sid, 2, 3, 22))
    reqs.append(row_height(sid, 3, 4, 34))

    # Índices dinâmicos — agora sem a seção duplicada de destaques
    top_hdr = 5
    top_sub = 6
    top_start = 7
    top_end = top_start + len(top)

    niche_hdr = top_end + 1
    niche_sub = niche_hdr + 1
    niche_start = niche_sub + 1
    niche_end = niche_start + len(least)

    user_hdr = niche_end + 1
    user_sub = user_hdr + 1
    user_start = user_sub + 1
    user_end = user_start + len(sorted_users)

    # Top 10
    reqs.append(merge_cells(sid, top_hdr, top_hdr + 1, 0, NCOLS))
    reqs.append(repeat_cell(sid, top_hdr, top_hdr + 1, 0, NCOLS,
        cell_fmt(DARK_HDR, WHITE, bold=True, size=11, align="LEFT", wrap="CLIP")))
    reqs.append(repeat_cell(sid, top_sub, top_sub + 1, 0, 5,
        cell_fmt(GRAY_HDR, WHITE, bold=True, size=10, align="CENTER", wrap="CLIP")))

    for i in range(len(top)):
        r = top_start + i
        bg = GRAY_ALT if i % 2 == 0 else WHITE
        reqs.append(repeat_cell(sid, r, r + 1, 0, 5,
            cell_fmt(bg, BLACK, size=10, align="LEFT", wrap="CLIP")))
        reqs.append(repeat_cell(sid, r, r + 1, 1, 2,
            cell_fmt(bg, {"red": 0.20, "green": 0.55, "blue": 0.25}, size=10, align="CENTER", wrap="CLIP")))
        reqs.append(repeat_cell(sid, r, r + 1, 2, 4,
            cell_fmt(bg, BLACK, bold=True, size=10, align="CENTER", wrap="CLIP")))
        reqs.append(repeat_cell(sid, r, r + 1, 4, 5,
            cell_fmt(bg, {"red": 0.25, "green": 0.25, "blue": 0.28}, size=9, align="LEFT", wrap="CLIP")))
    reqs.append(outer_border(sid, top_hdr, top_end, 0, 5))

    # Menos vistos
    reqs.append(merge_cells(sid, niche_hdr, niche_hdr + 1, 0, NCOLS))
    reqs.append(repeat_cell(sid, niche_hdr, niche_hdr + 1, 0, NCOLS,
        cell_fmt(DARK_HDR, WHITE, bold=True, size=11, align="LEFT", wrap="CLIP")))
    reqs.append(repeat_cell(sid, niche_sub, niche_sub + 1, 0, 3,
        cell_fmt(GRAY_HDR, WHITE, bold=True, size=10, align="CENTER", wrap="CLIP")))

    for i in range(len(least)):
        r = niche_start + i
        bg = GRAY_ALT if i % 2 == 0 else WHITE
        reqs.append(repeat_cell(sid, r, r + 1, 0, 3,
            cell_fmt(bg, BLACK, size=10, align="LEFT", wrap="CLIP")))
        reqs.append(repeat_cell(sid, r, r + 1, 2, 3,
            cell_fmt(bg, {"red": 0.6, "green": 0.15, "blue": 0.69}, bold=True, size=10, align="CENTER", wrap="CLIP")))
    reqs.append(outer_border(sid, niche_hdr, niche_end, 0, 3))

    # Ranking usuários
    reqs.append(merge_cells(sid, user_hdr, user_hdr + 1, 0, NCOLS))
    reqs.append(repeat_cell(sid, user_hdr, user_hdr + 1, 0, NCOLS,
        cell_fmt(DARK_HDR, WHITE, bold=True, size=11, align="LEFT", wrap="CLIP")))
    reqs.append(repeat_cell(sid, user_sub, user_sub + 1, 0, 7,
        cell_fmt(GRAY_HDR, WHITE, bold=True, size=10, align="CENTER", wrap="CLIP")))

    reqs.append(repeat_cell(sid, user_sub, user_sub + 1, 1, 2,
        cell_fmt(STATUS_BG["Assistido"], STATUS_FG["Assistido"], bold=True, size=10, align="CENTER")))
    reqs.append(repeat_cell(sid, user_sub, user_sub + 1, 2, 3,
        cell_fmt(STATUS_BG["Assistindo"], STATUS_FG["Assistindo"], bold=True, size=10, align="CENTER")))
    reqs.append(repeat_cell(sid, user_sub, user_sub + 1, 3, 4,
        cell_fmt(STATUS_BG["Planejando"], STATUS_FG["Planejando"], bold=True, size=10, align="CENTER")))
    reqs.append(repeat_cell(sid, user_sub, user_sub + 1, 4, 5,
        cell_fmt(STATUS_BG["Dropado"], STATUS_FG["Dropado"], bold=True, size=10, align="CENTER")))
    reqs.append(repeat_cell(sid, user_sub, user_sub + 1, 5, 6,
        cell_fmt(STATUS_BG["Pausado"], STATUS_FG["Pausado"], bold=True, size=10, align="CENTER")))

    for i in range(len(sorted_users)):
        r = user_start + i
        bg = GRAY_ALT if i % 2 == 0 else WHITE
        reqs.append(repeat_cell(sid, r, r + 1, 0, 7,
            cell_fmt(bg, BLACK, size=10, align="CENTER", wrap="CLIP")))
        reqs.append(repeat_cell(sid, r, r + 1, 0, 1,
            cell_fmt(bg, BLACK, bold=True, size=10, align="LEFT", wrap="CLIP")))
    reqs.append(outer_border(sid, user_hdr, user_end, 0, 7))

    # Alturas
    reqs.append(row_height(sid, top_sub, top_end, 24))
    reqs.append(row_height(sid, niche_sub, niche_end, 24))
    reqs.append(row_height(sid, user_sub, user_end, 24))

    # Larguras
    reqs.append(col_width(sid, 0, 1, 360))
    reqs.append(col_width(sid, 1, 2, 160))
    reqs.append(col_width(sid, 2, 3, 110))
    reqs.append(col_width(sid, 3, 4, 100))
    reqs.append(col_width(sid, 4, 5, 250))
    reqs.append(col_width(sid, 5, 6, 100))
    reqs.append(col_width(sid, 6, 7, 85))
    for c in range(7, NCOLS):
        reqs.append(col_width(sid, c, c + 1, 85))

    return reqs

# ─────────────────────────────────────────────
# SYNC COMPLETO (uma rodada)
# ─────────────────────────────────────────────

def run_sync(spreadsheet, verbose=True):
    now = now_br("%d/%m/%Y  %H:%M")
    all_data = fetch_all_users(verbose=verbose)
    master, grid = build_master_list(all_data)
    analytics    = build_analytics(master, grid)

    ws_sync = spreadsheet.sheet1

    try:
        ws_stats = spreadsheet.worksheet("Resumo")
    except gspread.WorksheetNotFound:
        ws_stats = spreadsheet.add_worksheet("Resumo", rows=300, cols=15)

    all_reqs = []
    reqs_sync, _ = write_sync_sheet(ws_sync, master, grid, analytics, now)
    all_reqs.extend(reqs_sync)
    reqs_stats = write_stats_sheet(ws_stats, master, grid, analytics)
    all_reqs.extend(reqs_stats)
    for i in range(0, len(all_reqs), 500):
        spreadsheet.batch_update({"requests": all_reqs[i:i+500]})

    return all_data

# ─────────────────────────────────────────────
# AUTENTICAÇÃO GOOGLE
# ─────────────────────────────────────────────

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

def get_google_client():
    """
    No GitHub Actions, usa o secret GOOGLE_SERVICE_ACCOUNT_JSON.
    No Colab/local, se o secret não existir, tenta usar as credenciais padrão.
    """
    service_account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")

    if service_account_json:
        try:
            info = json.loads(service_account_json)
            creds = Credentials.from_service_account_info(info, scopes=SCOPES)
            return gspread.authorize(creds)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                "O secret GOOGLE_SERVICE_ACCOUNT_JSON não parece ser um JSON válido. "
                "Cole o conteúdo inteiro do arquivo .json da conta de serviço."
            ) from e

    creds, _ = default(scopes=SCOPES)
    return gspread.authorize(creds)

def open_or_create_spreadsheet(gc):
    spreadsheet_id = os.environ.get("SPREADSHEET_ID", "").strip()

    if spreadsheet_id:
        return gc.open_by_key(spreadsheet_id)

    try:
        return gc.open(SPREADSHEET_NAME)
    except gspread.SpreadsheetNotFound:
        return gc.create(SPREADSHEET_NAME)

def organize_spreadsheet_tabs(spreadsheet):
    spreadsheet.sheet1.update_title("Animes")

    # A versão atual usa apenas: Animes e Resumo.
    try:
        old_stats = spreadsheet.worksheet("Estatisticas")
        try:
            spreadsheet.worksheet("Resumo")
            spreadsheet.del_worksheet(old_stats)
        except gspread.WorksheetNotFound:
            old_stats.update_title("Resumo")
    except gspread.WorksheetNotFound:
        pass

    try:
        old_highlights = spreadsheet.worksheet("Destaques")
        spreadsheet.del_worksheet(old_highlights)
    except gspread.WorksheetNotFound:
        pass

# ─────────────────────────────────────────────
# MAIN — execução única para GitHub Actions
# ─────────────────────────────────────────────

def main():
    print("=" * 55)
    print("  Armário dos Animes  |  GitHub Actions")
    print("=" * 55)

    print("\nConectando ao Google Sheets...")
    gc = get_google_client()
    spreadsheet = open_or_create_spreadsheet(gc)
    organize_spreadsheet_tabs(spreadsheet)

    print(f"Planilha aberta: {spreadsheet.url}")
    print("Horário usado: Brasília (America/Sao_Paulo).")
    print("-" * 55)

    agora = now_br("%H:%M:%S")
    print(f"[{agora}] Buscando listas no AniList...")

    run_sync(spreadsheet, verbose=True)

    agora2 = now_br("%H:%M:%S")
    print(f"[{agora2}] Planilha atualizada com sucesso!")


if __name__ == "__main__":
    main()
