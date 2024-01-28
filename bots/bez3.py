import random
from src.game_constants import *
from src.robot_controller import *
from src.player import *
from src.map import *

from scipy import ndimage
import numpy as np

ATTACK_TOWERS = [TowerType.GUNSHIP, TowerType.BOMBER]

class Mode(Enum):
    GUNSHIP = 1
    BOMBER = 2
    SOLAR_FARM = 3
    SOLAR_FARM_MAYBE = 4

class BotPlayer(Player):
    def __init__(self, map: Map):
        self.map = map
        self.tower_idx = 0

    def dilate_by(self, binary_map, radius):
        return ndimage.binary_dilation(binary_map, iterations=radius)
    
    def init_turn_one(self, rc: RobotController):
        self.num_towers = {
            TowerType.GUNSHIP: 0,
            TowerType.BOMBER: 0,
            TowerType.SOLAR_FARM: 0,
            TowerType.REINFORCER: 0,
        }
        
        # convenience
        self.pts = [ (x,y) for x in range(self.map.width) for y in range(self.map.height) ]
        self.width = self.map.width
        self.height = self.map.height

        # binary_placeable
        self.binary_placeable = np.zeros((self.width, self.height), dtype=bool)
        for x, y in self.pts:
            if rc.is_placeable(rc.get_ally_team(), x, y):
                self.binary_placeable[x, y] = True

        # binary_path
        self.binary_path = np.zeros((self.width, self.height), dtype=bool)
        for x, y in self.map.path:
            self.binary_path[x, y] = True
        self.path_len = len(self.map.path)

        # binary_hugging_path
        self.binary_hugging_path = self.binary_path[:]
        self.binary_hugging_path = self.dilate_by(self.binary_hugging_path, 1)

        # binary_good_gunship_spots
        self.binary_good_gunship_spots = self.binary_hugging_path * self.binary_placeable

        # count_nearby_paths_10
        self.count_nearby_paths_10 = np.zeros((self.width, self.height), dtype=int)
        for x, y in self.pts:
            for xp, yp in self.pts_within_range(x, y, TowerType.BOMBER.range):
                if self.binary_path[xp, yp]:
                    self.count_nearby_paths_10[x, y] += self.binary_path[xp, yp]
        # count_nearby_paths_60
        self.has_nearby_paths_60 = np.zeros((self.width, self.height), dtype=int)
        for x, y in self.pts:
            for xp, yp in self.pts_within_range(x, y, TowerType.GUNSHIP.range):
                if self.binary_path[xp, yp]:
                    self.has_nearby_paths_60[x, y] += self.binary_path[xp, yp]

        # score_good_bomber_spots
        self.score_good_bomber_spots = self.count_nearby_paths_10 * self.binary_placeable

        # binary_bottom_left_quadrant
        self.binary_bottom_left_quadrant = np.zeros((self.width, self.height), dtype=bool)
        self.binary_bottom_left_quadrant[:self.width//3, :self.height//3] = True

        # binary_good_farm_spots
        self.binary_path_dilate = self.dilate_by(self.binary_path, 2)
        self.binary_good_farm_spots = ~self.binary_path_dilate & self.binary_bottom_left_quadrant & self.binary_placeable

        self.good_farm_spots_list = sorted(self.pts, key=lambda pt: (self.binary_good_farm_spots[pt[0], pt[1]], pt[0] + pt[1]), reverse=False)

        # score_good_reinforcer_spots
        self.score_good_reinforcer_spots = np.zeros((self.width, self.height), dtype=int)

        self.max_num_farms = 0
        self.bomb_pct = .33
        self.rushing = False
        self.end_game = False
        self.solar_limit = 0

    # ----------------------------------------------------------------------
    # PHASE
    # ----------------------------------------------------------------------
    def early_game(self):
        return [
            Mode.GUNSHIP,
            Mode.GUNSHIP,
            Mode.SOLAR_FARM,
            Mode.SOLAR_FARM_MAYBE,
            Mode.BOMBER,
            Mode.SOLAR_FARM,
            Mode.GUNSHIP,
            Mode.SOLAR_FARM_MAYBE,
            Mode.SOLAR_FARM,
            Mode.BOMBER,
            Mode.SOLAR_FARM_MAYBE,
            Mode.GUNSHIP,
            Mode.GUNSHIP,
            Mode.SOLAR_FARM_MAYBE,
            Mode.GUNSHIP,
            Mode.GUNSHIP,
            Mode.GUNSHIP,
            Mode.BOMBER,
            Mode.SOLAR_FARM,
            Mode.GUNSHIP,
            Mode.GUNSHIP,
            Mode.SOLAR_FARM_MAYBE,
            Mode.SOLAR_FARM_MAYBE,
            Mode.GUNSHIP,
            Mode.SOLAR_FARM_MAYBE,
            Mode.BOMBER,
            Mode.GUNSHIP,
            Mode.SOLAR_FARM_MAYBE,
            Mode.SOLAR_FARM,
            Mode.SOLAR_FARM_MAYBE,
            Mode.SOLAR_FARM,
            Mode.SOLAR_FARM_MAYBE,
            Mode.SOLAR_FARM,
            Mode.GUNSHIP,
            Mode.SOLAR_FARM_MAYBE,
            Mode.SOLAR_FARM,
            Mode.SOLAR_FARM_MAYBE,
            Mode.BOMBER,
            Mode.SOLAR_FARM_MAYBE,
            Mode.SOLAR_FARM_MAYBE,
            Mode.GUNSHIP,
            Mode.SOLAR_FARM_MAYBE,
            Mode.SOLAR_FARM_MAYBE,
            Mode.SOLAR_FARM_MAYBE,
            Mode.SOLAR_FARM_MAYBE,
            Mode.SOLAR_FARM_MAYBE,
            Mode.BOMBER,
            Mode.GUNSHIP,
            Mode.BOMBER,
            Mode.SOLAR_FARM_MAYBE,
        ]
    
    def furthest_bloon(self, rc):
        self.debris = rc.get_debris(rc.get_ally_team())
        farthest = min([self.path_len - debris.progress for debris in self.debris] or [1000])
        return farthest
    def furthest_bloon_opps(self, rc):
        self.debris = rc.get_debris(rc.get_enemy_team())
        farthest = min([self.path_len - debris.progress for debris in self.debris] or [1000])
        return farthest
    
    def count_health_of_balloons_send_by_enemy(self, rc):
        self.debris = rc.get_debris(rc.get_ally_team())
        healths = [debris.health for debris in self.debris if debris.sent_by_opponent]
        return sum(healths or [0])
    
    def mode(self, rc):
        if self.tower_idx == 0:
            farthest = self.furthest_bloon(rc)
            if farthest >= 50:
                self.lol = "early_cheese"
                return Mode.SOLAR_FARM


        self.lol = "early_game"
        if self.tower_idx < len(self.early_game()):
            return self.early_game()[self.tower_idx]

        return Mode.SOLAR_FARM_MAYBE
        
    def random_attack_tower(self, rc: RobotController):
        rng = random.random()
        if rng < self.bomb_pct:
            return TowerType.BOMBER
        else:
            return TowerType.GUNSHIP
        
    def try_sell_farm(self, rc, lax=False):
        if rc.get_health(rc.get_ally_team()) >= 1250:
            if not lax and self.num_towers[TowerType.SOLAR_FARM] < self.max_num_farms * .7:
                return
        for tower in rc.get_towers(rc.get_ally_team()):
            if tower.type == TowerType.SOLAR_FARM:
                rc.sell_tower(tower.id)
                print(f'[{rc.get_turn()}] Sold {tower.type} at ({tower.x}, {tower.y}). Balance: {rc.get_balance(rc.get_ally_team())}')
                
                x, y = tower.x, tower.y
                self.num_towers[tower.type] -= 1
                self.binary_placeable[x, y] = True
                for xp, yp in self.pts_within_range(x, y, TowerType.REINFORCER.range):
                    if self.binary_path[xp, yp]:
                        self.score_good_reinforcer_spots[x, y] -= 1
                self.score_good_bomber_spots[x, y] *= -1
                self.binary_good_farm_spots[x, y] = True
                self.binary_good_gunship_spots[x, y] = True
                break

    def try_sell_reinforcer(self, rc):
        for tower in rc.get_towers(rc.get_ally_team()):
            if tower.type == TowerType.REINFORCER:
                rc.sell_tower(tower.id)
                print(f'[{rc.get_turn()}] Sold {tower.type} at ({tower.x}, {tower.y}). Balance: {rc.get_balance(rc.get_ally_team())}')
                
                x, y = tower.x, tower.y
                self.num_towers[tower.type] -= 1
                self.binary_placeable[x, y] = True
                self.score_good_reinforcer_spots[x, y] *= -1
                self.score_good_bomber_spots[x, y] *= -1
                self.binary_good_farm_spots[x, y] = True
                self.binary_good_gunship_spots[x, y] = True
                break

    def furthest_bloon_pct(self, rc):
        farthest = self.furthest_bloon(rc)
        return farthest / self.path_len
    def furthest_bloon_pct_opps(self, rc):
        farthest = self.furthest_bloon(rc)
        return farthest / self.path_len

    def mode_to_type(self, rc, mode):
        if self.furthest_bloon(rc) < 15 and rc.get_turn() > 1000:
            self.try_sell_farm(rc)
        
        if self.furthest_bloon(rc) < 30:
            return self.random_attack_tower(rc)
        


        if mode == Mode.GUNSHIP:
            return TowerType.GUNSHIP
        elif mode == Mode.BOMBER:
            return TowerType.BOMBER
        elif mode == Mode.SOLAR_FARM:
            return TowerType.SOLAR_FARM
        elif mode == Mode.SOLAR_FARM_MAYBE:
            self.towers_attack_random(rc)
            self.num_attacking_cnt = self.num_attacking(rc)
            attack_tower = self.num_towers[TowerType.GUNSHIP] + self.num_towers[TowerType.BOMBER]
            # if 90% of our towers are attacking, we're in attack mode
            assert(attack_tower > 0)
            if self.num_attacking_cnt / attack_tower > 0.85 and self.furthest_bloon_pct(rc) < .4:
                return self.random_attack_tower(rc)
            return TowerType.SOLAR_FARM
        else:
            print(f"ERROR: invalid mode {mode}")

    
    
    # ----------------------------------------------------------------------
    # PLAY TURN
    # ----------------------------------------------------------------------
    
    def play_tower(self, rc: RobotController, tower_type: TowerType):
        if tower_type == TowerType.GUNSHIP:
            self.try_place_gunship(rc)
        elif tower_type == TowerType.BOMBER:
            self.try_place_bomber(rc)
        elif tower_type == TowerType.SOLAR_FARM:
            lol = np.max(self.score_good_reinforcer_spots)
            if lol >= 8:
                self.try_place_reinforcer(rc)
            else:
                self.try_place_farmer(rc)
        else:
            print(f"ERROR: invalid type {tower_type}")
    
    def try_send_debris(self, rc, cd, health):
        if rc.can_send_debris(cd, health):
            rc.send_debris(cd, health)
            print(f'[{rc.get_turn()}] Sent debris with cd {cd} and health {health}. Balance {rc.get_balance(rc.get_ally_team())}')
            return True
        return False
    
    def num_defense_towers_opponent(self, rc):
        num_defense_towers = 0
        for tower in rc.get_towers(rc.get_enemy_team()):
            if tower.type in ATTACK_TOWERS:
                num_defense_towers += 1
        return num_defense_towers

    
    def play_turn(self, rc: RobotController):
        if rc.get_turn() == 1:
            self.init_turn_one(rc)
            self.try_send_debris(rc, 1, 51)


        self.max_num_farms = max(self.num_towers[TowerType.SOLAR_FARM], self.max_num_farms)
        self.towers_attack_random(rc)

        if 1500 < rc.get_turn() < 1800:
            return
        
        if rc.get_turn() == 1800:
            self.rushing = True
            self.rushing_health = 151
            self.cooldown = 8
            for i in range(self.num_towers[TowerType.SOLAR_FARM] // 2):
                self.try_sell_farm(rc, lax=True)
            return

        if self.rushing and rc.get_turn() % self.cooldown == 0:
            if self.try_send_debris(rc, self.cooldown, self.rushing_health):
                return
            self.rushing = False

        if self.rushing and rc.get_turn() % self.cooldown != 0:
            return

        if random.random() < .005 and self.num_attacking_towers_enemy(rc) < 3:
            self.try_send_debris(rc, 15, 190)

        if rc.get_turn() < 1500 and self.count_health_of_balloons_send_by_enemy(rc) > 51 * 15:
            self.rushing = True
            self.rushing_health = 51
            self.cooldown = 1
            for i in range(self.num_towers[TowerType.SOLAR_FARM]):
                self.try_sell_farm(rc, lax=True)
            self.try_place_bomber(rc)
            self.try_place_bomber(rc)
            self.try_place_bomber(rc)
            self.try_place_bomber(rc)
            self.try_place_bomber(rc)
            self.try_place_bomber(rc)
            return
        

        if rc.get_turn() == 1500 and self.num_towers[TowerType.SOLAR_FARM] >= 9:
            if rc.get_health(rc.get_enemy_team()) < 2500:
                for i in range(5):
                    self.try_sell_farm(rc, lax=True)
                self.rushing = True
                self.rushing_health = 51
                self.cooldown = 1
                return

        if rc.get_turn() == 2800 and self.num_towers[TowerType.SOLAR_FARM] > 15:
            if self.furthest_bloon_pct_opps(rc) < .4:
                for i in range(self.num_towers[TowerType.SOLAR_FARM] * .5):
                    self.try_sell_farm(rc, lax=True)
                self.rushing = True
                self.rushing_health = 151
                self.solar_limit += 5
                self.cooldown = 1
                return

        # if rc.get_turn() == 3500 or rc.get_turn() == 5500:
        #     for i in range(int(self.num_towers[TowerType.SOLAR_FARM] * .5)):
        #         self.try_sell_farm(rc, lax=True)
        #     self.rushing = True
        #     self.rushing_health = 301
        #     self.solar_limit += 5
        #     self.cooldown = 1
        #     return

        mode = self.mode(rc)
        tower_type = self.mode_to_type(rc, mode)
        if rc.get_turn() % 100 == 0:
            if rc.get_ally_team() == Team.BLUE:
                print(f'[{rc.get_turn()}] {tower_type} {rc.get_balance(rc.get_ally_team())} {self.furthest_bloon_pct(rc):.2f} {self.furthest_bloon_pct_opps(rc):.2f} {self.num_defense_towers_opponent(rc)} {self.num_towers[TowerType.SOLAR_FARM]} {self.num_towers[TowerType.GUNSHIP]} {self.num_towers[TowerType.BOMBER]}')
        self.play_tower(rc, tower_type)

        self.towers_attack_random(rc)
    
    # ----------------------------------------------------------------------
    # PLACE GUNSHIP
    #     random place hugging path that can see at least 5 path tiles
    # ----------------------------------------------------------------------
    def try_place_gunship(self, rc: RobotController):
        if rc.get_balance(rc.get_ally_team()) < TowerType.GUNSHIP.cost:
            return
        
        for _ in range(1000):
            x, y = self.random_pt()
            if self.binary_good_gunship_spots[x, y] and rc.is_placeable(rc.get_ally_team(), x, y):
                if self.num_towers[TowerType.GUNSHIP]  > 3 * (2 + self.num_towers[TowerType.BOMBER]):
                    self.try_place_bomber(rc)
                    return
                self.build_tower(rc, TowerType.GUNSHIP, x, y)
                return
        
        print("couldn't place gunship")
        for x, y in self.pts:
            if self.has_nearby_paths_60[x, y] and rc.is_placeable(rc.get_ally_team(), x, y):
                self.build_tower(rc, TowerType.GUNSHIP, x, y)
                return
                
    
    def find_xy_of_placeable(self, rc: RobotController):
        for x, y in self.pts:
            if rc.is_placeable(rc.get_ally_team(), x, y):
                return x, y
        return 0, 0

    # ----------------------------------------------------------------------
    # PLACE BOMBER
    #     find path that can see MOST path tiles
    # ----------------------------------------------------------------------
    def try_place_bomber(self, rc: RobotController):
        if rc.get_balance(rc.get_ally_team()) < TowerType.BOMBER.cost:
            return
        
        best_score = np.max(self.score_good_bomber_spots)
        for x, y in self.pts:
            if self.score_good_bomber_spots[x, y] == best_score:
                if rc.is_placeable(rc.get_ally_team(), x, y):
                    if best_score < 6:
                        self.bomb_pct = .1
                    self.build_tower(rc, TowerType.BOMBER, x, y)
                    return
                else:
                    self.score_good_bomber_spots[x, y] *= -1
            
        
        print("couldn't place bomber")

    # ----------------------------------------------------------------------
    # PLACE FARMER
    #     random spot in bottom left of screen
    # ----------------------------------------------------------------------
    def try_place_farmer(self, rc: RobotController):
        if rc.get_balance(rc.get_ally_team()) < TowerType.SOLAR_FARM.cost:
            return
        
        x, y = self.good_farm_spots_list[-1]
        if rc.is_placeable(rc.get_ally_team(), x, y):

            tower_type = TowerType.SOLAR_FARM

            # if there are 1.5 as many farms as attack type towers, build a gunslinger
            if self.num_towers[TowerType.SOLAR_FARM] > 10 and self.num_towers[TowerType.SOLAR_FARM] > 1.5 * (self.num_towers[TowerType.GUNSHIP] + self.num_towers[TowerType.BOMBER]):
                tower_type = self.random_attack_tower(rc)
                self.play_tower(rc, tower_type)
                return
            if self.num_towers[TowerType.SOLAR_FARM] > 25 + self.solar_limit:
                tower_type = self.random_attack_tower(rc)
                self.play_tower(rc, tower_type)
                return

            self.build_tower(rc, tower_type, x, y)
            self.good_farm_spots_list.pop(-1)
            return
        else:
            self.good_farm_spots_list.pop(-1)

        
        print("couldn't place farmer")
        self.good_farm_spots_list.insert(0, self.find_xy_of_placeable(rc))

    # ----------------------------------------------------------------------
    # PLACE REINFORCER
    #     spot in range to most farmers
    # ----------------------------------------------------------------------
    def try_place_reinforcer(self, rc: RobotController):
        if rc.get_balance(rc.get_ally_team()) < TowerType.REINFORCER.cost:
            return
        
        best_score = np.max(self.score_good_reinforcer_spots)
        for x, y in self.pts:
            if self.score_good_reinforcer_spots[x, y] == best_score and rc.is_placeable(rc.get_ally_team(), x, y):
                self.build_tower(rc, TowerType.REINFORCER, x, y)
                return
        
        print("couldn't place reinforcer")
    

    # ----------------------------------------------------------------------
    # Utils
    # ----------------------------------------------------------------------
    
    # def update(self, rc):
    #     self.binary_placeable = np.zeros((self.width, self.height), dtype=bool)
    #     for x, y in self.pts:
    #         if rc.is_placeable(rc.get_ally_team(), x, y):
    #             self.binary_placeable[x, y] = True
    #     self.score_good_reinforcer_spots[~self.binary_placeable] = -1
    #     self.score_good_bomber_spots[~self.binary_placeable] = -1
    #     self.binary_good_farm_spots[~self.binary_placeable] = False
    #     self.binary_good_gunship_spots[~self.binary_placeable] = False

    def pts_within_range(self, x, y, r):
        pts = []
        for dx in range(-r, r+1):
            for dy in range(-r, r+1):
                xp = x + dx
                yp = y + dy
                if self.map.is_in_bounds(xp, yp):
                    if dx ** 2 + dy ** 2 <= r:
                        pts.append((xp, yp))
        return pts

    def random_pt(self):
        return random.choice(self.pts)
    
    def build_tower(self, rc: RobotController, tower_type: TowerType, x, y):
        assert(rc.can_build_tower(tower_type, x, y))

        # if rc.get_turn() == 750:
        #     while rc.can_send_debris(2, 76):
        #         self.try_send_debris(rc, 2, 76)
        #     return

        rc.build_tower(tower_type, x, y)
        print(f'[{rc.get_turn()}] Building {tower_type} at ({x}, {y}). Balance: {rc.get_balance(rc.get_ally_team())}')
        self.num_towers[tower_type] += 1
        if tower_type == TowerType.SOLAR_FARM:
            for xp, yp in self.pts_within_range(x, y, TowerType.REINFORCER.range):
                if self.binary_placeable[xp, yp]:
                    self.score_good_reinforcer_spots[xp, yp] += 1
        if tower_type == TowerType.GUNSHIP or tower_type == TowerType.BOMBER:
            for xp, yp in self.pts_within_range(x, y, TowerType.REINFORCER.range):
                if self.binary_placeable[xp, yp]:
                    self.score_good_reinforcer_spots[xp, yp] += .8
        self.binary_placeable[x, y] = False
        self.score_good_reinforcer_spots[x, y] *= -1
        self.score_good_bomber_spots[x, y] *= -1
        self.binary_good_farm_spots[x, y] = False
        self.binary_good_gunship_spots[x, y] = False
        if self.lol != "early_cheese":
            self.tower_idx += 1

    # ----------------------------------------------------------------------
    # ATTACKING AI
    # ----------------------------------------------------------------------
        
    def towers_attack_random(self, rc: RobotController):
        self.debris = {debris.id: debris for debris in rc.get_debris(rc.get_ally_team())}
        self.my_towers = {tower.id:tower for tower in rc.get_towers(rc.get_ally_team())}
        for tower in self.my_towers.values():
            if tower.type == TowerType.GUNSHIP:
                rc.auto_snipe(tower.id, SnipePriority.FIRST)
            elif tower.type == TowerType.BOMBER:
                if rc.can_bomb(tower.id):
                    rc.bomb(tower.id)
    
    def num_attacking(self, rc: RobotController):
        num_attacking = 0
        for tower in rc.get_towers(rc.get_ally_team()):
            if tower.type == TowerType.GUNSHIP:
                if tower.current_cooldown < tower.type.cooldown:
                    num_attacking += 1
        return num_attacking
    
    def num_attacking_towers_enemy(self, rc):
        num_attacking = 0
        for tower in rc.get_towers(rc.get_enemy_team()):
            if tower.type in ATTACK_TOWERS:
                if tower.current_cooldown < tower.type.cooldown:
                    num_attacking += 1
        return num_attacking
    
    