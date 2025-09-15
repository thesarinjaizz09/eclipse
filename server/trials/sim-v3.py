# simulation_two_intersections.py
"""
Two 4-way intersections traffic simulation adapted from user's single-intersection code.
Each Intersection runs its own signal controller and spawns vehicles independently.
"""

import random
import time
import threading
import pygame
import os
import queue
import uuid

FRAME_QUEUE = queue.Queue(maxsize=1)  # Only keep the latest frame
DEBUG_MODE = False

pygame.init()

# --------------------------
# === Global Configuration ===
# --------------------------
DEFAULT_GREEN = {0: 10, 1: 10, 2: 10, 3: 10}
DEFAULT_RED = 60
DEFAULT_YELLOW = 1

STARVATION_LIMIT = 2  # cycles before a lane is forced green
AGING_WEIGHT = 2      # boost per cycle waited
RANDOM_GREEN = True
RANDOM_GREEN_RANGE = (10, 20)

SIMULATION_TIME = 300
TIME_ELAPSED_COORDS = (1100, 50)

info = pygame.display.Info()
BACKGROUND_PATH = "images/new.png"
SCREEN_WIDTH, SCREEN_HEIGHT = info.current_w, info.current_h

# Load the background image
background = pygame.image.load("images/new2.png")

# Scale background to fit screen
background = pygame.transform.scale(background, (SCREEN_WIDTH, SCREEN_HEIGHT))

# Create window same size as scaled background
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Intersection Simulation")

# Convert for faster blitting
background = background.convert()

# Movement constants
STOPPING_GAP = 25
MOVING_GAP = 25
SPEEDS = {'car': 2.5, 'bus': 2, 'truck': 2, 'bike': 2.75}
ROTATION_ANGLE = 3

ALLOWED_VEHICLE_TYPES = {'car': True, 'bus': True, 'truck': True, 'bike': True}
VEHICLE_TYPES = {0: 'car', 1: 'bus', 2: 'truck', 3: 'bike'}

STARTUP_DELAY = 5

SECONDS_PER_VEHICLE = 0.5
MIN_GREEN_DURATION = 1
MAX_GREEN = 20

# Which lanes the simultaneous left-turn map uses (keeps original ordering)
SIMULTANEOUS_MAP = {1: 0, 2: 1, 3: 2, 0: 3}

# --------------------------
# === Intersection class ===
# --------------------------
class TrafficSignal:
    def __init__(self, red: int, yellow: int, green: int):
        self.red = red
        self.yellow = yellow
        self.green = green
        self.signal_text = ""

class Intersection:
    """
    Encapsulates all state for a single 4-way intersection.
    Coordinates are relative to an x_offset (so we can place intersections side-by-side).
    """
    def __init__(self, name, x_offset=0, entry_zones=None, intersection_id=0, intersection_maps=None):
        self.name = name
        self.x_offset = x_offset
        self.INTERSECTION_ID = intersection_id
        self.INTERSECTION_MAPS = intersection_maps
        self.wait_cycles = {direction: 0 for direction in ["up", "down", "left", "right"]}

        # per-intersection screen coordinates (these mirror your original layout but shifted)
        # SIGNAL_COORDS etc. are shifted horizontally by x_offset
        self.SIGNAL_COORDS = [(128 + x_offset, 296), (404 + x_offset, 296), (404 + x_offset, 636), (128 + x_offset, 636)]
        self.SIGNAL_TIMER_COORDS = [(530 + x_offset, 210), (810 + x_offset, 210), (810 + x_offset, 550), (530 + x_offset, 550)]
        self.VEHICLE_COUNT_COORDS = [(480 + x_offset, 210), (880 + x_offset, 210), (880 + x_offset, 550), (480 + x_offset, 550)]
        
        self.allowed_spawn_directions = ["up", "down", "left", "right"]

        # stop-lines and defaults: keep same vertical/horizontal coords but shift
        self.STOP_LINES = {'right': 181 + x_offset, 'down': 408, 'left': 380 + x_offset, 'up': 612}
        self.DEFAULT_STOP = {'right': 161 + x_offset, 'down': 398, 'left': 400 + x_offset, 'up': 622}

        # spawn coordinates and lanes (shift X positions by x_offset)
        self.START_X = {
            'right': [0 + x_offset, 0 + x_offset, 0 + x_offset],
            'down':  [350 + x_offset, 317 + x_offset, 286 + x_offset],
            'left':  [0 + x_offset, 1400 + x_offset, 1400 + x_offset],
            'up':    [184 + x_offset, 215 + x_offset, 248 + x_offset]
        }
        self.START_Y = {'right': [410, 443, 476], 'down': [0, 0, 0], 'left': [582, 549, 516], 'up': [1023, 1023, 1203]}

        # midpoints used by turning logic (shift X by x_offset where appropriate)
        self.MID = {
            'right': {'x': 310 + x_offset, 'y': 445},
            'down':  {'x': 300 + x_offset, 'y': 538},
            'left':  {'x': 290 + x_offset, 'y': 405},
            'up':    {'x': 300 + x_offset, 'y': 500},
        }

        # label map local to this intersection (reuse global)
        self.DIRECTION_MAP = {0: 'right', 1: 'down', 2: 'left', 3: 'up'}
        self.DIRECTION_LABELS = {'up': 'South', 'down': 'North', 'left': 'East', 'right': 'West'}

        # vehicles per direction per lane (3 lanes: 0,1,2)
        # vehicles structure: vehicles[direction][lane_list...] and 'crossed'
        self.simulation = pygame.sprite.Group()
        self.vehicles = {
            'right': {0: [], 1: [], 2: [], 'crossed': {
                0: 0,
                1: 0,
                2: 0
            }},
            'down':  {0: [], 1: [], 2: [], 'crossed': {
                0: 0,
                1: 0,
                2: 0
            }},
            'left':  {0: [], 1: [], 2: [], 'crossed': {
                0: 0,
                1: 0,
                2: 0
            }},
            'up':    {0: [], 1: [], 2: [], 'crossed': {
                0: 0,
                1: 0,
                2: 0
            }}
        }

        # tracks vehicles that turned vs not turned per lane (used to maintain spacing after crossing)
        self.vehicles_turned = {'right': {0: [], 1: [], 2: []}, 'down': {0: [], 1: [], 2: []}, 'left': {0: [], 1: [], 2: []}, 'up': {0: [], 1: [], 2: []}}
        self.vehicles_not_turned = {'right': {0: [], 1: [], 2: []}, 'down': {0: [], 1: [], 2: []}, 'left': {0: [], 1: [], 2: []}, 'up': {0: [], 1: [], 2: []}}

        # mutable start positions (we will copy from START_X/Y)
        self.start_x = {k: list(v) for k, v in self.START_X.items()}
        self.start_y = {k: list(v) for k, v in self.START_Y.items()}

        # spawn counts
        self.SPAWN_COUNTS = {'up': {0:0,1:0,2:0}, 'down': {0:0,1:0,2:0}, 'left': {0:0,1:0,2:0}, 'right': {0:0,1:0,2:0}}

        # lane state for decisions
        self.LANE_STATE = {
            "up": {"label": "North", "spawned": 0, "crossed": 0, "remaining": 0},
            "down": {"label": "South", "spawned": 0, "crossed": 0, "remaining": 0},
            "left": {"label": "West", "spawned": 0, "crossed": 0, "remaining": 0},
            "right": {"label": "East", "spawned": 0, "crossed": 0, "remaining": 0}
        }

        # signals and control state
        self.signals = []
        self.no_of_signals = 4
        self.current_green = None
        self.lane_green = []
        self.simultaneous_green = None
        self.simultaneous_lane_green = []
        self.current_yellow = 0
        self.last_green = None
        self.lane0duration = 0
        self.lane1duration = 0
        self.lane2duration = 0

        # initialize signals
        self.initialize_signals()

        # allowed vehicle indices (populated externally)
        self.allowed_vehicle_type_indices = []
        
        if entry_zones is not None:
            # Expect a dict like {"left": pygame.Rect(...), "right": pygame.Rect(...)}
            self.ENTRY_ZONES = entry_zones
        else:
            # fallback default zones (like your current hardcoded values)
            self.ENTRY_ZONES = None

        # Define exit zones for this intersection
        self.EXIT_ZONES = {
            'right': pygame.Rect(550 + x_offset, 411, 100, 200),
            'left': pygame.Rect(250 + x_offset, 411, 100, 200)
        }

    def initialize_signals(self):
        ts = [TrafficSignal(DEFAULT_RED, DEFAULT_YELLOW, 0) for _ in range(4)]
        self.signals = ts
        self.current_green = None
        self.simultaneous_green = None
        self.current_yellow = 0
        self.last_green = None

    def get_remaining_counts(self):
        remaining = {}
        for direction in self.SPAWN_COUNTS:
            total_spawned = self.SPAWN_COUNTS[direction][0] + self.SPAWN_COUNTS[direction][1] + self.SPAWN_COUNTS[direction][2]
            total_crossed = self.vehicles[direction]['crossed'][0] + self.vehicles[direction]['crossed'][1] + self.vehicles[direction]['crossed'][2]
            remaining[direction] = total_spawned - total_crossed
        return remaining
    def get_remaining_counts_lane(self, lane):
        remaining = {}
        for direction in self.SPAWN_COUNTS:
            total_spawned = self.SPAWN_COUNTS[direction][lane]
            total_crossed = self.vehicles[direction]['crossed'][lane]
            remaining[direction] = total_spawned - total_crossed
        return remaining

    def is_vehicle_in_intersection(self, vehicle):
        """Check if a vehicle is within this intersection's bounds"""
        # Simple rectangular check - adjust as needed for your intersection layout
        x, y = vehicle.x, vehicle.y
        width, height = vehicle.image.get_rect().width, vehicle.image.get_rect().height
        
        # Define intersection bounds (adjust these values based on your intersection layout)
        left_bound = self.x_offset + 200
        right_bound = self.x_offset + 450
        top_bound = 300
        bottom_bound = 700
        
        return (left_bound <= x <= right_bound or 
                left_bound <= x + width <= right_bound or
                top_bound <= y <= bottom_bound or
                top_bound <= y + height <= bottom_bound)

