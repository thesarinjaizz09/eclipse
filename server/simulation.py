"""
Refactored Traffic Signal Simulation (Pygame)
- Logic preserved from original implementation (vehicle spawn, stop/turn behavior, signal cycling).
- Cleaner structure: helper functions, clearer naming, fewer duplications.
- Line-level and block-level comments added for readability.
"""

import random
import time
import threading
import pygame
import sys
import os

# --------------------------
# === Configuration ===
# --------------------------
# Default times (seconds)
DEFAULT_GREEN = {0: 10, 1: 10, 2: 10, 3: 10}  # green durations for each signal index
DEFAULT_RED = 60
DEFAULT_YELLOW = 1

# Enable randomized green durations between this range (inclusive)
RANDOM_GREEN = True
RANDOM_GREEN_RANGE = (10, 20)  # (min, max)

# Simulation time and UI positions
SIMULATION_TIME = 300         # total simulation seconds before auto-stop
TIME_ELAPSED_COORDS = (1100, 50)

# Visual layout coords (must match your images/intersection)

SCREEN_WIDTH, SCREEN_HEIGHT = 1400, 800
BACKGROUND_PATH = "images/intersection.png"

# Signal icon positions (for blitting red/yellow/green images)
SIGNAL_COORDS = [(530, 230), (810, 230), (810, 570), (530, 570)]
SIGNAL_TIMER_COORDS = [(530, 210), (810, 210), (810, 550), (530, 550)]
VEHICLE_COUNT_COORDS = [(480, 210), (880, 210), (880, 550), (480, 550)]

# Stop-lines and default stops (where vehicles should stop when light is red)
STOP_LINES = {'right': 590, 'down': 330, 'left': 800, 'up': 535}
DEFAULT_STOP = {'right': 580, 'down': 320, 'left': 810, 'up': 545}

# Movement gaps
STOPPING_GAP = 25    # px gap when stopped
MOVING_GAP = 25      # px gap when moving

# Vehicle speeds (pixels per tick)
SPEEDS = {'car': 2.5, 'bus': 2, 'truck': 2, 'bike': 2.75}

# Starting coordinates per direction (x and y lists for lane offsets)
START_X = {'right': [0, 0, 0], 'down': [755, 727, 697], 'left': [1400, 1400, 1400], 'up': [602, 627, 657]}
START_Y = {'right': [348, 370, 398], 'down': [0, 0, 0], 'left': [498, 466, 436], 'up': [800, 800, 800]}

SPAWN_COUNTS = {
    'up':    {1: 0, 2: 0},
    'down':  {1: 0, 2: 0},
    'left':  {1: 0, 2: 0},
    'right': {1: 0, 2: 0}
}
simulation = pygame.sprite.Group()
# Mid points used in turning logic (approximate pivot coords)
MID = {
    'right': {'x': 705, 'y': 445},
    'down':  {'x': 695, 'y': 450},
    'left':  {'x': 695, 'y': 425},
    'up':    {'x': 695, 'y': 400},
}

# Which vehicle types are enabled
ALLOWED_VEHICLE_TYPES = {'car': True, 'bus': True, 'truck': True, 'bike': True}
# map integer -> vehicle type name (used by older logic)
VEHICLE_TYPES = {0: 'car', 1: 'bus', 2: 'truck', 3: 'bike'}

# Direction mapping: index -> direction string
DIRECTION_MAP = {0: 'right', 1: 'down', 2: 'left', 3: 'up'}
DIRECTION_LABELS = {
    'up': 'South',
    'down': 'North',
    'left': 'East',
    'right': 'West'
}
# put this at the top of your file
LANE_STATE = {
    "up": {"label": "North", "spawned": 0, "crossed": 0, "remaining": 0},
    "down": {"label": "South", "spawned": 0, "crossed": 0, "remaining": 0},
    "left": {"label": "West", "spawned": 0, "crossed": 0, "remaining": 0},
    "right": {"label": "East", "spawned": 0, "crossed": 0, "remaining": 0}
}


# Rotation used when a vehicle turns (degrees per frame)
ROTATION_ANGLE = 3

STARTUP_DELAY = 5  # seconds
startup_time = None
startup_mode = True

# --------------------------
# === Global Simulation State ===
# --------------------------
# Signal objects (list of TrafficSignal)
signals = []

# Vehicles storage structure:
# vehicles[direction]['lane_index'] -> list of Vehicle instances
# vehicles[direction]['crossed'] -> total crossed count
vehicles = {
    'right': {0: [], 1: [], 2: [], 'crossed': 0},
    'down':  {0: [], 1: [], 2: [], 'crossed': 0},
    'left':  {0: [], 1: [], 2: [], 'crossed': 0},
    'up':    {0: [], 1: [], 2: [], 'crossed': 0}
}

SIMULTANEOUS_MAP = {
    1: 0,  # North allows East
    2: 1,  # East allows South
    3: 2,  # South allows West
    0: 3   # West allows North
}

# Lists to keep track of turned / not-turned vehicles for maintaining gaps after they cross
vehicles_turned = {'right': {1: [], 2: []}, 'down': {1: [], 2: []}, 'left': {1: [], 2: []}, 'up': {1: [], 2: []}}
vehicles_not_turned = {'right': {1: [], 2: []}, 'down': {1: [], 2: []}, 'left': {1: [], 2: []}, 'up': {1: [], 2: []}}

