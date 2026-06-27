# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ARMÁRIO DOS ANIMES — AniList + MyAnimeList -> Google Sheets
# Dashboard melhorado + estatísticas novas — versão sem merge e sem freeze
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# COLAB — rode antes, em células separadas, se precisar:
#
# !pip install -q requests gspread google-auth
#
# from google.colab import auth
# auth.authenticate_user()
# print("Autenticado!")
#
# Opcional — anti-desconexão:
# from IPython.display import display, Javascript
# display(Javascript("""
#   function clickConnect() {
#     try {
#       document.querySelector("#top-toolbar > colab-connect-button")
#         .shadowRoot.querySelector("#connect").click();
#     } catch(e) {}
#   }
#   setInterval(clickConnect, 60000);
# """))
# print("Keep-alive ativo!")
#
# Depois cole/rode este script inteiro.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

import os
import time
import json
import hashlib
import requests
import gspread

from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo

from google.auth import default
from google.oauth2.service_account import Credentials


# ─────────────────────────────────────────────
# CONFIGURAÇÕES GERAIS
# ─────────────────────────────────────────────

TZ = ZoneInfo("America/Sao_Paulo")

ANILIST_API_URL = "https://graphql.anilist.co"
SPREADSHEET_NAME = "planoha animes armário - (python fucking good bro)"

# Em modo loop, ele checa de tempos em tempos.
SYNC_INTERVAL = 300  # 300 = 5 min

# True = fica rodando em loop.
# False = roda uma vez e para.
AUTO_LOOP = True

# Se usar GitHub Actions/Render/etc, você pode setar SPREADSHEET_ID.
# Se deixar vazio, ele abre/cria pelo nome.
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "").strip()


# ─────────────────────────────────────────────
# USUÁRIOS
# ─────────────────────────────────────────────

ANILIST_USERNAMES = [
    "CianBrz",
    "BingoRTv",
    "Dioo",
    "Gumya",
    "Jotalhos",
    "niccname",
    "ViniAxd",
    "SleepyGT",
    "Cafito",
]

# Usuários do MyAnimeList.
# Este script usa o endpoint público load.json do próprio MAL.
MAL_USERNAMES = [
    "KakaCrads",
]

USERNAMES = ANILIST_USERNAMES + MAL_USERNAMES


# ─────────────────────────────────────────────
# STATUS
# ─────────────────────────────────────────────

STATUS_MAP_ANILIST = {
    "COMPLETED": "Assistido",
    "DROPPED": "Dropado",
    "PAUSED": "Pausado",
    "CURRENT": "Assistindo",
    "PLANNING": "Planejando",
}

STATUS_VALUES = [
    "Assistido",
    "Assistindo",
    "Planejando",
    "Dropado",
    "Pausado",
]

STATUS_BG = {
    "Assistido": {"red": 0.204, "green": 0.659, "blue": 0.325},
    "Dropado": {"red": 0.898, "green": 0.224, "blue": 0.208},
    "Pausado": {"red": 0.984, "green": 0.737, "blue": 0.020},
    "Assistindo": {"red": 0.259, "green": 0.522, "blue": 0.957},
    "Planejando": {"red": 0.612, "green": 0.153, "blue": 0.690},
    "-": {"red": 0.930, "green": 0.930, "blue": 0.930},
}

STATUS_FG = {
    "Assistido": {"red": 1, "green": 1, "blue": 1},
    "Dropado": {"red": 1, "green": 1, "blue": 1},
    "Pausado": {"red": 0.18, "green": 0.14, "blue": 0.02},
    "Assistindo": {"red": 1, "green": 1, "blue": 1},
    "Planejando": {"red": 1, "green": 1, "blue": 1},
    "-": {"red": 0.60, "green": 0.60, "blue": 0.60},
}


# ─────────────────────────────────────────────
# CORES DO DASHBOARD
# ─────────────────────────────────────────────

WHITE = {"red": 1, "green": 1, "blue": 1}
BLACK = {"red": 0.08, "green": 0.08, "blue": 0.08}

DARK_HDR = {"red": 0.08, "green": 0.11, "blue": 0.22}
DARKER = {"red": 0.05, "green": 0.07, "blue": 0.14}
GRAY_ALT = {"red": 0.97, "green": 0.97, "blue": 0.985}
GRAY_HDR = {"red": 0.20, "green": 0.20, "blue": 0.22}

LIGHT_BLUE = {"red": 0.90, "green": 0.94, "blue": 1.00}
LIGHT_GREEN = {"red": 0.90, "green": 0.97, "blue": 0.91}
LIGHT_PURPLE = {"red": 0.97, "green": 0.91, "blue": 0.98}
LIGHT_ORANGE = {"red": 1.00, "green": 0.95, "blue": 0.88}
LIGHT_RED = {"red": 1.00, "green": 0.90, "blue": 0.90}
LIGHT_YELLOW = {"red": 1.00, "green": 0.98, "blue": 0.84}

BLUE_TXT = {"red": 0.08, "green": 0.20, "blue": 0.45}
GREEN_TXT = {"red": 0.08, "green": 0.35, "blue": 0.12}
PURPLE_TXT = {"red": 0.30, "green": 0.08, "blue": 0.36}
ORANGE_TXT = {"red": 0.55, "green": 0.24, "blue": 0.04}
RED_TXT = {"red": 0.65, "green": 0.12, "blue": 0.10}
YELLOW_TXT = {"red": 0.55, "green": 0.42, "blue": 0.00}

GOLD = {"red": 0.80, "green": 0.60, "blue": 0.00}
SILVER = {"red": 0.55, "green": 0.55, "blue": 0.58}
BRONZE = {"red": 0.60, "green": 0.36, "blue": 0.17}

AVATAR_COLORS = [
    ({"red": 0.18, "green": 0.39, "blue": 0.78}, WHITE),
    ({"red": 0.61, "green": 0.15, "blue": 0.69}, WHITE),
    ({"red": 0.20, "green": 0.66, "blue": 0.33}, WHITE),
    ({"red": 0.90, "green": 0.35, "blue": 0.13}, WHITE),
    ({"red": 0.00, "green": 0.59, "blue": 0.53}, WHITE),
    ({"red": 0.76, "green": 0.19, "blue": 0.39}, WHITE),
    ({"red": 0.20, "green": 0.52, "blue": 0.74}, WHITE),
    ({"red": 0.48, "green": 0.35, "blue": 0.72}, WHITE),
    ({"red": 0.85, "green": 0.55, "blue": 0.10}, WHITE),
    ({"red": 0.10, "green": 0.55, "blue": 0.60}, WHITE),
]