# --------------------------
# === Shared Vehicle class ===
# --------------------------
def is_green_for(intersection: Intersection, direction_number, lane=None, will_turn=None):
    
    if intersection.current_yellow == 1:
        return False
    # Primary lane always green
    if direction_number == intersection.current_green:
        if lane in intersection.lane_green:
            return True
    sim_dir = SIMULTANEOUS_MAP.get(intersection.current_green)
    if sim_dir is not None:
        if direction_number == intersection.simultaneous_green and will_turn == 1 and lane in intersection.simultaneous_lane_green:
            return True
    return False

class Vehicle(pygame.sprite.Sprite):
    """
    Vehicle belongs to a specific Intersection instance.
    """
    def __init__(self, intersection: Intersection, lane, vehicle_class, direction_number, direction, will_turn):
        pygame.sprite.Sprite.__init__(self)
        # self.inter = intersection
        self.current_intersection = intersection
        self.lane = lane
        self.vehicle_class = vehicle_class
        self.speed = SPEEDS[vehicle_class]
        self.direction_number = direction_number
        self.direction = direction
        self.will_turn = will_turn
        self.turned = 0
        self.rotate_angle = 0
        self.crossed = 0
        self.crossed_index = 0
        self.has_switched = False
        self.next_intersection = None
        self.switch_ready = False

        # initial coords from intersection's mutable starts
        self.x = self.current_intersection.start_x[direction][lane]
        self.y = self.current_intersection.start_y[direction][lane]

        # add to intersection vehicles and record index
        self.current_intersection.vehicles[direction][lane].append(self)
        self.index = len(self.current_intersection.vehicles[direction][lane]) - 1

        # image load (images path same structure)
        path = os.path.join("images", direction, f"{vehicle_class}.png")
        if not os.path.exists(path):
            # fallback blank surface if missing to avoid crash
            self.original_image = pygame.Surface((30, 15))
            self.original_image.fill((100,100,100))
        else:
            self.original_image = pygame.image.load(path)
        self.image = self.original_image.copy()

        # compute stop coord based on previous vehicle
        self.stop = self._compute_initial_stop()

        # advance spawn position for next vehicle
        self._advance_spawn_position()

        self.current_intersection.simulation.add(self)
        

    def _compute_initial_stop(self):
        if len(self.current_intersection.vehicles[self.direction][self.lane]) > 1:
            prev = self.current_intersection.vehicles[self.direction][self.lane][self.index - 1]
            if prev.crossed == 0:
                if self.direction == 'right':
                    return prev.stop - prev.image.get_rect().width - STOPPING_GAP
                elif self.direction == 'left':
                    return prev.stop + prev.image.get_rect().width + STOPPING_GAP
                elif self.direction == 'down':
                    return prev.stop - prev.image.get_rect().height - STOPPING_GAP
                elif self.direction == 'up':
                    return prev.stop + prev.image.get_rect().height + STOPPING_GAP
        return self.current_intersection.DEFAULT_STOP[self.direction]

    def _advance_spawn_position(self):
        if self.direction == 'right':
            delta = self.image.get_rect().width + STOPPING_GAP
            self.current_intersection.start_x[self.direction][self.lane] -= delta
        elif self.direction == 'left':
            delta = self.image.get_rect().width + STOPPING_GAP
            self.current_intersection.start_x[self.direction][self.lane] += delta
        elif self.direction == 'down':
            delta = self.image.get_rect().height + STOPPING_GAP
            self.current_intersection.start_y[self.direction][self.lane] -= delta
        elif self.direction == 'up':
            delta = self.image.get_rect().height + STOPPING_GAP
            self.current_intersection.start_y[self.direction][self.lane] += delta

    def render(self, screen):
        screen.blit(self.image, (self.x, self.y))

    def move(self):
        # Check if vehicle is entering another intersection
        if not self.has_switched:
            for inter in INTERSECTIONS:
                if inter is not self.current_intersection:
                    for dir_name, zone in inter.ENTRY_ZONES.items():
                        if zone.collidepoint(self.x, self.y):
                            # Prepare to switch to the new intersection
                            self.next_intersection = inter
                            self.switch_ready = True
                            break
                    if self.switch_ready:
                        break
        
        # Finalize the switch if vehicle has completely left current intersection
        # print(self.current_intersection.is_vehicle_in_intersection(self))
        if not self.has_switched and self.switch_ready:
            self._switch_intersection()
        
        # Move the vehicle according to current intersection rules
        dir = self.direction
        if dir == 'right':
            self._handle_crossing(condition=(self.x + self.image.get_rect().width > self.current_intersection.STOP_LINES[dir]))
            self._move_right()
        elif dir == 'down':
            self._handle_crossing(condition=(self.y + self.image.get_rect().height > self.current_intersection.STOP_LINES[dir]))
            self._move_down()
        elif dir == 'left':
            self._handle_crossing(condition=(self.x < self.current_intersection.STOP_LINES[dir]))
            self._move_left()
        elif dir == 'up':
            self._handle_crossing(condition=(self.y < self.current_intersection.STOP_LINES[dir]))
            self._move_up()

    def _switch_intersection(self):
        """Switch vehicle to follow the rules of the new intersection"""
        try:
            # Remove from current intersection's vehicle lists
            if self in self.current_intersection.vehicles[self.direction][self.lane]:
                # Store the current index before removal
                old_index = self.index
                self.current_intersection.vehicles[self.direction][self.lane].remove(self)
                
                # Update indexes of all vehicles behind this one in the same lane
                for i in range(old_index, len(self.current_intersection.vehicles[self.direction][self.lane])):
                    self.current_intersection.vehicles[self.direction][self.lane][i].index = i
        except ValueError:
            pass  # Vehicle might have already been removed
        
        # Switch to the new intersection
        old_intersection = self.current_intersection
        self.current_intersection = self.next_intersection
        self.inter = self.current_intersection
        self.next_intersection = None
        self.switch_ready = False
        self.has_switched = True
        # print('Updated has Switched now', self.has_switched)
        
        # Reset vehicle state for the new intersection
        self.crossed = 0
        self.turned = 0
        self.crossed_index = 0
        # self.rotate_angle = 0
        
        if old_intersection.name == 'A':
            self.direction = 'right'
        elif old_intersection.name == 'B':
            self.direction = 'left'
        
        # Add to new intersection's vehicle list
        self.current_intersection.vehicles[self.direction][self.lane].append(self)
        self.index = len(self.current_intersection.vehicles[self.direction][self.lane]) - 1
        self.current_intersection.SPAWN_COUNTS[self.direction][self.lane] += 1
        self.direction_number = [k for k, v in self.current_intersection.DIRECTION_MAP.items() if v == self.direction][0]
        
        # Recompute stop position based on vehicles in the new intersection
        self.stop = self._compute_initial_stop()
        
        # print(f"Vehicle switched from {old_intersection.name} to {self.current_intersection.name}")
        
        # print(f"Vehicle switched from {old_intersection.name} to {self.current_intersection.name}")

    def _handle_crossing(self, condition: bool):
        if self.crossed == 0 and condition:
            self.crossed = 1
            self.current_intersection.vehicles[self.direction]['crossed'][self.lane] += 1
            if self.will_turn == 0:
                self.current_intersection.vehicles_not_turned[self.direction][self.lane].append(self)
                self.crossed_index = len(self.current_intersection.vehicles_not_turned[self.direction][self.lane]) - 1

    # Movement methods below mirror earlier logic but use self.inter state and is_green_for(self.inter,...)
    def _move_right(self):
        inter = self.current_intersection
        if self.will_turn == 1:
            if self.lane == 0:
                if self.crossed == 0 or (self.x + self.image.get_rect().width < inter.STOP_LINES[self.direction] + 10):
                    if ((self.x + self.image.get_rect().width <= self.stop or is_green_for(self.current_intersection, 0, self.lane, self.will_turn) or self.crossed == 1)
                            and (self.index == 0 or (self.x + self.image.get_rect().width < (inter.vehicles[self.direction][self.lane][self.index - 1].x - MOVING_GAP))
                                 or inter.vehicles[self.direction][self.lane][self.index - 1].turned == 1)):
                        self.x += self.speed
                else:
                    if self.turned == 0:
                        self.rotate_angle += ROTATION_ANGLE
                        self.image = pygame.transform.rotate(self.original_image, self.rotate_angle)
                        self.x += 2.4
                        self.y -= 2.8
                        if self.has_switched:
                            if self.rotate_angle == 180:
                                self.turned = 1
                                inter.vehicles_turned[self.direction][self.lane].append(self)
                                self.crossed_index = len(inter.vehicles_turned[self.direction][self.lane]) - 1
                        else:
                            if self.rotate_angle == 90:
                                self.turned = 1
                                inter.vehicles_turned[self.direction][self.lane].append(self)
                                self.crossed_index = len(inter.vehicles_turned[self.direction][self.lane]) - 1
                    else:
                        if (self.crossed_index == 0 or
                                self.y > (inter.vehicles_turned[self.direction][self.lane][self.crossed_index - 1].y +
                                          inter.vehicles_turned[self.direction][self.lane][self.crossed_index - 1].image.get_rect().height + MOVING_GAP)):
                            self.y -= self.speed
            elif self.lane == 2:
                if self.crossed == 0 or (self.x + self.image.get_rect().width < inter.MID[self.direction]['x']):
                    if ((self.x + self.image.get_rect().width <= self.stop or is_green_for(self.current_intersection, 0, self.lane, self.will_turn) or self.crossed == 1)
                            and (self.index == 0 or (self.x + self.image.get_rect().width < (inter.vehicles[self.direction][self.lane][self.index - 1].x - MOVING_GAP))
                                 or inter.vehicles[self.direction][self.lane][self.index - 1].turned == 1)):
                        self.x += self.speed
                else:
                    if self.turned == 0:
                        self.rotate_angle += ROTATION_ANGLE
                        self.image = pygame.transform.rotate(self.original_image, -self.rotate_angle)
                        self.x += 2
                        self.y += 1.8
                        if self.has_switched:
                            if self.rotate_angle == 180:
                                self.turned = 1
                                inter.vehicles_turned[self.direction][self.lane].append(self)
                                self.crossed_index = len(inter.vehicles_turned[self.direction][self.lane]) - 1
                        else:
                            if self.rotate_angle == 90:
                                self.turned = 1
                                inter.vehicles_turned[self.direction][self.lane].append(self)
                                self.crossed_index = len(inter.vehicles_turned[self.direction][self.lane]) - 1
                    else:
                        if (self.crossed_index == 0 or
                                (self.y + self.image.get_rect().height) <
                                (inter.vehicles_turned[self.direction][self.lane][self.crossed_index - 1].y - MOVING_GAP)):
                            self.y += self.speed
        else:
            if self.crossed == 0:
                if ((self.x + self.image.get_rect().width <= self.stop or  is_green_for(self.current_intersection, 0, self.lane, self.will_turn))
                        and (self.index == 0 or (self.x + self.image.get_rect().width <
                                                (inter.vehicles[self.direction][self.lane][self.index - 1].x - MOVING_GAP)))):
                    self.x += self.speed
            else:
                if (self.crossed_index == 0 or
                        (self.x + self.image.get_rect().width <
                         (inter.vehicles_not_turned[self.direction][self.lane][self.crossed_index - 1].x - MOVING_GAP))):
                    self.x += self.speed

    def _move_down(self):
        inter = self.current_intersection
        if self.will_turn == 1:
            if self.lane == 0:
                if self.crossed == 0 or (self.y + self.image.get_rect().height < inter.STOP_LINES[self.direction] + 25):
                    if ((self.y + self.image.get_rect().height <= self.stop or is_green_for(self.current_intersection, 1, self.lane, self.will_turn) or self.crossed == 1)
                            and (self.index == 0 or (self.y + self.image.get_rect().height <
                                                     (inter.vehicles[self.direction][self.lane][self.index - 1].y - MOVING_GAP))
                                 or inter.vehicles[self.direction][self.lane][self.index - 1].turned == 1)):
                        self.y += self.speed
                else:
                    if self.turned == 0:
                        self.rotate_angle += ROTATION_ANGLE
                        self.image = pygame.transform.rotate(self.original_image, self.rotate_angle)
                        self.x += 1.2
                        self.y += 1.8
                        # print('Old Turned Switch', self.turned)
                        # print('Check Turned Switch', self.has_switched)
                        # if self.has_switched:
                        if self.rotate_angle >= 90:
                            self.turned = 1
                            inter.vehicles_turned[self.direction][self.lane].append(self)
                            self.crossed_index = len(inter.vehicles_turned[self.direction][self.lane]) - 1
                        
                    else:
                        if (self.crossed_index == 0 or
                                (self.x + self.image.get_rect().width) <
                                (inter.vehicles_turned[self.direction][self.lane][self.crossed_index - 1].x - MOVING_GAP)):
                            self.x += self.speed
            elif self.lane == 2:
                if self.crossed == 0 or (self.y + self.image.get_rect().height < inter.MID[self.direction]['y']):
                    if ((self.y + self.image.get_rect().height <= self.stop or is_green_for(self.current_intersection, 1, self.lane, self.will_turn) or self.crossed == 1)
                            and (self.index == 0 or (self.y + self.image.get_rect().height <
                                                     (inter.vehicles[self.direction][self.lane][self.index - 1].y - MOVING_GAP))
                                 or inter.vehicles[self.direction][self.lane][self.index - 1].turned == 1)):
                        self.y += self.speed
                else:
                    if self.turned == 0:
                        self.rotate_angle += ROTATION_ANGLE
                        self.image = pygame.transform.rotate(self.original_image, -self.rotate_angle)
                        self.x -= 2.5
                        self.y += 2
                        if self.rotate_angle >= 90:
                            self.turned = 1
                            inter.vehicles_turned[self.direction][self.lane].append(self)
                            self.crossed_index = len(inter.vehicles_turned[self.direction][self.lane]) - 1
                    else:
                        if (self.crossed_index == 0 or
                                (self.x > (inter.vehicles_turned[self.direction][self.lane][self.crossed_index - 1].x +
                                           inter.vehicles_turned[self.direction][self.lane][self.crossed_index - 1].image.get_rect().width + MOVING_GAP))):
                            self.x -= self.speed
        else:
            if self.crossed == 0:
                if ((self.y + self.image.get_rect().height <= self.stop or is_green_for(self.current_intersection, 1, self.lane, self.will_turn))
                        and (self.index == 0 or (self.y + self.image.get_rect().height <
                                                 (inter.vehicles[self.direction][self.lane][self.index - 1].y - MOVING_GAP)))):
                    self.y += self.speed
            else:
                if (self.crossed_index == 0 or
                        (self.y + self.image.get_rect().height <
                         (inter.vehicles_not_turned[self.direction][self.lane][self.crossed_index - 1].y - MOVING_GAP))):
                    self.y += self.speed

    def _move_left(self):
        inter = self.current_intersection
        if self.will_turn == 1:
            if self.lane == 0:
                if self.crossed == 0 or (self.x > inter.STOP_LINES[self.direction]):
                    if ((self.x >= self.stop or is_green_for(self.current_intersection, 2, self.lane, self.will_turn) or self.crossed == 1)
                            and (self.index == 0 or (self.x > (inter.vehicles[self.direction][self.lane][self.index - 1].x + inter.vehicles[self.direction][self.lane][self.index - 1].image.get_rect().width + MOVING_GAP))
                                 or inter.vehicles[self.direction][self.lane][self.index - 1].turned == 1)):
                        self.x -= self.speed
                else:
                    if self.turned == 0:
                        self.rotate_angle += ROTATION_ANGLE
                        self.image = pygame.transform.rotate(self.original_image, self.rotate_angle)
                        self.x -= 1
                        self.y += 1.2
                        if self.has_switched:
                            if self.rotate_angle == 180:
                                self.turned = 1
                                inter.vehicles_turned[self.direction][self.lane].append(self)
                                self.crossed_index = len(inter.vehicles_turned[self.direction][self.lane]) - 1
                        else:
                            if self.rotate_angle == 90:
                                self.turned = 1
                                inter.vehicles_turned[self.direction][self.lane].append(self)
                                self.crossed_index = len(inter.vehicles_turned[self.direction][self.lane]) - 1
                    else:
                        if (self.crossed_index == 0 or
                                (self.y + self.image.get_rect().height) < (inter.vehicles_turned[self.direction][self.lane][self.crossed_index - 1].y - MOVING_GAP)):
                            self.y += self.speed
            elif self.lane == 2:
                if self.crossed == 0 or (self.x > inter.MID[self.direction]['x']):
                    if ((self.x >= self.stop or is_green_for(self.current_intersection, 2, self.lane, self.will_turn) or self.crossed == 1)
                            and (self.index == 0 or (self.x > (inter.vehicles[self.direction][self.lane][self.index - 1].x + inter.vehicles[self.direction][self.lane][self.index - 1].image.get_rect().width + MOVING_GAP))
                                 or inter.vehicles[self.direction][self.lane][self.index - 1].turned == 1)):
                        self.x -= self.speed
                else:
                    if self.turned == 0:
                        self.rotate_angle += ROTATION_ANGLE
                        self.image = pygame.transform.rotate(self.original_image, -self.rotate_angle)
                        self.x -= 1.8
                        self.y -= 2.5
                        if self.has_switched:
                            if self.rotate_angle == 180:
                                self.turned = 1
                                inter.vehicles_turned[self.direction][self.lane].append(self)
                                self.crossed_index = len(inter.vehicles_turned[self.direction][self.lane]) - 1
                        else:
                            if self.rotate_angle == 90:
                                self.turned = 1
                                inter.vehicles_turned[self.direction][self.lane].append(self)
                                self.crossed_index = len(inter.vehicles_turned[self.direction][self.lane]) - 1
                    else:
                        if (self.crossed_index == 0 or
                                self.y > (inter.vehicles_turned[self.direction][self.lane][self.crossed_index - 1].y +
                                          inter.vehicles_turned[self.direction][self.lane][self.crossed_index - 1].image.get_rect().height + MOVING_GAP)):
                            self.y -= self.speed
        else:
            if self.crossed == 0:
                if ((self.x >= self.stop or is_green_for(self.current_intersection, 2, self.lane, self.will_turn))
                        and (self.index == 0 or (self.x > (inter.vehicles[self.direction][self.lane][self.index - 1].x + inter.vehicles[self.direction][self.lane][self.index - 1].image.get_rect().width + MOVING_GAP)))):
                    self.x -= self.speed
            else:
                if (self.crossed_index == 0 or
                        (self.x > (inter.vehicles_not_turned[self.direction][self.lane][self.crossed_index - 1].x +
                                   inter.vehicles_not_turned[self.direction][self.lane][self.crossed_index - 1].image.get_rect().width + MOVING_GAP))):
                    self.x -= self.speed

    def _move_up(self):
        inter = self.current_intersection
        if self.will_turn == 1:
            if self.lane == 0:
                if self.crossed == 0 or (self.y > inter.STOP_LINES[self.direction]):
                    if ((self.y >= self.stop or is_green_for(self.current_intersection, 3, self.lane, self.will_turn) or self.crossed == 1)
                            and (self.index == 0 or (self.y > (inter.vehicles[self.direction][self.lane][self.index - 1].y + inter.vehicles[self.direction][self.lane][self.index - 1].image.get_rect().height + MOVING_GAP))
                                 or inter.vehicles[self.direction][self.lane][self.index - 1].turned == 1)):
                        self.y -= self.speed
                else:
                    if self.turned == 0:
                        self.rotate_angle += ROTATION_ANGLE
                        self.image = pygame.transform.rotate(self.original_image, self.rotate_angle)
                        self.x -= 2
                        self.y -= 1.2
                        if self.rotate_angle >= 90:
                            self.turned = 1
                            inter.vehicles_turned[self.direction][self.lane].append(self)
                            self.crossed_index = len(inter.vehicles_turned[self.direction][self.lane]) - 1
                    else:
                        if (self.crossed_index == 0 or
                                (self.x > (inter.vehicles_turned[self.direction][self.lane][self.crossed_index - 1].x +
                                           inter.vehicles_turned[self.direction][self.lane][self.crossed_index - 1].image.get_rect().width + MOVING_GAP))):
                            self.x -= self.speed
            elif self.lane == 2:
                if self.crossed == 0 or (self.y > inter.MID[self.direction]['y']):
                    if ((self.y >= self.stop or is_green_for(self.current_intersection, 3, self.lane, self.will_turn) or self.crossed == 1)
                            and (self.index == 0 or (self.y > (inter.vehicles[self.direction][self.lane][self.index - 1].y + inter.vehicles[self.direction][self.lane][self.index - 1].image.get_rect().height + MOVING_GAP))
                                 or inter.vehicles[self.direction][self.lane][self.index - 1].turned == 1)):
                        self.y -= self.speed
                else:
                    if self.turned == 0:
                        self.rotate_angle += ROTATION_ANGLE
                        self.image = pygame.transform.rotate(self.original_image, -self.rotate_angle)
                        self.x += 1
                        self.y -= 1
                        if self.rotate_angle >= 90:
                            self.turned = 1
                            inter.vehicles_turned[self.direction][self.lane].append(self)
                            self.crossed_index = len(inter.vehicles_turned[self.direction][self.lane]) - 1
                    else:
                        if (self.crossed_index == 0 or
                                (self.x < (inter.vehicles_turned[self.direction][self.lane][self.crossed_index - 1].x - inter.vehicles_turned[self.direction][self.lane][self.crossed_index - 1].image.get_rect().width - MOVING_GAP))):
                            self.x += self.speed
        else:
            if self.crossed == 0:
                if ((self.y >= self.stop or is_green_for(self.current_intersection, 3, self.lane, self.will_turn))
                        and (self.index == 0 or (self.y > (inter.vehicles[self.direction][self.lane][self.index - 1].y + inter.vehicles[self.direction][self.lane][self.index - 1].image.get_rect().height + MOVING_GAP)))):
                    self.y -= self.speed
            else:
                if (self.crossed_index == 0 or
                        (self.y > (inter.vehicles_not_turned[self.direction][self.lane][self.crossed_index - 1].y +
                                   inter.vehicles_not_turned[self.direction][self.lane][self.crossed_index - 1].image.get_rect().height + MOVING_GAP))):
                    self.y -= self.speed

