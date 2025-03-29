from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from utils.db import add_user
from aiogram.fsm.context import FSMContext
from aiogram import F

router = Router()

@router.message(Command("start"))
async def start_handler(message: Message, state: FSMContext):
    # Check existing registration
    if not await get_user(message.from_user.id):
        await message.answer("Добро пожаловать! Введите ваше имя и номер телефона:")
        await state.set_state("registration")
    else:
        text, markup = create_main_menu()
        await message.answer(text, reply_markup=markup)

@router.message(F.text, StateFilter("registration"))
async def process_registration(message: Message, state: FSMContext):
    # Validate phone number pattern
    if not re.match(r'^\+7\d{10}$', message.text):
        await message.answer("Неверный формат номера. Введите в формате +79991234567")
        return
    
    name, phone = message.text.split()
    await add_user(message.from_user.id, name, phone)
    await state.clear()
    await message.answer("Регистрация завершена! Введите кодовое слово для активации курса:")