# Mutable start coords (we update them as we spawn vehicles so that next vehicle starts further back)
start_x = {k: list(v) for k, v in START_X.items()}
start_y = {k: list(v) for k, v in START_Y.items()}

# Simulation control flags
no_of_signals = 4
current_green = None          # which signal index is currently green
simultaneous_green = None          # which signal index is currently green
next_green = None             # which signal index will be green next
current_yellow = 0         # 0->not yellow, 1->yellow active

# Vehicle-spawn helper list (indices corresponding to VEHICLE_TYPES)
allowed_vehicle_type_indices = []

# UI / timing state
time_elapsed = 0

SECONDS_PER_VEHICLE = 1  # Green duration per remaining vehicle
MIN_GREEN_DURATION = 5   # Minimum green phase in seconds
MAX_GREEN = 60
last_green = None     



# --------------------------
# === Helper Classes ===
# --------------------------

def is_green_for(direction_number, lane=None, will_turn=None):
    global current_green

    # ✅ Primary lane always green
    if direction_number == current_green:
        return True

    # ✅ Simultaneous left-turn only
    sim_dir = SIMULTANEOUS_MAP.get(current_green)
    if sim_dir is not None:
        if direction_number == sim_dir and will_turn == 1:
            return True

    return False

class TrafficSignal:
    """Holds remaining red, yellow, green durations and a textual value for display."""
    def __init__(self, red: int, yellow: int, green: int):
        self.red = red
        self.yellow = yellow
        self.green = green
        self.signal_text = ""  # value to display above the signal