# --------------------------
# === Global & threads ===
# --------------------------
# Create two intersections side-by-side: left at x_offset=0, right shifted by +700 pixels
left_intersection_id = str(uuid.uuid4())
right_intersection_id = str(uuid.uuid4())
intersection_left = Intersection("A", x_offset=0, entry_zones={
    'right': pygame.Rect(733, 411, 100, 200),
}, intersection_id=left_intersection_id, intersection_maps={
    'left': 0,
    'right': right_intersection_id,
    'up': right_intersection_id,
    'down': right_intersection_id
})
intersection_left.allowed_spawn_directions = ["up", "down", "right"]
# intersection_left.allowed_spawn_directions = ["right"]
intersection_right = Intersection("B", x_offset=748, entry_zones={
    'left': pygame.Rect(470, 411, 100, 200),
}, intersection_id=right_intersection_id, intersection_maps={
    'left': left_intersection_id,
    'right': '0',
    'up': left_intersection_id,
    'down': left_intersection_id
})
intersection_right.allowed_spawn_directions = ["up", "down", "left"]
# intersection_right.allowed_spawn_directions = ["left"]

INTERSECTIONS = [intersection_left, intersection_right]

# fill allowed_vehicle_type_indices for each intersection
for inter in INTERSECTIONS:
    inter.allowed_vehicle_type_indices = [i for i, name in VEHICLE_TYPES.items() if ALLOWED_VEHICLE_TYPES.get(name, False)]

