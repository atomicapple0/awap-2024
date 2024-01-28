import random
from src.game_constants import SnipePriority, TowerType
from src.robot_controller import RobotController
from src.player import Player
from src.map import Map

class BotPlayer(Player):
    def __init__(self, map: Map):
        self.map = map

    def towers_attack(self, rc: RobotController):
        towers = rc.get_towers(rc.get_ally_team())
        for tower in towers:
            if tower.type == TowerType.GUNSHIP:
                rc.auto_snipe(tower.id, SnipePriority.FIRST)
            elif tower.type == TowerType.BOMBER:
                rc.auto_bomb(tower.id)

    def play_turn(self, rc: RobotController):
        if rc.can_build_tower(TowerType.BOMBER, 8, 10):
            rc.build_tower(TowerType.BOMBER, 8, 10)
        self.towers_attack(rc)
