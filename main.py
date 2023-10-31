import sys
from random import Random

import pygame
from pygame.locals import *
from pygame.math import Vector2
from pygame.surface import Surface
from pygame.time import Clock


class BgScroll:
    def __init__(self, image: Surface, dx: float = 1, flip: bool = False) -> None:
        image = pygame.transform.scale(image, (Game.WIDTH, Game.HEIGHT))
        if flip:
            image = pygame.transform.flip(image, True, True)
        self.image = image
        self.x = 0
        self.dx = dx

    def update(self, clock: Clock) -> None:
        self.x += self.dx
        if self.x > Game.WIDTH:
            self.x = 0

    def draw(self, surface: Surface) -> None:
        surface.blit(self.image, (self.x, 0))
        surface.blit(self.image, (self.x - Game.WIDTH, 0))


class Sprite:
    def __init__(self, image: Surface, position: Vector2, frame_count: int = 1) -> None:
        self.original_image = image
        self.image = None
        self._position = position
        frame_width = image.get_width() / frame_count
        frame_height = image.get_height()
        self.frames = []
        self.frames.extend(
            Rect(i * frame_width, 0, frame_width, frame_height)
            for i in range(frame_count)
        )
        self._current_frame = 0
        self._rotate = 0
        self.velocity = Vector2(0, 0)
        self.wrap = False
        self.radius = frame_width / 2
        self.is_dead = False
        self.drotate = 0
        self._scale = 1
        self.create_image()

    def get_current_frame(self) -> int:
        return self._current_frame

    def set_current_frame(self, value: int) -> None:
        self._current_frame = max(0, min(len(self.frames) - 1, value))
        self.create_image()

    def get_rotate(self) -> int:
        return self._rotate

    def set_rotate(self, value: int) -> None:
        self._rotate = value % 360
        self.create_image()

    def get_position(self) -> Vector2:
        return self._position

    def set_position(self, value: Vector2) -> None:
        if self.wrap:
            x = (value.x + Game.WIDTH) % Game.WIDTH
            y = (value.y + Game.HEIGHT) % Game.HEIGHT
            self._position = Vector2(x, y)
        else:
            self._position = value

    def get_scale(self) -> float:
        return self._scale

    def set_scale(self, value: float):
        self._scale = value
        self.create_image()

    def create_image(self) -> None:
        image = self.original_image.subsurface(self.frames[self._current_frame])
        if self._scale != 1:
            image = pygame.transform.scale(image, (
                int(image.get_width() * self._scale), int(image.get_height() * self._scale)))
            self.radius = image.get_width() / 2
        if self._rotate != 0:
            orig_rect = image.get_rect()  # type: Rect
            rot_image = pygame.transform.rotate(image, self._rotate)  # type: Surface
            rot_rect = orig_rect.copy()
            rot_rect.center = rot_image.get_rect().center
            image = rot_image.subsurface(rot_rect).copy()
        self.image = image

    def is_circle_collide(self, other) -> bool:
        return (self._position - other.position).length() < self.radius + other.radius

    def update(self, clock: Clock) -> None:
        self.position += self.velocity
        self.rotate += self.drotate

    def draw(self, surface: Surface) -> None:
        if not self.is_dead:
            surface.blit(self.image, (self._position.x - self.radius, self._position.y - self.radius))

    current_frame = property(get_current_frame, set_current_frame)
    rotate = property(get_rotate, set_rotate)
    position = property(get_position, set_position)
    scale = property(get_scale, set_scale)


class Ship(Sprite):

    def __init__(self, image: Surface, position: Vector2) -> None:
        super().__init__(image, position, 2)
        self.thrust = False
        self.wrap = True

    def get_heading(self) -> Vector2:
        p = Vector2()
        p.from_polar((1, -self.rotate))
        return p

    def update(self, clock: Clock) -> None:
        if self.thrust:
            self.current_frame = 1
            self.velocity += self.get_heading() * 0.1
            Game.sound_manager.play_thrust()
        else:
            self.current_frame = 0
            Game.sound_manager.stop_thrust()
        self.velocity *= 0.99
        super().update(clock)


class Manager:
    def __init__(self, image: Surface) -> None:
        self.image = image
        self.objects = []

    def update(self, clock: Clock) -> None:
        i = len(self.objects) - 1
        while i >= 0:
            self.objects[i].update(clock)
            if self.objects[i].is_dead:
                self.objects.remove(self.objects[i])
            i -= 1

    def draw(self, surface: Surface) -> None:
        for o in self.objects:
            o.draw(surface)