# ─────────────────────────────────────────────
# DATAS
# ─────────────────────────────────────────────

def now_br(fmt="%d/%m/%Y  %H:%M"):
    return datetime.now(TZ).strftime(fmt)


def next_check_br(seconds):
    return datetime.fromtimestamp(time.time() + seconds, TZ).strftime("%H:%M:%S")


# ─────────────────────────────────────────────
# ANILIST
# ─────────────────────────────────────────────

MEDIA_LIST_QUERY = """
query ($username: String) {
  MediaListCollection(userName: $username, type: ANIME) {
    lists {
      entries {
        status
        media {
          id
          title {
            romaji
            english
          }
        }
      }
    }
  }
}
"""


def fetch_anilist_user(username):
    r = requests.post(
        ANILIST_API_URL,
        json={
            "query": MEDIA_LIST_QUERY,
            "variables": {"username": username},
        },
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=30,
    )

    if r.status_code == 429:
        wait = int(r.headers.get("Retry-After", 60))
        print(f"  Rate limit AniList! Aguardando {wait}s...")
        time.sleep(wait)
        return fetch_anilist_user(username)

    r.raise_for_status()
    data = r.json()

    if "errors" in data:
        print(f"  Erro AniList para '{username}': {data['errors']}")
        return {}

    collection = data.get("data", {}).get("MediaListCollection")
    if not collection:
        print(f"  Nenhuma lista encontrada no AniList para '{username}'.")
        return {}

    anime_map = {}

    for lst in collection.get("lists", []):
        for entry in lst.get("entries", []):
            media = entry.get("media", {})
            mid = media.get("id")

            if not mid:
                continue

            title_data = media.get("title", {})
            title = (
                title_data.get("english")
                or title_data.get("romaji")
                or f"ID:{mid}"
            )

            anime_map[mid] = {
                "title": title,
                "status": STATUS_MAP_ANILIST.get(entry.get("status"), "-"),
            }

    return anime_map


# ─────────────────────────────────────────────
# MYANIMELIST — load.json
# ─────────────────────────────────────────────

def normalize_mal_status(raw_status):
    """
    Status do MAL no endpoint /load.json:
    1 = Assistindo
    2 = Assistido
    3 = Pausado
    4 = Dropado
    6 = Planejando
    """
    status_map = {
        1: "Assistindo",
        2: "Assistido",
        3: "Pausado",
        4: "Dropado",
        6: "Planejando",
        "1": "Assistindo",
        "2": "Assistido",
        "3": "Pausado",
        "4": "Dropado",
        "6": "Planejando",
    }

    return status_map.get(raw_status, "-")


def fetch_mal_user(username):
    """
    Busca a lista pública do MyAnimeList usando o endpoint JSON carregado pelo site.

    Exemplo:
    https://myanimelist.net/animelist/KakaCrads/load.json?offset=0&status=7

    status=7 significa "todos os status".
    """

    anime_map = {}
    offset = 0
    limit = 300

    session = requests.Session()

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Referer": f"https://myanimelist.net/animelist/{username}",
    }

    while True:
        url = f"https://myanimelist.net/animelist/{username}/load.json"

        try:
            r = session.get(
                url,
                params={
                    "offset": offset,
                    "status": 7,
                },
                headers=headers,
                timeout=30,
            )

            if r.status_code == 403:
                print(f"  MAL bloqueou a requisição para '{username}' — HTTP 403.")
                print("  Teste rodar localmente/Colab ou usar a API oficial do MAL.")
                return anime_map

            if r.status_code == 404:
                print(f"  Usuário MAL '{username}' não encontrado.")
                return anime_map

            if r.status_code == 429:
                print("  Rate limit do MAL. Aguardando 15s...")
                time.sleep(15)
                continue

            r.raise_for_status()

            try:
                items = r.json()
            except ValueError:
                print(f"  MAL não retornou JSON para '{username}'.")
                print(f"  Resposta inicial: {r.text[:300]}")
                return anime_map

        except requests.RequestException as e:
            print(f"  Erro ao buscar MAL '{username}': {e}")
            return anime_map

        print(f"    MAL offset {offset}: {len(items)} itens")

        if not items:
            break

        for idx, entry in enumerate(items):
            mal_id = entry.get("anime_id")

            if not mal_id:
                continue

            title = (
                entry.get("anime_title_eng")
                or entry.get("anime_title")
                or f"MAL:{mal_id}"
            )

            raw_status = entry.get("status")
            status = normalize_mal_status(raw_status)

            if offset == 0 and idx < 5:
                print(
                    f"      DEBUG MAL: {title} | "
                    f"raw_status={raw_status} | status={status}"
                )

            key = f"mal_{mal_id}"

            anime_map[key] = {
                "title": title,
                "status": status,
            }

        offset += limit
        time.sleep(1.2)

    return anime_map


# ─────────────────────────────────────────────
# BUSCA TODOS OS USUÁRIOS
# ─────────────────────────────────────────────

def fetch_all_users(verbose=True):
    all_data = {}

    for u in ANILIST_USERNAMES:
        if verbose:
            print(f"  [AniList] -> {u}...", end=" ", flush=True)

        all_data[u] = fetch_anilist_user(u)

        if verbose:
            print(f"{len(all_data[u])} animes")

        time.sleep(1)

    for u in MAL_USERNAMES:
        if verbose:
            print(f"  [MAL]     -> {u}...", flush=True)

        all_data[u] = fetch_mal_user(u)

        if verbose:
            print(f"  [MAL]     -> {u}: {len(all_data[u])} animes")

        time.sleep(1)

    return all_data


def build_master_list(all_data):
    master = {}
    grid = {}

    for u, anime_map in all_data.items():
        for mid, info in anime_map.items():
            if mid not in master:
                master[mid] = info["title"]
                grid[mid] = {}

            grid[mid][u] = info["status"]

    for mid in grid:
        for u in USERNAMES:
            grid[mid].setdefault(u, "-")

    return master, grid