# timing & startup
startup_time = time.time()
startup_mode = True
time_elapsed = 0

# load images (global)
def load_image_safe(path, fallback_size=(20,20)):
    if os.path.exists(path):
        return pygame.image.load(path)
    else:
        surf = pygame.Surface(fallback_size)
        surf.fill((120,120,120))
        return surf

# --------------------------
# === Dynamic signal controller per intersection ===
# --------------------------
def can_open_lane(inter: Intersection, dir_name: str, all_inters: list) -> bool:
    """
    Check if the lane in same direction at other intersections has < 10 vehicles.
    """
    for other in all_inters:
        if other is inter:  # skip self
            continue
        # check each lane (0,1,2) for this direction
        total = sum(len(other.vehicles[dir_name][lane]) for lane in range(3))
        if total >= 10:
            return False
    return True

def get_intersection_by_id(all_inters, inter_id):
    for inter in all_inters:
        if str(inter.INTERSECTION_ID) == str(inter_id):
            return inter
    return None



def dynamic_signal_controller(inter: Intersection):
    inter.SIGNAL_CONTROL_RUNNING = True
    while inter.SIGNAL_CONTROL_RUNNING:
        # choose next green using remaining counts prioritization (avoid last green)
        remaining_counts = inter.get_remaining_counts()
        # print(f"Intersection Id - {inter.name} , {remaining_counts}")
        priorities = {}
        for dir_name, count in remaining_counts.items():
            priorities[dir_name] = AGING_WEIGHT * inter.wait_cycles[dir_name]
        # print(priorities)
        
        # --- Handle starvation: force a lane if it waited too long ---
        forced_dir = None
        lane0duration = 0
        lane1duration = 0
        lane2duration = 0
        chosen_count = 0
        chosen_count_sim = 0
        # Build list of (dir, wait, vehicles)
        candidates = [(d, wait, remaining_counts.get(d, 0)) for d, wait in inter.wait_cycles.items()]

        # Filter only directions that are starving and have vehicles
        candidates = [c for c in candidates if c[1] >= STARVATION_LIMIT and c[2] > 0]

        if candidates:
            # Sort by wait time first, then by vehicle count (descending)
            candidates.sort(key=lambda x: (x[1], x[2]), reverse=True)

            # Pick the one with highest starvation (and then highest vehicles if tied)
            forced_dir, _, chosen_count = candidates[0]
        print(f"Force Directory : {forced_dir} for {inter.name}")
        if forced_dir:
            chosen_dir = forced_dir
        else:
            sorted_dirs = sorted(remaining_counts.items(), key=lambda x: x[1], reverse=True)
            chosen_dir = None
            for dir_name, count in sorted_dirs:
                if dir_name != inter.last_green:
                    chosen_dir, chosen_count = dir_name, count
                    break
            if chosen_dir is None:
                chosen_dir, chosen_count = sorted_dirs[0]
                
        for dir_name in inter.wait_cycles:
            if dir_name == chosen_dir:
                inter.wait_cycles[dir_name] = 0
            else:
                inter.wait_cycles[dir_name] += 1

        # --- ✅ NEW LOGIC: neighbor check using get_remaining_counts ---
        neighbor_id = inter.INTERSECTION_MAPS.get(chosen_dir, 0)
        print(neighbor_id)
        if neighbor_id != 0 and neighbor_id != "0":
            neighbor = get_intersection_by_id(INTERSECTIONS, neighbor_id)
            if neighbor:
                inter.lane_green.clear()
                # print("Intersection: ", inter.name)
                if inter.name == 'A':
                    # print("Chosen Direction: ", chosen_dir)
                    if chosen_dir == 'right':
                        neighbour_lane_remaining = neighbor.get_remaining_counts_lane(1)['right']
                        # #print('Neighbour remaining: ', neighbour_lane_remaining)
                        vehicles_in_chosen = inter.get_remaining_counts_lane(1)['right']
                        vehicles_in_chosen1 = inter.get_remaining_counts_lane(0)['right']
                        vehicles_in_chosen2 = inter.get_remaining_counts_lane(2)['right']
                        inter.simultaneous_lane_green.append(0)
                        
                        if neighbour_lane_remaining >= 5:
                            inter.lane_green.append(0)
                            inter.lane_green.append(2)
                            lane0duration = max(MIN_GREEN_DURATION, int(vehicles_in_chosen1 * SECONDS_PER_VEHICLE))
                            lane2duration = max(MIN_GREEN_DURATION, int(vehicles_in_chosen2 * SECONDS_PER_VEHICLE))
                        else:
                            allowed_to_pass = 5 - neighbour_lane_remaining
                            chosen_count = min(vehicles_in_chosen, allowed_to_pass)
                            lane1duration = max(MIN_GREEN_DURATION, int(chosen_count * SECONDS_PER_VEHICLE))
                            lane0duration = max(MIN_GREEN_DURATION, int(vehicles_in_chosen1 * SECONDS_PER_VEHICLE))
                            lane2duration = max(MIN_GREEN_DURATION, int(vehicles_in_chosen2 * SECONDS_PER_VEHICLE))
                            inter.lane_green.append(0)
                            inter.lane_green.append(1)
                            inter.lane_green.append(2)
                    if chosen_dir == 'up':
                        neighbour_lane_remaining = neighbor.get_remaining_counts_lane(2)['right']
                        #print('Neighbour remaining: ', neighbour_lane_remaining)
                        vehicles_in_chosen = inter.get_remaining_counts_lane(2)['up']
                        vehicles_in_chosen1 = inter.get_remaining_counts_lane(0)['up']
                        vehicles_in_chosen2 = inter.get_remaining_counts_lane(1)['up']
                        inter.simultaneous_lane_green.append(0)
                        if neighbour_lane_remaining >= 5:
                            inter.lane_green.append(0)
                            inter.lane_green.append(1)
                            lane0duration = max(MIN_GREEN_DURATION, int(vehicles_in_chosen1 * SECONDS_PER_VEHICLE))
                            lane1duration = max(MIN_GREEN_DURATION, int(vehicles_in_chosen2 * SECONDS_PER_VEHICLE))
                        else:
                            allowed_to_pass = 5 - neighbour_lane_remaining
                            chosen_count = min(vehicles_in_chosen, allowed_to_pass)
                            lane2duration = max(MIN_GREEN_DURATION, int(chosen_count * SECONDS_PER_VEHICLE))
                            lane0duration = max(MIN_GREEN_DURATION, int(vehicles_in_chosen1 * SECONDS_PER_VEHICLE))
                            lane1duration = max(MIN_GREEN_DURATION, int(vehicles_in_chosen2 * SECONDS_PER_VEHICLE))
                            inter.lane_green.append(2)
                            inter.lane_green.append(0)
                            inter.lane_green.append(1)
                    if chosen_dir == 'down':
                        neighbour_lane_remaining = neighbor.get_remaining_counts_lane(0)['right']
                        #print('Neighbour remaining: ', neighbour_lane_remaining)
                        vehicles_in_chosen = inter.get_remaining_counts_lane(0)['down']
                        vehicles_in_chosen1 = inter.get_remaining_counts_lane(1)['down']
                        vehicles_in_chosen2 = inter.get_remaining_counts_lane(2)['down']
                        inter.simultaneous_lane_green.append(0)
                        if neighbour_lane_remaining >= 5:
                            inter.lane_green.append(2)
                            inter.lane_green.append(1)
                            lane1duration = max(MIN_GREEN_DURATION, int(vehicles_in_chosen1 * SECONDS_PER_VEHICLE))
                            lane2duration = max(MIN_GREEN_DURATION, int(vehicles_in_chosen2 * SECONDS_PER_VEHICLE))
                        else:
                            allowed_to_pass = 5 - neighbour_lane_remaining
                            chosen_count = min(vehicles_in_chosen, allowed_to_pass)
                            lane0duration = max(MIN_GREEN_DURATION, int(chosen_count * SECONDS_PER_VEHICLE))
                            lane1duration = max(MIN_GREEN_DURATION, int(vehicles_in_chosen1 * SECONDS_PER_VEHICLE))
                            lane2duration = max(MIN_GREEN_DURATION, int(vehicles_in_chosen2 * SECONDS_PER_VEHICLE))
                            inter.lane_green.append(0)
                            inter.lane_green.append(2)
                            inter.lane_green.append(1)
                    if chosen_dir == 'left':
                        neighbour_lane_remaining = neighbor.get_remaining_counts_lane(0)['right']
                        #print('Neighbour remaining: ', neighbour_lane_remaining)
                        inter.lane_green.append(0)
                        inter.lane_green.append(2)
                        inter.lane_green.append(1)
                        vehicles_in_chosen = inter.get_remaining_counts_lane(0)['down']
                        vehicles_in_chosen0 = inter.get_remaining_counts_lane(0)['left']
                        vehicles_in_chosen1 = inter.get_remaining_counts_lane(1)['left']
                        vehicles_in_chosen2 = inter.get_remaining_counts_lane(2)['left']
                        lane0duration = max(MIN_GREEN_DURATION, int(vehicles_in_chosen0 * SECONDS_PER_VEHICLE))
                        lane1duration = max(MIN_GREEN_DURATION, int(vehicles_in_chosen1 * SECONDS_PER_VEHICLE))
                        lane2duration = max(MIN_GREEN_DURATION, int(vehicles_in_chosen2 * SECONDS_PER_VEHICLE))
                        if neighbour_lane_remaining >= 5:
                            pass
                        else:
                            allowed_to_pass = 5 - neighbour_lane_remaining
                            chosen_count_sim = min(vehicles_in_chosen, allowed_to_pass)
                            inter.simultaneous_lane_green.append(0)
                if inter.name == 'B':
                    # print("Chosen Direction: ", chosen_dir)
                    if chosen_dir == 'left':
                        neighbour_lane_remaining = neighbor.get_remaining_counts_lane(1)['left']
                        #print('Neighbour remaining: ', neighbour_lane_remaining)
                        vehicles_in_chosen = inter.get_remaining_counts_lane(1)['left']
                        vehicles_in_chosen1 = inter.get_remaining_counts_lane(0)['left']
                        vehicles_in_chosen2 = inter.get_remaining_counts_lane(2)['left']
                        lane0duration = max(MIN_GREEN_DURATION, int(vehicles_in_chosen1 * SECONDS_PER_VEHICLE))
                        lane2duration = max(MIN_GREEN_DURATION, int(vehicles_in_chosen2 * SECONDS_PER_VEHICLE))
                        inter.simultaneous_lane_green.append(0)
                        if neighbour_lane_remaining >= 5:
                            inter.lane_green.append(2)
                            inter.lane_green.append(0)
                        else:
                            allowed_to_pass = 5 - neighbour_lane_remaining
                            chosen_count = min(vehicles_in_chosen, allowed_to_pass)
                            inter.lane_green.append(1)
                            inter.lane_green.append(2)
                            inter.lane_green.append(0)
                            lane1duration = max(MIN_GREEN_DURATION, int(chosen_count * SECONDS_PER_VEHICLE))
                    if chosen_dir == 'up':
                        neighbour_lane_remaining = neighbor.get_remaining_counts_lane(0)['left']
                        #print('Neighbour remaining: ', neighbour_lane_remaining)
                        vehicles_in_chosen = inter.get_remaining_counts_lane(0)['up']
                        vehicles_in_chosen1 = inter.get_remaining_counts_lane(1)['up']
                        vehicles_in_chosen2 = inter.get_remaining_counts_lane(2)['up']
                        lane1duration = max(MIN_GREEN_DURATION, int(vehicles_in_chosen1 * SECONDS_PER_VEHICLE))
                        lane2duration = max(MIN_GREEN_DURATION, int(vehicles_in_chosen2 * SECONDS_PER_VEHICLE))
                        inter.simultaneous_lane_green.append(0)
                        if neighbour_lane_remaining >= 5:
                            inter.lane_green.append(2)
                            inter.lane_green.append(1)
                        else:
                            allowed_to_pass = 5 - neighbour_lane_remaining
                            chosen_count = min(vehicles_in_chosen, allowed_to_pass)
                            inter.lane_green.append(0)
                            inter.lane_green.append(2)
                            inter.lane_green.append(1)
                            lane0duration = max(MIN_GREEN_DURATION, int(chosen_count * SECONDS_PER_VEHICLE))
                    if chosen_dir == 'down':
                        neighbour_lane_remaining = neighbor.get_remaining_counts_lane(2)['left']
                        #print('Neighbour remaining: ', neighbour_lane_remaining)
                        vehicles_in_chosen = inter.get_remaining_counts_lane(2)['down']
                        vehicles_in_chosen1 = inter.get_remaining_counts_lane(0)['down']
                        vehicles_in_chosen2 = inter.get_remaining_counts_lane(1)['down']
                        lane0duration = max(MIN_GREEN_DURATION, int(vehicles_in_chosen1 * SECONDS_PER_VEHICLE))
                        lane1duration = max(MIN_GREEN_DURATION, int(vehicles_in_chosen2 * SECONDS_PER_VEHICLE))
                        inter.simultaneous_lane_green.append(0)
                        if neighbour_lane_remaining >= 5:
                            inter.lane_green.append(0)
                            inter.lane_green.append(1)
                        else:
                            allowed_to_pass = 5 - neighbour_lane_remaining
                            chosen_count = min(vehicles_in_chosen, allowed_to_pass)
                            inter.lane_green.append(2)
                            inter.lane_green.append(0)
                            inter.lane_green.append(1)
                            lane2duration = max(MIN_GREEN_DURATION, int(chosen_count * SECONDS_PER_VEHICLE))
                    if chosen_dir == 'right':
                        neighbour_lane_remaining = neighbor.get_remaining_counts_lane(0)['left']
                        #print('Neighbour remaining: ', neighbour_lane_remaining)
                        inter.lane_green.append(0)
                        inter.lane_green.append(2)
                        inter.lane_green.append(1)
                        vehicles_in_chosen = inter.get_remaining_counts_lane(0)['up']
                        vehicles_in_chosen0 = inter.get_remaining_counts_lane(0)['right']
                        vehicles_in_chosen1 = inter.get_remaining_counts_lane(1)['right']
                        vehicles_in_chosen2 = inter.get_remaining_counts_lane(2)['right']
                        lane0duration = max(MIN_GREEN_DURATION, int(vehicles_in_chosen0 * SECONDS_PER_VEHICLE))
                        lane1duration = max(MIN_GREEN_DURATION, int(vehicles_in_chosen1 * SECONDS_PER_VEHICLE))
                        lane2duration = max(MIN_GREEN_DURATION, int(vehicles_in_chosen2 * SECONDS_PER_VEHICLE))
                        if neighbour_lane_remaining >= 5:
                            pass
                        else:
                            allowed_to_pass = 5 - neighbour_lane_remaining
                            chosen_count_sim = min(vehicles_in_chosen, allowed_to_pass)
                            inter.simultaneous_lane_green.append(0)
        else:
            inter.lane_green.clear()
                # print("Intersection: ", inter.name)
            if inter.name == 'A' and chosen_dir == 'left':
                print('In inter A (forced left)')
                neighbour_lane_remaining = neighbor.get_remaining_counts_lane(0)['right']
                inter.lane_green.append(0)
                inter.lane_green.append(1)
                inter.lane_green.append(2)
                v0 = inter.get_remaining_counts_lane(0)['left']
                v1 = inter.get_remaining_counts_lane(1)['left']
                v2 = inter.get_remaining_counts_lane(2)['left']
                print("Test A:", v0, v1, v2)

                lane0duration = max(MIN_GREEN_DURATION, int(v0 * SECONDS_PER_VEHICLE))
                lane1duration = max(MIN_GREEN_DURATION, int(v1 * SECONDS_PER_VEHICLE))
                lane2duration = max(MIN_GREEN_DURATION, int(v2 * SECONDS_PER_VEHICLE))

            elif inter.name == 'B' and chosen_dir == 'right':
                print('In inter B (forced right)')
                neighbour_lane_remaining = neighbor.get_remaining_counts_lane(0)['left']
                inter.lane_green.append(0)
                inter.lane_green.append(1)
                inter.lane_green.append(2)
                v0 = inter.get_remaining_counts_lane(0)['right']
                v1 = inter.get_remaining_counts_lane(1)['right']
                v2 = inter.get_remaining_counts_lane(2)['right']
                print("Test B:", v0, v1, v2)

                lane0duration = max(MIN_GREEN_DURATION, int(v0 * SECONDS_PER_VEHICLE))
                lane1duration = max(MIN_GREEN_DURATION, int(v1 * SECONDS_PER_VEHICLE))
                lane2duration = max(MIN_GREEN_DURATION, int(v2 * SECONDS_PER_VEHICLE))
        # --- rest of your existing green/yellow/red setup ---
        maxDuration = max(lane0duration, lane1duration, lane2duration)
        green_duration = max(MIN_GREEN_DURATION, maxDuration)
        green_duration = min(green_duration, MAX_GREEN)
        sim_green_duration = max(MIN_GREEN_DURATION, int(chosen_count_sim * SECONDS_PER_VEHICLE))
        sim_green_duration = min(sim_green_duration, MAX_GREEN)

        inter.current_green = [k for k, v in inter.DIRECTION_MAP.items() if v == chosen_dir][0]
        inter.last_green = chosen_dir
        inter.current_yellow = 0
        # print(inter.lane_green)
        inter.simultaneous_green = SIMULTANEOUS_MAP[inter.current_green]

        # reset signals
        for sig in inter.signals:
            sig.green = 0
            sig.yellow = 0
            sig.red = green_duration + DEFAULT_YELLOW

        # set active + simultaneous green
        for idx in [inter.current_green]:
            inter.signals[idx].green = green_duration
            inter.signals[idx].yellow = DEFAULT_YELLOW
            inter.signals[idx].red = sum(
                inter.signals[j].green + inter.signals[j].yellow
                for j in range(inter.no_of_signals)
                if j not in [idx, inter.current_green]
            )
        for idx in [inter.simultaneous_green]:
            inter.signals[idx].green = sim_green_duration
            inter.signals[idx].yellow = DEFAULT_YELLOW
            inter.signals[idx].red = sum(
                inter.signals[j].green + inter.signals[j].yellow
                for j in range(inter.no_of_signals)
                if j not in [idx, inter.current_green]
            )
            
            
        while (
            green_duration > 0
            or lane0duration > 0
            or lane1duration > 0
            or lane2duration > 0
            or sim_green_duration > 0
        ):
    # --- decrement and check lane0 ---
            if lane0duration > 0:
                lane0duration -= 1
                if lane0duration == 0 and 0 in inter.lane_green:
                    inter.lane_green.remove(0)
                    # print("⚡ Lane 0 finished, removing from green set.")
                    for vehicle in inter.vehicles[inter.DIRECTION_MAP[inter.current_green]][0]:
                        vehicle.stop = inter.DEFAULT_STOP[inter.DIRECTION_MAP[inter.current_green]]

            # --- decrement and check lane1 ---
            if lane1duration > 0:
                lane1duration -= 1
                if lane1duration == 0 and 1 in inter.lane_green:
                    inter.lane_green.remove(1)
                    # print("⚡ Lane 1 finished, removing from green set.")
                    for vehicle in inter.vehicles[inter.DIRECTION_MAP[inter.current_green]][1]:
                        vehicle.stop = inter.DEFAULT_STOP[inter.DIRECTION_MAP[inter.current_green]]

            # --- decrement and check lane2 ---
            if lane2duration > 0:
                lane2duration -= 1
                if lane2duration == 0 and 2 in inter.lane_green:
                    inter.lane_green.remove(2)
                    # print("⚡ Lane 2 finished, removing from green set.")
                    for vehicle in inter.vehicles[inter.DIRECTION_MAP[inter.current_green]][2]:
                        vehicle.stop = inter.DEFAULT_STOP[inter.DIRECTION_MAP[inter.current_green]]

            # --- decrement and check sim_green ---
            if sim_green_duration > 0:
                sim_green_duration -= 1
                if sim_green_duration == 0:
                    # print("⚡ Simultaneous green finished → turning red.")
                    inter.signals[inter.simultaneous_green].green = 0
                    for lane in range(0, 3):
                        for vehicle in inter.vehicles[inter.DIRECTION_MAP[inter.simultaneous_green]][lane]:
                            vehicle.stop = inter.DEFAULT_STOP[inter.DIRECTION_MAP[inter.simultaneous_green]]

            # --- decrement and check overall green_duration ---
            if green_duration > 0:
                green_duration -= 1
                if green_duration == 0:
                    # print("⚡ Main green finished → switching to yellow.")
                    inter.signals[inter.current_green].green = 0
                    inter.signals[inter.current_green].yellow = DEFAULT_YELLOW

            time.sleep(1)
        # countdown loop
        # while inter.signals[inter.current_green].green > 0 or inter.signals[inter.current_green].yellow > 0:
        #     active_dir_name = inter.DIRECTION_MAP[inter.current_green]
        #     remaining_now = inter.get_remaining_counts().get(active_dir_name, 0)
        #     if remaining_now == 0 and inter.signals[inter.current_green].green > 0:
        #         print(f"⚡ No vehicles left in {active_dir_name}, switching to yellow early.")
        #         inter.signals[inter.current_green].green = 0
        #         inter.signals[inter.current_green].yellow = DEFAULT_YELLOW
        #         for lane in range(0, 3):
        #             for vehicle in inter.vehicles[inter.DIRECTION_MAP[inter.current_green]][lane]:
        #                 vehicle.stop = inter.DEFAULT_STOP[inter.DIRECTION_MAP[inter.current_green]]
        #     if inter.signals[inter.current_green].green > 0:
        #         inter.signals[inter.current_green].green -= 1
        #         inter.current_yellow = 0
        #     elif inter.signals[inter.current_green].yellow > 0:
        #         inter.signals[inter.current_green].yellow -= 1
        #         inter.current_yellow = 1
        #         # reset stops for vehicles in these directions so they can go fully
        #         for lane in range(0, 3):
        #             for vehicle in inter.vehicles[inter.DIRECTION_MAP[inter.current_green]][lane]:
        #                 vehicle.stop = inter.DEFAULT_STOP[inter.DIRECTION_MAP[inter.current_green]]

        #     # update red timers for other signals
        #     for i in range(inter.no_of_signals):
        #         if i not in [inter.current_green, inter.simultaneous_green]:
        #             inter.signals[i].red = inter.signals[inter.current_green].green + inter.signals[inter.current_green].yellow
        #     time.sleep(1)

        # while inter.signals[inter.simultaneous_green].green > 0 or inter.signals[inter.simultaneous_green].yellow > 0:
            # active_dir_name = inter.DIRECTION_MAP[inter.simultaneous_green]
            # remaining_now = inter.get_remaining_counts().get(active_dir_name, 0)
            # if remaining_now == 0 and inter.signals[inter.simultaneous_green].green > 0:
            #     print(f"⚡ No vehicles left in {active_dir_name}, switching to yellow early.")
            #     inter.signals[inter.simultaneous_green].green = 0
            #     inter.signals[inter.simultaneous_green].yellow = DEFAULT_YELLOW
            #     for lane in range(0, 3):
            #         for vehicle in inter.vehicles[inter.DIRECTION_MAP[inter.simultaneous_green]][lane]:
            #             vehicle.stop = inter.DEFAULT_STOP[inter.DIRECTION_MAP[inter.simultaneous_green]]
            # if inter.signals[inter.simultaneous_green].green > 0:
            #     inter.signals[inter.simultaneous_green].green -= 1
            # elif inter.signals[inter.simultaneous_green].yellow > 0:
            #     inter.signals[inter.simultaneous_green].yellow -= 1
            #     # reset stops for vehicles in these directions so they can go fully
            #     for lane in range(0, 3):
            #         for vehicle in inter.vehicles[inter.DIRECTION_MAP[inter.simultaneous_green]][lane]:
            #             vehicle.stop = inter.DEFAULT_STOP[inter.DIRECTION_MAP[inter.simultaneous_green]]
            # time.sleep(1)
