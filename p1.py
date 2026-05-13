import cv2
import mediapipe as mp
# import pygame
import numpy as np
import threading
import math
import random
import time

# ─── CONFIG ───────────────────────────────────────────────────
WIDTH, HEIGHT = 800, 600
CAMERA_INDEX  = 0          # change to 1, 2… if wrong camera

# ─── SHARED STATE (thread-safe via simple assignment) ──────────
hand_data = {
    "landmarks": [],        # list of (x,y) in screen coords
    "pinch":     False,
    "spread":    False,
    "fist":      False,
    "fingers_up": 0,
    "palm_center": None,
}
running = True

# ─── PARTICLES ────────────────────────────────────────────────
class Particle:
    def __init__(self):
        self.reset()

    def reset(self):
        angle  = random.uniform(0, 2 * math.pi)
        radius = random.uniform(50, 350)
        self.base_x = WIDTH  // 2 + math.cos(angle) * radius
        self.base_y = HEIGHT // 2 + math.sin(angle) * radius
        self.x = self.base_x
        self.y = self.base_y
        self.vx = random.uniform(-0.3, 0.3)
        self.vy = random.uniform(-0.3, 0.3)
        self.size   = random.uniform(1, 3)
        self.color  = (
            random.randint(100, 255),
            random.randint(50,  200),
            random.randint(150, 255),
        )
        self.alpha  = random.randint(120, 255)
        self.angle  = angle
        self.orbit_r= radius
        self.orbit_speed = random.uniform(0.002, 0.008) * random.choice([-1, 1])

    def update(self, pull_x=None, pull_y=None, explode=False, spin_boost=0):
        self.angle += self.orbit_speed + spin_boost * 0.01

        # Drift toward orbit path
        target_x = WIDTH  // 2 + math.cos(self.angle) * self.orbit_r
        target_y = HEIGHT // 2 + math.sin(self.angle) * self.orbit_r
        self.x += (target_x - self.x) * 0.05
        self.y += (target_y - self.y) * 0.05

        # Hand pull
        if pull_x and pull_y:
            dx = pull_x - self.x
            dy = pull_y - self.y
            dist = math.hypot(dx, dy) + 1
            force = min(5000 / (dist * dist), 3)
            self.vx += (dx / dist) * force
            self.vy += (dy / dist) * force

        # Explode
        if explode:
            self.vx += random.uniform(-5, 5)
            self.vy += random.uniform(-5, 5)

        self.x  += self.vx
        self.y  += self.vy
        self.vx *= 0.92
        self.vy *= 0.92

        # Wrap
        if self.x < 0:   self.x = WIDTH
        if self.x > WIDTH:  self.x = 0
        if self.y < 0:   self.y = HEIGHT
        if self.y > HEIGHT: self.y = 0

    def draw(self, surface):
        # s = pygame.Surface((int(self.size*4)+2, int(self.size*4)+2), pygame.SRCALPHA)
        # pygame.draw.circle(s, (*self.color, self.alpha),
        #                    (int(self.size*2)+1, int(self.size*2)+1), int(self.size)+1)
        # surface.blit(s, (int(self.x - self.size*2), int(self.y - self.size*2)))
        pass


# ─── GEOMETRIC SHAPES ─────────────────────────────────────────
class Shape:
    def __init__(self):
        self.cx = random.randint(150, WIDTH-150)
        self.cy = random.randint(150, HEIGHT-150)
        self.kind   = random.choice(["triangle","square","hexagon","star","ring"])
        self.color  = (random.randint(100,255), random.randint(100,255), random.randint(100,255))
        self.radius = random.uniform(30, 70)
        self.angle  = 0
        self.rot_speed = random.uniform(-0.02, 0.02)
        self.alpha  = 180

    def poly_points(self, n, cx, cy, r, offset=0):
        pts = []
        for i in range(n):
            a = offset + 2 * math.pi * i / n
            pts.append((cx + math.cos(a)*r, cy + math.sin(a)*r))
        return pts

    def draw(self, surface, spin_boost=0):
        # self.angle += self.rot_speed + spin_boost * 0.005
        # s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        # c = (*self.color, self.alpha)
        # r = int(self.radius)
        #
        # if self.kind == "triangle":
        #     pts = self.poly_points(3, self.cx, self.cy, r, self.angle)
        #     pygame.draw.polygon(s, c, pts, 2)
        # elif self.kind == "square":
        #     pts = self.poly_points(4, self.cx, self.cy, r, self.angle + math.pi/4)
        #     pygame.draw.polygon(s, c, pts, 2)
        # elif self.kind == "hexagon":
        #     pts = self.poly_points(6, self.cx, self.cy, r, self.angle)
        #     pygame.draw.polygon(s, c, pts, 2)
        # elif self.kind == "star":
        #     outer = self.poly_points(5, self.cx, self.cy, r,       self.angle)
        #     inner = self.poly_points(5, self.cx, self.cy, r*0.4,   self.angle + math.pi/5)
        #     pts = []
        #     for o, i in zip(outer, inner):
        #         pts.extend([o, i])
        #     pygame.draw.polygon(s, c, pts, 2)
        # elif self.kind == "ring":
        #     pygame.draw.circle(s, c, (self.cx, self.cy), r, 2)
        #     pygame.draw.circle(s, c, (self.cx, self.cy), r//2, 2)
        #
        # surface.blit(s, (0, 0))
        pass

    def attract(self, px, py):
        dx = px - self.cx
        dy = py - self.cy
        dist = math.hypot(dx, dy) + 1
        self.cx += dx / dist * 2
        self.cy += dy / dist * 2