def compute_hash(all_data):
    snap = {
        u: sorted(
            [(str(mid), info["status"]) for mid, info in am.items()],
            key=lambda x: x[0],
        )
        for u, am in sorted(all_data.items())
    }

    return hashlib.md5(
        json.dumps(snap, sort_keys=True).encode()
    ).hexdigest()


# ─────────────────────────────────────────────
# ANALYTICS
# ─────────────────────────────────────────────

def build_analytics(master, grid):
    N = len(USERNAMES)

    watched_count = {
        mid: sum(1 for u in USERNAMES if grid[mid].get(u) == "Assistido")
        for mid in master
    }

    dropped_count = {
        mid: sum(1 for u in USERNAMES if grid[mid].get(u) == "Dropado")
        for mid in master
    }

    active_count = {
        mid: sum(1 for u in USERNAMES if grid[mid].get(u) == "Assistindo")
        for mid in master
    }

    top_watched = sorted(
        [(mid, c) for mid, c in watched_count.items() if c > 0],
        key=lambda x: (-x[1], master[x[0]].lower()),
    )[:10]

    low_seen_animes = sorted(
        [(mid, c) for mid, c in watched_count.items() if 0 < c <= 2],
        key=lambda x: (x[1], master[x[0]].lower()),
    )[:10]

    all_watched_by_all = sum(1 for c in watched_count.values() if c == N)

    user_stats = {}

    for u in USERNAMES:
        counts = Counter(grid[mid].get(u, "-") for mid in master)

        user_stats[u] = {
            s: counts.get(s, 0)
            for s in STATUS_VALUES + ["-"]
        }

        user_stats[u]["total"] = sum(
            user_stats[u].get(s, 0)
            for s in STATUS_VALUES
        )

        total = user_stats[u]["total"]
        watched = user_stats[u]["Assistido"]

        user_stats[u]["percent_completed"] = round((watched / total) * 100, 1) if total else 0
        user_stats[u]["to_watch"] = user_stats[u]["Planejando"] + user_stats[u]["Pausado"]

    # Únicos = animes que só aquele usuário assistiu
    unique_watched = {}
    for u in USERNAMES:
        unique_watched[u] = sum(
            1 for mid in master
            if grid[mid].get(u) == "Assistido"
            and watched_count[mid] == 1
        )
        user_stats[u]["unique_watched_count"] = unique_watched[u]

    # Pares mais compatíveis = animes assistidos em comum
    pair_scores = []
    for i in range(len(USERNAMES)):
        for j in range(i + 1, len(USERNAMES)):
            u1 = USERNAMES[i]
            u2 = USERNAMES[j]

            common = sum(
                1 for mid in master
                if grid[mid].get(u1) == "Assistido"
                and grid[mid].get(u2) == "Assistido"
            )

            pair_scores.append((u1, u2, common))

    most_common_pair = max(pair_scores, key=lambda x: x[2]) if pair_scores else ("-", "-", 0)

    # Animes divisivos = gente assistiu e gente dropou
    different_opinion_animes = sorted(
        [
            (
                mid,
                watched_count[mid],
                dropped_count[mid],
                watched_count[mid] + dropped_count[mid],
            )
            for mid in master
            if watched_count[mid] > 0 and dropped_count[mid] > 0
        ],
        key=lambda x: (-x[3], -x[1], -x[2], master[x[0]].lower()),
    )[:10]

    most_watched_user = max(USERNAMES, key=lambda u: user_stats[u]["Assistido"])
    most_dropped_user = max(USERNAMES, key=lambda u: user_stats[u]["Dropado"])
    biggest_list_user = max(USERNAMES, key=lambda u: user_stats[u]["total"])
    best_percent_completed_user = max(USERNAMES, key=lambda u: user_stats[u]["percent_completed"])
    biggest_to_watch_user = max(USERNAMES, key=lambda u: user_stats[u]["to_watch"])
    most_unique_watched_user = max(USERNAMES, key=lambda u: user_stats[u]["unique_watched_count"])

    return {
        "top_watched": top_watched,
        "low_seen_animes": low_seen_animes,
        "different_opinion_animes": different_opinion_animes,
        "user_stats": user_stats,
        "most_watched_user": most_watched_user,
        "most_dropped_user": most_dropped_user,
        "biggest_list_user": biggest_list_user,
        "best_percent_completed_user": best_percent_completed_user,
        "biggest_to_watch_user": biggest_to_watch_user,
        "most_unique_watched_user": most_unique_watched_user,
        "unique_watched": unique_watched,
        "most_common_pair": most_common_pair,
        "watched_count": watched_count,
        "dropped_count": dropped_count,
        "active_count": active_count,
        "all_watched_by_all": all_watched_by_all,
        "total_unique": len(master),
    }


# ─────────────────────────────────────────────
# HELPERS DE FORMATAÇÃO
# ─────────────────────────────────────────────

def cell_fmt(
    bg,
    fg=None,
    bold=False,
    size=10,
    align="CENTER",
    wrap="CLIP",
    italic=False,
    strikethrough=False,
):
    return {
        "backgroundColor": bg,
        "horizontalAlignment": align,
        "verticalAlignment": "MIDDLE",
        "wrapStrategy": wrap,
        "textFormat": {
            "bold": bold,
            "italic": italic,
            "strikethrough": strikethrough,
            "fontSize": size,
            "foregroundColor": fg or BLACK,
        },
    }


def repeat_cell(sid, r1, r2, c1, c2, fmt):
    return {
        "repeatCell": {
            "range": {
                "sheetId": sid,
                "startRowIndex": r1,
                "endRowIndex": r2,
                "startColumnIndex": c1,
                "endColumnIndex": c2,
            },
            "cell": {
                "userEnteredFormat": fmt,
            },
            "fields": (
                "userEnteredFormat("
                "backgroundColor,"
                "horizontalAlignment,"
                "verticalAlignment,"
                "wrapStrategy,"
                "textFormat)"
            ),
        }
    }