class Vehicle(pygame.sprite.Sprite):
    """
    Represents a moving vehicle sprite.
    Important attributes:
      - lane : integer (0,1,2) - lane index
      - vehicle_class : 'car'|'bus'|...
      - direction : 'right'|'down'|'left'|'up'
      - will_turn : 0 or 1 (1 means it intends to turn)
      - turned : 0/1 whether rotation is complete
    """
    def __init__(self, lane, vehicle_class, direction_number, direction, will_turn):
        pygame.sprite.Sprite.__init__(self)
        # basic properties
        self.lane = lane
        self.vehicle_class = vehicle_class
        self.speed = SPEEDS[vehicle_class]
        self.direction_number = direction_number
        self.direction = direction
        self.will_turn = will_turn
        self.turned = 0
        self.rotate_angle = 0
        self.crossed = 0            # set to 1 when vehicle crosses the stop line
        self.crossed_index = 0      # index into vehicles_turned or vehicles_not_turned lists

        # initial coordinates (copy current start positions)
        self.x = start_x[direction][lane]
        self.y = start_y[direction][lane]

        # append to vehicles structure and determine index within lane
        vehicles[direction][lane].append(self)
        self.index = len(vehicles[direction][lane]) - 1

        # load sprite image for this vehicle from images/<direction>/<vehicle>.png
        path = os.path.join("images", direction, f"{vehicle_class}.png")
        self.original_image = pygame.image.load(path)
        self.image = self.original_image.copy()

        # compute stop coordinate based on vehicle ahead (preserve stopping gap)
        self.stop = self._compute_initial_stop()

        # move the spawning start coordinate back so next vehicle spawns a bit behind
        self._advance_spawn_position()

        # add to sprite group for rendering (main simulation group)
        simulation.add(self)

    # ---- helper methods ----
    def _compute_initial_stop(self):
        """
        If there is a vehicle ahead that hasn't crossed, place this vehicle behind it
        maintaining STOPPING_GAP distance. Otherwise return the default stop for direction.
        """
        if len(vehicles[self.direction][self.lane]) > 1:
            prev = vehicles[self.direction][self.lane][self.index - 1]
            if prev.crossed == 0:
                # vehicle-specific coordinate calculations by direction
                if self.direction == 'right':
                    return prev.stop - prev.image.get_rect().width - STOPPING_GAP
                elif self.direction == 'left':
                    return prev.stop + prev.image.get_rect().width + STOPPING_GAP
                elif self.direction == 'down':
                    return prev.stop - prev.image.get_rect().height - STOPPING_GAP
                elif self.direction == 'up':
                    return prev.stop + prev.image.get_rect().height + STOPPING_GAP
        return DEFAULT_STOP[self.direction]

    def _advance_spawn_position(self):
        """Move the global start coordinate so next spawned vehicle doesn't overlap."""
        if self.direction == 'right':
            delta = self.image.get_rect().width + STOPPING_GAP
            start_x[self.direction][self.lane] -= delta
        elif self.direction == 'left':
            delta = self.image.get_rect().width + STOPPING_GAP
            start_x[self.direction][self.lane] += delta
        elif self.direction == 'down':
            delta = self.image.get_rect().height + STOPPING_GAP
            start_y[self.direction][self.lane] -= delta
        elif self.direction == 'up':
            delta = self.image.get_rect().height + STOPPING_GAP
            start_y[self.direction][self.lane] += delta

    # ---- drawing & movement ----
    def render(self, screen):
        """Draw the vehicle image at its current coordinates."""
        screen.blit(self.image, (self.x, self.y))
        
    


    def move(self):
        """
        Core movement logic. This preserves the original behavior:
          - vehicles stop before stop lines during red (unless they crossed)
          - turning vehicles rotate gradually and follow turn trajectory
          - straight vehicles move forward keeping gaps
        The code is separated by direction but comments explain each block.
        """
        # For readability we call small helpers when needed
        dir = self.direction

        # When vehicle first crosses the stop line mark it and record for counting
        if dir == 'right':
            self._handle_crossing(condition=(self.x + self.image.get_rect().width > STOP_LINES[dir]))
            self._move_right()
        elif dir == 'down':
            self._handle_crossing(condition=(self.y + self.image.get_rect().height > STOP_LINES[dir]))
            self._move_down()
        elif dir == 'left':
            self._handle_crossing(condition=(self.x < STOP_LINES[dir]))
            self._move_left()
        elif dir == 'up':
            self._handle_crossing(condition=(self.y < STOP_LINES[dir]))
            self._move_up()

    def _handle_crossing(self, condition: bool):
        """When the front passes the stop-line condition, mark crossed and append to non-turned list if needed."""
        if self.crossed == 0 and condition:
            self.crossed = 1
            vehicles[self.direction]['crossed'] += 1
            if self.will_turn == 0:
                vehicles_not_turned[self.direction][self.lane].append(self)
                self.crossed_index = len(vehicles_not_turned[self.direction][self.lane]) - 1

    # ---- per-direction movement, preserved logic with clearer structure ----
    def _move_right(self):
        """Movement rules for vehicles travelling right -> leftwards screen movement (increasing x)."""
        # If vehicle intends to turn
        if self.will_turn == 1:
            # Lane 1: turn up-left (rotate +)
            if self.lane == 1:
                # close to stop line and not rotated yet -> either move straight or begin turn
                if self.crossed == 0 or (self.x + self.image.get_rect().width < STOP_LINES[self.direction] + 40):
                    # allowed to move forward if before stop or green or already crossed, and gap maintained
                    if ((self.x + self.image.get_rect().width <= self.stop or is_green_for(0) or self.crossed == 1)
                            and (self.index == 0 or (self.x + self.image.get_rect().width < (vehicles[self.direction][self.lane][self.index - 1].x - MOVING_GAP))
                                 or vehicles[self.direction][self.lane][self.index - 1].turned == 1)):
                        self.x += self.speed
                else:
                    # start turning animation
                    if self.turned == 0:
                        self.rotate_angle += ROTATION_ANGLE
                        self.image = pygame.transform.rotate(self.original_image, self.rotate_angle)
                        self.x += 2.4
                        self.y -= 2.8
                        if self.rotate_angle == 90:
                            self.turned = 1
                            vehicles_turned[self.direction][self.lane].append(self)
                            self.crossed_index = len(vehicles_turned[self.direction][self.lane]) - 1
                    else:
                        # after turned, move on new track keeping gap to previously turned vehicle
                        if (self.crossed_index == 0 or
                                self.y > (vehicles_turned[self.direction][self.lane][self.crossed_index - 1].y +
                                          vehicles_turned[self.direction][self.lane][self.crossed_index - 1].image.get_rect().height + MOVING_GAP)):
                            self.y -= self.speed
            # Lane 2: turn down-left (rotate -)
            elif self.lane == 2:
                if self.crossed == 0 or (self.x + self.image.get_rect().width < MID[self.direction]['x']):
                    if ((self.x + self.image.get_rect().width <= self.stop or (current_green==0 and current_yellow==0) or self.crossed == 1)
                            and (self.index == 0 or (self.x + self.image.get_rect().width < (vehicles[self.direction][self.lane][self.index - 1].x - MOVING_GAP))
                                 or vehicles[self.direction][self.lane][self.index - 1].turned == 1)):
                        self.x += self.speed
                else:
                    if self.turned == 0:
                        self.rotate_angle += ROTATION_ANGLE
                        self.image = pygame.transform.rotate(self.original_image, -self.rotate_angle)
                        self.x += 2
                        self.y += 1.8
                        if self.rotate_angle == 90:
                            self.turned = 1
                            vehicles_turned[self.direction][self.lane].append(self)
                            self.crossed_index = len(vehicles_turned[self.direction][self.lane]) - 1
                    else:
                        if (self.crossed_index == 0 or
                                (self.y + self.image.get_rect().height) <
                                (vehicles_turned[self.direction][self.lane][self.crossed_index - 1].y - MOVING_GAP)):
                            self.y += self.speed
        else:
            # Straight-driving (not turning)
            if self.crossed == 0:
                if ((self.x + self.image.get_rect().width <= self.stop or is_green_for(0))
                        and (self.index == 0 or (self.x + self.image.get_rect().width <
                                                (vehicles[self.direction][self.lane][self.index - 1].x - MOVING_GAP)))):
                    self.x += self.speed
            else:
                if (self.crossed_index == 0 or
                        (self.x + self.image.get_rect().width <
                         (vehicles_not_turned[self.direction][self.lane][self.crossed_index - 1].x - MOVING_GAP))):
                    self.x += self.speed

    def _move_down(self):
        """Movement rules for 'down' direction (increasing y)."""
        if self.will_turn == 1:
            # Lane 1: turn right (rotate +)
            if self.lane == 1:
                if self.crossed == 0 or (self.y + self.image.get_rect().height < STOP_LINES[self.direction] + 50):
                    if ((self.y + self.image.get_rect().height <= self.stop or is_green_for(1, self.lane, self.will_turn) or self.crossed == 1)
                            and (self.index == 0 or (self.y + self.image.get_rect().height <
                                                     (vehicles[self.direction][self.lane][self.index - 1].y - MOVING_GAP))
                                 or vehicles[self.direction][self.lane][self.index - 1].turned == 1)):
                        self.y += self.speed
                else:
                    if self.turned == 0:
                        self.rotate_angle += ROTATION_ANGLE
                        self.image = pygame.transform.rotate(self.original_image, self.rotate_angle)
                        self.x += 1.2
                        self.y += 1.8
                        if self.rotate_angle == 90:
                            self.turned = 1
                            vehicles_turned[self.direction][self.lane].append(self)
                            self.crossed_index = len(vehicles_turned[self.direction][self.lane]) - 1
                    else:
                        if (self.crossed_index == 0 or
                                (self.x + self.image.get_rect().width) <
                                (vehicles_turned[self.direction][self.lane][self.crossed_index - 1].x - MOVING_GAP)):
                            self.x += self.speed
            # Lane 2: alternate turn path
            elif self.lane == 2:
                if self.crossed == 0 or (self.y + self.image.get_rect().height < MID[self.direction]['y']):
                    if ((self.y + self.image.get_rect().height <= self.stop or (current_green == 1 and current_yellow == 0) or self.crossed == 1)
                            and (self.index == 0 or (self.y + self.image.get_rect().height <
                                                     (vehicles[self.direction][self.lane][self.index - 1].y - MOVING_GAP))
                                 or vehicles[self.direction][self.lane][self.index - 1].turned == 1)):
                        self.y += self.speed
                else:
                    if self.turned == 0:
                        self.rotate_angle += ROTATION_ANGLE
                        self.image = pygame.transform.rotate(self.original_image, -self.rotate_angle)
                        self.x -= 2.5
                        self.y += 2
                        if self.rotate_angle == 90:
                            self.turned = 1
                            vehicles_turned[self.direction][self.lane].append(self)
                            self.crossed_index = len(vehicles_turned[self.direction][self.lane]) - 1
                    else:
                        if (self.crossed_index == 0 or
                                (self.x > (vehicles_turned[self.direction][self.lane][self.crossed_index - 1].x +
                                           vehicles_turned[self.direction][self.lane][self.crossed_index - 1].image.get_rect().width + MOVING_GAP))):
                            self.x -= self.speed
        else:
            if self.crossed == 0:
                if ((self.y + self.image.get_rect().height <= self.stop or is_green_for(1, self.lane, self.will_turn))
                        and (self.index == 0 or (self.y + self.image.get_rect().height <
                                                 (vehicles[self.direction][self.lane][self.index - 1].y - MOVING_GAP)))):
                    self.y += self.speed
            else:
                if (self.crossed_index == 0 or
                        (self.y + self.image.get_rect().height <
                         (vehicles_not_turned[self.direction][self.lane][self.crossed_index - 1].y - MOVING_GAP))):
                    self.y += self.speed

    def _move_left(self):
        """Movement rules for 'left' direction (decreasing x)."""
        if self.will_turn == 1:
            if self.lane == 1:
                if self.crossed == 0 or (self.x > STOP_LINES[self.direction] - 70):
                    if ((self.x >= self.stop or is_green_for(2, self.lane, self.will_turn) or self.crossed == 1)
                            and (self.index == 0 or (self.x > (vehicles[self.direction][self.lane][self.index - 1].x + vehicles[self.direction][self.lane][self.index - 1].image.get_rect().width + MOVING_GAP))
                                 or vehicles[self.direction][self.lane][self.index - 1].turned == 1)):
                        self.x -= self.speed
                else:
                    if self.turned == 0:
                        self.rotate_angle += ROTATION_ANGLE
                        self.image = pygame.transform.rotate(self.original_image, self.rotate_angle)
                        self.x -= 1
                        self.y += 1.2
                        if self.rotate_angle == 90:
                            self.turned = 1
                            vehicles_turned[self.direction][self.lane].append(self)
                            self.crossed_index = len(vehicles_turned[self.direction][self.lane]) - 1
                    else:
                        if (self.crossed_index == 0 or
                                (self.y + self.image.get_rect().height) < (vehicles_turned[self.direction][self.lane][self.crossed_index - 1].y - MOVING_GAP)):
                            self.y += self.speed
            elif self.lane == 2:
                if self.crossed == 0 or (self.x > MID[self.direction]['x']):
                    if ((self.x >= self.stop or (current_green==2 and current_yellow==0) or self.crossed == 1)
                            and (self.index == 0 or (self.x > (vehicles[self.direction][self.lane][self.index - 1].x + vehicles[self.direction][self.lane][self.index - 1].image.get_rect().width + MOVING_GAP))
                                 or vehicles[self.direction][self.lane][self.index - 1].turned == 1)):
                        self.x -= self.speed
                else:
                    if self.turned == 0:
                        self.rotate_angle += ROTATION_ANGLE
                        self.image = pygame.transform.rotate(self.original_image, -self.rotate_angle)
                        self.x -= 1.8
                        self.y -= 2.5
                        if self.rotate_angle == 90:
                            self.turned = 1
                            vehicles_turned[self.direction][self.lane].append(self)
                            self.crossed_index = len(vehicles_turned[self.direction][self.lane]) - 1
                    else:
                        if (self.crossed_index == 0 or
                                self.y > (vehicles_turned[self.direction][self.lane][self.crossed_index - 1].y +
                                          vehicles_turned[self.direction][self.lane][self.crossed_index - 1].image.get_rect().height + MOVING_GAP)):
                            self.y -= self.speed
        else:
            if self.crossed == 0:
                if ((self.x >= self.stop or is_green_for(2, self.lane, self.will_turn))
                        and (self.index == 0 or (self.x > (vehicles[self.direction][self.lane][self.index - 1].x + vehicles[self.direction][self.lane][self.index - 1].image.get_rect().width + MOVING_GAP)))):
                    self.x -= self.speed
            else:
                if (self.crossed_index == 0 or
                        (self.x > (vehicles_not_turned[self.direction][self.lane][self.crossed_index - 1].x +
                                   vehicles_not_turned[self.direction][self.lane][self.crossed_index - 1].image.get_rect().width + MOVING_GAP))):
                    self.x -= self.speed

    def _move_up(self):
        """Movement rules for 'up' direction (decreasing y)."""
        
        if self.will_turn == 1:
            if self.lane == 1:
                if self.crossed == 0 or (self.y > STOP_LINES[self.direction] - 60):
                    if ((self.y >= self.stop or is_green_for(3, self.lane, self.will_turn) or self.crossed == 1)
                            and (self.index == 0 or (self.y > (vehicles[self.direction][self.lane][self.index - 1].y + vehicles[self.direction][self.lane][self.index - 1].image.get_rect().height + MOVING_GAP))
                                 or vehicles[self.direction][self.lane][self.index - 1].turned == 1)):
                        self.y -= self.speed
                else:
                    if self.turned == 0:
                        self.rotate_angle += ROTATION_ANGLE
                        self.image = pygame.transform.rotate(self.original_image, self.rotate_angle)
                        self.x -= 2
                        self.y -= 1.2
                        if self.rotate_angle == 90:
                            self.turned = 1
                            vehicles_turned[self.direction][self.lane].append(self)
                            self.crossed_index = len(vehicles_turned[self.direction][self.lane]) - 1
                    else:
                        if (self.crossed_index == 0 or
                                (self.x > (vehicles_turned[self.direction][self.lane][self.crossed_index - 1].x +
                                           vehicles_turned[self.direction][self.lane][self.crossed_index - 1].image.get_rect().width + MOVING_GAP))):
                            self.x -= self.speed
            elif self.lane == 2:
                if self.crossed == 0 or (self.y > MID[self.direction]['y']):
                    if ((self.y >= self.stop or (current_green == 3 and current_yellow == 0) or self.crossed == 1)
                            and (self.index == 0 or (self.y > (vehicles[self.direction][self.lane][self.index - 1].y + vehicles[self.direction][self.lane][self.index - 1].image.get_rect().height + MOVING_GAP))
                                 or vehicles[self.direction][self.lane][self.index - 1].turned == 1)):
                        self.y -= self.speed
                else:
                    if self.turned == 0:
                        self.rotate_angle += ROTATION_ANGLE
                        self.image = pygame.transform.rotate(self.original_image, -self.rotate_angle)
                        self.x += 1
                        self.y -= 1
                        if self.rotate_angle == 90:
                            self.turned = 1
                            vehicles_turned[self.direction][self.lane].append(self)
                            self.crossed_index = len(vehicles_turned[self.direction][self.lane]) - 1
                    else:
                        if (self.crossed_index == 0 or
                                (self.x < (vehicles_turned[self.direction][self.lane][self.crossed_index - 1].x - vehicles_turned[self.direction][self.lane][self.crossed_index - 1].image.get_rect().width - MOVING_GAP))):
                            self.x += self.speed
        else:
            if self.crossed == 0:
                if ((self.y >= self.stop or is_green_for(3, self.lane, self.will_turn))
                        and (self.index == 0 or (self.y > (vehicles[self.direction][self.lane][self.index - 1].y + vehicles[self.direction][self.lane][self.index - 1].image.get_rect().height + MOVING_GAP)))):
                    self.y -= self.speed
            else:
                if (self.crossed_index == 0 or
                        (self.y > (vehicles_not_turned[self.direction][self.lane][self.crossed_index - 1].y +
                                   vehicles_not_turned[self.direction][self.lane][self.crossed_index - 1].image.get_rect().height + MOVING_GAP))):
                    self.y -= self.speed