# ─── HAND TRACKING THREAD ─────────────────────────────────────
def hand_thread():
    global running
    mp_hands    = mp.solutions.hands
    mp_drawing  = mp.solutions.drawing_utils

    cap = cv2.VideoCapture(CAMERA_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  320)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

    with mp_hands.Hands(
        model_complexity=0,
        min_detection_confidence=0.6,
        min_tracking_confidence=0.5,
        max_num_hands=1
    ) as hands:
        while running:
            ret, frame = cap.read()
            if not ret:
                continue

            frame = cv2.flip(frame, 1)
            rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = hands.process(rgb)

            lm_screen = []
            pinch = spread = fist = False
            fingers_up = 0
            palm_center = None

            if result.multi_hand_landmarks:
                hl = result.multi_hand_landmarks[0]
                h, w = frame.shape[:2]

                for lm in hl.landmark:
                    sx = int(lm.x * WIDTH)
                    sy = int(lm.y * HEIGHT)
                    lm_screen.append((sx, sy))

                if lm_screen:
                    # Palm center (avg of wrist + 5 knuckles)
                    base_ids = [0,1,5,9,13,17]
                    px = sum(lm_screen[i][0] for i in base_ids) // 6
                    py = sum(lm_screen[i][1] for i in base_ids) // 6
                    palm_center = (px, py)

                    # Pinch: thumb tip (4) ↔ index tip (8)
                    t  = lm_screen[4]
                    idx= lm_screen[8]
                    pinch = math.hypot(t[0]-idx[0], t[1]-idx[1]) < 50

                    # Spread: palm width
                    pw = math.hypot(
                        lm_screen[5][0]-lm_screen[17][0],
                        lm_screen[5][1]-lm_screen[17][1]
                    )
                    spread = pw > 120

                    # Count fingers up (simple knuckle check)
                    tips    = [8, 12, 16, 20]
                    knuckles= [6, 10, 14, 18]
                    fingers_up = sum(
                        1 for t2, k in zip(tips, knuckles)
                        if lm_screen[t2][1] < lm_screen[k][1]
                    )
                    fist = fingers_up == 0

                # Draw on camera frame
                mp_drawing.draw_landmarks(frame, hl, mp_hands.HAND_CONNECTIONS)

            hand_data["landmarks"]   = lm_screen
            hand_data["pinch"]       = pinch
            hand_data["spread"]      = spread
            hand_data["fist"]        = fist
            hand_data["fingers_up"]  = fingers_up
            hand_data["palm_center"] = palm_center

            # Show small camera preview (optional, press Q to close)
            small = cv2.resize(frame, (320, 240))
            cv2.imshow("Hand Tracking (Q to quit)", small)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                running = False
                break

    cap.release()
    cv2.destroyAllWindows()


