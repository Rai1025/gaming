#Controls
#W/S or Up/Down = choose   Enter/Space = play   Esc = quit
#A/D or arrows = move   Space/W/Up = jump
#Left click = rocket jump
#Left Shift = phase dash
#R = restart level   Esc or P = pause
#Esc or P = resume   R = restart   M = back to level select
#N = next level   R = retry   M or Esc = level select

import math
import os
import sys
import pygame
import json
import threading
import urllib.request

# General setup
pygame.init()
WIDTH, HEIGHT = 800, 450
TILE = 50
FPS = 60
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Explosive Dash")
clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 28)
small_font = pygame.font.SysFont(None, 22)
big_font = pygame.font.SysFont(None, 64)

LEVEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "levels")

MOVE_SPEED = 260
GRAVITY = 1800
MAX_FALL = 900
JUMP_SPEED = 680
JUMP_CUT = 0.45
GROUND_DRAG = 2400
AIR_DRAG = 500
ROCKET_SPEED = 750
DASH_SPEED = 700
DASH_TIME = 0.18
JUMP_KEYS = (pygame.K_SPACE, pygame.K_w, pygame.K_UP)

# Colors
SKY = (127, 178, 229)
INK = (20, 25, 40)
WHITE = (255, 255, 255)
RED = (200, 50, 50)
GOLD = (242, 193, 78)

API_URL = "http://localhost:5000/api/scores"
# Submit score meant to allow the game to work when the api is offline and prevent freezing due to it
def submit_score(username, level_name, time_sec):
    def send():
        try:
            body = json.dumps({"username": username, "level": level_name,
                               "time": round(time_sec, 2)}).encode("utf-8")
            req = urllib.request.Request(API_URL, data=body,
                                         headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=3)
        except Exception as err:
            print("Could not save score:", err)
    threading.Thread(target=send, daemon=True).start()

# Levels loaded from a separate file
def pretty_name(filename):
    return os.path.splitext(filename)[0].replace("_", " ").title()
