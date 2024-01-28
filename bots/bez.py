import random
from src.game_constants import *
from src.robot_controller import *
from src.player import *
from src.map import *


from collections import defaultdict
import random

# monkey pp
# dps of all towers * num points reachable
# aka how much damage we can inflict on a balloon with speed 1 from start to end
# divided by path len
# ==> how much damage we can inflict per turn

# bloons pp
# how much damage this balloon must take each turn for it to die before the end

ATTACK_TOWERS = [TowerType.GUNSHIP, TowerType.BOMBER]

ATTACK_TOWER_ORDER = [
    TowerType.GUNSHIP, 
    TowerType.GUNSHIP, 
    TowerType.GUNSHIP, 
    -1, 
    -1, 
    -1, 
    TowerType.GUNSHIP, 
    -1, 
    -1, 
    -1, 
    -1, 
    -1, 
    -1, 
    -1, 
    -1, 
    -1, 
    -1, 
    -1,
]

class BotPlayer(Player):
    def __init__(self, map: Map):
        self.map = map
        
        self.path_pts = self.map.path
        self.path_len = len(self.path_pts)

        self.path_pts_to_idx = { pt: i for i, pt in enumerate(self.path_pts) }

        self.pp = 0
        self.num_farms = 0
        self.map_heat = [[0 for _ in range(self.map.height)] for _ in range(self.map.width)]

    def init_at_1(self, rc: RobotController):
        self.me = rc.get_ally_team()
        self.counter = 0
        self.update_attack_tower()

        # precompute all point within 'near' of path
        near = 5
        self.pts_within_5_of_any_path = set()
        for x, y in self.path_pts:
            for dx in range(-near, near+1):
                for dy in range(-near, near+1):
                    if self.map.is_in_bounds(x+dx, y+dy):
                        if dx**2 + dy**2 <= near**2:
                            self.pts_within_5_of_any_path.add((x+dx, y+dy))
        self.pts_within_5_of_any_path = list(self.pts_within_5_of_any_path)
        # precompute all point within 'near' of path
        near = 1
        self.pts_within_1_of_any_path = set()
        for x, y in self.path_pts:
            for dx in range(-near, near+1):
                for dy in range(-near, near+1):
                    if self.map.is_in_bounds(x+dx, y+dy):
                        if dx**2 + dy**2 <= near**2:
                            self.pts_within_1_of_any_path.add((x+dx, y+dy))
        self.pts_within_1_of_any_path = list(self.pts_within_1_of_any_path)
                            
        
        # precompute all points in path within dist of path
        self.path_coords_within_gunship = defaultdict(list)
        for x in range(self.map.width):
            for y in range(self.map.height):
                if self.map.is_in_bounds(x, y):
                    for (px, py) in self.path_pts:
                        if (x-px)**2 + (y-py)**2 <= TowerType.GUNSHIP.range:
                            self.path_coords_within_gunship[(x,y)].append((px, py))

        # precompute all points in path within dist of path
        self.path_coords_within_bomber = defaultdict(list)
        for x in range(self.map.width):
            for y in range(self.map.height):
                if self.map.is_in_bounds(x, y):
                    for (px, py) in self.path_pts:
                        if (x-px)**2 + (y-py)**2 <= TowerType.BOMBER.range:
                            self.path_coords_within_bomber[(x,y)].append((px, py))

    def init_each(self, rc: RobotController):
        self.debris = rc.get_debris(self.me)
        self.debris_hp = {debris.id: debris.health for debris in self.debris}
        self.my_towers = {tower.id:tower for tower in rc.get_towers(self.me) }
        
    def my_auto_snipe(self, rc: RobotController, tower_id: int, priority: SnipePriority):
        
        tower = self.my_towers[tower_id]
        if tower.type != TowerType.GUNSHIP:
            raise GameException("Auto sniping only works on Gunships")

        # Get list of snipeable debris
        debris = []
        for deb in rc.get_debris(self.me):
            if rc.can_snipe(tower_id, deb.id) and self.debris_hp[deb.id] > 0:
                debris.append(deb)
        
        if len(debris) == 0:
            return
        
        if priority == SnipePriority.FIRST:
            get_priority = lambda debris: debris.progress
        elif priority == SnipePriority.LAST:
            get_priority = lambda debris: -debris.progress
        elif priority == SnipePriority.CLOSE:
            get_priority = lambda debris: -(debris.x - tower.x)**2 - (debris.y - tower.y)**2
        elif priority == SnipePriority.WEAK:
            get_priority = lambda debris: -debris.total_health
        elif priority == SnipePriority.STRONG:
            get_priority = lambda debris: debris.total_health
        else:
            raise GameException("Invalid priority passed to auto_snipe")
        highest_priority = max(debris, key=get_priority)


        self.debris_hp[highest_priority.id] -= TowerType.GUNSHIP.damage
        rc.snipe(tower_id, highest_priority.id)

    def my_auto_bomb(self, rc: RobotController, tower_id: int):
        # print(tower_id, len(self.my_towers))
        # tower = self.my_towers[tower_id]

        if not rc.can_bomb(tower_id):
            return
        
        nearby_debris = rc.sense_debris_in_range_of_tower(self.me, tower_id)
        nearby_debris_that_is_alive = [debris for debris in nearby_debris if self.debris_hp[debris.id] > 0]
        if len(nearby_debris_that_is_alive) == 0:
            return
        
        for debris in nearby_debris_that_is_alive:
            self.debris_hp[debris.id] -= TowerType.BOMBER.damage
        
        rc.bomb(tower_id)

    def in_range_of_tower(self, x: int, y: int, xp: int, yp: int, tower_type: TowerType) -> bool:
        rg = tower_type.range
        dist = (x-xp)**2 + (y-yp)**2
        return dist <= rg

    def is_placeable(rc: RobotController, team: Team, x: int, y: int) -> bool:
        if not rc.map.is_space(x, y):
            return False
        for tower in rc.towers[team].values():
            if (tower.x, tower.y) == (x, y):
                return False
        return True


    def place_best_gun(self, rc: RobotController):
        if (rc.get_balance(self.me) < TowerType.GUNSHIP.cost):
            return
        pp = TowerType.GUNSHIP.damage / TowerType.GUNSHIP.cooldown
        random.shuffle(self.pts_within_1_of_any_path)
        for (x, y) in self.pts_within_1_of_any_path:
            if rc.can_build_tower(TowerType.GUNSHIP, x, y):
                self.build(rc, TowerType.GUNSHIP, x, y)
                self.pp += pp
                
    def get_best_bomb(self, rc: RobotController):
        best_x = 0
        best_y = 0
        best_paths = 0
        for (x, y) in self.pts_within_5_of_any_path:
            if rc.is_placeable(self.me, x, y):
                paths = len(self.path_coords_within_bomber[(x,y)])
                if paths > best_paths:
                    best_paths = paths
                    best_x = x
                    best_y = y
        return best_x, best_y, best_paths

    def place_best_bomb(self, rc: RobotController, best_x, best_y, best_paths):
        if rc.get_balance(self.me) < TowerType.BOMBER.cost:
            return
        pp = best_paths * TowerType.BOMBER.damage / TowerType.BOMBER.cooldown
        if rc.can_build_tower(TowerType.BOMBER, best_x, best_y):
            self.build(rc, TowerType.BOMBER, best_x, best_y)
            self.pp += pp

    def build(self, rc: RobotController, tower_type: TowerType, x: int, y: int):
        rc.build_tower(tower_type, x, y)
        print(f'built {tower_type} at {x} {y}')
        if tower_type in ATTACK_TOWERS:
            self.update_attack_tower()

        
    def place_best_farm(self, rc: RobotController):
        if rc.get_balance(self.me) < TowerType.SOLAR_FARM.cost:
            return
        # find space with most farms nearby
        best_count = 0
        best_x = 0
        best_y = 0
        for x in range(self.map.width):
            for y in range(self.map.height):
                if rc.is_placeable(self.me, x, y):
                    count = self.heat[x][y]
                    if count > best_count:
                        best_count = count
                        best_x = x
                        best_y = y
        if rc.can_build_tower(TowerType.SOLAR_FARM, best_x, best_y):
            self.build(rc, TowerType.SOLAR_FARM, best_x, best_y)
            
            for dx in range(-5, 6):
                for dy in range(-5, 6):
                    if rc.map.is_in_bounds(best_x+dx, best_y+dy):
                        self.heat[best_x+dx][best_y+dy] += 1

    
    def update_attack_tower(self):
        self.counter += 1
        self.next_attack_tower_type = ATTACK_TOWER_ORDER[self.counter % len(ATTACK_TOWER_ORDER)]
        print(f'next attack tower type: {self.next_attack_tower_type}')

    
    def state(self, rc: RobotController):
        debris = rc.get_debris(rc.get_ally_team())
        if not debris:
            return "safe"
        most_health = max(debris, key=lambda deb: deb.total_health)
        farthest = max(debris, key=lambda deb: deb.progress)
        farthest = farthest.progress / self.path_len

        if most_health.total_health / (self.path_len - most_health.progress) >= self.pp:
            return "danger"
        
        if farthest >= 0.8:
            return "danger"
        
        return "safe"


    def phase(self, rc: RobotController):
        if self.num_towers < 3:
            return "phase 1"
        return "phase 2"


    def play_turn(self, rc: RobotController):
        if rc.get_turn() == 1:
            self.init_at_1(rc)
            print('init at one')
        self.init_each(rc)
        
        state = self.state(rc)

        phase = self.phase(rc)
        
        if rc.get_turn() % 10 == 0:
            print(f'{rc.get_turn()}: {phase} {state} {self.pp} {self.next_attack_tower_type}')


        if "danger" in state:
            # print(f'we gotta build!')
            # coin flip 0 or 1
            
            tower_type = self.next_attack_tower_type

            best_x, best_y, best_paths = self.get_best_bomb(rc)
            if best_paths > 14:
                self.place_best_bomb(rc, best_x, best_y, best_paths)
            else:
                self.place_best_gun(rc)
        
        if "safe" in state:
            if rc.get_balance(self.me) > TowerType.SOLAR_FARM.cost and self.num_farms < 5:
                for (x, y) in self.pts_within_5_of_any_path:
                    if rc.can_build_tower(TowerType.SOLAR_FARM, x, y):
                        rc.build_tower(TowerType.SOLAR_FARM, x, y)
                        break
                self.num_farms += 1

    

        self.towers_attack_random(rc)

        # my_path_dps, my_path_pp = self.compute_path_dps(rc)
        # self.visualize_path(my_path_pp)
        # print(my_path_pp)

    
    def towers_attack_random(self, rc: RobotController):
        self.init_each(rc)
        towers = rc.get_towers(rc.get_ally_team())
        for tower in towers:
            if tower.type == TowerType.GUNSHIP:
                self.my_auto_snipe(rc, tower.id, SnipePriority.FIRST)
            elif tower.type == TowerType.BOMBER:
                self.my_auto_bomb(rc, tower.id)
