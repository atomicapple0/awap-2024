import random
from src.game_constants import *
from src.robot_controller import *
from src.player import *
from src.map import *

ATTACK_TOWERS = [TowerType.GUNSHIP, TowerType.BOMBER]

import cv2
import numpy as np
from collections import defaultdict
import random

# monkey pp
# dps of all towers * num points reachable
# aka how much damage we can inflict on a balloon with speed 1 from start to end
# divided by path len
# ==> how much damage we can inflict per turn

# bloons pp
# how much damage this balloon must take each turn for it to die before the end



class BotPlayer(Player):
    def __init__(self, map: Map):
        self.map = map

        self.path_pts = self.map.path
        self.path_len = len(self.path_pts)

        self.path_pts_to_idx = { pt: i for i, pt in enumerate(self.path_pts) }

        self.total_pp = 0

    def init_at_1(self, rc: RobotController):
        self.me = rc.get_ally_team()
        self.next_attack_tower_type = ATTACK_TOWERS[random.randint(0, 1)]

        # precompute all point within 'near' of path
        near = 5
        self.pts_within_5_of_any_path = set()
        for x, y in self.path_pts:
            for dx in range(-near, near+1):
                for dy in range(-near, near+1):
                    if self.map.is_in_bounds(x+dx, y+dy):
                        if dx**2 + dy**2 <= near**2:
                            self.pts_within_5_of_any_path.add((x+dx, y+dy))
                            
        
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
        self.my_towers = rc.get_towers(self.me)
        
    def my_auto_snipe(self, rc: RobotController, tower_id: int, priority: SnipePriority):
        
        print(tower_id, len(self.my_towers), len(rc.get_towers(rc.get_ally_team())))
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
    
    def compute_dps_tower_at_point(self, tt: TowerType):
        dps = tt.damage / tt.cooldown
        if tt == TowerType.BOMBER:
            dps *= 10
        return dps

    def compute_path_dps(self, rc: RobotController):
        path_dps = [0] * self.path_len
    
        for path_idx, (x, y) in enumerate(self.path_pts):
            for tower in ATTACK_TOWERS:
                rg = tower.type.range
                for tower in rc.sense_towers_within_radius_squared(self.me, x, y, rg):
                    dps = self.compute_dps_tower_at_point(tower.type)
                    path_dps[path_idx] += dps

        # path_pp is suffix sum of path_dps
        path_pp = [0] * self.path_len
        path_pp[-1] = path_dps[-1]
        for i in range(self.path_len - 2, -1, -1):
            path_pp[i] = path_pp[i+1] + path_dps[i]

        return path_dps, path_pp
    
    def visualize_path(self, values):
        map = [[0] * self.map.width for _ in range(self.map.height)]
        for i, v in enumerate(values):
            x, y = self.path_pts[i]
            map[y][x] = v
        map = np.array(map, dtype=np.uint8)
        big = cv2.resize(map, (0,0), fx=5, fy=5) 

        cv2.imshow("viz", big)
        cv2.waitKey(1)

    def find_best_tower(self, rc: RobotController, tower_type: TowerType):
        best_type = None
        best_x = 0
        best_y = 0
        best_pp = -1

        for (x, y) in self.pts_within_5_of_any_path:
            if rc.is_placeable(self.me, x, y):
                pp = 0

                nbr_path_pts = []
                if tower_type == TowerType.GUNSHIP:
                    nbr_path_pts = self.path_coords_within_gunship[(x,y)]
                elif tower_type == TowerType.BOMBER:
                    nbr_path_pts = self.path_coords_within_bomber[(x,y)]
                
                for (px, py) in nbr_path_pts:
                    dps = self.compute_dps_tower_at_point(tower_type)
                    pp += dps
                if pp >= best_pp:
                    best_type = tower_type
                    best_x = x
                    best_y = y
                    best_pp = pp

        assert(best_pp is not None)
        return best_type, best_x, best_y, best_pp
    
    def sum_bloon_pp(self, rc: RobotController):
        bloons_pp = 0

        for bloon in rc.get_debris(self.me):
            path_idx = self.path_pts_to_idx[(bloon.x, bloon.y)]
            path_left = self.path_len - path_idx
            turns_left = path_left * bloon.total_cooldown
            pp = bloon.health / turns_left
            bloons_pp += pp

        return bloons_pp


    def play_turn(self, rc: RobotController):
        if rc.get_turn() == 1:
            self.init_at_1(rc)
        self.init_each(rc)
        
        bloons_pp = self.sum_bloon_pp(rc)
        
        # print(f'{bloons_pp} {self.total_pp}')

        

        if 1.2 * bloons_pp > self.total_pp:
            # print(f'we gotta build!')
            # coin flip 0 or 1
            
            btt, bx, by, bpp = self.find_best_tower(rc, self.next_attack_tower_type)
            if rc.can_build_tower(btt, bx, by):
                # print(f'we built {btt} at {bx} {by} with {bpp}')
                rc.build_tower(btt, bx, by)
                self.total_pp += bpp / self.path_len
                self.next_attack_tower_type = ATTACK_TOWERS[random.randint(0, 1)]

    

        self.towers_attack_random(rc)

        # my_path_dps, my_path_pp = self.compute_path_dps(rc)
        # self.visualize_path(my_path_pp)
        # print(my_path_pp)


    def build_towers_random(self, rc: RobotController):
        x = random.randint(0, self.map.height-1)
        y = random.randint(0, self.map.height-1)
        tower = random.randint(1, 4) # randomly select a tower
        if (rc.can_build_tower(TowerType.GUNSHIP, x, y) and 
            rc.can_build_tower(TowerType.BOMBER, x, y) and
            rc.can_build_tower(TowerType.SOLAR_FARM, x, y) and
            rc.can_build_tower(TowerType.REINFORCER, x, y)
        ):
            if tower == 1:
                rc.build_tower(TowerType.BOMBER, x, y)
            elif tower == 2:
                rc.build_tower(TowerType.GUNSHIP, x, y)
            elif tower == 3:
                rc.build_tower(TowerType.SOLAR_FARM, x, y)
            elif tower == 4:
                rc.build_tower(TowerType.REINFORCER, x, y)
    
    def towers_attack_random(self, rc: RobotController):
        self.init_each(rc)
        towers = rc.get_towers(rc.get_ally_team())
        for tower in towers:
            if tower.type == TowerType.GUNSHIP:
                self.my_auto_snipe(rc, tower.id, SnipePriority.FIRST)
            elif tower.type == TowerType.BOMBER:
                self.my_auto_bomb(rc, tower.id)
