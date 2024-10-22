import dotenv
import aiogram
import os

dotenv.load_dotenv()

bot = aiogram.Bot(
    os.environ["TOKEN"]
)