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
import os
import queue
import uuid

# Global list to store all vehicles
VEHICLE_LIST = []
STOP_FLAG = False
USER_OVERRIDE_DIR = None  

FRAME_QUEUE = queue.Queue(maxsize=1)  # Only keep the latest frame
DEBUG_MODE = False
SIM_STARTED = False

pygame.init()

# --------------------------
# === Configuration ===
# --------------------------
# Default times (seconds)
DEFAULT_GREEN = 30  # green durations for each signal index
DEFAULT_RED = 60
DEFAULT_YELLOW = 2

SHARED_SCREEN = None

# Enable randomized green durations between this range (inclusive)
RANDOM_GREEN = True
RANDOM_GREEN_RANGE = (10, 20)  # (min, max)

# Simulation time and UI positions
SIMULATION_TIME = 300         # total simulation seconds before auto-stop
TIME_ELAPSED_COORDS = (1100, 50)

# Visual layout coords (must match your images/intersection)

info = pygame.display.Info()
BACKGROUND_PATH = "images/33191.jpg"
SCREEN_WIDTH, SCREEN_HEIGHT = info.current_w, info.current_h

# Signal icon positions (for blitting red/yellow/green images)
SIGNAL_COORDS = [(445, 290), (810, 290), (810, 644), (445, 644)]
SIGNAL_TIMER_COORDS = [(530, 210), (810, 210), (810, 550), (530, 550)]
VEHICLE_COUNT_COORDS = [(480, 210), (880, 210), (880, 550), (480, 550)]

# Stop-lines and default stops (where vehicles should stop when light is red)
STOP_LINES = {'right': 508, 'down': 408, 'left': 776, 'up': 612}
DEFAULT_STOP = {'right': 498, 'down': 398, 'left': 786, 'up': 622}

# Movement gaps
STOPPING_GAP = 25    # px gap when stopped
MOVING_GAP = 25      # px gap when moving

# Vehicle speeds (pixels per tick)
SPEEDS = {'car': 2.5, 'bus': 2, 'truck': 2, 'bike': 2.75}
AVG_SPEED = 2.35

# Starting coordinates per direction (x and y lists for lane offsets)
START_X = {'right': [0, 0, 0], 'down': [736, 693, 650], 'left': [1400, 1400, 1400], 'up': [511, 554, 597]}
START_Y = {'right': [410, 443, 476], 'down': [0, 0, 0], 'left': [581, 548, 515], 'up': [1023, 1023, 1203]}