def border_req(sid, r1, r2, c1, c2, style="SOLID", width=1, color=None, inner=True):
    color = color or {"red": 0.82, "green": 0.82, "blue": 0.85}
    b = {"style": style, "width": width, "color": color}

    req = {
        "updateBorders": {
            "range": {
                "sheetId": sid,
                "startRowIndex": r1,
                "endRowIndex": r2,
                "startColumnIndex": c1,
                "endColumnIndex": c2,
            },
            "top": b,
            "bottom": b,
            "left": b,
            "right": b,
        }
    }

    if inner:
        req["updateBorders"]["innerHorizontal"] = b
        req["updateBorders"]["innerVertical"] = b

    return req


def outer_border(sid, r1, r2, c1, c2, color=None, width=2):
    color = color or DARK_HDR
    b = {"style": "SOLID", "width": width, "color": color}

    thin = {
        "style": "SOLID",
        "width": 1,
        "color": {"red": 0.82, "green": 0.82, "blue": 0.85},
    }

    return {
        "updateBorders": {
            "range": {
                "sheetId": sid,
                "startRowIndex": r1,
                "endRowIndex": r2,
                "startColumnIndex": c1,
                "endColumnIndex": c2,
            },
            "top": b,
            "bottom": b,
            "left": b,
            "right": b,
            "innerHorizontal": thin,
            "innerVertical": thin,
        }
    }


def row_height(sid, r1, r2, px):
    return {
        "updateDimensionProperties": {
            "range": {
                "sheetId": sid,
                "dimension": "ROWS",
                "startIndex": r1,
                "endIndex": r2,
            },
            "properties": {
                "pixelSize": px,
            },
            "fields": "pixelSize",
        }
    }


def col_width(sid, c1, c2, px):
    return {
        "updateDimensionProperties": {
            "range": {
                "sheetId": sid,
                "dimension": "COLUMNS",
                "startIndex": c1,
                "endIndex": c2,
            },
            "properties": {
                "pixelSize": px,
            },
            "fields": "pixelSize",
        }
    }


def merge_cells(sid, r1, r2, c1, c2):
    """
    Versão segura: NÃO mescla células.

    Motivo:
    O Google Sheets dá erro quando tenta congelar linhas/colunas que cruzam células mescladas.
    Para deixar o dashboard mais estável no GitHub Actions/Colab, esta função vira um
    "no-op" visual: apenas mantém o wrapStrategy da região.
    """
    return {
        "repeatCell": {
            "range": {
                "sheetId": sid,
                "startRowIndex": r1,
                "endRowIndex": r2,
                "startColumnIndex": c1,
                "endColumnIndex": c2,
            },
            "cell": {
                "userEnteredFormat": {
                    "wrapStrategy": "CLIP"
                }
            },
            "fields": "userEnteredFormat.wrapStrategy",
        }
    }


def unmerge_all(sid):
    return {
        "unmergeCells": {
            "range": {
                "sheetId": sid,
            }
        }
    }


def freeze(sid, rows=1, cols=0):
    return {
        "updateSheetProperties": {
            "properties": {
                "sheetId": sid,
                "gridProperties": {
                    "frozenRowCount": rows,
                    "frozenColumnCount": cols,
                },
            },
            "fields": (
                "gridProperties.frozenRowCount,"
                "gridProperties.frozenColumnCount"
            ),
        }
    }


# ─────────────────────────────────────────────
# ABA ANIMES
# ─────────────────────────────────────────────

def write_sync_sheet(ws, master, grid, analytics, last_updated):
    sid = ws.id
    N = len(USERNAMES)

    sorted_ids = sorted(master, key=lambda m: master[m].lower())
    n = len(sorted_ids)

    TITLE_ROW = 0
    LEGEND_ROW = 1
    HEADER_ROW = 2
    DATA_START = 3

    total_cols = N + 1

    rows = []

    title_row = [f"ARMÁRIO DOS ANIMES  —  Atualizado em {last_updated}"] + [""] * N
    legend_row = [
        "LEGENDA",
        "Assistido",
        "Assistindo",
        "Planejando",
        "Pausado",
        "Dropado",
        "Sem registro",
    ] + [""] * max(0, total_cols - 7)

    header_row = ["Nome do anime"] + USERNAMES

    rows.append(title_row[:total_cols])
    rows.append(legend_row[:total_cols])
    rows.append(header_row)

    for rank, mid in enumerate(sorted_ids, 1):
        rows.append(
            [f"{rank}. {master[mid]}"]
            + [grid[mid].get(u, "-") for u in USERNAMES]
        )

    ws.clear()
    ws.update(range_name="A1", values=rows)

    reqs = []
    reqs.append(unmerge_all(sid))
    # Freeze desativado para evitar conflito com merges antigos no Google Sheets.
    reqs.append({"clearBasicFilter": {"sheetId": sid}})

    reqs.append(
        repeat_cell(
            sid,
            0,
            len(rows),
            0,
            total_cols,
            cell_fmt(WHITE, BLACK, size=10, align="CENTER", wrap="CLIP"),
        )
    )

    # Título
    reqs.append(merge_cells(sid, TITLE_ROW, TITLE_ROW + 1, 0, total_cols))
    reqs.append(
        repeat_cell(
            sid,
            TITLE_ROW,
            TITLE_ROW + 1,
            0,
            total_cols,
            cell_fmt(DARK_HDR, WHITE, bold=True, size=14, align="LEFT"),
        )
    )
    reqs.append(row_height(sid, TITLE_ROW, TITLE_ROW + 1, 38))

    # Legenda
    reqs.append(
        repeat_cell(
            sid,
            LEGEND_ROW,
            LEGEND_ROW + 1,
            0,
            total_cols,
            cell_fmt(GRAY_HDR, WHITE, bold=True, size=9, align="CENTER"),
        )
    )

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
            reqs.append(
                repeat_cell(
                    sid,
                    LEGEND_ROW,
                    LEGEND_ROW + 1,
                    col,
                    col + 1,
                    cell_fmt(
                        STATUS_BG[st],
                        STATUS_FG[st],
                        bold=True,
                        size=9,
                        align="CENTER",
                    ),
                )
            )

    reqs.append(row_height(sid, LEGEND_ROW, LEGEND_ROW + 1, 28))

    # Cabeçalho
    reqs.append(
        repeat_cell(
            sid,
            HEADER_ROW,
            HEADER_ROW + 1,
            0,
            total_cols,
            cell_fmt(DARK_HDR, WHITE, bold=True, size=10, align="CENTER"),
        )
    )

    reqs.append(
        repeat_cell(
            sid,
            HEADER_ROW,
            HEADER_ROW + 1,
            0,
            1,
            cell_fmt(DARK_HDR, WHITE, bold=True, size=10, align="LEFT"),
        )
    )

    for i in range(N):
        bg, fg = AVATAR_COLORS[i % len(AVATAR_COLORS)]
        reqs.append(
            repeat_cell(
                sid,
                HEADER_ROW,
                HEADER_ROW + 1,
                i + 1,
                i + 2,
                cell_fmt(bg, fg, bold=True, size=10, align="CENTER"),
            )
        )

    reqs.append(row_height(sid, HEADER_ROW, HEADER_ROW + 1, 34))

    # Dados
    for i, mid in enumerate(sorted_ids):
        r = DATA_START + i
        bg = GRAY_ALT if i % 2 == 0 else WHITE

        reqs.append(
            repeat_cell(
                sid,
                r,
                r + 1,
                0,
                1,
                cell_fmt(bg, BLACK, size=10, align="LEFT"),
            )
        )

        for col_i, u in enumerate(USERNAMES):
            st = grid[mid].get(u, "-")

            reqs.append(
                repeat_cell(
                    sid,
                    r,
                    r + 1,
                    col_i + 1,
                    col_i + 2,
                    cell_fmt(
                        STATUS_BG.get(st, STATUS_BG["-"]),
                        STATUS_FG.get(st, STATUS_FG["-"]),
                        bold=(st != "-"),
                        size=10,
                        align="CENTER",
                    ),
                )
            )

    reqs.append(row_height(sid, DATA_START, DATA_START + n, 24))
    reqs.append(outer_border(sid, 0, len(rows), 0, total_cols))
    # Freeze desativado para evitar conflito com merges antigos no Google Sheets.

    reqs.append(
        {
            "setBasicFilter": {
                "filter": {
                    "range": {
                        "sheetId": sid,
                        "startRowIndex": HEADER_ROW,
                        "endRowIndex": len(rows),
                        "startColumnIndex": 0,
                        "endColumnIndex": total_cols,
                    }
                }
            }
        }
    )

    reqs.append(col_width(sid, 0, 1, 390))

    for i in range(1, total_cols):
        reqs.append(col_width(sid, i, i + 1, 115))

    return reqs, sorted_ids


