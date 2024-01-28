import random
from src.game_constants import SnipePriority, TowerType
from src.robot_controller import RobotController
from src.player import Player
from src.map import Map

class BotPlayer(Player):
    def __init__(self, map: Map):
        self.map = map

    def play_turn(self, rc: RobotController):
        while rc.can_send_debris(1,26):
            rc.send_debris(1,26)
