from .start import router as start_router
# from .add_topic import router as add_topic_router
from .file_handler import router as file_router
# from .voice_handler import router as voice_router
from .general import router as general_router
from .loaddata import router as loaddata_router

from aiogram import Dispatcher

def register_all_handlers(dp: Dispatcher):
    dp.include_router(start_router)
    dp.include_router(loaddata_router)
    # dp.include_router(add_topic_router)
    dp.include_router(file_router)
    # dp.include_router(voice_router)
    dp.include_router(general_router)