# --------------------------
# === Vehicle generator (global, puts into either intersection) ===
# --------------------------
def vehicle_generator_loop():
    spawn_interval = 0.25
    spawn_counter = 0

    while True:
        # choose intersection randomly
        inter = random.choice(INTERSECTIONS)
        # inter  = INTERSECTIONS[0]

        # pick lane (1 or 2)
        lane_number = random.randint(0, 2)

        # turning logic based on lane
        if lane_number in (0, 2):
            will_turn = 1
        else:  # lane_number == 1
            will_turn = 0
        # will_turn = 0

        # random vehicle type
        vehicle_idx = random.choice(inter.allowed_vehicle_type_indices)

        # pick direction only from allowed list
        direction = random.choice(inter.allowed_spawn_directions)
        # convert direction string to number using DIRECTION_MAP
        direction_number = [k for k, v in inter.DIRECTION_MAP.items() if v == direction][0]

        # create vehicle
        Vehicle(inter, lane_number, VEHICLE_TYPES[vehicle_idx], direction_number, direction, will_turn)

        # increment spawn count
        inter.SPAWN_COUNTS[direction][lane_number] += 1
        # spawn_counter += 1

        time.sleep(spawn_interval)
        # break
        # if spawn_counter > 10:
        #     break


# --------------------------
# === Timer thread ===
# --------------------------
def simulation_timer_loop():
    global time_elapsed
    while True:
        time.sleep(1)
        time_elapsed += 1
        if time_elapsed == SIMULATION_TIME:
            show_stats_and_exit()

