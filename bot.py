import os
import sys
import subprocess
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from playwright.async_api import async_playwright

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Токен бота из окружения Bothost
TOKEN = os.getenv("9176690291:AAHVV0RjsNzvA1ePYot63S6C5KNaUJZJYoY")

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Глобальные переменные для переиспользования браузера
playwright_instance = None
browser = None

class CdekStates(StatesGroup):
    waiting_for_product = State()
    waiting_for_weight = State()
    waiting_for_price = State()
    waiting_for_order_id = State()

# Авто-установка бинарников и запуск браузера при старте
async def on_startup(bot: Bot):
    global playwright_instance, browser
    logging.info("Проверка и установка браузеров Playwright...")
    
    try:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
        subprocess.run([sys.executable, "-m", "playwright", "install-deps"], check=False)
    except Exception as e:
        logging.error(f"Ошибка авто-установки Playwright: {e}")

    logging.info("Запуск фонового экземпляра Playwright...")
    playwright_instance = await async_playwright().start()
    browser = await playwright_instance.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
    )
    logging.info("Playwright успешно запущен и готов к работе!")

dp.startup.register(on_startup)

# Команда /start
@dp.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Опиши **название товара**:")
    await state.set_state(CdekStates.waiting_for_product)

# Шаг 1: Название товара
@dp.message(CdekStates.waiting_for_product)
async def process_product(message: Message, state: FSMContext):
    await state.update_data(product=message.text)
    await message.answer("Введи **вес товара** (например, 0.5 кг):")
    await state.set_state(CdekStates.waiting_for_weight)

# Шаг 2: Вес
@dp.message(CdekStates.waiting_for_weight)
async def process_weight(message: Message, state: FSMContext):
    await state.update_data(weight=message.text)
    await message.answer("Введи **стоимость / объявленную цену** (только цифру, например 12500):")
    await state.set_state(CdekStates.waiting_for_price)

# Шаг 3: Цена
@dp.message(CdekStates.waiting_for_price)
async def process_price(message: Message, state: FSMContext):
    await state.update_data(price=message.text)
    await message.answer("Введи **номер заказа** (должен начинаться с **285** и содержать ровно **13 цифр**):")
    await state.set_state(CdekStates.waiting_for_order_id)

# Шаг 4: Финал — генерация PDF без лагов
@dp.message(CdekStates.waiting_for_order_id)
async def process_order_id(message: Message, state: FSMContext):
    await state.update_data(order_id=message.text)
    data = await state.get_data()
    
    await message.answer("⏳ Генерирую накладную...")

    pdf_path = "cdek.pdf"
    html_path = os.path.abspath("cdek.html")

    try:
        # Используем быструю вкладку вместо запуска нового браузера
        page = await browser.new_page()
        await page.goto(f"file://{html_path}", wait_until="networkidle")

        # Генерация PDF
        await page.pdf(path=pdf_path, format="A4", print_background=True)
        await page.close()

        # Отправляем файл пользователю
        from aiogram.types import FSInputFile
        document = FSInputFile(pdf_path)
        await message.answer_document(document, caption="Вот твоя накладная CDEK! 📦")

    except Exception as e:
        logging.error(f"Ошибка при генерации PDF: {e}")
        await message.answer("Произошла ошибка при генерации накладной. Попробуй еще раз.")

    await state.clear()

if __name__ == "__main__":
    import asyncio
    asyncio.run(dp.start_polling(bot))