# --------------------------
# === Simulation Utilities ===
# --------------------------

def get_remaining_counts():
    remaining = {}
    for direction in SPAWN_COUNTS:
        total_spawned = SPAWN_COUNTS[direction][1] + SPAWN_COUNTS[direction][2]
        total_crossed = vehicles[direction]['crossed']
        remaining[direction] = total_spawned - total_crossed
    return remaining

def initialize_signals():
    """
    Initialize signals but keep all red for STARTUP_DELAY seconds
    (non-blocking, so UI keeps running).
    """
    global signals, next_green, startup_time, startup_mode

    signals.clear()

    # all-red phase first
    ts1 = TrafficSignal(DEFAULT_RED, DEFAULT_YELLOW, 0)
    ts2 = TrafficSignal(DEFAULT_RED, DEFAULT_YELLOW, 0)
    ts3 = TrafficSignal(DEFAULT_RED, DEFAULT_YELLOW, 0)
    ts4 = TrafficSignal(DEFAULT_RED, DEFAULT_YELLOW, 0)
    signals = [ts1, ts2, ts3, ts4]

    startup_time = time.time()  # mark when simulation started
    startup_mode = True  # ensure we are in startup

def spawn_vehicle():
    """
    Spawns a single random vehicle according to allowed vehicle types.
    Uses the same probability rules as original:
      - lane chosen 1 or 2 (not lane 0)
      - 40% chance to be turning for lane 1 and lane 2
      - direction chosen from a random partition using dist thresholds
    """
    vehicle_idx = random.choice(allowed_vehicle_type_indices)  # integer 0..3
    lane_number = random.randint(1, 2)
    will_turn = 0
    if lane_number in (1, 2):
        if random.randint(0, 99) < 40:
            will_turn = 1

    t = random.randint(0, 99)
    # partition thresholds in original: 25% for each direction (0..24,25..49 etc.)
    if t < 25:
        direction_number = 0
    elif t < 50:
        direction_number = 1
    elif t < 75:
        direction_number = 2
    else:
        direction_number = 3

    Vehicle(lane_number, VEHICLE_TYPES[vehicle_idx], direction_number, DIRECTION_MAP[direction_number], will_turn)

