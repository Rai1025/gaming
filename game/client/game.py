"""
Pygame platformer: run, jump, ROCKET JUMP (left click) and PHASE DASH (Left Shift).
Goal: reach the flag as fast as you can. Press R to restart.

Controls:  A/D or arrows = move   Space/W/Up = jump (hold for higher)
           Left click   = rocket jump (launches you AWAY from the cursor)
           Left Shift   = phase dash (horizontal, passes through purple walls)
"""
import math
import sys
import pygame

pygame.init()

# =====================================================================
# 1. SETUP
# =====================================================================
WIDTH, HEIGHT = 800, 450
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Pygame Platformer: Rocket + Phase Dash")
clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 28)
FPS = 60

# =====================================================================
# 2. TUNING CONSTANTS: change these to change the "feel"
# =====================================================================
# --- basic movement ---
GRAVITY = 1800         # px/s^2, added to vel.y each second (positive = down)
MAX_FALL = 900         # terminal velocity
MOVE_SPEED = 260       # normal top horizontal speed
ACCEL = 2000           # speed gained per second while holding a direction
FRICTION = 2400        # speed lost per second on the ground with no input
AIR_FRICTION = 500     # speed lost per second in the air with no input (lower = floatier)
JUMP_SPEED = 680       # upward speed at takeoff
JUMP_CUT = 0.45        # releasing jump early multiplies upward speed by this
COYOTE_TIME = 0.1      # grace period for jumping after leaving a ledge
JUMP_BUFFER = 0.12     # an early jump press is remembered for this long

# --- rocket jump ---
ROCKET_SPEED = 750     # speed given by the launch
ROCKET_COOLDOWN = 0.5  # seconds between rockets
BOOST_DRAG = 700       # how fast speed ABOVE MOVE_SPEED bleeds off while steering

# --- phase dash ---
DASH_SPEED = 700       # fixed speed during the dash
DASH_TIME = 0.18       # dash duration (distance is about DASH_SPEED * DASH_TIME = 126 px)

JUMP_KEYS = (pygame.K_SPACE, pygame.K_w, pygame.K_UP)

# =====================================================================
# 3. LEVEL
# =====================================================================
# 1 = solid tile   2 = thin phase wall (dash can pass through)   G = goal flag
TILE = 50
LEVEL = [
    "................",
    "................",
    "..............G.",
    "......2.....1111",
    "......2.........",
    "......2.........",
    "......2.........",
    "1111111111111111",
    "1111111111111111",
]
LEVEL_W = len(LEVEL[0]) * TILE