class Level:

    def __init__(self, filename):
        self.filename = filename
        self.name = pretty_name(filename)
        self.tiles = []
        self.phase_tiles = []
        self.goal = None
        self.spawn = None

        with open(os.path.join(LEVEL_DIR, filename), encoding="utf-8") as f:
            lines = [line.rstrip() for line in f]
        rows = [line for line in lines if line and not line.startswith(";")]
        self.width = max(len(line) for line in rows) * TILE
        self.height = len(rows) * TILE

        for row, line in enumerate(rows):
            for col, ch in enumerate(line):
                x, y = col * TILE, row * TILE
                if ch == "#":
                    self.tiles.append(pygame.Rect(x, y, TILE, TILE))
                elif ch == "P":
                    self.phase_tiles.append(pygame.Rect(x + TILE // 3, y, TILE // 3, TILE))
                elif ch == "G":
                    self.goal = pygame.Rect(x + 10, y, TILE - 20, TILE)
                elif ch == "S":
                    self.spawn = (x + 10, y + TILE - 44)
                elif ch not in ". ":
                    raise ValueError(f"unknown character '{ch}' in row {row + 1}")

        if self.spawn is None:
            raise ValueError("no S (start) found")
        if self.goal is None:
            raise ValueError("no G (goal) found")


def scan_levels():
    entries = []
    if not os.path.isdir(LEVEL_DIR):
        return entries
    for filename in sorted(os.listdir(LEVEL_DIR)):
        if not filename.lower().endswith(".txt"):
            continue
        try:
            entries.append({"name": pretty_name(filename), "level": Level(filename), "error": None})
        except (ValueError, OSError) as err:
            entries.append({"name": pretty_name(filename), "level": None, "error": str(err)})
    return entries

class Player:
    def __init__(self, level):
        self.level = level
        self.rect = pygame.Rect(0, 0, 30, 44)
        self.respawn()

    def respawn(self):
        self.x, self.y = self.level.spawn
        self.rect.topleft = self.level.spawn
        self.vel_x = 0.0
        self.vel_y = 0.0
        self.boost_x = 0.0
        self.on_ground = False
        self.jumped = False
        self.facing = 1
        self.can_rocket = True
        self.can_dash = True
        self.dashing = False
        self.dash_timer = 0.0
        self.dash_dir = 1

    def solids(self):
        if self.dashing:
            return self.level.tiles
        return self.level.tiles + self.level.phase_tiles

    def handle_event(self, event, cam):
        if event.type == pygame.KEYDOWN:
            if event.key in JUMP_KEYS and self.on_ground and not self.dashing:
                self.vel_y = -JUMP_SPEED
                self.jumped = True
            if event.key == pygame.K_LSHIFT and self.can_dash and not self.dashing:
                self.dashing = True
                self.dash_timer = DASH_TIME
                self.dash_dir = self.facing
                self.can_dash = False
                self.boost_x = 0

        if event.type == pygame.KEYUP and event.key in JUMP_KEYS:
            if self.jumped and self.vel_y < 0:
                self.vel_y *= JUMP_CUT
                self.jumped = False

        if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                and self.can_rocket and not self.dashing):
            player_on_screen = pygame.Vector2(self.rect.centerx - cam[0], self.rect.centery - cam[1])
            aim = pygame.Vector2(event.pos) - player_on_screen
            if aim.length() > 0:
                push = -aim.normalize() * ROCKET_SPEED
                self.boost_x = push.x
                self.vel_y = push.y
                self.can_rocket = False
                self.jumped = False

    def inside_phase_wall(self):
        return any(self.rect.colliderect(t) for t in self.level.phase_tiles)

    def update(self, dt):
        probe = self.rect.move(0, 1)
        self.on_ground = any(probe.colliderect(t) for t in self.solids())
        if self.on_ground and not self.dashing:
                self.can_dash = True
                self.can_rocket = True

        keys = pygame.key.get_pressed()
        direction = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
        if direction != 0:
            self.facing = direction

        if self.dashing:
            self.dash_timer -= dt
            self.vel_x = self.dash_dir * DASH_SPEED
            self.vel_y = 0
            if self.dash_timer <= 0:
                if not self.inside_phase_wall():
                    self.dashing = False
                elif self.dash_timer < -0.5:
                    self.respawn()   # Incase the player is in a wall
                    return
        else:
            drag = (GROUND_DRAG if self.on_ground else AIR_DRAG) * dt
            if abs(self.boost_x) <= drag:
                self.boost_x = 0
            else:
                self.boost_x -= math.copysign(drag, self.boost_x)

            self.vel_x = direction * MOVE_SPEED + self.boost_x
            self.vel_y = min(self.vel_y + GRAVITY * dt, MAX_FALL)
            if self.vel_y >= 0:
                self.jumped = False

        self.move_x(self.vel_x * dt)
        self.move_y(self.vel_y * dt)

        probe = self.rect.move(0, 1)
        self.on_ground = any(probe.colliderect(t) for t in self.solids())
        if self.on_ground and not self.dashing:
            self.can_dash = True

        if self.rect.top > self.level.height + 200:
            self.respawn()

    def move_x(self, dx):
        self.x += dx
        self.rect.x = round(self.x)
        for tile in self.solids():
            if self.rect.colliderect(tile):
                if dx > 0:
                    self.rect.right = tile.left
                elif dx < 0:
                    self.rect.left = tile.right
                self.x = self.rect.x
                self.boost_x = 0
        if self.rect.left < 0 or self.rect.right > self.level.width:
            self.rect.left = max(0, min(self.rect.left, self.level.width - self.rect.width))
            self.x = self.rect.x
            self.boost_x = 0

    def move_y(self, dy):
        self.y += dy
        self.rect.y = round(self.y)
        for tile in self.solids():
            if self.rect.colliderect(tile):
                if dy > 0:
                    self.rect.bottom = tile.top
                elif dy < 0:
                    self.rect.top = tile.bottom
                self.y = self.rect.y
                self.vel_y = 0

    def draw(self, surface, cam):
        color = (120, 200, 255) if self.dashing else GOLD
        pygame.draw.rect(surface, color, self.rect.move(-cam[0], -cam[1]))

def draw_text(text, y, color=INK, f=None):
    """Draws text horizontally centred on the screen."""
    surf = (f or font).render(text, True, color)
    screen.blit(surf, surf.get_rect(center=(WIDTH // 2, y)))

def get_camera(level, player):
    cam_x = player.rect.centerx - WIDTH // 2
    cam_y = player.rect.centery - HEIGHT // 2
    cam_x = max(0, min(cam_x, level.width - WIDTH))
    cam_y = max(0, min(cam_y, level.height - HEIGHT))
    return cam_x, cam_y

def draw_level(level, player, cam, show_aim):
    cx, cy = cam
    screen.fill(SKY)
    for t in level.tiles:
        r = t.move(-cx, -cy)
        pygame.draw.rect(screen, (47, 74, 58), r)
        pygame.draw.rect(screen, (34, 58, 44), r, 1)
    for t in level.phase_tiles:
        pygame.draw.rect(screen, (170, 110, 220), t.move(-cx, -cy))
    pygame.draw.rect(screen, (230, 70, 70), level.goal.move(-cx, -cy))
    player.draw(screen, cam)
    if show_aim and player.can_rocket:
        start = (player.rect.centerx - cx, player.rect.centery - cy)
        pygame.draw.line(screen, WHITE, start, pygame.mouse.get_pos(), 1)

def draw_hud(level, player, run_time):
    hud = (f"{level.name}   Time {run_time:5.2f}s   Dash {'ready' if player.can_dash else '--'}"
           f"   Rocket {'ready' if player.can_rocket else '--'}")
    screen.blit(font.render(hud, True, INK), (10, 10))

def dim_screen():
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 150))
    screen.blit(overlay, (0, 0))

def draw_name_screen(username):
    screen.fill(SKY)
    draw_text("ENTER YOUR NAME", 120, INK, big_font)
    pygame.draw.rect(screen, WHITE, (250, 200, 300, 50), border_radius=6)
    draw_text(username + "|", 225, INK)
    draw_text("Type your name, then press Enter", 300, INK, small_font)

def draw_menu(entries, selected, best_times):
    screen.fill(SKY)
    draw_text("LEVEL SELECT", 60, INK, big_font)

    if not entries:
        draw_text("No levels found.", 200, RED)
        draw_text("Put .txt level files in the 'levels' folder next to game.py", 235, INK, small_font)
    else:
        visible = 6
        first = max(0, min(selected - visible // 2, len(entries) - visible))
        for i in range(first, min(first + visible, len(entries))):
            entry = entries[i]
            y = 130 + (i - first) * 38
            if i == selected:
                pygame.draw.rect(screen, (255, 255, 255), (150, y - 17, WIDTH - 300, 34), border_radius=6)
            color = RED if entry["error"] else INK
            name = entry["name"] + ("  (broken)" if entry["error"] else "")
            screen.blit(font.render(name, True, color), (170, y - 9))
            best = best_times.get(entry["name"])
            if best is not None:
                label = font.render(f"best {best:.2f}s", True, INK)
                screen.blit(label, (WIDTH - 170 - label.get_width(), y - 9))
        if entries[selected]["error"]:
            draw_text("Problem: " + entries[selected]["error"], 372, RED, small_font)

    draw_text("W/S or Up/Down: choose     Enter/Space: play     Esc: quit", 410, INK, small_font)

def quit_game():
    pygame.quit()
    sys.exit()

def main():
    state = "name"
    username = ""
    entries = scan_levels()
    selected = 0
    current = 0
    best_times = {}
    player = None
    run_time = 0.0
    new_best = False

    def start(index):
        return Player(entries[index]["level"]), 0.0

    while True:
        dt = min(clock.tick(FPS) / 1000, 1 / 30)
        camera = get_camera(player.level, player) if state not in ("menu", "name") else (0, 0)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                quit_game()
            is_key = event.type == pygame.KEYDOWN
            if state == "name":
                if is_key:
                    if event.key == pygame.K_ESCAPE:
                        quit_game()
                    elif event.key == pygame.K_RETURN and username.strip():
                        username = username.strip()
                        state = "menu"
                    elif event.key == pygame.K_BACKSPACE:
                        username = username[:-1]
                    elif event.unicode.isprintable() and event.unicode and len(username) < 15:
                        username += event.unicode

            elif state == "menu":
                if is_key and entries:
                    if event.key in (pygame.K_UP, pygame.K_w):
                        selected = (selected - 1) % len(entries)
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        selected = (selected + 1) % len(entries)
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        if entries[selected]["level"] is not None:
                            current = selected
                            player, run_time = start(current)
                            state = "playing"
                if is_key and event.key == pygame.K_ESCAPE:
                    quit_game()

            elif state == "playing":
                if is_key and event.key in (pygame.K_ESCAPE, pygame.K_p):
                    state = "paused"
                elif is_key and event.key == pygame.K_r:
                    player, run_time = start(current)
                else:
                    player.handle_event(event, camera)

            elif state == "paused":
                if is_key and event.key in (pygame.K_ESCAPE, pygame.K_p):
                    state = "playing"
                elif is_key and event.key == pygame.K_r:
                    player, run_time = start(current)
                    state = "playing"
                elif is_key and event.key == pygame.K_m:
                    entries = scan_levels()
                    selected = min(current, max(0, len(entries) - 1))
                    state = "menu"

            elif state == "won":
                if is_key and event.key == pygame.K_r:
                    player, run_time = start(current)
                    state = "playing"
                elif is_key and event.key == pygame.K_n:
                    nxt = next((i for i in range(current + 1, len(entries))
                                if entries[i]["level"] is not None), None)
                    if nxt is not None:
                        current = nxt
                        player, run_time = start(current)
                        state = "playing"
                elif is_key and event.key in (pygame.K_m, pygame.K_ESCAPE):
                    entries = scan_levels()
                    selected = min(current, max(0, len(entries) - 1))
                    state = "menu"

        if state == "playing":
            player.update(dt)
            run_time += dt
            if player.rect.colliderect(entries[current]["level"].goal):
                name = entries[current]["name"]
                new_best = name not in best_times or run_time < best_times[name]
                if new_best:
                    best_times[name] = run_time
                submit_score(username, name, run_time)
                state = "won"

        if state == "name":
            draw_name_screen(username)
        elif state == "menu":
            draw_menu(entries, selected, best_times)
        else:
            level = entries[current]["level"]
            camera = get_camera(level, player)
            draw_level(level, player, camera, show_aim=(state == "playing"))
            draw_hud(level, player, run_time)
            if state == "paused":
                dim_screen()
                draw_text("PAUSED", 150, WHITE, big_font)
                draw_text("Esc / P: resume     R: restart     M: level select", 220, WHITE)
            elif state == "won":
                dim_screen()
                draw_text("LEVEL COMPLETE!", 140, WHITE, big_font)
                draw_text(f"Time: {run_time:.2f}s" + ("   (new best!)" if new_best else ""), 200, WHITE)
                draw_text("N: next level     R: retry     M / Esc: level select", 250, WHITE)

        pygame.display.flip()

if __name__ == "__main__":
    main()