def vehicle_generator_loop():
    """
    Thread loop: spawn 1 vehicle every second.
    Each vehicle is assigned a random direction, lane, type, and turn decision.
    """
    directions = ['up', 'down', 'left', 'right']  # matches DIRECTION_MAP
    spawn_interval = 0.7  # seconds between spawns

    global SPAWN_COUNTS, DIRECTION_MAP, current_green

    while True:
        # ✅ Handle startup safely (no KeyError when current_green is None)
        green_dir = DIRECTION_MAP[current_green] if current_green is not None else None

        # pick from directions except the active green
        spawn_choices = [d for d in directions if green_dir is None or d != green_dir]

        if not spawn_choices:
            time.sleep(spawn_interval)
            continue

        # choose random direction
        direction = random.choice(spawn_choices)

        # random lane (1 or 2)
        lane_number = 1 if random.randint(0, 99) < 60 else 2

        # 80% chance to turn
        will_turn = 1 if random.randint(0, 99) < 70 else 0

        # random vehicle type
        vehicle_idx = random.choice(allowed_vehicle_type_indices)

        # create vehicle
        Vehicle(lane_number, VEHICLE_TYPES[vehicle_idx], 0, direction, will_turn)

        # increment count for this lane
        SPAWN_COUNTS[direction][lane_number] += 1

        # debug print (optional)
        # print(
        #     f"Spawned {VEHICLE_TYPES[vehicle_idx]} in {direction} lane {lane_number} "
        #     f"| Total = {SPAWN_COUNTS[direction][lane_number]}"
        # )

        # wait 1 second before next vehicle
        time.sleep(spawn_interval)