def show_stats_and_exit():
    total = 0
    print('Intersection-wise Vehicle Counts:')
    for inter in INTERSECTIONS:
        print(f"Intersection {inter.name}:")
        for dname in ['right','down','left','up']:
            print(f"  {dname}: {inter.vehicles[dname]['crossed']}")
            total += inter.vehicles[dname]['crossed']
    print('Total vehicles passed:', total)
    print('Total time:', time_elapsed)
    os._exit(0)

# --------------------------
# === Drawing helpers ===
# --------------------------
def draw_lane_state_table(screen, font, lane_state, x=850, y=100, row_height=30):
    col_widths = [100, 100, 100, 100]
    headers = ["Direction", "Spawned", "Crossed", "Remaining"]
    for col, header in enumerate(headers):
        rect = pygame.Rect(x + sum(col_widths[:col]), y, col_widths[col], row_height)
        pygame.draw.rect(screen, (50,50,50), rect)
        pygame.draw.rect(screen, (255,255,255), rect, 2)
        text_surf = font.render(header, True, (255,255,255))
        screen.blit(text_surf, (rect.x + 5, rect.y + 5))

    for row_index, direction in enumerate(lane_state):
        data = lane_state[direction]
        row_y = y + row_height * (row_index + 1)
        for col, value in enumerate([direction.capitalize(), data['spawned'], data['crossed'], data['remaining']]):
            rect = pygame.Rect(x + sum(col_widths[:col]), row_y, col_widths[col], row_height)
            pygame.draw.rect(screen, (200,200,200), rect)
            pygame.draw.rect(screen, (255,255,255), rect, 2)
            text_surf = font.render(str(value), True, (0,0,0))
            screen.blit(text_surf, (rect.x + 5, rect.y + 5))

