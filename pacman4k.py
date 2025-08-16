#!/usr/bin/env python3
import pygame
import math
import random
import time
import sys

# =========================================================
# Paccman — files=off, vibes=on
# - SPACE: start / pause toggle on title and during play
# - ESC: quit
# - G: toggle "glitch" (forced kill-screen vibes)
# Levels loop 1..256; level 256 auto-enables glitch mode.
# Ghost AI targets approximate Namco logic (scatter/chase),
# Pinky offset, Inky vector double, Clyde shy logic,
# Blinky 'Elroy' speed-up phases.
# =========================================================

# Grid / tiles
GRID_W, GRID_H = 28, 31

# -----------------------------
# Small helpers
# -----------------------------
def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def frightened_duration_for_level(level: int) -> float:
    # Rough arcade-inspired curve (seconds)
    if level <= 1:   return 6.0
    if level <= 4:   return 5.0
    if level <= 8:   return 4.0
    if level <= 12:  return 3.0
    if level <= 20:  return 2.0
    if level <= 25:  return 1.0
    return 0.5

def make_tone_sound(freq, duration, volume):
    """Best-effort: try numpy -> fall back to array('h') -> silent."""
    try:
        import numpy as np
        sr = 22050
        n  = int(sr*duration)
        t  = np.arange(n, dtype=np.float32)
        wave = (np.sin(2*np.pi*freq*t/sr) * 32767 * volume).astype(np.int16)
        return pygame.sndarray.make_sound(wave)
    except Exception:
        try:
            from array import array
            sr = 22050
            n  = int(sr*duration)
            wave = array('h', (int(math.sin(2*math.pi*freq*i/sr)*32767*volume) for i in range(n)))
            return pygame.mixer.Sound(buffer=wave.tobytes())
        except Exception:
            return None