def show_stats_and_exit():
    """Print direction-wise counts and exit the program."""
    total = 0
    print('Direction-wise Vehicle Counts')
    for i in range(4):
        print('Direction', i + 1, ':', vehicles[DIRECTION_MAP[i]]['crossed'])
        total += vehicles[DIRECTION_MAP[i]]['crossed']
    print('Total vehicles passed:', total)
    print('Total time:', time_elapsed)
    os._exit(1)

def simulation_timer_loop():
    """Counts elapsed seconds and stops the simulation when SIMULATION_TIME reached."""
    global time_elapsed
    while True:
        time.sleep(1)
        time_elapsed += 1
        if time_elapsed == SIMULATION_TIME:
            show_stats_and_exit()

# --------------------------
# === Pygame UI / Main ===
# --------------------------

def dynamic_signal_controller():
    """
    Dynamic signal control with simultaneous green logic.
    """
    global current_green, current_yellow, last_green, SIGNAL_CONTROL_RUNNING, signals, simultaneous_green

    SIGNAL_CONTROL_RUNNING = True
    while SIGNAL_CONTROL_RUNNING:
        # 1️⃣ Pick next green direction
        remaining_counts = {d: LANE_STATE[d]["remaining"] for d in LANE_STATE}
        sorted_dirs = sorted(remaining_counts.items(), key=lambda x: x[1], reverse=True)
        for dir_name, count in sorted_dirs:
            if dir_name != last_green:
                chosen_dir, chosen_count = dir_name, count
                break
        else:
            chosen_dir, chosen_count = sorted_dirs[0]

        green_duration = max(MIN_GREEN_DURATION, int(chosen_count * SECONDS_PER_VEHICLE))
        green_duration = min(green_duration, MAX_GREEN)

        current_green = [k for k, v in DIRECTION_MAP.items() if v == chosen_dir][0]
        last_green = chosen_dir
        current_yellow = 0

        simultaneous_green = SIMULTANEOUS_MAP[current_green]

        # 2️⃣ Reset all signals first
        for sig in signals:
            sig.green = 0
            sig.yellow = 0
            sig.red = green_duration + DEFAULT_YELLOW

        # 3️⃣ Set active + simultaneous green
        for idx in [current_green, simultaneous_green]:
            signals[idx].green = green_duration
            signals[idx].yellow = DEFAULT_YELLOW
            signals[idx].red = sum(signals[j].green + signals[j].yellow for j in range(no_of_signals) if j not in [idx, current_green, simultaneous_green])

        # 4️⃣ Countdown
        while signals[current_green].green > 0 or signals[current_green].yellow > 0:
            if signals[current_green].green > 0:
                signals[current_green].green -= 1
                signals[simultaneous_green].green -= 1
                current_yellow = 0
            elif signals[current_green].yellow > 0:
                signals[current_green].yellow -= 1
                signals[simultaneous_green].yellow -= 1
                current_yellow = 1

            # Update red timers for other signals
            for i in range(no_of_signals):
                if i not in [current_green, simultaneous_green]:
                    signals[i].red = signals[current_green].green + signals[current_green].yellow

            time.sleep(1)

