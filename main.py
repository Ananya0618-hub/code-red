# Entry point used by the browser version (pygbag needs a file called main.py).
# On your computer you can run either `python main.py` or `python game.py`.
import asyncio
from game import Game

asyncio.run(Game().run())