class Shot(Sprite):
    MAX_TIME_TO_LIVE = 80

    def __init__(self, image: Surface, position: Vector2, velocity: Vector2) -> None:
        super().__init__(image, position)
        self.velocity = velocity
        self.wrap = True
        self.time_to_live = Shot.MAX_TIME_TO_LIVE

    def update(self, clock: Clock) -> None:
        if self.time_to_live > 0:
            self.time_to_live -= 1
            if self.time_to_live == 0:
                self.is_dead = True
        super().update(clock)


class ShotManager(Manager):
    MAX_SHOT_DELAY = 15

    def __init__(self, image: Surface) -> None:
        super().__init__(image)
        self.shot_delay = 0

    def update(self, clock: Clock) -> None:
        if self.shot_delay > 0:
            self.shot_delay -= 1
        super().update(clock)

    def add_shot(self, position: Vector2, velocity: Vector2) -> None:
        if self.shot_delay == 0:
            self.objects.append(Shot(self.image, position, velocity))
            self.shot_delay = ShotManager.MAX_SHOT_DELAY
            Game.sound_manager.play_shot()


class Asteroid(Sprite):
    def __init__(self, image: Surface, position: Vector2, velocity: Vector2, drotate: int, scale: float) -> None:
        super().__init__(image, position)
        self.velocity = velocity
        self.wrap = True
        self.drotate = drotate
        self.scale = scale


class AsteroidManager(Manager):
    rnd = Random()

    def add_asteroid(self, scale: float, position: Vector2 = None) -> None:
        if position is None:
            position = Vector2(self.rnd.randint(0, Game.WIDTH), self.rnd.randint(0, Game.HEIGHT))
        alfa = self.rnd.randint(0, 360)
        vel = Vector2()
        vel.from_polar((1, alfa))
        rot = self.rnd.randint(-10, 10)
        self.objects.append(Asteroid(self.image, position, vel, rot, scale))

    def add_asteroids(self, num: int) -> None:
        for _ in range(num):
            self.add_asteroid(1)


class Explosion(Sprite):
    def __init__(self, image: Surface, position: Vector2) -> None:
        super().__init__(image, position, 24)

    def update(self, clock: Clock) -> None:
        self.current_frame += 1
        if self.current_frame == 23:
            self.is_dead = True
        super().update(clock)


class ExplosionManager(Manager):
    def add_explosion(self, position: Vector2) -> None:
        self.objects.append(Explosion(self.image, position))
        Game.sound_manager.play_explosion()


class SoundManager:
    def __init__(self) -> None:
        pygame.mixer.init()
        self.sound = pygame.mixer.Sound("sounds\\soundtrack.ogg")
        self.sound.play(-1)
        self.shot = pygame.mixer.Sound("sounds\\missile.ogg")
        self.explosioves = pygame.mixer.Sound("sounds\\explosion.ogg")
        self.thrust = pygame.mixer.Sound("sounds\\thrust.ogg")
        self.playthrust = False

    def play_shot(self) -> None:
        self.shot.play(0)

    def play_explosion(self) -> None:
        self.explosioves.play(0)

    def play_thrust(self) -> None:
        if not self.playthrust:
            self.thrust.play(-1)
            self.playthrust=True

    def stop_thrust(self) -> None:
        if self.playthrust:
            self.thrust.stop()
            self.playthrust=False