# -----------------------------
# Level generation
# -----------------------------
def generate_level(level, glitch=False):
    maze = [[0]*GRID_W for _ in range(GRID_H)]

    # Border walls
    for x in range(GRID_W):
        maze[0][x] = 1
        maze[GRID_H-1][x] = 1
    for y in range(GRID_H):
        maze[y][0] = 1
        maze[y][GRID_W-1] = 1

    # A lightweight handcrafted pattern (symmetry-lite)
    for x in range(2, GRID_W-2):
        if x < 10 or x > 17:
            maze[2][x] = 1
        if x < 6 or x > 21:
            maze[4][x] = 1
        if 6 <= x <= 9 or 18 <= x <= 21:
            maze[6][x] = 1
        if 6 <= x <= 12 or 15 <= x <= 21:
            maze[9][x] = 1
        if 9 <= x <= 18:
            maze[11][x] = 1
        if x < 6 or x > 21:
            maze[14][x] = 1
        if 6 <= x <= 12 or 15 <= x <= 21:
            maze[16][x] = 1
        if 6 <= x <= 9 or 18 <= x <= 21:
            maze[19][x] = 1
        if x < 6 or x > 21:
            maze[21][x] = 1
        if x < 10 or x > 17:
            maze[23][x] = 1

    for y in range(2, 5):
        maze[y][2] = maze[y][GRID_W-3] = 1
    for y in range(2, 7):
        maze[y][6] = maze[y][GRID_W-7] = 1
    for y in range(2, 10):
        maze[y][9] = maze[y][GRID_W-10] = 1
    for y in range(6, 10):
        maze[y][12] = maze[y][GRID_W-13] = 1
    for y in range(11, 15):
        maze[y][6] = maze[y][GRID_W-7] = 1
    for y in range(14, 20):
        maze[y][2] = maze[y][GRID_W-3] = 1
    for y in range(16, 20):
        maze[y][9] = maze[y][GRID_W-10] = 1
    for y in range(16, 23):
        maze[y][12] = maze[y][GRID_W-13] = 1
    for y in range(21, 24):
        maze[y][6] = maze[y][GRID_W-7] = 1

    # Ghost house
    for x in range(10, 18):
        maze[13][x] = 1
        maze[15][x] = 1
    for y in range(13, 16):
        maze[y][10] = 1
        maze[y][17] = 1
    maze[13][13] = 0
    maze[13][14] = 0

    # Dots & power
    total_pellets = 0
    for y in range(GRID_H):
        for x in range(GRID_W):
            if maze[y][x] == 0:
                if 13 <= y <= 15 and 10 <= x <= 17:
                    continue
                if (x, y) in [(1,3),(GRID_W-2,3),(1,GRID_H-4),(GRID_W-2,GRID_H-4)]:
                    maze[y][x] = 3
                else:
                    maze[y][x] = 2
                total_pellets += 1

    # Palette
    palette = {
        "bg_top": (0, 0, 50),
        "bg_bot": (0, 0, 30),
        "wall": (20, 20, 200),
        "dot": (255, 255, 200),
        "power": (255, 255, 200),
        "player": (255, 255, 0),
        "ghosts": [(255, 0, 0), (255, 184, 255), (0, 255, 255), (255, 184, 82)],
        "frightened": (0, 0, 255),
        "fruit": (255, 0, 255)
    }

    # Speeds / elroy
    ghost_speed_pct = min(1.0 + (level - 1) * 0.05, 1.6)
    elroy = {"phase1_dots_left": 20, "phase2_dots_left": 10}

    # Scatter / chase timeline (simplified)
    if level == 1:
        timeline = [("scatter", 7), ("chase", 20), ("scatter", 7), ("chase", 20),
                    ("scatter", 5), ("chase", 20), ("scatter", 5), ("chase", -1)]
    else:
        timeline = [("scatter", 5), ("chase", 20), ("scatter", 5), ("chase", 20),
                    ("scatter", 5), ("chase", 20), ("scatter", 5), ("chase", -1)]

    # Kill-screen vibes: corrupt a bit on glitch to emulate level 256 weirdness
    if glitch:
        for _ in range(60):
            rx = random.randint(1, GRID_W-2)
            ry = random.randint(1, GRID_H-2)
            if maze[ry][rx] != 1:
                maze[ry][rx] = random.choice([0, 1, 2, 3])

    return {
        "maze": maze,
        "palette": palette,
        "speeds": {"ghost_pct": ghost_speed_pct, "elroy_thresholds": elroy},
        "stats": {"dots_eaten": 0, "total_pellets": total_pellets},
        "timers": {"frightened_timer": 0.0, "mode_timeline": timeline,
                   "mode_index": 0, "current_mode": timeline[0][0], "mode_timer": timeline[0][1]},
        "fruit": {"spawned": 0, "spawns_per_level": 2, "active": False, "timer": 0.0, "points": 100}
    }

# -----------------------------
# Entities
# -----------------------------
class Player:
    def __init__(self, level_data):
        self.x = 13.5
        self.y = 23.5
        self.score = 0
        self.lives = 3
        self.eat_ghost_combo = 0
        self.direction = (0, 0)
        self.next_direction = (0, 0)
        self.speed = 1.0

    def update(self, maze, keys, dt, level_data, sounds):
        chomp, power = sounds
        # Input (next desired dir)
        if keys[pygame.K_UP]:    self.next_direction = (0, -1)
        elif keys[pygame.K_DOWN]:self.next_direction = (0, 1)
        elif keys[pygame.K_LEFT]:self.next_direction = (-1, 0)
        elif keys[pygame.K_RIGHT]:self.next_direction = (1, 0)

        # Try to turn if possible (grid-snappy)
        if self.next_direction != (0, 0):
            nx = self.x + self.next_direction[0] * 0.5
            ny = self.y + self.next_direction[1] * 0.5
            gx, gy = int(nx), int(ny)
            if 0 <= gx < GRID_W and 0 <= gy < GRID_H and maze[gy][gx] != 1:
                self.direction = self.next_direction

        # Move
        if self.direction != (0, 0):
            new_x = self.x + self.direction[0] * self.speed * dt * 5
            new_y = self.y + self.direction[1] * self.speed * dt * 5
            gx, gy = int(new_x), int(new_y)
            if 0 <= gx < GRID_W and 0 <= gy < GRID_H and maze[gy][gx] != 1:
                self.x, self.y = new_x, new_y
            else:
                ax, ay = round(self.x), round(self.y)
                if 0 <= ax < GRID_W and 0 <= ay < GRID_H and maze[ay][ax] != 1:
                    self.x, self.y = ax, ay

        # Wrap
        if self.x < 0: self.x = GRID_W - 1
        elif self.x >= GRID_W: self.x = 0

        # Eat dots / power
        gx, gy = int(self.x), int(self.y)
        if 0 <= gx < GRID_W and 0 <= gy < GRID_H:
            cell = maze[gy][gx]
            if cell == 2:
                maze[gy][gx] = 0
                self.score += 10
                level_data["stats"]["dots_eaten"] += 1
                if chomp: chomp.play()
            elif cell == 3:
                maze[gy][gx] = 0
                self.score += 50
                level_data["stats"]["dots_eaten"] += 1
                level_data["timers"]["frightened_timer"] = frightened_duration_for_level(level_data.get("level",1))
                self.eat_ghost_combo = 0
                if power: power.play()

