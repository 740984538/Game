"""
深渊回响：无尽轮回
游戏入口文件
"""
import sys
import pygame
from src.core.game import Game
from src.utils.logger import setup_logger


def main():
    setup_logger()
    pygame.init()
    game = Game()
    game.run()
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