def draw_lane_state_table(screen, font, lane_state, x=850, y=100, row_height=30):
    """
    Draws a simple table for lane_state data.
    """
    col_widths = [100, 100, 100, 100]  # Increase widths for headers
    
    headers = ["Direction", "Spawned", "Crossed", "Remaining"]
    
    # Header row
    for col, header in enumerate(headers):
        rect = pygame.Rect(x + sum(col_widths[:col]), y, col_widths[col], row_height)
        pygame.draw.rect(screen, (50,50,50), rect)
        pygame.draw.rect(screen, (255,255,255), rect, 2)
        text_surf = font.render(header, True, (255,255,255))
        screen.blit(text_surf, (rect.x + 5, rect.y + 5))
    
    # Data rows
    for row_index, direction in enumerate(lane_state):
        data = lane_state[direction]
        row_y = y + row_height * (row_index + 1)
        for col, value in enumerate([DIRECTION_LABELS[direction], data['spawned'], data['crossed'], data['remaining']]):
            rect = pygame.Rect(x + sum(col_widths[:col]), row_y, col_widths[col], row_height)
            pygame.draw.rect(screen, (200,200,200), rect)
            pygame.draw.rect(screen, (255,255,255), rect, 2)
            text_surf = font.render(str(value), True, (0,0,0))
            screen.blit(text_surf, (rect.x + 5, rect.y + 5))

def draw_signals_table(screen, font, signals, current_green, current_yellow, sim_green, x=50, y=50, row_height=30):
    """
    Draws a live table showing each signal's status.
    - current_green: main green signal index
    - sim_green: lane index that has simultaneous left turn green
    """
    col_widths = [100, 100, 100, 100]  # Column widths
    headers = ["Direction", "Status", "Green Duration", "Countdown"]

    # Draw header row
    for col, header in enumerate(headers):
        rect = pygame.Rect(x + sum(col_widths[:col]), y, col_widths[col], row_height)
        pygame.draw.rect(screen, (50, 50, 50), rect)
        pygame.draw.rect(screen, (255, 255, 255), rect, 2)
        text_surf = font.render(header, True, (255, 255, 255))
        screen.blit(text_surf, (rect.x + 5, rect.y + 5))

    # Draw signal rows
    for i, ts in enumerate(signals):
        row_y = y + row_height * (i + 1)

        # Determine signal status
        if i == current_green:
            if current_yellow:
                status = "YELLOW"
                countdown = ts.yellow
            else:
                status = "GREEN"
                countdown = ts.green
        elif i == sim_green:
            if current_yellow:
                status = "YELLOW-LEFT"
                countdown = ts.yellow  # or separate sim yellow if available
            else:
                status = "GREEN-LEFT"
                countdown = ts.green
        else:
            status = "RED"
            countdown = ts.red

        # Values for row columns
        row_values = [DIRECTION_LABELS[DIRECTION_MAP[i]], status, ts.green, countdown]

        # Draw the row
        for col, value in enumerate(row_values):
            rect = pygame.Rect(x + sum(col_widths[:col]), row_y, col_widths[col], row_height)

            # Coloring for status column
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
    """
    Draws a small summary table showing total vehicles crossed and total time elapsed.
    """
    headers = ["Metric", "Value"]

    # Header row
    for col, header in enumerate(headers):
        rect = pygame.Rect(x + sum(col_widths[:col]), y, col_widths[col], row_height)
        pygame.draw.rect(screen, (50,50,50), rect)  # dark grey header
        pygame.draw.rect(screen, (255,255,255), rect, 2)  # border
        text_surf = font.render(header, True, (255,255,255))
        screen.blit(text_surf, (rect.x + 5, rect.y + 5))

    # Total vehicles crossed
    total_crossed = sum(lane_state[d]['crossed'] for d in lane_state)
    metrics = [ ("Time (s)", time_elapsed), ("Crossed (v)", total_crossed)]

    # Draw metric rows
    for row_index, (metric, value) in enumerate(metrics):
        row_y = y + row_height * (row_index + 1)
        for col, cell_value in enumerate([metric, value]):
            rect = pygame.Rect(x + sum(col_widths[:col]), row_y, col_widths[col], row_height)
            pygame.draw.rect(screen, (200,200,200), rect)  # light grey background
            pygame.draw.rect(screen, (255,255,255), rect, 2)  # border
            text_surf = font.render(str(cell_value), True, (0,0,0))
            screen.blit(text_surf, (rect.x + 5, rect.y + 5))