tiles, phase_tiles, goal = [], [], None
for row, line in enumerate(LEVEL):
    for col, ch in enumerate(line):
        x, y = col * TILE, row * TILE
        if ch == "1":
            tiles.append(pygame.Rect(x, y, TILE, TILE))
        elif ch == "2":
            # Phase walls are drawn thin (a third of a tile) so they read as "thin".
            phase_tiles.append(pygame.Rect(x + TILE // 3, y, TILE // 3, TILE))
        elif ch == "G":
            goal = pygame.Rect(x + 10, y, TILE - 20, TILE)


def sign(n):
    """Returns -1, 0 or 1 depending on the sign of n."""
    return (n > 0) - (n < 0)


# =====================================================================
# 4. PLAYER
# =====================================================================
class Player:
    def __init__(self, x, y):
        self.spawn = (x, y)
        self.rect = pygame.Rect(x, y, 30, 44)  # hitbox: used for collision and drawing
        self.pos = pygame.Vector2(x, y)        # precise float position (Rects only store ints)
        self.vel = pygame.Vector2(0, 0)        # velocity in px/second
        self.on_ground = False

        # Jump forgiveness timers (count down to 0)
        self.coyote = 0.0
        self.buffer = 0.0

        # Rocket state
        self.rocket_cd = 0.0

        # Dash state. "state" is a tiny state machine: "normal" or "dashing".
        # While dashing, normal input/gravity are suspended.
        self.state = "normal"
        self.dash_timer = 0.0
        self.dash_dir = pygame.Vector2(1, 0)
        self.can_dash = True                   # refilled on landing
        self.facing = 1                        # -1 left, 1 right; picks dash direction

    # ---------- which tiles block us right now? ----------
    def solids(self):
        """Dashing ignores phase walls. Otherwise they are solid like normal tiles."""
        return tiles if self.state == "dashing" else tiles + phase_tiles

    # ---------- one-off presses (jump buffer, rocket, dash) ----------
    def handle_event(self, event):
        # Jump press: start the buffer countdown. The jump itself happens in update.
        if event.type == pygame.KEYDOWN and event.key in JUMP_KEYS:
            self.buffer = JUMP_BUFFER

        # Rocket: launch opposite to the cursor. Not allowed mid-dash (design rule).
        if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                and self.rocket_cd <= 0 and self.state == "normal"):
            aim = pygame.Vector2(event.pos) - pygame.Vector2(self.rect.center)
            if aim.length() > 0:
                # SET velocity (not add) so the launch is consistent even if falling fast.
                self.vel = -aim.normalize() * ROCKET_SPEED
                self.rocket_cd = ROCKET_COOLDOWN
                self.coyote = 0  # a rocket shouldn't also grant a free ground jump

        # Dash: needs a charge. Starts the "dashing" state in the facing direction.
        if (event.type == pygame.KEYDOWN and event.key == pygame.K_LSHIFT
                and self.can_dash and self.state == "normal"):
            self.state = "dashing"
            self.dash_timer = DASH_TIME
            self.dash_dir = pygame.Vector2(self.facing, 0)
            self.can_dash = False

    # ---------- per-frame update ----------
    def update(self, dt):
        self.rocket_cd -= dt

        if self.state == "dashing":
            self.update_dash(dt)
        else:
            self.update_normal(dt)

        # Movement runs in both states, one axis at a time (see move_x / move_y).
        self.move_x(self.vel.x * dt)
        self.move_y(self.vel.y * dt)

        # Ground check: is a solid tile 1 px below our feet? Also recharges the dash.
        probe = self.rect.move(0, 1)
        self.on_ground = any(probe.colliderect(t) for t in self.solids())
        if self.on_ground:
            self.can_dash = True

        # Fell off the world? Respawn.
        if self.rect.top > HEIGHT + 200:
            self.respawn()

    def update_normal(self, dt):
        keys = pygame.key.get_pressed()
        direction = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
        if direction != 0:
            self.facing = direction

        # --- horizontal movement ---
        # "Boosted" means faster than MOVE_SPEED (e.g. after a rocket). We must NOT clamp
        # a boosted speed back to MOVE_SPEED instantly, or the rocket's horizontal push vanishes.
        was_under_cap = abs(self.vel.x) <= MOVE_SPEED
        if direction != 0:
            if was_under_cap or direction * self.vel.x < 0:
                # Normal acceleration (or steering against a boost).
                self.vel.x += direction * ACCEL * dt
                if was_under_cap:
                    self.vel.x = max(-MOVE_SPEED, min(MOVE_SPEED, self.vel.x))
            else:
                # Holding the same direction as a boost: let the extra speed bleed off gently.
                self.vel.x -= sign(self.vel.x) * BOOST_DRAG * dt
                self.vel.x = sign(self.vel.x) * max(MOVE_SPEED, abs(self.vel.x))
        else:
            # No input: slow down toward 0 (less friction in the air).
            slow = (FRICTION if self.on_ground else AIR_FRICTION) * dt
            self.vel.x = 0 if abs(self.vel.x) <= slow else self.vel.x - sign(self.vel.x) * slow

        # --- gravity ---
        self.vel.y = min(self.vel.y + GRAVITY * dt, MAX_FALL)

        # --- jump timers ---
        self.coyote = COYOTE_TIME if self.on_ground else self.coyote - dt
        self.buffer -= dt

        # Jump if a press is buffered AND we're grounded (or within coyote time).
        if self.buffer > 0 and self.coyote > 0:
            self.vel.y = -JUMP_SPEED  # negative = up
            self.buffer = 0
            self.coyote = 0

        # Variable jump height: releasing the key while rising cuts upward speed.
        # (Skipped right after a rocket so the rocket isn't cancelled by "no key held".)
        jump_held = any(keys[k] for k in JUMP_KEYS)
        rocketing = self.rocket_cd > ROCKET_COOLDOWN - 0.25
        if not jump_held and self.vel.y < 0 and not rocketing:
            self.vel.y *= JUMP_CUT ** (dt * 60)

    def update_dash(self, dt):
        self.dash_timer -= dt
        self.vel = self.dash_dir * DASH_SPEED  # fixed velocity: no gravity, no steering

        if self.dash_timer <= 0:
            # Don't end the dash while embedded in a phase wall, or collision would
            # snap us somewhere odd. Extend slightly until we're clear.
            if any(self.rect.colliderect(t) for t in phase_tiles):
                self.dash_timer = 0.02
            else:
                self.state = "normal"
                self.vel.x = self.facing * MOVE_SPEED  # keep a little momentum
                self.vel.y = 0

    # ---------- collision: one axis at a time ----------
    def move_x(self, dx):
        self.pos.x += dx
        self.rect.x = round(self.pos.x)
        for tile in self.solids():
            if self.rect.colliderect(tile):
                if dx > 0:
                    self.rect.right = tile.left    # moving right: stop at tile's left edge
                elif dx < 0:
                    self.rect.left = tile.right    # moving left: stop at tile's right edge
                self.pos.x = self.rect.x
                self.vel.x = 0
        # Level edges act as walls.
        if self.rect.left < 0 or self.rect.right > LEVEL_W:
            self.rect.left = max(0, min(self.rect.left, LEVEL_W - self.rect.width))
            self.pos.x = self.rect.x
            self.vel.x = 0

    def move_y(self, dy):
        self.pos.y += dy
        self.rect.y = round(self.pos.y)
        for tile in self.solids():
            if self.rect.colliderect(tile):
                if dy > 0:
                    self.rect.bottom = tile.top    # falling: land on top
                elif dy < 0:
                    self.rect.top = tile.bottom    # rising: bump head
                self.pos.y = self.rect.y
                self.vel.y = 0

    def respawn(self):
        self.pos.update(self.spawn)
        self.rect.topleft = self.spawn
        self.vel.update(0, 0)
        self.state = "normal"

    def draw(self, surface):
        # Colour hints at state: blue while dashing, yellow otherwise.
        color = (120, 200, 255) if self.state == "dashing" else (242, 193, 78)
        pygame.draw.rect(surface, color, self.rect)


# =====================================================================
# 5. GAME LOOP
# =====================================================================
def new_run():
    """Returns a fresh player, a zeroed timer, and won=False."""
    return Player(60, 300), 0.0, False


player, run_time, won = new_run()

while True:
    # dt = seconds since last frame. Clamped so a lag spike can't tunnel us through floors.
    dt = min(clock.tick(FPS) / 1000, 1 / 30)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
            player, run_time, won = new_run()
        if not won:
            player.handle_event(event)

    if not won:
        player.update(dt)
        run_time += dt
        if player.rect.colliderect(goal):
            won = True

    # ---------- draw ----------
    screen.fill((127, 178, 229))
    for t in tiles:
        pygame.draw.rect(screen, (47, 74, 58), t)
        pygame.draw.rect(screen, (34, 58, 44), t, 1)
    for t in phase_tiles:
        pygame.draw.rect(screen, (170, 110, 220), t)
    pygame.draw.rect(screen, (230, 70, 70), goal)  # the flag
    player.draw(screen)

    # Aim line shows where the rocket will point. The launch goes the opposite way.
    if player.rocket_cd <= 0:
        pygame.draw.line(screen, (255, 255, 255), player.rect.center, pygame.mouse.get_pos(), 1)

    hud = f"Time {run_time:5.2f}s   Dash {'ready' if player.can_dash else '--'}   Rocket {'ready' if player.rocket_cd <= 0 else '--'}"
    screen.blit(font.render(hud, True, (20, 25, 40)), (10, 10))
    if won:
        msg = font.render(f"Finished in {run_time:.2f}s. Press R to restart.", True, (20, 25, 40))
        screen.blit(msg, (WIDTH // 2 - msg.get_width() // 2, HEIGHT // 2 - 60))

    pygame.display.flip()