# ─────────────────────────────────────────────
# ABA RESUMO — DASHBOARD
# ─────────────────────────────────────────────

def write_stats_sheet(ws, master, grid, analytics):
    sid = ws.id
    N = len(USERNAMES)

    top = analytics["top_watched"]
    hidden = analytics["low_seen_animes"]
    divisive = analytics["different_opinion_animes"]
    us = analytics["user_stats"]
    wc = analytics["watched_count"]
    dc = analytics["dropped_count"]

    mwu = analytics["most_watched_user"]
    mdu = analytics["most_dropped_user"]
    blu = analytics["biggest_list_user"]
    bcu = analytics["best_percent_completed_user"]
    bbu = analytics["biggest_to_watch_user"]
    tcu = analytics["most_unique_watched_user"]

    all_watched = analytics["all_watched_by_all"]
    total_unique = analytics["total_unique"]
    pair_u1, pair_u2, pair_common = analytics["most_common_pair"]

    NCOLS = 12
    data = []

    def blank():
        return [""] * NCOLS

    def add_section(title):
        row_idx = len(data)
        row = blank()
        row[0] = f"  {title}"
        data.append(row)
        return row_idx

    # Título
    row = blank()
    row[0] = "  RESUMO DO GRUPO"
    row[9] = f"Atualizado: {now_br()}"
    data.append(row)

    data.append(blank())

    # Cards: 6 cards, cada um com 2 colunas
    card_labels = [
        "Total de animes",
        "Assistidos por todos",
        "Maior lista de animes",
        "Maior % concluída",
        "Maior to_watch",
        "Mais animes únicos",
    ]

    card_values = [
        str(total_unique),
        f"{all_watched} animes",
        f"{blu} ({us[blu]['total']})",
        f"{bcu} ({us[bcu]['percent_completed']}%)",
        f"{bbu} ({us[bbu]['to_watch']})",
        f"{tcu} ({us[tcu]['unique_watched_count']})",
    ]

    label_row = blank()
    value_row = blank()
    for i in range(6):
        c = i * 2
        label_row[c] = card_labels[i]
        value_row[c] = card_values[i]

    data.append(label_row)
    data.append(value_row)
    data.append(blank())

    # Top 10
    TOP_HDR = add_section("TOP 10 — ANIMES MAIS ASSISTIDOS")
    row = blank()
    row[0] = "Anime"
    row[4] = "Popularidade"
    row[6] = "Assistido por"
    row[8] = "% grupo"
    row[9] = "Quem assistiu"
    data.append(row)

    medals = ["🥇", "🥈", "🥉"] + [f"{i}." for i in range(4, 11)]

    for i, (mid, count) in enumerate(top):
        watchers = [u for u in USERNAMES if grid[mid].get(u) == "Assistido"]
        pips = "●" * count + "○" * (N - count)

        row = blank()
        row[0] = f"{medals[i]} {master[mid]}"
        row[4] = pips
        row[6] = f"{count} de {N}"
        row[8] = f"{round(count / N * 100)}%"
        row[9] = ", ".join(watchers)
        data.append(row)

    data.append(blank())

    # Pouco visto gems
    HIDDEN_HDR = add_section("ANIMES POUCO ASSISTIDOS PELO GRUPO")
    row = blank()
    row[0] = "Anime"
    row[6] = "Quem assistiu"
    row[10] = "Qtd."
    data.append(row)

    for mid, count in hidden:
        watchers = [u for u in USERNAMES if grid[mid].get(u) == "Assistido"]

        row = blank()
        row[0] = master[mid]
        row[6] = ", ".join(watchers)
        row[10] = f"{count} pessoa{'s' if count != 1 else ''}"
        data.append(row)

    data.append(blank())

    # Ranking de usuários
    USER_HDR = add_section("RANKING POR USUÁRIO")
    row = blank()
    row[0] = "Usuário"
    row[1] = "Assistido"
    row[2] = "Assistindo"
    row[3] = "Planejando"
    row[4] = "Dropado"
    row[5] = "Pausado"
    row[6] = "Total"
    row[7] = "% concluído"
    row[8] = "Para assistir"
    row[9] = "Únicos"
    data.append(row)

    sorted_users = sorted(USERNAMES, key=lambda u: -us[u]["Assistido"])
    USER_START = len(data)

    for pos, u in enumerate(sorted_users, 1):
        s = us[u]

        row = blank()
        row[0] = f"{pos}. {u}"
        row[1] = s["Assistido"]
        row[2] = s["Assistindo"]
        row[3] = s["Planejando"]
        row[4] = s["Dropado"]
        row[5] = s["Pausado"]
        row[6] = s["total"]
        row[7] = f"{s['percent_completed']}%"
        row[8] = s["to_watch"]
        row[9] = s["unique_watched_count"]
        data.append(row)

    data.append(blank())

    # Divisivos
    DIV_HDR = add_section("ANIMES COM OPINIÕES DIFERENTES")
    row = blank()
    row[0] = "Anime"
    row[6] = "Assistiram"
    row[8] = "Droparam"
    row[10] = "Total"
    data.append(row)

    if divisive:
        for mid, watched, dropped, score in divisive:
            row = blank()
            row[0] = master[mid]
            row[6] = watched
            row[8] = dropped
            row[10] = score
            data.append(row)
    else:
        row = blank()
        row[0] = "Nenhum anime com opiniões diferentes encontrado ainda."
        data.append(row)

    data.append(blank())

    # Compatibilidade + destaques
    COMPAT_HDR = add_section("ANIMES EM COMUM E DESTAQUES")
    highlights = [
        ("Dupla com mais animes em comum", f"{pair_u1} + {pair_u2} → {pair_common} animes em comum"),
        ("Pessoa que mais concluiu animes", f"{mwu} → {us[mwu]['Assistido']} concluídos"),
        ("Pessoa que mais dropou animes", f"{mdu} → {us[mdu]['Dropado']} dropados"),
        ("Maior lista de animes", f"{blu} → {us[blu]['total']} animes na lista"),
        ("Maior to_watch", f"{bbu} → {us[bbu]['to_watch']} planejados ou pausados"),
        ("Mais animes únicos", f"{tcu} → {us[tcu]['unique_watched_count']} animes únicos assistidos"),
    ]

    for label, value in highlights:
        row = blank()
        row[0] = label
        row[3] = value
        data.append(row)

    ws.clear()
    ws.update(range_name="A1", values=data)

    reqs = []
    reqs.append(unmerge_all(sid))
    # Freeze desativado para evitar conflito com merges antigos no Google Sheets.

    nrows = len(data)

    # Fundo geral
    reqs.append(
        repeat_cell(
            sid,
            0,
            nrows,
            0,
            NCOLS,
            cell_fmt(WHITE, BLACK, size=10, align="LEFT", wrap="CLIP"),
        )
    )

    # Título
    reqs.append(merge_cells(sid, 0, 1, 0, NCOLS))
    reqs.append(
        repeat_cell(
            sid,
            0,
            1,
            0,
            NCOLS,
            cell_fmt(DARKER, WHITE, bold=True, size=16, align="LEFT"),
        )
    )
    reqs.append(row_height(sid, 0, 1, 42))

    # Cards
    card_spans = [
        (0, 2),
        (2, 4),
        (4, 6),
        (6, 8),
        (8, 10),
        (10, 12),
    ]

    card_bgs = [
        LIGHT_BLUE,
        LIGHT_PURPLE,
        LIGHT_GREEN,
        LIGHT_YELLOW,
        LIGHT_ORANGE,
        LIGHT_RED,
    ]

    card_fgs = [
        BLUE_TXT,
        PURPLE_TXT,
        GREEN_TXT,
        YELLOW_TXT,
        ORANGE_TXT,
        RED_TXT,
    ]

    for i, (c1, c2) in enumerate(card_spans):
        reqs.append(merge_cells(sid, 2, 3, c1, c2))
        reqs.append(merge_cells(sid, 3, 4, c1, c2))

        reqs.append(
            repeat_cell(
                sid,
                2,
                3,
                c1,
                c2,
                cell_fmt(
                    card_bgs[i],
                    card_fgs[i],
                    bold=False,
                    size=9,
                    align="CENTER",
                    wrap="WRAP",
                ),
            )
        )

        reqs.append(
            repeat_cell(
                sid,
                3,
                4,
                c1,
                c2,
                cell_fmt(
                    card_bgs[i],
                    card_fgs[i],
                    bold=True,
                    size=12,
                    align="CENTER",
                    wrap="WRAP",
                ),
            )
        )

        reqs.append(
            outer_border(
                sid,
                2,
                4,
                c1,
                c2,
                color=card_fgs[i],
                width=1,
            )
        )

    reqs.append(row_height(sid, 2, 3, 24))
    reqs.append(row_height(sid, 3, 4, 38))

    # Descobre blocos dinamicamente
    section_rows = [TOP_HDR, HIDDEN_HDR, USER_HDR, DIV_HDR, COMPAT_HDR]

    for section_row in section_rows:
        reqs.append(
            merge_cells(sid, section_row, section_row + 1, 0, NCOLS)
        )
        reqs.append(
            repeat_cell(
                sid,
                section_row,
                section_row + 1,
                0,
                NCOLS,
                cell_fmt(DARK_HDR, WHITE, bold=True, size=11, align="LEFT"),
            )
        )
        reqs.append(row_height(sid, section_row, section_row + 1, 30))

    # Subcabeçalhos
    for subheader_row in [TOP_HDR + 1, HIDDEN_HDR + 1, USER_HDR + 1, DIV_HDR + 1]:
        reqs.append(
            repeat_cell(
                sid,
                subheader_row,
                subheader_row + 1,
                0,
                NCOLS,
                cell_fmt(GRAY_HDR, WHITE, bold=True, size=9, align="CENTER"),
            )
        )

    # Top 10 style
    top_start = TOP_HDR + 2
    top_end = top_start + len(top)

    for i in range(len(top)):
        r = top_start + i
        bg = GRAY_ALT if i % 2 == 0 else WHITE

        reqs.append(
            repeat_cell(
                sid,
                r,
                r + 1,
                0,
                NCOLS,
                cell_fmt(bg, BLACK, size=10, align="LEFT"),
            )
        )

        reqs.append(
            repeat_cell(
                sid,
                r,
                r + 1,
                4,
                5,
                cell_fmt(
                    bg,
                    GREEN_TXT,
                    bold=True,
                    size=10,
                    align="CENTER",
                ),
            )
        )

        reqs.append(
            repeat_cell(
                sid,
                r,
                r + 1,
                6,
                9,
                cell_fmt(
                    bg,
                    BLACK,
                    bold=True,
                    size=10,
                    align="CENTER",
                ),
            )
        )

    reqs.append(outer_border(sid, TOP_HDR, top_end, 0, NCOLS))
    reqs.append(row_height(sid, top_start, top_end, 24))

    # Pouco visto style
    hidden_start = HIDDEN_HDR + 2
    hidden_end = hidden_start + len(hidden)

    for i in range(len(hidden)):
        r = hidden_start + i
        bg = GRAY_ALT if i % 2 == 0 else WHITE

        reqs.append(
            repeat_cell(
                sid,
                r,
                r + 1,
                0,
                NCOLS,
                cell_fmt(bg, BLACK, size=10, align="LEFT"),
            )
        )

        reqs.append(
            repeat_cell(
                sid,
                r,
                r + 1,
                10,
                11,
                cell_fmt(bg, PURPLE_TXT, bold=True, size=10, align="CENTER"),
            )
        )

    reqs.append(outer_border(sid, HIDDEN_HDR, hidden_end, 0, NCOLS))
    reqs.append(row_height(sid, hidden_start, hidden_end, 24))

    # Ranking style
    user_header = USER_HDR + 1
    user_start = USER_START
    user_end = user_start + len(sorted_users)

    # Cabeçalhos coloridos do ranking
    status_cols = [
        (1, "Assistido"),
        (2, "Assistindo"),
        (3, "Planejando"),
        (4, "Dropado"),
        (5, "Pausado"),
    ]

    for c, st in status_cols:
        reqs.append(
            repeat_cell(
                sid,
                user_header,
                user_header + 1,
                c,
                c + 1,
                cell_fmt(STATUS_BG[st], STATUS_FG[st], bold=True, size=9, align="CENTER"),
            )
        )

    reqs.append(
        repeat_cell(
            sid,
            user_header,
            user_header + 1,
            6,
            10,
            cell_fmt(GRAY_HDR, WHITE, bold=True, size=9, align="CENTER"),
        )
    )

    for i in range(len(sorted_users)):
        r = user_start + i
        bg = GRAY_ALT if i % 2 == 0 else WHITE

        reqs.append(
            repeat_cell(
                sid,
                r,
                r + 1,
                0,
                1,
                cell_fmt(bg, BLACK, bold=True, size=10, align="LEFT"),
            )
        )

        for c, st in status_cols:
            reqs.append(
                repeat_cell(
                    sid,
                    r,
                    r + 1,
                    c,
                    c + 1,
                    cell_fmt(STATUS_BG[st], STATUS_FG[st], bold=True, size=10, align="CENTER"),
                )
            )

        reqs.append(
            repeat_cell(
                sid,
                r,
                r + 1,
                6,
                10,
                cell_fmt(bg, BLACK, bold=True, size=10, align="CENTER"),
            )
        )

    reqs.append(outer_border(sid, USER_HDR, user_end, 0, 10))
    reqs.append(row_height(sid, user_start, user_end, 25))

    # Divisivos style
    div_start = DIV_HDR + 2
    div_rows = max(len(divisive), 1)
    div_end = div_start + div_rows

    for i in range(div_rows):
        r = div_start + i
        bg = GRAY_ALT if i % 2 == 0 else WHITE

        reqs.append(
            repeat_cell(
                sid,
                r,
                r + 1,
                0,
                NCOLS,
                cell_fmt(bg, BLACK, size=10, align="LEFT"),
            )
        )

        reqs.append(
            repeat_cell(
                sid,
                r,
                r + 1,
                6,
                11,
                cell_fmt(bg, RED_TXT, bold=True, size=10, align="CENTER"),
            )
        )

    reqs.append(outer_border(sid, DIV_HDR, div_end, 0, NCOLS))
    reqs.append(row_height(sid, div_start, div_end, 24))

    # Compatibilidade style
    compat_start = COMPAT_HDR + 1
    compat_end = compat_start + len(highlights)

    for i in range(len(highlights)):
        r = compat_start + i
        bg = GRAY_ALT if i % 2 == 0 else WHITE

        reqs.append(
            repeat_cell(
                sid,
                r,
                r + 1,
                0,
                3,
                cell_fmt(bg, BLUE_TXT, bold=True, size=10, align="LEFT"),
            )
        )

        reqs.append(
            repeat_cell(
                sid,
                r,
                r + 1,
                3,
                NCOLS,
                cell_fmt(bg, BLACK, bold=True, size=10, align="LEFT"),
            )
        )

    reqs.append(outer_border(sid, COMPAT_HDR, compat_end, 0, NCOLS))
    reqs.append(row_height(sid, compat_start, compat_end, 24))

    # Larguras
    widths = {
        0: 260,
        1: 95,
        2: 95,
        3: 105,
        4: 95,
        5: 85,
        6: 90,
        7: 90,
        8: 85,
        9: 230,
        10: 95,
        11: 85,
    }

    for c in range(NCOLS):
        reqs.append(col_width(sid, c, c + 1, widths.get(c, 90)))

    # Não congelar a aba Resumo: ela usa várias células mescladas nos cards.
    # O Google Sheets pode rejeitar freeze quando há merges no dashboard.
    # A aba Animes continua congelada normalmente.
    # Freeze desativado para evitar conflito com merges antigos no Google Sheets.

    return reqs