# ---------------- MAIN LOOP ---------------- #
def main():
    global allowed_vehicle_type_indices, startup_mode, SPAWN_COUNTS

    allowed_vehicle_type_indices = [i for i, name in VEHICLE_TYPES.items() if ALLOWED_VEHICLE_TYPES.get(name, False)]
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("TRAFFIC SIMULATION")

    background = pygame.image.load(BACKGROUND_PATH)
    red_img = pygame.image.load('images/signals/red.png')
    yellow_img = pygame.image.load('images/signals/yellow.png')
    green_img = pygame.image.load('images/signals/green.png')
    font = pygame.font.Font(None, 30)

    initialize_signals()

    threading.Thread(target=vehicle_generator_loop, daemon=True).start()
    threading.Thread(target=simulation_timer_loop, daemon=True).start()

    clock = pygame.time.Clock()
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                show_stats_and_exit()

        # Start dynamic signals after startup delay
        if time.time() - startup_time >= STARTUP_DELAY and not hasattr(initialize_signals, "done"):
            initialize_signals.done = True
            threading.Thread(target=dynamic_signal_controller, daemon=True).start()
            startup_mode = False

        screen.blit(background, (0, 0))

        # Draw signals
        for i in range(no_of_signals):
            ts = signals[i]
            if startup_mode:
                ts.signal_text = ts.red if ts.red <= 10 else "---"
                screen.blit(red_img, SIGNAL_COORDS[i])
            else:
                if i == current_green or i == simultaneous_green:
                    if current_yellow:
                        ts.signal_text = ts.yellow
                        screen.blit(yellow_img, SIGNAL_COORDS[i])
                    else:
                        ts.signal_text = ts.green
                        screen.blit(green_img, SIGNAL_COORDS[i])
                else:
                    ts.signal_text = ts.red if ts.red <= 10 else "---"
                    screen.blit(red_img, SIGNAL_COORDS[i])

        # Draw signal timers
        # for i in range(no_of_signals):
        #     text_surf = font.render(str(signals[i].signal_text), True, (255, 255, 255), (0, 0, 0))
        #     screen.blit(text_surf, SIGNAL_TIMER_COORDS[i])

        # Draw vehicle counts
        # for i in range(no_of_signals):
        #     count = vehicles[DIRECTION_MAP[i]]['crossed']
        #     text_surf = font.render(str(count), True, (0, 0, 0), (255, 255, 255))
        #     screen.blit(text_surf, VEHICLE_COUNT_COORDS[i])

        # Draw elapsed time
        # te_surf = font.render(f"Time Elapsed: {time_elapsed}", True, (0, 0, 0), (255, 255, 255))
        # screen.blit(te_surf, TIME_ELAPSED_COORDS)
        font = pygame.font.SysFont("Arial", 15)
        # Update LANE_STATE for remaining vehicles (dummy placeholder)
        for direction in SPAWN_COUNTS:
            label = DIRECTION_LABELS[direction]
            spawned_total = SPAWN_COUNTS[direction][1] + SPAWN_COUNTS[direction][2]
            crossed_total = vehicles[direction]['crossed']
            LANE_STATE[direction]['spawned'] = spawned_total
            LANE_STATE[direction]['crossed'] = crossed_total
            LANE_STATE[direction]['remaining'] = spawned_total - crossed_total
            draw_lane_state_table(screen, font, LANE_STATE, x=900, y=100)

            # text = f"{label}: Spawned={spawned_total} | Crossed={crossed_total} | Remaining={spawned_total - crossed_total}"
            # surf = font.render(text, True, (0,0,0), (255,255,255))
            # screen.blit(surf, (850, y_offset))
            # y_offset += 30
            
        # After drawing signals & vehicle table, add:
        draw_signals_table(screen, font, signals, current_green, current_yellow, sim_green=simultaneous_green, x=75, y=100)
        draw_summary_table(screen, font, LANE_STATE, time_elapsed, x=900, y=600)

        # draw_signals_table(screen, font)

        # Draw and move vehicles
        for vehicle in list(simulation):
            vehicle.render(screen)
            vehicle.move()

        pygame.display.update()
        clock.tick(60)

if __name__ == "__main__":
    main()