class Ghost:
    def __init__(self, x, y, speed, color_index, target_func):
        self.x = x
        self.y = y
        self.speed = speed
        self.base_speed = speed
        self.color_index = color_index
        self.target_func = target_func
        self.mode = "scatter"
        self.frightened = False
        self.eaten = False
        self.home_time = 0.0
        self.dir = (0, 0)
        self.scatter_target = (0, 0)

    def update(self, maze, player, ghosts, dt, level_data):
        # If eaten, go home
        if self.eaten:
            tx, ty = 13.5, 14.0
            if math.hypot(self.x - tx, self.y - ty) < 0.5:
                self.eaten = False
                self.x, self.y = 13.5, 14.0
                self.dir = (0, -1)
                return
        elif self.frightened:
            if random.random() < 0.05 or self.dir == (0, 0):
                self.dir = random.choice([(0,-1),(0,1),(-1,0),(1,0)])
        else:
            # Choose target
            if self.mode == "scatter":
                tx, ty = self.scatter_target
            else:
                tx, ty = self.target_func(player, self, ghosts)

            # Don't reverse except when blocked
            possible = [(0,-1),(0,1),(-1,0),(1,0)]
            if self.dir != (0, 0):
                opp = (-self.dir[0], -self.dir[1])
                if opp in possible:
                    possible.remove(opp)

            best_dir = self.dir
            best_dist = float('inf')
            for dx, dy in possible:
                nx = self.x + dx
                ny = self.y + dy
                gx, gy = int(nx), int(ny)
                if 0 <= gx < GRID_W and 0 <= gy < GRID_H and maze[gy][gx] != 1:
                    d = math.hypot(nx - tx, ny - ty)
                    if d < best_dist:
                        best_dist = d
                        best_dir = (dx, dy)
            self.dir = best_dir

        # Move
        spd = self.speed * dt * 5
        if self.frightened: spd *= 0.5
        if self.eaten:      spd *= 2.0

        nx = self.x + self.dir[0]*spd
        ny = self.y + self.dir[1]*spd
        gx, gy = int(nx), int(ny)
        if 0 <= gx < GRID_W and 0 <= gy < GRID_H and maze[gy][gx] != 1:
            self.x, self.y = nx, ny

        if self.x < 0: self.x = GRID_W-1
        elif self.x >= GRID_W: self.x = 0

# -----------------------------
# Ghost target funcs (Namco-ish)
# -----------------------------
def blinky_target(player, ghost, ghosts=None):
    return (player.x, player.y)

def pinky_target(player, ghost, ghosts=None):
    # 4 tiles ahead; emulate up-direction overflow by offsetting left when facing up
    ahead = 4
    dx, dy = player.direction
    ax = player.x + dx * ahead
    ay = player.y + dy * ahead
    if (dx, dy) == (0, -1):  # up quirk
        ax -= 4
    return (clamp(ax,0,GRID_W-1), clamp(ay,0,GRID_H-1))

def inky_target(player, ghost, ghosts):
    # Vector from Blinky to two tiles ahead of player, doubled
    blinky = ghosts[0]
    dx, dy = player.direction
    ax = player.x + dx*2
    ay = player.y + dy*2
    vx = ax - blinky.x
    vy = ay - blinky.y
    tx = ax + vx
    ty = ay + vy
    return (clamp(tx,0,GRID_W-1), clamp(ty,0,GRID_H-1))