# ─────────────────────────────────────────────
# GOOGLE SHEETS
# ─────────────────────────────────────────────

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def get_google_client():
    """
    Funciona em:
    - Google Colab, usando auth.authenticate_user()
    - GitHub Actions/servidor, usando GOOGLE_SERVICE_ACCOUNT_JSON
    """

    service_account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")

    if service_account_json:
        try:
            info = json.loads(service_account_json)
            creds = Credentials.from_service_account_info(info, scopes=SCOPES)
            return gspread.authorize(creds)

        except json.JSONDecodeError as e:
            raise RuntimeError(
                "O secret GOOGLE_SERVICE_ACCOUNT_JSON não é um JSON válido."
            ) from e

    creds, _ = default(scopes=SCOPES)
    return gspread.authorize(creds)


def open_or_create_spreadsheet(gc):
    if SPREADSHEET_ID:
        return gc.open_by_key(SPREADSHEET_ID)

    try:
        return gc.open(SPREADSHEET_NAME)

    except gspread.SpreadsheetNotFound:
        return gc.create(SPREADSHEET_NAME)


def organize_spreadsheet_tabs(spreadsheet):
    spreadsheet.sheet1.update_title("Animes")

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
        spreadsheet.worksheet("Resumo")
    except gspread.WorksheetNotFound:
        spreadsheet.add_worksheet(title="Resumo", rows=500, cols=15)



