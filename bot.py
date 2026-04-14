import discord
from discord.ext import commands, tasks
import requests
from bs4 import BeautifulSoup
import os
import json
from dotenv import load_dotenv
from urllib.parse import urljoin
from io import BytesIO
from flask import Flask
import threading

app = Flask(__name__)

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

URL = "https://www.moto-ocasion.com/motos-de-ocasion/"
FILE = "vistos.json"

activo = False


def cargar_vistos():
    try:
        with open(FILE, "r") as f:
            return set(json.load(f))
    except:
        return set()


def guardar_vistos(vistos):
    with open(FILE, "w") as f:
        json.dump(list(vistos), f)


vistos = cargar_vistos()


def obtener_anuncios():
    url = "https://www.moto-ocasion.com/motos-de-ocasion/"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36"}
    r = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(r.text, "html.parser")

    anuncios = []

    for card in soup.select(".moto-card[data-href]"):

        url_anuncio = card.get("data-href")

        # 🚨 FILTRO: evitar basura
        if not url_anuncio or "/motos-de-ocasion/" not in url_anuncio:
            continue

        # evitar página genérica
        if url_anuncio.rstrip("/") == "https://www.moto-ocasion.com/motos-de-ocasion":
            continue

        modelo = card.select_one("h4.moto-title")
        modelo = modelo.get_text(strip=True) if modelo else None

        km = card.select_one("p.badge-kilometros")
        km = km.get_text(strip=True) if km else None

        carnet = card.select_one("p.badge-carnet")
        carnet = carnet.get_text(strip=True) if carnet else None

        anyo = card.select_one("p.badge-ano")
        anyo = anyo.get_text(strip=True) if anyo else None

        precio = card.select_one("p.moto-price")
        precio = precio.get_text(strip=True) if precio else None

        img_tag = card.select_one(".moto-image-wrapper img")
        imagen = None
        if img_tag and img_tag.get("src"):
            imagen = urljoin(url, img_tag["src"])

        anuncios.append({
            "modelo": modelo,
            "km": km,
            "carnet": carnet,
            "precio": precio,
            "anyo": anyo,
            "imagen": imagen,
            "urlAnuncio": url_anuncio
        })

    return anuncios


@tasks.loop(minutes=5)
async def comprobar():
    global vistos

    if not activo:
        return

    canal = bot.get_channel(CHANNEL_ID)
    anuncios = obtener_anuncios()

    for a in anuncios:
        link = a["urlAnuncio"]

        # 🔥 FILTRO ANTI-BASURA (PASO 3)
        if not link or "/motos-de-ocasion/" not in link:
            continue

        if link not in vistos:
            vistos.add(link)
            guardar_vistos(vistos)

            embed = discord.Embed(
                title=a["modelo"],
                url=link,
                color=0xFF4500
            )

            embed.description = (
                f"💰 Precio: {a['precio']}\n"
                f"📅 Año: {a['anyo']}\n"
                f"🏍️ KM: {a['km']}\n"
                f"🪪 Carnet: {a['carnet']}"
            )
            print("IMAGEN:", a["imagen"])
            file = None

            if a["imagen"]:
                try:
                    img_data = requests.get(a["imagen"], timeout=10).content
                    file = discord.File(BytesIO(img_data), filename="moto.jpg")
                    embed.set_image(url="attachment://moto.jpg")

                except Exception as e:
                    print("Error imagen:", e)

            await canal.send(embed=embed, file=file)


@bot.command()
async def start(ctx):
    global activo
    activo = True
    await ctx.send("🟢 ACTIVADO")


@bot.command()
async def stop(ctx):
    global activo
    activo = False
    await ctx.send("🔴 PARADO")


@bot.command()
async def status(ctx):
    await ctx.send(f"Estado: {'ACTIVO' if activo else 'PARADO'}")


bot.run(TOKEN)


@app.route("/")
def home():
    return "Bot activo"

def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
    
    
@bot.event
async def on_ready():
    print(f"Bot listo: {bot.user}")
    threading.Thread(target=run_web).start()  # 👈 IMPORTANTE
    comprobar.start()