# ─── MAIN ─────────────────────────────────────────────────────
def main():
    global running

    # pygame.init()
    # screen = pygame.display.set_mode((WIDTH, HEIGHT))
    # pygame.display.set_caption("✦ Galaxy Hand Controller ✦")
    # clock  = pygame.time.Clock()

    # Assets
    # particles = [Particle() for _ in range(500)]
    # shapes    = [Shape() for _ in range(6)]

    # font_big  = pygame.font.SysFont("monospace", 18)
    # font_sm   = pygame.font.SysFont("monospace", 13)

    # Background stars
    # bg_stars = [(random.randint(0,WIDTH), random.randint(0,HEIGHT),
    #              random.randint(1,2), random.uniform(0.3,1.0)) for _ in range(200)]

    # Start hand thread
    ht = threading.Thread(target=hand_thread, daemon=True)
    ht.start()

    # explode_timer = 0
    # spin_boost    = 0
    # trail         = []

    try:
        while running:
            # ── Snapshot hand state ──
            lms         = hand_data["landmarks"]
            pinch       = hand_data["pinch"]
            spread      = hand_data["spread"]
            fist        = hand_data["fist"]
            fingers_up  = hand_data["fingers_up"]
            palm        = hand_data["palm_center"]

            # ── Gesture logic ──
            # if fist:
            #     explode_timer = 8
            #     spin_boost    = 0
            # if spread:
            #     spin_boost = 5
            # else:
            #     spin_boost = max(spin_boost - 0.1, 0)
            #
            # explode_now = explode_timer > 0
            # if explode_timer > 0:
            #     explode_timer -= 1
            #
            # pull_x, pull_y = (palm if palm else (None, None))
            #
            # # Trail
            # if palm:
            #     trail.append(palm)
            #     if len(trail) > 30:
            #         trail.pop(0)
            #
            # # ── Draw background ──
            # screen.fill((3, 3, 18))
            #
            # # Background stars twinkle
            # for sx, sy, sr, sbr in bg_stars:
            #     c = int(sbr * 180)
            #     pygame.draw.circle(screen, (c, c, c+30), (sx, sy), sr)
            #
            # # ── Draw nebula glow behind everything ──
            # nebula = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            # if palm:
            #     for radius, alpha in [(200, 8), (120, 14), (60, 20)]:
            #         pygame.draw.circle(nebula, (80, 30, 160, alpha), palm, radius)
            # screen.blit(nebula, (0, 0))
            #
            # # ── Update & draw particles ──
            # for p in particles:
            #     p.update(pull_x, pull_y, explode_now, spin_boost)
            #     p.draw(screen)
            #
            # # ── Draw shapes ──
            # for sh in shapes:
            #     if pinch and palm:
            #         sh.attract(*palm)
            #     sh.draw(screen, spin_boost)
            #
            # # ── Draw trail ──
            # for i in range(1, len(trail)):
            #     alpha_val = int(255 * i / len(trail))
            #     col = (alpha_val, int(alpha_val * 0.4), 200)
            #     if i > 1:
            #     #     pygame.draw.line(screen, col, trail[i-1], trail[i], 2)
            #
            # # ── Draw hand skeleton ──
            # if lms:
            #     CONNECTIONS = mp.solutions.hands.HAND_CONNECTIONS
            #     for conn in CONNECTIONS:
            #         a, b = conn
            #         if a < len(lms) and b < len(lms):
            #             pygame.draw.line(screen, (0, 200, 180), lms[a], lms[b], 2)
            #
            #     for i, (lx, ly) in enumerate(lms):
            #         is_tip = i in [4, 8, 12, 16, 20]
            #         r = 6 if is_tip else 3
            #         col = (255, 80, 80) if is_tip else (80, 255, 200)
            #         pygame.draw.circle(screen, col, (lx, ly), r)
            #         pygame.draw.circle(screen, (255,255,255), (lx, ly), r, 1)
            #
            # # ── HUD ──
            gesture = "·"
            if pinch:   gesture = "PINCH  → attract shapes"
            elif fist:  gesture = "FIST   → explode galaxy"
            elif spread:gesture = "SPREAD → spin galaxy"
            elif fingers_up == 1: gesture = "POINT  → pull particles"
            elif fingers_up >= 4: gesture = "OPEN HAND → free orbit"
            #
            # hud_lines = [
            #     "✦ GALAXY HAND CONTROLLER ✦",
            #     f"Gesture: {gesture}",
            #     f"Fingers up: {fingers_up}   Spin: {spin_boost:.1f}",
            # ]
            # for i, line in enumerate(hud_lines):
            #     col = (180, 120, 255) if i == 0 else (120, 220, 200)
            #     surf = font_sm.render(line, True, col)
            #     screen.blit(surf, (12, 10 + i * 18))
            #
            # help_txt = [
            #     "PINCH → pull shapes",
            #     "FIST  → explode",
            #     "SPREAD → spin",
            #     "POINT → attract",
            #     "ESC to quit",
            # ]
            # for i, t in enumerate(help_txt):
            #     surf = font_sm.render(t, True, (80, 80, 120))
            #     screen.blit(surf, (WIDTH - 160, 10 + i * 17))
            #
            # pygame.display.flip()
            # clock.tick(60)

            print(f"Landmarks: {len(lms)}, Pinch: {pinch}, Spread: {spread}, Fist: {fist}, Fingers up: {fingers_up}, Palm: {palm}, Gesture: {gesture}")
            time.sleep(0.1)

    except KeyboardInterrupt:
        running = False
    # pygame.quit()
if __name__ == "__main__":
    main()