# ─────────────────────────────────────────────
# LIMPEZA DE MERGES/FREEZE ANTIGOS
# ─────────────────────────────────────────────

def clear_sheet_layout_conflicts(spreadsheet, worksheets):
    """
    Limpa merges e congelamentos antigos antes do batch principal.

    Isso é importante porque uma execução anterior pode ter deixado células mescladas
    na planilha. Mesmo que o código novo não crie merges, o Google Sheets ainda pode
    recusar qualquer updateSheetProperties de freeze se houver merges antigos.
    """
    requests = []

    for ws in worksheets:
        sid = ws.id

        requests.append({
            "unmergeCells": {
                "range": {
                    "sheetId": sid
                }
            }
        })

        requests.append({
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sid,
                    "gridProperties": {
                        "frozenRowCount": 0,
                        "frozenColumnCount": 0,
                    },
                },
                "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount",
            }
        })

    if requests:
        spreadsheet.batch_update({"requests": requests})


# ─────────────────────────────────────────────
# SYNC
# ─────────────────────────────────────────────

def run_sync(spreadsheet, verbose=True):
    last_updated = now_br("%d/%m/%Y  %H:%M")

    all_data = fetch_all_users(verbose=verbose)
    master, grid = build_master_list(all_data)
    analytics = build_analytics(master, grid)

    ws_animes = spreadsheet.worksheet("Animes")
    ws_resumo = spreadsheet.worksheet("Resumo")

    # Limpa merges/freeze antigos em uma chamada separada antes da formatação.
    clear_sheet_layout_conflicts(spreadsheet, [ws_animes, ws_resumo])

    all_reqs = []

    reqs_sync, _ = write_sync_sheet(
        ws_animes,
        master,
        grid,
        analytics,
        last_updated,
    )
    all_reqs.extend(reqs_sync)

    reqs_stats = write_stats_sheet(
        ws_resumo,
        master,
        grid,
        analytics,
    )
    all_reqs.extend(reqs_stats)

    for i in range(0, len(all_reqs), 500):
        spreadsheet.batch_update(
            {
                "requests": all_reqs[i:i + 500],
            }
        )

    return all_data