SPAWN_COUNTS = {
    'up':    {0: 0, 1: 0, 2: 0},
    'down':  {0: 0, 1: 0, 2: 0},
    'left':  {0: 0, 1: 0, 2: 0},
    'right': {0: 0, 1: 0, 2: 0}
}
simulation = pygame.sprite.Group()
# Mid points used in turning logic (approximate pivot coords)
MID = {
    'right': {'x': 670, 'y': 445},
    'down':  {'x': 695, 'y': 530},
    'left':  {'x': 640, 'y': 405},
    'up':    {'x': 685, 'y': 500},
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
SUGGESTION = ""


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
vehicles_turned = {'right': {0: [], 1: [], 2: []}, 'down': {0: [], 1: [], 2: []}, 'left': {0: [], 1: [], 2: []}, 'up': {0: [], 1: [], 2: []}}
vehicles_not_turned = {'right': {0: [], 1: [], 2: []}, 'down': {0: [], 1: [], 2: []}, 'left': {0: [], 1: [], 2: []}, 'up': {0: [], 1: [], 2: []}}

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

SECONDS_PER_VEHICLE = 0.5 # Green duration per remaining vehicle
SPAWN_INTERVAL = 0.5
MIN_GREEN_DURATION = 2   # Minimum green phase in seconds
MAX_GREEN = 30
last_green = None     



# --------------------------
# === Helper Classes ===
# --------------------------

def is_green_for(direction_number, lane=None, will_turn=None):
    global current_green, current_yellow
    
    if current_yellow == 1:
        return False

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
        
    def to_dict(self):
        return {
            "red": self.red,
            "yellow": self.yellow,
            "green": self.green,
            "signal-text": self.signal_text
            # include other attributes you want to save
        }

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
            if self.lane == 0:
                # close to stop line and not rotated yet -> either move straight or begin turn
                if self.crossed == 0 or (self.x + self.image.get_rect().width < STOP_LINES[self.direction] + 10):
                    # allowed to move forward if before stop or green or already crossed, and gap maintained
                    if ((self.x + self.image.get_rect().width <= self.stop or is_green_for(0, self.lane, self.will_turn) or self.crossed == 1)
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
                if ((self.x + self.image.get_rect().width <= self.stop or  is_green_for(0, self.lane, self.will_turn))
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
            if self.lane == 0:
                if self.crossed == 0 or (self.y + self.image.get_rect().height < STOP_LINES[self.direction] + 25):
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
            if self.lane == 0:
                if self.crossed == 0 or (self.x > STOP_LINES[self.direction]):
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
            if self.lane == 0:
                if self.crossed == 0 or (self.y > STOP_LINES[self.direction]):
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
        total_spawned = SPAWN_COUNTS[direction][0] + SPAWN_COUNTS[direction][1] + SPAWN_COUNTS[direction][2]
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

def vehicle_generator_loop():
    global SPAWN_INTERVAL, SPAWN_COUNTS, DIRECTION_MAP, current_green

    directions = ['up', 'down', 'left', 'right']  # matches DIRECTION_MAP
    spawn_interval = SPAWN_INTERVAL  # seconds between spawns

    while True:
        green_dir = DIRECTION_MAP[current_green] if current_green is not None else None
        spawn_choices = [d for d in directions if green_dir is None or d != green_dir]

        if not spawn_choices:
            time.sleep(spawn_interval)
            continue

        direction = random.choice(spawn_choices)
        lane_number = random.randint(0, 2)
        will_turn = 1 if lane_number in (0, 2) else 0

        vehicle_idx = random.choice(list(VEHICLE_TYPES.keys()))
        vehicle_type = VEHICLE_TYPES[vehicle_idx]
        speed = SPEEDS[vehicle_type]
        
        Vehicle(lane_number, VEHICLE_TYPES[vehicle_idx], 0, direction, will_turn)

        # increment count for this lane
        SPAWN_COUNTS[direction][lane_number] += 1

        # --- Add vehicle with UUID ---
        vehicle_data = {
            "id": str(uuid.uuid4()),  # generate a unique UUID
            "lane_number": lane_number,
            "will_turn": will_turn,
            "direction": direction,
            "vehicle_type": vehicle_type,
            "speed": speed
        }

        VEHICLE_LIST.append(vehicle_data)

        # optional debug
        # print(f"Spawned vehicle: {vehicle_data}")

        time.sleep(spawn_interval)

def show_stats_and_exit():
    global SIM_STARTED
    """Print direction-wise counts and exit the program."""
    total = 0
    print('Direction-wise Vehicle Counts')
    for i in range(4):
        print('Direction', i + 1, ':', vehicles[DIRECTION_MAP[i]]['crossed'])
        total += vehicles[DIRECTION_MAP[i]]['crossed']
    print('Total vehicles passed:', total)
    print('Total time:', time_elapsed)
    SIM_STARTED = False
    # os._exit(1)

def simulation_timer_loop():
    """Counts elapsed seconds and stops the simulation when SIMULATION_TIME reached."""
    global time_elapsed
    while True:
        time.sleep(1)
        time_elapsed += 1
        # if time_elapsed == SIMULATION_TIME:
        #     show_stats_and_exit()

# --------------------------
# === Pygame UI / Main ===
# --------------------------

def dynamic_signal_controller():
    """
    Dynamic signal control with simultaneous green logic.
    """
    global current_green, current_yellow, last_green, SIGNAL_CONTROL_RUNNING, signals, simultaneous_green, USER_OVERRIDE_DIR, SUGGESTION
    
    Map = {
        'left': "East",
        "right": 'West',
        'up': 'South',
        'down': 'North'
    }

    SIGNAL_CONTROL_RUNNING = True
    while SIGNAL_CONTROL_RUNNING:
            chosen_dir = None
            
            # remaining_counts = {d: LANE_STATE[d]["remaining"] for d in LANE_STATE}
            # sorted_dirs = sorted(remaining_counts.items(), key=lambda x: x[1], reverse=True)

            # for dir_name, count in sorted_dirs:
            #     if dir_name != last_green:
            #         suggested_dir, suggested_count = dir_name, count
            #         break
            # else:
            #     suggested_dir, suggested_count = sorted_dirs[0]

            # # duration suggestion
            # green_duration = max(MIN_GREEN_DURATION, int(suggested_count * SECONDS_PER_VEHICLE))
            # green_duration = min(green_duration, MAX_GREEN)

            # # 💡 store suggestion for frontend
            # SUGGESTION = f"Suggested: {Map[suggested_dir]} - ({suggested_count} vehicles) - ({green_duration} seconds)"

            # 1️⃣ Wait for user input
            while USER_OVERRIDE_DIR is None and SIGNAL_CONTROL_RUNNING:
                time.sleep(0.2)  # idle until user gives a command

            if not SIGNAL_CONTROL_RUNNING:
                break

            # 2️⃣ Use user-selected direction
            chosen_dir = USER_OVERRIDE_DIR
            USER_OVERRIDE_DIR = None  # reset so it waits for next command

            green_duration = DEFAULT_GREEN

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
                    for lane in range(0, 3):
                        for vehicle in vehicles[DIRECTION_MAP[current_green]][lane]:
                            vehicle.stop = DEFAULT_STOP[DIRECTION_MAP[current_green]]
                        for vehicle in vehicles[DIRECTION_MAP[simultaneous_green]][lane]:
                            vehicle.stop = DEFAULT_STOP[DIRECTION_MAP[simultaneous_green]]

                # Update red timers for other signals
                for i in range(no_of_signals):
                    if i not in [current_green, simultaneous_green]:
                        signals[i].red = signals[current_green].green + signals[current_green].yellow
                time.sleep(1)

def dynamic_suggestions_controller():
    """
    Dynamic signal control with simultaneous green logic.
    """
    global current_green, current_yellow, last_green, SIGNAL_CONTROL_RUNNING, signals, simultaneous_green, USER_OVERRIDE_DIR, SUGGESTION
    
    Map = {
        'left': "East",
        "right": 'West',
        'up': 'South',
        'down': 'North'
    }

    SIGNAL_CONTROL_RUNNING = True
    while SIGNAL_CONTROL_RUNNING:
            
            remaining_counts = {d: LANE_STATE[d]["remaining"] for d in LANE_STATE}
            sorted_dirs = sorted(remaining_counts.items(), key=lambda x: x[1], reverse=True)

            for dir_name, count in sorted_dirs:
                if dir_name != last_green:
                    suggested_dir, suggested_count = dir_name, count
                    break
            else:
                suggested_dir, suggested_count = sorted_dirs[0]

            # duration suggestion
            green_duration = max(MIN_GREEN_DURATION, int(suggested_count * SECONDS_PER_VEHICLE))
            green_duration = min(green_duration, MAX_GREEN)

            # 💡 store suggestion for frontend
            SUGGESTION = f"Suggested: {Map[suggested_dir]} - ({suggested_count} vehicles) - ({green_duration} seconds)"

            time.sleep(3)

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
def main(start_pygame=True, stop_flag=lambda: False):
    while not STOP_FLAG:
        if start_pygame:
            global allowed_vehicle_type_indices, startup_mode, SPAWN_COUNTS, LANE_STATE, time_elapsed, current_green, current_yellow, simultaneous_green, LATEST_FRAME
            global signals, no_of_signals, startup_time, SHARED_SCREEN, SIM_STARTED
            
            SIM_STARTED = True

            allowed_vehicle_type_indices = [i for i, name in VEHICLE_TYPES.items() if ALLOWED_VEHICLE_TYPES.get(name, False)]
            screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
            pygame.display.set_caption("TRAFFIC SIMULATION")
            SHARED_SCREEN = screen
            background = pygame.image.load(BACKGROUND_PATH)
            background = pygame.transform.scale(background, (SCREEN_WIDTH, SCREEN_HEIGHT))
            red_img = pygame.image.load('images/signals/red.png')
            yellow_img = pygame.image.load('images/signals/yellow.png')
            green_img = pygame.image.load('images/signals/green.png')
            font = pygame.font.SysFont("Arial", 15)


            initialize_signals()

            threading.Thread(target=vehicle_generator_loop, daemon=True).start()
            threading.Thread(target=simulation_timer_loop, daemon=True).start()

            clock = pygame.time.Clock()
            while True:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        show_stats_and_exit()
                    elif event.type == pygame.MOUSEBUTTONDOWN:
                        print("Mouse clicked at:", event.pos)
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_d:
                            global DEBUG_MODE
                            DEBUG_MODE = not DEBUG_MODE
                            print("DEBUG MODE:", DEBUG_MODE)

                # Start dynamic signals after startup delay
                if time.time() - startup_time >= STARTUP_DELAY and not hasattr(initialize_signals, "done"):
                    initialize_signals.done = True
                    threading.Thread(target=dynamic_signal_controller, daemon=True).start()
                    threading.Thread(target=dynamic_suggestions_controller, daemon=True).start()
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

                # Update LANE_STATE for remaining vehicles (dummy placeholder)
                for direction in SPAWN_COUNTS:
                    spawned_total = SPAWN_COUNTS[direction][0] + SPAWN_COUNTS[direction][1] + SPAWN_COUNTS[direction][2]
                    crossed_total = vehicles[direction]['crossed']
                    LANE_STATE[direction]['spawned'] = spawned_total
                    LANE_STATE[direction]['crossed'] = crossed_total
                    LANE_STATE[direction]['remaining'] = spawned_total - crossed_total
                    # draw_lane_state_table(screen, font, LANE_STATE, x=900, y=100)
                    
                # After drawing signals & vehicle table, add:
                # draw_signals_table(screen, font, signals, current_green, current_yellow, sim_green=simultaneous_green, x=75, y=100)
                # draw_summary_table(screen, font, lane_state=LANE_STATE)
                # draw_summary_table(screen, font, LANE_STATE, time_elapsed, x=900, y=600)

                # draw_signals_table(screen, font)

                # Draw and move vehicles
                for _ in range(1):
                    for vehicle in list(simulation):
                        vehicle.render(screen)
                        vehicle.move()
                    
                # for vehicle in list(simulation):
                #     vehicle.render(screen)
                #     vehicle.move()
                
                # Draw stop lines for debugging
                # for d, coord in STOP_LINES.items():
                #     if d in ['right', 'left']:
                #         pygame.draw.line(screen, (255, 0, 0), (coord, 0), (coord, SCREEN_HEIGHT), 2)
                #     else:
                #         pygame.draw.line(screen, (0, 255, 0), (0, coord), (SCREEN_WIDTH, coord), 2)
                        
                if DEBUG_MODE:
                    # # --- Stop lines (red) ---
                    # for d, coord in STOP_LINES.items():
                    #     if d in ['right', 'left']:  # vertical
                    #         pygame.draw.line(screen, (255, 0, 0), (coord, 0), (coord, SCREEN_HEIGHT), 2)
                    #     else:  # horizontal
                    #         pygame.draw.line(screen, (255, 0, 0), (0, coord), (SCREEN_WIDTH, coord), 2)

                    # # --- Default stop positions (blue dots) ---
                    # for d, coord in DEFAULT_STOP.items():
                    #     if d in ['right', 'left']:
                    #         pygame.draw.circle(screen, (0, 0, 255), (coord, SCREEN_HEIGHT//2), 5)
                    #     else:
                    #         pygame.draw.circle(screen, (0, 0, 255), (SCREEN_WIDTH//2, coord), 5)

                    # --- Spawn points (cyan dots) ---
                    for direction in START_X:
                        for i in range(3):
                            pygame.draw.circle(screen, (0, 255, 255), (START_X[direction][i], START_Y[direction][i]), 6)

                    # --- Lane center lines (magenta) ---
                    for direction in START_X:
                        for i in range(3):
                            if direction in ['right', 'left']:  # horizontal roads
                                y = START_Y[direction][i]
                                pygame.draw.line(screen, (255, 0, 255), (0, y), (SCREEN_WIDTH, y), 1)
                            else:  # vertical roads
                                x = START_X[direction][i]
                                pygame.draw.line(screen, (255, 0, 255), (x, 0), (x, SCREEN_HEIGHT), 1)

                    # --- Turning pivot points (yellow) ---
                    # for d, pos in MID.items():
                    #     pygame.draw.circle(screen, (255, 255, 0), (pos['x'], pos['y']), 8)


                pygame.display.update()
                # frame_data = pygame.surfarray.array3d(screen)
                    
                # Update the placeholder with the new frame.
                # frame_placeholder.image(frame_data, channels="RGB", use_column_width=True)
                
                # Copy the screen for streaming (non-blocking)
                if FRAME_QUEUE.empty():
                        FRAME_QUEUE.put(pygame.surfarray.make_surface(pygame.surfarray.array3d(screen)))
                clock.tick(120)
        
    
if __name__ == "__main__":
    # Start Pygame simulation
    main()