class Game:
    WIDTH = 800
    HEIGHT = 600
    GAME_MENU = 0
    GAME_PLAY = 1
    TEXT_WAIT = 30
    MAX_RESPAWN_TIME = 250
    sound_manager = None

    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Asteroids")
        self.surface = pygame.display.set_mode((Game.WIDTH, Game.HEIGHT))
        self.clock = pygame.time.Clock()

        self.background = pygame.image.load("images\\nebula_blue.f2014.png").convert()
        self.bgscroll1 = BgScroll(pygame.image.load("images\\debris2_blue.png").convert_alpha(), 0.5, True)
        self.bgscroll2 = BgScroll(pygame.image.load("images\\debris2_blue.png").convert_alpha())
        self.ship = Ship(pygame.image.load("images\\double_ship.png").convert_alpha(), Vector2(100, 100))
        self.ship.is_dead = True
        self.shot_manager = ShotManager(pygame.image.load("images\\shot2.png").convert_alpha())
        self.asteroid_manager = AsteroidManager(pygame.image.load("images\\asteroid_blue.png").convert_alpha())
        self.explosion_manager = ExplosionManager(pygame.image.load("images\\explosion_alpha.png").convert_alpha())
        self.game_state = Game.GAME_MENU
        self.logo = pygame.image.load("images\\asteroids.png")
        self.font = pygame.font.Font("fonts\\calibri.ttf", 16)
        self.text_visible = True
        self.text_blink = 0
        self.level = 0
        self.lives = 0
        self.score = 0
        self.respawn_time = 0
        Game.sound_manager = SoundManager()

    def run(self) -> None:
        while True:
            for event in pygame.event.get():
                if event.type == QUIT:
                    pygame.quit()
                    sys.exit()
            self.update(self.clock)
            self.draw(self.surface)
            pygame.display.update()
            self.clock.tick(60)

    def update(self, clock: Clock) -> None:
        self.bgscroll1.update(clock)
        self.bgscroll2.update(clock)
        keys = pygame.key.get_pressed()
        if self.game_state == Game.GAME_MENU:
            if keys[K_SPACE]:
                self.restart()
            if self.text_blink > 0:
                self.text_blink -= 1
            else:
                self.text_blink = Game.TEXT_WAIT
                self.text_visible = not self.text_visible
        else:
            if keys[K_LEFT]:
                self.ship.rotate += 5
            if keys[K_RIGHT]:
                self.ship.rotate -= 5
            self.ship.thrust = keys[K_UP]
            if keys[K_LCTRL]:
                self.shot_manager.add_shot(self.ship.position + self.ship.get_heading() * self.ship.radius,
                                           self.ship.get_heading() * 3)
            if self.respawn_time > 0:
                self.respawn_time -= 1
                if self.respawn_time == 0:
                    self.ship.is_dead = False
                    self.ship.position = Vector2(Game.WIDTH / 2, Game.HEIGHT / 2)
        self.ship.update(clock)
        self.chk_collisions()
        self.shot_manager.update(clock)
        self.asteroid_manager.update(clock)
        self.explosion_manager.update(clock)
        if len(self.asteroid_manager.objects) == 0:
            self.level += 1
            self.asteroid_manager.add_asteroids(3 + self.level * 2)

    def draw(self, surface: Surface) -> None:
        surface.blit(self.background, (0, 0))
        self.bgscroll1.draw(surface)
        if self.game_state == Game.GAME_MENU:
            surface.blit(self.logo, ((Game.WIDTH - self.logo.get_width()) / 2, 100))
            if self.text_visible:
                text = self.font.render("Press SPACE to continue", True, (255, 255, 255))  # type: Surface
                text_rect = text.get_rect()  # type: Rect
                text_rect.x = (Game.WIDTH - text_rect.width) / 2
                text_rect.y = 350
                surface.blit(text, text_rect)
        self.bgscroll2.draw(surface)
        self.ship.draw(surface)
        self.shot_manager.draw(surface)
        self.asteroid_manager.draw(surface)
        self.explosion_manager.draw(surface)
        text = self.font.render(
            f"Lives:{str(self.lives)} Level:{str(self.level)} Score:{str(self.score)}",
            True,
            (255, 255, 255),
        )
        text_rect = text.get_rect()
        text_rect.x = 10
        text_rect.y = 10
        surface.blit(text, text_rect)

    def chk_collisions(self) -> None:
        for asteroid in self.asteroid_manager.objects:
            for shot in self.shot_manager.objects:
                if not asteroid.is_dead and not shot.is_dead and shot.is_circle_collide(asteroid):
                    shot.is_dead = True
                    asteroid.is_dead = True
                    self.explosion_manager.add_explosion(asteroid.position)
                    self.score += 1000
                    if asteroid.scale > 0.5:
                        scale = 0.75 if asteroid.scale == 1 else 0.5
                        self.asteroid_manager.add_asteroid(scale, asteroid.position)
                        self.asteroid_manager.add_asteroid(scale, asteroid.position)
            if not asteroid.is_dead and not self.ship.is_dead and self.ship.is_circle_collide(asteroid):
                self.lives -= 1
                self.ship.is_dead = True
                self.ship.thrust = False
                self.explosion_manager.add_explosion(self.ship.position)
                if self.lives == 0:
                    self.game_state = Game.GAME_MENU
                else:
                    self.respawn_time = Game.MAX_RESPAWN_TIME

    def restart(self):
        self.ship.position = Vector2(Game.WIDTH / 2, Game.HEIGHT / 2)
        self.ship.is_dead = False
        self.asteroid_manager.objects.clear()
        self.asteroid_manager.add_asteroids(5)
        self.level = 1
        self.lives = 3
        self.score = 0
        self.game_state = Game.GAME_PLAY


game = Game()
game.run()