def test_mal():
    print("=" * 55)
    print("  TESTE DO MYANIMELIST")
    print("=" * 55)

    for user in MAL_USERNAMES:
        print(f"\nTestando MAL: {user}")
        data = fetch_mal_user(user)
        print(f"Total encontrado: {len(data)} animes")

        for mid, info in list(data.items())[:10]:
            print(mid, "=>", info)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    print("=" * 55)
    print("  Armário dos Animes | AniList + MyAnimeList")
    print("=" * 55)
    print(f"  AniList: {len(ANILIST_USERNAMES)} usuários")
    print(f"  MAL:     {len(MAL_USERNAMES)} usuário(s)")
    print("=" * 55)

    print("\nConectando ao Google Sheets...")

    gc = get_google_client()
    spreadsheet = open_or_create_spreadsheet(gc)
    organize_spreadsheet_tabs(spreadsheet)

    print(f"Planilha aberta: {spreadsheet.url}")
    print("Horário: Brasília (America/Sao_Paulo)")
    print("-" * 55)

    if not AUTO_LOOP:
        agora = now_br("%H:%M:%S")
        print(f"[{agora}] Rodando sync único...")
        run_sync(spreadsheet, verbose=True)
        print(f"[{now_br('%H:%M:%S')}] Planilha atualizada com sucesso!")
        return

    print(f"Verificando a cada {SYNC_INTERVAL // 60} minutos.")
    print("Para parar: botão de stop no Colab.")
    print("-" * 55)

    last_hash = None
    sync_count = 0

    while True:
        agora = now_br("%H:%M:%S")
        print(f"[{agora}] Verificando mudanças...", end=" ", flush=True)

        all_data = fetch_all_users(verbose=False)
        current_hash = compute_hash(all_data)

        if current_hash != last_hash:
            msg = "Primeira execução." if last_hash is None else "MUDANÇA DETECTADA!"
            print(msg)

            sync_count += 1

            master, grid = build_master_list(all_data)
            analytics = build_analytics(master, grid)
            last_updated = now_br("%d/%m/%Y  %H:%M")

            ws_animes = spreadsheet.worksheet("Animes")
            ws_resumo = spreadsheet.worksheet("Resumo")

            # Limpa merges/freeze antigos em uma chamada separada antes da formatação.
            clear_sheet_layout_conflicts(spreadsheet, [ws_animes, ws_resumo])

            all_reqs = []

            reqs_sync, _ = write_sync_sheet(
                ws_animes,
                master,
                grid,
                analytics,
                last_updated,
            )
            all_reqs.extend(reqs_sync)

            reqs_stats = write_stats_sheet(
                ws_resumo,
                master,
                grid,
                analytics,
            )
            all_reqs.extend(reqs_stats)

            for i in range(0, len(all_reqs), 500):
                spreadsheet.batch_update(
                    {
                        "requests": all_reqs[i:i + 500],
                    }
                )

            last_hash = current_hash

            print(f"[{now_br('%H:%M:%S')}] Planilha atualizada! sync #{sync_count}")

        else:
            print("Sem mudanças.")

        print(f"  Próxima verificação: {next_check_br(SYNC_INTERVAL)}")
        time.sleep(SYNC_INTERVAL)


if __name__ == "__main__":
    main()

    # Para testar só o MAL, comente a linha acima e descomente:
    # test_mal()