def draw_signals_table(screen, font, inter: Intersection, x=50, y=50, row_height=30):
    col_widths = [100, 100, 100, 100]
    headers = ["Direction", "Status", "Green Duration", "Countdown"]
    for col, header in enumerate(headers):
        rect = pygame.Rect(x + sum(col_widths[:col]), y, col_widths[col], row_height)
        pygame.draw.rect(screen, (50, 50, 50), rect)
        pygame.draw.rect(screen, (255, 255, 255), rect, 2)
        text_surf = font.render(header, True, (255, 255, 255))
        screen.blit(text_surf, (rect.x + 5, rect.y + 5))

    for i, ts in enumerate(inter.signals):
        row_y = y + row_height * (i + 1)
        if i == inter.current_green:
            if inter.current_yellow:
                status = "YELLOW"
                countdown = ts.yellow
            else:
                status = "GREEN"
                countdown = ts.green
        elif i == inter.simultaneous_green:
            if inter.current_yellow:
                status = "YELLOW-LEFT"
                countdown = ts.yellow
            else:
                status = "GREEN-LEFT"
                countdown = ts.green
        else:
            status = "RED"
            countdown = ts.red

        row_values = [inter.DIRECTION_LABELS[inter.DIRECTION_MAP[i]], status, ts.green, countdown]
        for col, value in enumerate(row_values):
            rect = pygame.Rect(x + sum(col_widths[:col]), row_y, col_widths[col], row_height)
            if col == 1:
                color_map = {
                    "RED": (200, 0, 0),
                    "YELLOW": (255, 255, 0),
                    "GREEN": (0, 200, 0),
                    "GREEN-LEFT": (0, 150, 0),
                    "YELLOW-LEFT": (200, 200, 0)
                }
                pygame.draw.rect(screen, color_map.get(value, (200, 200, 200)), rect)
            else:
                pygame.draw.rect(screen, (200, 200, 200), rect)
            pygame.draw.rect(screen, (255, 255, 255), rect, 2)
            text_surf = font.render(str(value), True, (0, 0, 0))
            screen.blit(text_surf, (rect.x + 5, rect.y + 5))

