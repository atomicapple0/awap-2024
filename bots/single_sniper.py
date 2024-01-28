import random
from src.game_constants import SnipePriority, TowerType
from src.robot_controller import RobotController
from src.player import Player
from src.map import Map

class BotPlayer(Player):
    def __init__(self, map: Map):
        self.map = map

    def play_turn(self, rc: RobotController):
        rc.build_tower(TowerType.BOMBER, self.map.width // 2,  self.map.height // 2)
        rc.build_tower(TowerType.GUNSHIP, self.map.width // 2 + 1,  self.map.height // 2 + 1)
