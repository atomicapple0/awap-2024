from src.player import Player
from src.map import Map
from src.robot_controller import RobotController
from src.game_constants import TowerType, Team, SnipePriority, GameConstants
from src.debris import Debris
from src.tower import Tower
from typing import List

class BotPlayer(Player):
    def __init__(self, map: Map):
        self.map = map
        self.time_bank = GameConstants.INITIAL_TIME_POOL
        self.passive_income = GameConstants.PASSIVE_INCOME
        self.turn_counter = 0

    def play_turn(self, rc: RobotController):
        map_width = self.map.width
        map_height = self.map.height
        ally_team = rc.get_ally_team()
        enemy_team = rc.get_enemy_team()

        self.place_towers(rc, ally_team, map_width, map_height)
        self.attack_with_towers(rc, ally_team, enemy_team)
        self.manage_resources(rc, ally_team)
        self.send_debris(rc)

    def place_towers(self, rc: RobotController, ally_team: Team, map_width: int, map_height: int):
        for x in range(0, map_width, 5):
            for y in range(0, map_height, 5):
                if rc.can_build_tower(TowerType.SOLAR_FARM, x, y):
                    rc.build_tower(TowerType.SOLAR_FARM, x, y)

        for x in range(0, map_width, 8):
            for y in range(0, map_height, 8):
                if rc.can_build_tower(TowerType.GUNSHIP, x, y):
                    rc.build_tower(TowerType.GUNSHIP, x, y)
        
        for x in range(0, map_width, 6):
            for y in range(0, map_height, 6):
                if rc.can_build_tower(TowerType.REINFORCER, x, y):
                    rc.build_tower(TowerType.REINFORCER, x, y)

        for x in range(0, map_width, 3):
                for y in range(0, map_height, 3):
                    if rc.can_build_tower(TowerType.BOMBER, x, y):
                        rc.build_tower(TowerType.BOMBER, x, y)

    def attack_with_towers(self, rc: RobotController, ally_team: Team, enemy_team: Team):
        priority = SnipePriority.FIRST
        ally_towers = rc.get_towers(ally_team)
        enemy_debris = rc.get_debris(enemy_team)

        for tower in ally_towers:
            if tower.type == TowerType.GUNSHIP:
                rc.auto_snipe(tower.id, priority)
            elif tower.type == TowerType.BOMBER:
                rc.auto_bomb(tower.id)

    def manage_resources(self, rc: RobotController, ally_team: Team):
        self.time_bank += GameConstants.ADDITIONAL_TIME_PER_TURN

        health = GameConstants.STARTING_HEALTH
        cooldown = 5
        debris_cost = rc.get_debris_cost(cooldown, health)
        # print(f"Debris Cost: {debris_cost}")

        if self.time_bank < 0.0:
            raise Exception("Time limit exceeded")

    def send_debris(self, rc: RobotController):
        cooldown, min_health, max_health = 5, 50, 200
        health = min(min_health + self.turn_counter * 10, max_health)

        debris_cost = rc.get_debris_cost(cooldown, health)

        if rc.can_send_debris(cooldown, health):
            rc.send_debris(cooldown, health)

        self.turn_counter += 1