def draw_summary_table(screen, font, lane_state, time_elapsed, x=850, y=300, row_height=30, col_widths=[150, 150]):
    headers = ["Metric", "Value"]
    for col, header in enumerate(headers):
        rect = pygame.Rect(x + sum(col_widths[:col]), y, col_widths[col], row_height)
        pygame.draw.rect(screen, (50,50,50), rect)
        pygame.draw.rect(screen, (255,255,255), rect, 2)
        text_surf = font.render(header, True, (255,255,255))
        screen.blit(text_surf, (rect.x + 5, rect.y + 5))

    total_crossed = sum(lane_state[d]['crossed'] for d in lane_state)
    metrics = [ ("Time (s)", time_elapsed), ("Crossed (v)", total_crossed)]
    for row_index, (metric, value) in enumerate(metrics):
        row_y = y + row_height * (row_index + 1)
        for col, cell_value in enumerate([metric, value]):
            rect = pygame.Rect(x + sum(col_widths[:col]), row_y, col_widths[col], row_height)
            pygame.draw.rect(screen, (200,200,200), rect)
            pygame.draw.rect(screen, (255,255,255), rect, 2)
            text_surf = font.render(str(cell_value), True, (0,0,0))
            screen.blit(text_surf, (rect.x + 5, rect.y + 5))

# --------------------------
# === Main / pygame loop ===
# --------------------------
def main(start_pygame=True):
    global startup_time, startup_mode, time_elapsed

    if start_pygame:
        red_img = load_image_safe('images/signals/red.png', (40,40))
        yellow_img = load_image_safe('images/signals/yellow.png', (40,40))
        green_img = load_image_safe('images/signals/green.png', (40,40))
        font = pygame.font.SysFont("Arial", 15)

        # start threads
        threading.Thread(target=vehicle_generator_loop, daemon=True).start()
        threading.Thread(target=simulation_timer_loop, daemon=True).start()

        # start dynamic signal controllers for both intersections after startup
        def start_controllers_after_delay():
            global startup_mode
            time.sleep(STARTUP_DELAY)
            for inter in INTERSECTIONS:
                threading.Thread(target=dynamic_signal_controller, args=(inter,), daemon=True).start()
                # print("t")
            startup_mode = False

        threading.Thread(target=start_controllers_after_delay, daemon=True).start()

        clock = pygame.time.Clock()
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    show_stats_and_exit()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_d:
                        global DEBUG_MODE
                        DEBUG_MODE = not DEBUG_MODE
                        print("DEBUG MODE:", DEBUG_MODE)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    print("Mouse clicked at:", event.pos)
            screen.blit(background, (0,0))

            # draw each intersection's signals and vehicles
            for inter in INTERSECTIONS:
                # draw signals icons
                for i in range(inter.no_of_signals):
                    ts = inter.signals[i]
                    if startup_mode:
                        ts.signal_text = ts.red if ts.red <= 10 else "---"
                        screen.blit(red_img, inter.SIGNAL_COORDS[i])
                    else:
                        if i == inter.current_green or i == inter.simultaneous_green:
                            if inter.current_yellow:
                                ts.signal_text = ts.yellow
                                screen.blit(yellow_img, inter.SIGNAL_COORDS[i])
                            else:
                                ts.signal_text = ts.green
                                screen.blit(green_img, inter.SIGNAL_COORDS[i])
                        else:
                            ts.signal_text = ts.red if ts.red <= 10 else "---"
                            screen.blit(red_img, inter.SIGNAL_COORDS[i])

                # update lane state
                for direction in inter.SPAWN_COUNTS:
                    spawned_total = inter.SPAWN_COUNTS[direction][0] + inter.SPAWN_COUNTS[direction][1] + inter.SPAWN_COUNTS[direction][2]
                    crossed_total = inter.vehicles[direction]['crossed'][0] + inter.vehicles[direction]['crossed'][1] + inter.vehicles[direction]['crossed'][2]
                    inter.LANE_STATE[direction]['spawned'] = spawned_total
                    inter.LANE_STATE[direction]['crossed'] = crossed_total
                    inter.LANE_STATE[direction]['remaining'] = spawned_total - crossed_total

                # draw signal table for this intersection
                # offset the table X so it does not overlap
                table_x = 50 if inter.name == "A" else 350
                # draw_signals_table(screen, font, inter, x=table_x, y=50)

                # move + render vehicles in the intersection
                for _ in range(1):
                    for vehicle in list(inter.simulation):
                        vehicle.render(screen)
                        vehicle.move()

                # debug visuals (stoplines)
                if DEBUG_MODE:
                    # Stop lines
                    # for d, coord in inter.STOP_LINES.items():
                    #     if d in ['right', 'left']:
                    #         pygame.draw.line(screen, (255, 0, 0), (coord, 0), (coord, SCREEN_HEIGHT), 2)
                    #     else:
                    #         pygame.draw.line(screen, (0, 255, 0), (0, coord), (SCREEN_WIDTH, coord), 2)

                    # Spawn lanes (lines + points)
                    for direction in inter.START_X:
                        for lane in range(3):
                            x = inter.START_X[direction][lane]
                            y = inter.START_Y[direction][lane]

                            # draw spawn point
                            pygame.draw.circle(screen, (0, 0, 255), (int(x), int(y)), 5)

                            # draw line from spawn to stop line or midpoint
                            if direction == "right":
                                end_x = inter.STOP_LINES["right"]
                                end_y = y
                            elif direction == "left":
                                end_x = inter.STOP_LINES["left"]
                                end_y = y
                            elif direction == "down":
                                end_x = x
                                end_y = inter.STOP_LINES["down"]
                            elif direction == "up":
                                end_x = x
                                end_y = inter.STOP_LINES["up"]

                            pygame.draw.line(screen, (0, 0, 200), (int(x), int(y)), (int(end_x), int(end_y)), 2)

                    # Midpoints (turn reference points)
                    for direction, mid in inter.MID.items():
                        pygame.draw.circle(screen, (255, 255, 0), (int(mid['x']), int(mid['y'])), 6)   
                        
                    for name, rect in inter.ENTRY_ZONES.items():
                        pygame.draw.rect(screen, (255, 165, 0), rect, 2)  # orange outline
                            # label zone
                        label = font.render(f"{inter.name}-{name}", True, (255,165,0))
                        screen.blit(label, (rect.x, rect.y - 15))
                        
                    # for name, rect in inter.EXIT_ZONES.items():
                    #     pygame.draw.rect(screen, (0, 255, 0), rect, 2)  # green outline
                    #     label = font.render(f"{inter.name}-exit-{name}", True, (0,255,0))
                    #     screen.blit(label, (rect.x, rect.y - 15))

                # draw small lane state table per intersection
                # summary_x = 850 if inter.name == "A" else 1100
                # draw_lane_state_table(screen, font, inter.LANE_STATE, x=summary_x, y=50)
                # draw_summary_table(screen, font, inter.LANE_STATE, time_elapsed, x=summary_x, y=250)

            # copy frame to FRAME_QUEUE for streaming
            if FRAME_QUEUE.empty():
                FRAME_QUEUE.put(pygame.surfarray.make_surface(pygame.surfarray.array3d(screen)))

            pygame.display.update()
            clock.tick(60)

if __name__ == "__main__":
    main()