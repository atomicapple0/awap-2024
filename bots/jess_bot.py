import random
from src.game_constants import SnipePriority, TowerType
from src.robot_controller import RobotController
from src.player import Player
from src.map import Map
from enum import Enum


class PlayPhase(Enum):
    # Initially build enough gunships to keep alive
    INIT = 0

    # Build farm each turn
    FARMING = 1

    # Interleave gunships with bombers, with more gunships than bombers
    BOMBERS = 2

    # Build reinforcer each turn
    REINFORCE = 3

    # Send debris each turn
    SEND_DEBRIS = 4


# Rough transitions:
# INIT -> BOMBERS <-> FARMING

# transition to REINFORCE maybe?
# usually, we win/lose before we get to FARMING or REINFORCE phase


class BotPlayer(Player):
    def __init__(self, map: Map):
        self.map = map

        # Current gameplay phase
        self.offense_mode = False
        self.debris_before_switch = 10
        self.debris_in_current_mode = 0

        # Phases within defense mode
        self.cur_phase = PlayPhase.INIT
        self.towers_built_in_phase = 0

        # Stuff for maps
        self.path_tiles = set(self.map.path)
        self.distFromNearestPath = {}

        # Used for deciding whether to build "support" towers (i.e. SOLAR_FARM, REINFORCER)
        #                                 or "attacking" towers (i.e. GUNSHIP, BOMBER).
        # Any tile with distance from path >= DISTANCE_THRESHOLD ===> build support tower
        #               distance from path <  DISTANCE_THRESHOLD ===> build attacking tower
        self.DISTANCE_THRESHOLD = 2

        # Sparsity factors
        # At most GUNSHIP_SPARSITY_FACTOR towers in the radius of a gunship
        self.GUNSHIP_SPARSITY_RADIUS = 60
        self.GUNSHIP_SPARSITY_FACTOR = 5

        # In the BOMBER phase, this is the rate at which to put a gunship per bomber.
        # This number is >= 1
        self.GUNSHIPS_PER_BOMBER = 1

        # In the REINFORCER phase,
        # Minimum amount of towers that must be within reinforcer radius
        # in order for it to be built at that position
        self.REINFORCER_MIN_THRESHOLD = 3

        # Count of number of towers built
        self.numTowers = {
            TowerType.GUNSHIP: 0,
            TowerType.BOMBER: 0,
            TowerType.SOLAR_FARM: 0,
            TowerType.REINFORCER: 0,
        }

        # Maximum number of each tower type that can be built
        # TODO: adjust based on size of map
        self.MAX_TOWERS = {
            TowerType.GUNSHIP: 100000,
            TowerType.BOMBER: 100000,
            TowerType.SOLAR_FARM: 20,
            TowerType.REINFORCER: 20,
        }

        # Prices of each tower (couldn't find place in API for it)
        self.towerCost = {
            TowerType.GUNSHIP: 1000,
            TowerType.BOMBER: 1750,
            TowerType.SOLAR_FARM: 2000,
            TowerType.REINFORCER: 3000,
        }

    def get_dist_to_nearest_path(self, x, y):
        if (x, y) in self.distFromNearestPath:
            return self.distFromNearestPath[(x, y)]
        minDist = 1000000000000000
        for tileX, tileY in self.map.path:
            dist = (tileX - x) * (tileX - x) + (tileY - y) * (tileY - y)
            minDist = min(minDist, dist)
        self.distFromNearestPath[(x, y)] = minDist
        return minDist

    # PLAYYYYYYYYY ----------------------------------
    def play_turn(self, rc: RobotController):
        if self.offense_mode:
            self.spawn_debris(rc)
        else:
            self.build_towers(rc)
        self.towers_attack(rc)

        if not self.offense_mode:
            if self.cur_phase != PlayPhase.INIT and self.towers_built_in_phase >= 5:
                print("Switching to debris-sending mode")
                self.offense_mode = not self.offense_mode
                self.towers_built_in_phase = 0
        else:
            if self.debris_in_current_mode >= self.debris_before_switch:
                print("Switching to tower-building mode")
                self.offense_mode = not self.offense_mode
                self.debris_in_current_mode = 0

    # DEFENSE (towers)-------------------------------
    # Tower-building functions
    def build_towers(self, rc: RobotController):
        self.build_towers_by_phase(rc)
        self.transition_to_next_phase()

    def build_towers_by_phase(self, rc: RobotController):
        if self.cur_phase == PlayPhase.INIT:
            self.build_tower(rc, TowerType.GUNSHIP)
        elif self.cur_phase == PlayPhase.FARMING:
            self.build_tower(rc, TowerType.SOLAR_FARM)
        elif self.cur_phase == PlayPhase.BOMBERS:
            if (
                self.numTowers[TowerType.BOMBER] == 0
                or self.numTowers[TowerType.GUNSHIP] // self.numTowers[TowerType.BOMBER]
                < self.GUNSHIPS_PER_BOMBER
            ):
                self.build_tower(rc, TowerType.BOMBER)
            else:
                self.build_tower(rc, TowerType.GUNSHIP)
        elif self.cur_phase == PlayPhase.REINFORCE:
            self.build_tower(rc, TowerType.REINFORCER)

    def transition_to_next_phase(self):
        if self.cur_phase == PlayPhase.INIT:
            # transition to farming phase when we have enough gunships
            if self.towers_built_in_phase >= 10:
                print("[Tower Building Mode] Transition from INIT to BOMBERS phase")
                self.cur_phase = PlayPhase.BOMBERS
                # self.towers_built_in_phase = 0
        elif self.cur_phase == PlayPhase.FARMING:
            # transition to bomber phase when we have enough farms
            if self.towers_built_in_phase >= 1:
                print("[Tower Building Mode] Transition from FARMING to BOMBERS phase")
                self.cur_phase = PlayPhase.BOMBERS
                # self.towers_built_in_phase = 0
        elif self.cur_phase == PlayPhase.BOMBERS:
            # transition to farming phase when we have enough towers
            if self.towers_built_in_phase >= 5:
                print("[Tower Building Mode] Transition from BOMBERS to FARMING phase")
                self.cur_phase = PlayPhase.FARMING
                # self.towers_built_in_phase = 0
        elif self.cur_phase == PlayPhase.REINFORCE:
            if self.towers_built_in_phase >= 1:
                print(
                    "[Tower Building Mode] Transition from REINFORCE to BOMBERS phase"
                )
                self.cur_phase = PlayPhase.BOMBERS
                # self.towers_built_in_phase = 0

    def is_position_good(self, rc: RobotController, x, y, tower_type):
        if not rc.is_placeable(rc.get_ally_team(), x, y):
            return False

        # If building GUNSHIP, make sure it's not too crowded
        # if tower_type == TowerType.GUNSHIP:
        #    if (
        #        len(
        #            rc.sense_towers_within_radius_squared(
        #                rc.get_ally_team(), x, y, self.GUNSHIP_SPARSITY_RADIUS
        #            )
        #        )
        #        >= self.GUNSHIP_SPARSITY_FACTOR
        #    ):
        #        return False

        # If building REINFORCER, make sure it's in range of sufficient towers
        #   that it will reinforce
        if tower_type == TowerType.REINFORCER:
            if (
                len(rc.sense_towers_within_radius_squared(rc.get_ally_team(), x, y, 5))
                < self.REINFORCER_MIN_THRESHOLD
            ):
                return False

        # We want support towers to be far from the path, and
        #         attacking towers to be near the path.
        if tower_type == TowerType.SOLAR_FARM or tower_type == TowerType.REINFORCER:
            return self.get_dist_to_nearest_path(x, y) >= self.DISTANCE_THRESHOLD
        else:
            return self.get_dist_to_nearest_path(x, y) < self.DISTANCE_THRESHOLD

    def build_tower(self, rc: RobotController, tower_type: TowerType):
        # Make sure does not exceed cap on the tower type
        if self.numTowers[tower_type] >= self.MAX_TOWERS[tower_type]:
            return

        # Make sure have enough balance
        if rc.get_balance(rc.get_ally_team()) < self.towerCost[tower_type]:
            # print(
            #    f"{rc.get_balance(rc.get_ally_team())} not enough balance for {tower_type}"
            # )
            return

        # Probe for viable position to build tower
        x = random.randint(0, self.map.height - 1)
        y = random.randint(0, self.map.height - 1)
        tries = 0
        while not self.is_position_good(rc, x, y, tower_type):
            x = random.randint(0, self.map.height - 1)
            y = random.randint(0, self.map.height - 1)
            tries += 1

        # Build tower
        if rc.can_build_tower(tower_type, x, y):
            rc.build_tower(tower_type, x, y)
            print(f"Built {tower_type} at ({x},{y})")
            self.numTowers[tower_type] += 1
            self.towers_built_in_phase += 1

    # Tower-attacking functions
    def towers_attack(self, rc: RobotController):
        towers = rc.get_towers(rc.get_ally_team())
        for tower in towers:
            if tower.type == TowerType.GUNSHIP:
                rc.auto_snipe(tower.id, SnipePriority.FIRST)
            elif tower.type == TowerType.BOMBER:
                rc.auto_bomb(tower.id)

    # OFFENSE (sending debris)--------------------------
    def spawn_debris(self, rc: RobotController):
        try:
            rc.send_debris(1, 24)
            self.debris_in_current_mode += 1
        except:
            pass