def clyde_target(player, ghost, ghosts=None):
    # If far (>8), chase; else scatter corner
    if math.hypot(ghost.x - player.x, ghost.y - player.y) > 8:
        return (player.x, player.y)
    return ghost.scatter_target

# -----------------------------
# Drawing
# -----------------------------
def build_background_surface(w, h, top_col, bot_col):
    surf = pygame.Surface((w, h))
    pygame.draw.rect(surf, top_col, (0, 0, w, h//2))
    pygame.draw.rect(surf, bot_col, (0, h//2, w, h//2))
    return surf

def draw_maze(surf, maze, palette, tile_size, hud_h, glitch=False):
    jitter = 0
    if glitch:
        jitter = 1  # tiny shake to sell the effect
    for y in range(GRID_H):
        for x in range(GRID_W):
            cell = maze[y][x]
            ox = random.randint(-jitter, jitter) if glitch else 0
            oy = random.randint(-jitter, jitter) if glitch else 0
            if cell == 1:
                pygame.draw.rect(surf, palette["wall"],
                                 (x*tile_size+ox, y*tile_size+hud_h+oy, tile_size, tile_size))
            elif cell == 2:
                pygame.draw.circle(surf, palette["dot"],
                                   (x*tile_size + tile_size//2 + ox,
                                    y*tile_size + tile_size//2 + hud_h + oy),
                                   tile_size//5)
            elif cell == 3:
                pygame.draw.circle(surf, palette["power"],
                                   (x*tile_size + tile_size//2 + ox,
                                    y*tile_size + tile_size//2 + hud_h + oy),
                                   tile_size//3)

def draw_player(surf, player, palette, tile_size, hud_h):
    x = int(player.x * tile_size)
    y = int(player.y * tile_size) + hud_h
    radius = tile_size // 2 - 1

    # mouth direction
    if player.direction == (0, -1):
        start_angle, end_angle = math.pi*1.25, math.pi*0.75
    elif player.direction == (0, 1):
        start_angle, end_angle = math.pi*0.75, math.pi*0.25
    elif player.direction == (-1, 0):
        start_angle, end_angle = math.pi*1.75, math.pi*1.25
    else:
        start_angle, end_angle = math.pi*0.25, math.pi*1.75

    pygame.draw.circle(surf, palette["player"], (x, y), radius)
    mouth_points = [
        (x, y),
        (x + radius*math.cos(start_angle), y + radius*math.sin(start_angle)),
        (x + radius*math.cos(end_angle),   y + radius*math.sin(end_angle)),
    ]
    pygame.draw.polygon(surf, palette["bg_bot"], mouth_points)

def draw_ghost(surf, ghost, palette, tile_size, hud_h, frightened_timer):
    x = int(ghost.x * tile_size)
    y = int(ghost.y * tile_size) + hud_h
    radius = tile_size // 2 - 1
    height = tile_size - 2

    if ghost.eaten:
        color = palette["bg_bot"]
    elif ghost.frightened:
        color = palette["frightened"] if (frightened_timer > 2 or int(frightened_timer*4) % 2 == 0) else (255,255,255)
    else:
        color = palette["ghosts"][ghost.color_index]

    pygame.draw.circle(surf, color, (x, y), radius)
    pygame.draw.rect(surf, color, (x - radius, y, radius*2, height - radius))
    for i in range(4):
        wx = x - radius + i*radius + radius//2
        pygame.draw.circle(surf, color, (wx, y + height - radius), radius//2)

    # Eyes
    eye_r = radius//3
    eye_y = y - radius//2
    if not ghost.eaten:
        pygame.draw.circle(surf, (255,255,255), (x - radius//2, eye_y), eye_r)
        pygame.draw.circle(surf, (255,255,255), (x + radius//2, eye_y), eye_r)
        pr = eye_r//2
        dx, dy = ghost.dir
        if ghost.frightened:
            pygame.draw.circle(surf, (0,0,255), (x - radius//2, eye_y), pr)
            pygame.draw.circle(surf, (0,0,255), (x + radius//2, eye_y), pr)
        else:
            pygame.draw.circle(surf, (0,0,0), (x - radius//2 + dx*pr, eye_y + dy*pr), pr)
            pygame.draw.circle(surf, (0,0,0), (x + radius//2 + dx*pr, eye_y + dy*pr), pr)
    else:
        pygame.draw.circle(surf, (255,255,255), (x - radius//2, eye_y), eye_r)
        pygame.draw.circle(surf, (255,255,255), (x + radius//2, eye_y), eye_r)
        pygame.draw.circle(surf, (0,0,0), (x - radius//2, eye_y), eye_r//2)
        pygame.draw.circle(surf, (0,0,0), (x + radius//2, eye_y), eye_r//2)

def draw_fruit(surf, level_data, palette, tile_size, hud_h):
    if level_data["fruit"]["active"]:
        x = int(13.5 * tile_size)
        y = int(17 * tile_size) + hud_h
        r = tile_size//2 - 1
        pygame.draw.circle(surf, palette["fruit"], (x, y), r)

def draw_hud(surf, player, level_data, tile_size, hud_h, level, high_score=0):
    font = pygame.font.Font(None, 28)
    small_font = pygame.font.Font(None, 24)

    # Score and High Score
    score_text = font.render(f"SCORE: {player.score:06d}", True, (255,255,255))
    surf.blit(score_text, (10, 10))

    if high_score > 0:
        high_text = small_font.render(f"HIGH: {high_score:06d}", True, (255,255,0))
        surf.blit(high_text, (10, 35))

    # Lives (Pac-Man icons)
    for i in range(player.lives):
        x = surf.get_width() - 30 - i*25
        y = 20
        pygame.draw.circle(surf, level_data["palette"]["player"], (x, y), 8)
        mouth = [
            (x, y),
            (x + 8*math.cos(math.pi*0.25), y + 8*math.sin(math.pi*0.25)),
            (x + 8*math.cos(math.pi*1.75), y + 8*math.sin(math.pi*1.75)),
        ]
        pygame.draw.polygon(surf, level_data["palette"]["bg_top"], mouth)

    # Level indicator with fruit symbols
    lvl_text = font.render(f"LEVEL: {level}", True, (255,255,255))
    surf.blit(lvl_text, (surf.get_width()//2 - 50, 10))

    # Show bonus fruit symbols for completed levels (up to 7)
    fruit_colors = [(255,0,0), (255,128,0), (255,255,0), (0,255,0),
                    (0,255,255), (255,0,255), (255,192,203)]
    for i in range(min(7, level-1)):
        fx = surf.get_width()//2 + 60 + i*15
        fy = 20
        color = fruit_colors[i % len(fruit_colors)]
        pygame.draw.circle(surf, color, (fx, fy), 6)

def draw_title(canvas, w, h, hud_h, palette, high_score=0):
    canvas.fill((0,0,0))
    title_font = pygame.font.Font(None, 72)
    small_font = pygame.font.Font(None, 36)
    tiny_font  = pygame.font.Font(None, 28)

    t1 = title_font.render("PAC-MAN", True, (255,255,0))
    t2 = small_font.render("BANDAI NAMCO PRESENTS", True, (255,128,0))
    t3 = small_font.render("Press SPACE to start", True, (255,255,255))
    t4 = tiny_font.render("files=off · vibes=on · 256 levels", True, (160,200,255))

    # Show high score on title screen
    if high_score > 0:
        t5 = small_font.render(f"HIGH SCORE: {high_score:06d}", True, (255,255,0))
        canvas.blit(t5, (w//2 - t5.get_width()//2, h//2 - 160))

    # Simple Pac-Man art
    pacman_x, pacman_y = w//2 - 100, h//2 - 40
    pygame.draw.circle(canvas, (255,255,0), (pacman_x, pacman_y), 20)
    mouth_points = [(pacman_x, pacman_y), (pacman_x + 20, pacman_y - 10), (pacman_x + 20, pacman_y + 10)]
    pygame.draw.polygon(canvas, (0,0,0), mouth_points)

    for i in range(5):
        dot_x = pacman_x + 40 + i * 15
        pygame.draw.circle(canvas, (255,255,200), (dot_x, pacman_y), 3)

    cx = w//2
    canvas.blit(t1, (cx - t1.get_width()//2, h//2 - 120))
    canvas.blit(t2, (cx - t2.get_width()//2, h//2 - 200))
    canvas.blit(t3, (cx - t3.get_width()//2, h//2 + 40))
    canvas.blit(t4, (cx - t4.get_width()//2, h//2 + 80))

def draw_ready(canvas, w, hud_h):
    font = pygame.font.Font(None, 48)
    txt = font.render("READY!", True, (255,255,0))
    canvas.blit(txt, (w//2 - txt.get_width()//2, hud_h + 18*20))

def draw_game_over(canvas, w, h):
    big = pygame.font.Font(None, 72)
    small = pygame.font.Font(None, 36)
    a = big.render("GAME OVER", True, (255,64,64))
    b = small.render("Press SPACE to restart", True, (255,255,255))
    canvas.blit(a, (w//2 - a.get_width()//2, h//2 - 40))
    canvas.blit(b, (w//2 - b.get_width()//2, h//2 + 20))

# -----------------------------
# Main game
# -----------------------------
def run_game(auto=False, fps=60, tile=20):
    pygame.mixer.pre_init(44100, -16, 1, 512)
    pygame.init()
    pygame.display.set_caption("Paccman — Bandai Namco Presents (files=off, vibes=on)")

    hud_h = 64
    logical_w = GRID_W * tile
    logical_h = GRID_H * tile + hud_h
    WINDOW_W, WINDOW_H = 600, 400

    window = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    canvas = pygame.Surface((logical_w, logical_h)).convert_alpha()

    def present():
        sx = WINDOW_W / logical_w
        sy = WINDOW_H / logical_h
        scale = min(sx, sy)
        out_w = max(1, int(logical_w * scale))
        out_h = max(1, int(logical_h * scale))
        try:
            scaled = pygame.transform.smoothscale(canvas, (out_w, out_h))
            window.fill((0,0,0))
            window.blit(scaled, ((WINDOW_W - out_w)//2, (WINDOW_H - out_h)//2))
        except Exception:
            window.fill((0,0,0))
            window.blit(canvas, ((WINDOW_W - logical_w)//2, (WINDOW_H - logical_h)//2))
        pygame.display.flip()

    # Sounds
    try:
        pygame.mixer.init()
        chomp       = make_tone_sound(freq=1000, duration=0.06, volume=0.35)
        power       = make_tone_sound(freq=520,  duration=0.12, volume=0.45)
        eat_ghost   = make_tone_sound(freq=800,  duration=0.15, volume=0.50)
        death       = make_tone_sound(freq=200,  duration=0.50, volume=0.40)
        fruit_sound = make_tone_sound(freq=1200, duration=0.10, volume=0.40)
        siren       = make_tone_sound(freq=300,  duration=0.20, volume=0.25)  # Background tension
        intermission= make_tone_sound(freq=880,  duration=0.30, volume=0.35)  # Level complete
        extra_life  = make_tone_sound(freq=1500, duration=0.25, volume=0.45)  # Bonus life
    except Exception:
        chomp = power = eat_ghost = death = fruit_sound = siren = intermission = extra_life = None

    clock = pygame.time.Clock()
    level = 1
    glitch_override = False
    high_score = 0
    bonus_life_awarded = False

    level_data = None
    bg = None

    def reset_level():
        nonlocal player, ghosts, level_data, bg
        # Auto-glitch on level 256 for kill-screen vibes
        forced_glitch = glitch_override or (level >= 256)
        level_data = generate_level(level, glitch=forced_glitch)
        level_data["level"] = level

        player = Player(level_data)

        ghost_speed = 1.18 * level_data["speeds"]["ghost_pct"]
        ghosts = [
            Ghost(13.5, 11.5, ghost_speed, 0, blinky_target),  # Blinky
            Ghost(12.0, 14.0, ghost_speed, 1, pinky_target),   # Pinky
            Ghost(13.5, 14.0, ghost_speed, 2, inky_target),    # Inky
            Ghost(15.0, 14.0, ghost_speed, 3, clyde_target)    # Clyde
        ]
        ghosts[0].scatter_target = (GRID_W-3, 3)
        ghosts[1].scatter_target = (3, 3)
        ghosts[2].scatter_target = (GRID_W-3, GRID_H-3)
        ghosts[3].scatter_target = (3, GRID_H-3)

        ghosts[0].home_time = 0
        ghosts[1].home_time = 2 if level > 1 else 4
        ghosts[2].home_time = 4 if level > 1 else 8
        ghosts[3].home_time = 6 if level > 1 else 12

        tl = level_data["timers"]["mode_timeline"]
        level_data["timers"]["mode_index"] = 0
        level_data["timers"]["current_mode"] = tl[0][0]
        level_data["timers"]["mode_timer"] = tl[0][1]
        level_data["timers"]["frightened_timer"] = 0.0

        bg = build_background_surface(logical_w, GRID_H * tile,
                                      level_data["palette"]["bg_top"],
                                      level_data["palette"]["bg_bot"])

    # Game state
    STATE_TITLE = "title"
    STATE_READY = "ready"
    STATE_PLAY  = "play"
    STATE_OVER  = "over"
    state = STATE_TITLE
    ready_timer = 0.0

    player = None
    ghosts = []
    reset_level()

    paused = False
    running = True
    while running:
        dt = clock.tick(fps) / 1000.0
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    running = False
                elif ev.key == pygame.K_SPACE:
                    if state == STATE_TITLE:
                        reset_level()
                        state = STATE_READY
                        ready_timer = 1.6
                    elif state == STATE_READY:
                        pass
                    elif state == STATE_PLAY:
                        paused = not paused
                    elif state == STATE_OVER:
                        level = 1
                        bonus_life_awarded = False
                        reset_level()
                        state = STATE_READY
                        ready_timer = 1.6
                elif ev.key == pygame.K_g:
                    glitch_override = not glitch_override
                    reset_level()
                elif ev.key == pygame.K_b:
                    if chomp: chomp.play()
                elif ev.key == pygame.K_o:
                    if power: power.play()

        # --- Update ---
        if state == STATE_TITLE:
            pass

        elif state == STATE_READY:
            ready_timer -= dt
            if ready_timer <= 0:
                state = STATE_PLAY

        elif state == STATE_PLAY:
            if not paused:
                keys = pygame.key.get_pressed()
                player.update(level_data["maze"], keys, dt, level_data, (chomp, power))

                # Ghosts
                for g in ghosts:
                    if g.home_time > 0:
                        g.home_time -= dt
                        continue
                    g.mode = level_data["timers"]["current_mode"]
                    g.frightened = level_data["timers"]["frightened_timer"] > 0
                    g.update(level_data["maze"], player, ghosts, dt, level_data)

                # Timers
                level_data["timers"]["mode_timer"] -= dt
                if level_data["timers"]["mode_timer"] <= 0:
                    level_data["timers"]["mode_index"] += 1
                    tl = level_data["timers"]["mode_timeline"]
                    if level_data["timers"]["mode_index"] < len(tl):
                        mode, dur = tl[level_data["timers"]["mode_index"]]
                        level_data["timers"]["current_mode"] = mode
                        level_data["timers"]["mode_timer"] = dur

                if level_data["timers"]["frightened_timer"] > 0:
                    level_data["timers"]["frightened_timer"] = max(
                        0.0, level_data["timers"]["frightened_timer"] - dt
                    )

                # Fruit system with level-based scoring
                dots_eaten = level_data["stats"]["dots_eaten"]
                fruit_spawn_dots = [70, 170]
                if (
                    dots_eaten in fruit_spawn_dots
                    and level_data["fruit"]["spawned"] < level_data["fruit"]["spawns_per_level"]
                ):
                    level_data["fruit"]["active"] = True
                    level_data["fruit"]["timer"] = 9 + random.random()
                    level_data["fruit"]["spawned"] += 1

                    fruit_values = [100, 300, 500, 700, 1000, 2000, 3000, 5000]
                    level_data["fruit"]["points"] = fruit_values[min(level-1, len(fruit_values)-1)]

                if level_data["fruit"]["active"]:
                    level_data["fruit"]["timer"] -= dt
                    if level_data["fruit"]["timer"] <= 0:
                        level_data["fruit"]["active"] = False
                    # eat fruit
                    if math.hypot(player.x - 13.5, player.y - 17) < 0.5:
                        level_data["fruit"]["active"] = False
                        player.score += level_data["fruit"]["points"]
                        if fruit_sound: fruit_sound.play()

                # Check for bonus life at 10,000 points
                if player.score >= 10000 and not bonus_life_awarded:
                    player.lives += 1
                    bonus_life_awarded = True
                    if extra_life:
                        extra_life.play()

                # Update high score
                if player.score > high_score:
                    high_score = player.score

                # Collisions with ghosts
                for g in ghosts:
                    if math.hypot(player.x - g.x, player.y - g.y) < 0.5:
                        if g.frightened and not g.eaten:
                            g.eaten = True
                            ghost_points = (2 ** player.eat_ghost_combo) * 200
                            player.score += ghost_points
                            player.eat_ghost_combo += 1
                            if eat_ghost: eat_ghost.play()
                            print(f"Ghost eaten for {ghost_points} points!")
                        elif not g.eaten and not g.frightened:
                            player.lives -= 1
                            if death: death.play()
                            if player.lives <= 0:
                                state = STATE_OVER
                            else:
                                # respawn with brief invulnerability
                                player.x, player.y = 13.5, 23.5
                                for idx, gg in enumerate(ghosts):
                                    gg.x, gg.y = [13.5, 12.0, 13.5, 15.0][idx], [14.0, 14.0, 14.0, 14.0][idx]
                                    gg.eaten = False
                                    gg.dir = (0,-1) if idx == 0 else (0,0)
                                    gg.home_time = [0, 2, 4, 6][idx] if level > 1 else [0, 4, 8, 12][idx]
                                level_data["timers"]["frightened_timer"] = 0.0

                # Level clear
                if dots_eaten >= level_data["stats"]["total_pellets"]:
                    level_bonus = 100 * level
                    player.score += level_bonus
                    if intermission: intermission.play()
                    print(f"Level {level} complete! Bonus: {level_bonus} points")

                    level += 1
                    if level > 256:
                        level = 1
                    reset_level()
                    state = STATE_READY
                    ready_timer = 2.0  # Slightly longer for level transition

                # Blinky Elroy
                elroy_dots = level_data["speeds"]["elroy_thresholds"]
                remaining = level_data["stats"]["total_pellets"] - dots_eaten
                if remaining == elroy_dots["phase1_dots_left"] and not hasattr(ghosts[0], '_elroy1_done'):
                    ghosts[0].speed *= 1.05
                    ghosts[0]._elroy1_done = True
                if remaining == elroy_dots["phase2_dots_left"] and not hasattr(ghosts[0], '_elroy2_done'):
                    ghosts[0].speed *= 1.05
                    ghosts[0]._elroy2_done = True

        elif state == STATE_OVER:
            pass

        # --- Draw ---
        canvas.fill((0,0,0))
        if state == STATE_TITLE:
            draw_title(canvas, logical_w, logical_h, hud_h,
                       level_data["palette"] if level_data else {"bg_top": (0,0,50), "bg_bot": (0,0,30)},
                       high_score)
        else:
            canvas.blit(bg, (0, hud_h))
            draw_maze(canvas, level_data["maze"], level_data["palette"], tile, hud_h,
                      glitch=(glitch_override or level>=256))
            if state in (STATE_PLAY, STATE_READY, STATE_OVER):
                draw_player(canvas, player, level_data["palette"], tile, hud_h)
                for g in ghosts:
                    draw_ghost(canvas, g, level_data["palette"], tile, hud_h,
                               level_data["timers"]["frightened_timer"])
                draw_fruit(canvas, level_data, level_data["palette"], tile, hud_h)
                draw_hud(canvas, player, level_data, tile, hud_h, level, high_score)
            if state == STATE_READY:
                draw_ready(canvas, logical_w, hud_h)
            if state == STATE_OVER:
                draw_game_over(canvas, logical_w, logical_h)

        present()

    pygame.quit()

if __name__ == "__main__":
    run_game(fps=60, tile=20)
