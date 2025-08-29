import sys
import random
import os
import csv
import time
from typing import Dict, List, Tuple, Optional
from PyQt6.QtWidgets import QApplication, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QPushButton, QWidget
from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QPixmap, QPainter
import pygame

# --- Sprite Data Classes ---
class SpriteInfo:
    def __init__(self, sheet_num: int, sprite_index: int, sprite_id: int,
                 width: int, height: int, x_offset: int, y_offset: int,
                 sheet_x: int, sheet_y: int):
        self.sheet_num = sheet_num
        self.sprite_index = sprite_index
        self.sprite_id = sprite_id
        self.width = width
        self.height = height
        self.x_offset = x_offset
        self.y_offset = y_offset
        self.sheet_x = sheet_x
        self.sheet_y = sheet_y

class SpriteFrame:
    def __init__(self, pixmap: QPixmap = None):
        self.pixmap = pixmap or QPixmap()

# --- Refactored Sprite Animator ---
class SpriteAnimator:
    """
    Handles directional sprite frames and movement.
    Direction indices: 0=N, 1=E, 2=S, 3=W
    Supports diagonal movement (45-degree tilt)
    """
    def __init__(self, scale_factor: float = 1.0):
        self.direction_frames: Dict[int, List[SpriteFrame]] = {0: [], 1: [], 2: [], 3: []}
        self.current_direction = 0
        self.current_frame_index = 0
        self.frame_duration = 100
        self.last_frame_time = 0
        self.pos_x = 0.0
        self.pos_y = 0.0
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.move_speed = 1.0
        self.is_moving = False
        self.next_direction_change_time = 0
        self.max_canvas_width = 0
        self.max_canvas_height = 0
        self.sprite_details: Dict[int, SpriteInfo] = {}
        self.spritesheets: Dict[int, QPixmap] = {}
        self.scale_factor = scale_factor

    # --- Load sprite info from NFO ---
    def load_sprite_info(self, nfo_path: str) -> bool:
        try:
            with open(nfo_path, 'r') as file:
                reader = csv.reader(file)
                for row in reader:
                    if not row or (row[0].startswith('#')):
                        continue
                    if len(row) >= 11:
                        try:
                            sheet_num = int(row[0].strip())
                            sprite_index = int(row[1].strip())
                            sprite_id = int(row[2].strip())
                            width = int(row[4].strip())
                            height = int(row[5].strip())
                            x_offset = int(row[6].strip())
                            y_offset = int(row[7].strip())
                            sheet_x = int(row[9].strip())
                            sheet_y = int(row[10].strip())
                            if 0 < width < 4096 and 0 < height < 4096:
                                self.sprite_details[sprite_id] = SpriteInfo(sheet_num, sprite_index, sprite_id,
                                                                            width, height, x_offset, y_offset,
                                                                            sheet_x, sheet_y)
                        except:
                            continue
            return len(self.sprite_details) > 0
        except FileNotFoundError:
            print(f"Could not open {nfo_path}")
            return False

    # --- Load spritesheets ---
    def load_spritesheet(self, sprite_directory: str) -> bool:
        sheet_numbers = {info.sheet_num for info in self.sprite_details.values()}
        for sheet_num in sheet_numbers:
            filename = os.path.join(sprite_directory, f"sprite_{sheet_num}.png")
            pixmap = QPixmap(filename)
            if pixmap.isNull():
                print(f"Could not load spritesheet: {filename}")
                return False
            self.spritesheets[sheet_num] = pixmap
        return True

    # --- Load frames for each direction ---
    def load_direction_frames(self, base_sprite_ids:list[int], frames_per_direction: int = 5):
        """
        Assumes consecutive sprite IDs for directions:
        base_sprite_id + 0 = North
        base_sprite_id + 1 = East
        base_sprite_id + 2 = South
        base_sprite_id + 3 = West
        """
        self.direction_frames = {0: [], 1: [], 2: [], 3: []}
        ref_x_offset = ref_y_offset = 0
        base_sprite_id = random.choice(base_sprite_ids)
        for dir_idx in range(4):
            for i in range(frames_per_direction):
                sprite_id = base_sprite_id + dir_idx + i*4
                if sprite_id not in self.sprite_details:
                    continue
                info = self.sprite_details[sprite_id]
                if info.sheet_num not in self.spritesheets:
                    continue
                spritesheet = self.spritesheets[info.sheet_num]
                
                # Create original canvas
                canvas = QPixmap(info.width, info.height)
                canvas.fill(Qt.GlobalColor.transparent)
                painter = QPainter(canvas)
                painter.drawPixmap(0, 0, spritesheet, info.sheet_x, info.sheet_y, info.width, info.height)
                painter.end()
                
                # Scale the canvas if needed
                if self.scale_factor != 1.0:
                    scaled_width = int(info.width * self.scale_factor)
                    scaled_height = int(info.height * self.scale_factor)
                    canvas = canvas.scaled(scaled_width, scaled_height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                
                self.direction_frames[dir_idx].append(SpriteFrame(canvas))

        # Determine max canvas (scaled dimensions)
        self.max_canvas_width = max([f.pixmap.width() for frames in self.direction_frames.values() for f in frames] or [0])
        self.max_canvas_height = max([f.pixmap.height() for frames in self.direction_frames.values() for f in frames] or [0])

    # --- Setup movement ---
    def setup_walking(self, screen_width: int, screen_height: int, start_x=None, start_y=None):
        self.pos_x = float(random.randint(0, screen_width - self.max_canvas_width)) if start_x is None else start_x
        self.pos_y = float(random.randint(0, screen_height - self.max_canvas_height)) if start_y is None else start_y
        self.set_direction(random.randint(0, 3))
        self.is_moving = True
        self.next_direction_change_time = int(time.time()*1000) + random.randint(1000, 3000)

    def set_direction(self, direction: int):
        self.current_direction = direction
        speed = self.move_speed
        # 45-degree diagonal tilt mapping
        if direction == 0:  # North-East
            self.velocity_x, self.velocity_y = speed, -speed
        elif direction == 1:  # South-East
            self.velocity_x, self.velocity_y = speed, speed
        elif direction == 2:  # South-West
            self.velocity_x, self.velocity_y = -speed, speed
        elif direction == 3:  # North-West
            self.velocity_x, self.velocity_y = -speed, -speed

    # --- Update animation and position ---
    def update(self, screen_width: int, screen_height: int):
        if not self.is_moving:
            return

        current_time = int(time.time() * 1000)

        # Frame animation
        frames = self.direction_frames.get(self.current_direction, [])
        if frames and current_time - self.last_frame_time >= self.frame_duration:
            self.current_frame_index = (self.current_frame_index + 1) % len(frames)
            self.last_frame_time = current_time

        # Random direction change
        if current_time >= self.next_direction_change_time:
            new_dir = random.choice([0, 1, 2, 3])
            if new_dir != self.current_direction:
                self.set_direction(new_dir)
            self.next_direction_change_time = current_time + random.randint(1000, 3000)

        # Move
        self.pos_x += self.velocity_x
        self.pos_y += self.velocity_y

        bounced = False
        if self.pos_x < 0 or self.pos_x > screen_width - self.max_canvas_width:
            bounced = True
        if self.pos_y < 0 or self.pos_y > screen_height - self.max_canvas_height:
            bounced = True

        if bounced:
            self.set_direction(random.choice([0,1,2,3]))

        self.pos_x = max(0, min(self.pos_x, screen_width - self.max_canvas_width))
        self.pos_y = max(0, min(self.pos_y, screen_height - self.max_canvas_height))

    def get_current_frame(self) -> Optional[SpriteFrame]:
        frames = self.direction_frames.get(self.current_direction, [])
        if not frames:
            return None
        return frames[self.current_frame_index]

    def get_position(self) -> Tuple[float, float]:
        return self.pos_x, self.pos_y

# --- Desktop Peep ---
class DesktopPeep:
    def __init__(self, base_sprite_id: int, nfo_path: str, sprite_directory: str, scale_factor: float = 1.0):
        self.animator = SpriteAnimator(scale_factor)
        if not self.animator.load_sprite_info(nfo_path) or not self.animator.load_spritesheet(sprite_directory):
            # fallback
            self.use_fallback = True
            fallback_size = int(64 * scale_factor)
            self.fallback_pixmap = QPixmap(fallback_size, fallback_size)
            self.fallback_pixmap.fill(Qt.GlobalColor.yellow)
            self.x = random.randint(0,800)
            self.y = random.randint(0,600)
            self.dx = random.choice([-2,-1,1,2])
            self.dy = random.choice([-2,-1,1,2])
        else:
            self.use_fallback = False
            self.animator.load_direction_frames(base_sprite_id)
            self.animator.move_speed = 0.5

        self.graphics_item = QGraphicsPixmapItem()
        if self.use_fallback:
            self.graphics_item.setPixmap(self.fallback_pixmap)

    def setup(self, screen_width:int, screen_height:int):
        if not self.use_fallback:
            self.animator.setup_walking(screen_width, screen_height)
        else:
            self.graphics_item.setPos(self.x, self.y)

    def update(self, screen_width:int, screen_height:int):
        if self.use_fallback:
            self.x += self.dx
            self.y += self.dy
            if self.x<0 or self.x+64>screen_width: self.dx*=-1
            if self.y<0 or self.y+64>screen_height: self.dy*=-1
            self.graphics_item.setPos(self.x, self.y)
        else:
            self.animator.update(screen_width, screen_height)
            frame = self.animator.get_current_frame()
            if frame:
                self.graphics_item.setPixmap(frame.pixmap)
            x, y = self.animator.get_position()
            self.graphics_item.setPos(x, y)

# --- Audio Manager ---
class AudioManager:
    def __init__(self):
        pygame.mixer.init()
        self.music_playing = False
        self.is_muted = False
        self.current_volume = 0.7  # Default volume
    
    def play_music(self, music_file: str):
        try:
            if os.path.exists(music_file):
                pygame.mixer.music.load(music_file)
                pygame.mixer.music.play(-1)  # -1 means loop indefinitely
                pygame.mixer.music.set_volume(self.current_volume)
                self.music_playing = True
                print(f"Playing background music: {music_file}")
            else:
                print(f"Music file not found: {music_file}")
        except pygame.error as e:
            print(f"Error playing music: {e}")
    
    def toggle_mute(self):
        if self.is_muted:
            pygame.mixer.music.set_volume(self.current_volume)
            self.is_muted = False
        else:
            pygame.mixer.music.set_volume(0.0)
            self.is_muted = True
        return self.is_muted
    
    def stop_music(self):
        if self.music_playing:
            pygame.mixer.music.stop()
            self.music_playing = False

# --- Control Panel Widget ---
class ControlPanel(QWidget):
    def __init__(self, audio_manager, main_canvas):
        super().__init__()
        self.audio_manager = audio_manager
        self.main_canvas = main_canvas
        self.is_minimized = False
        
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        
        # Position at bottom right
        screen_geom = QApplication.primaryScreen().geometry()
        self.expanded_size = (170, 50)  # Width for all buttons
        self.minimized_size = (50, 50)  # Width for just minimize button
        self.setGeometry(screen_geom.width() - self.expanded_size[0] - 10, screen_geom.height() - 60, *self.expanded_size)
        
        self.create_buttons()
        self.show()
    
    def create_buttons(self):
        # Minimize/Expand button
        self.minimize_button = QPushButton("−", self)
        self.minimize_button.setGeometry(0, 0, 50, 50)
        self.minimize_button.clicked.connect(self.toggle_minimize)
        self.minimize_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(100, 100, 100, 120);
                color: white;
                border: 2px solid rgba(255, 255, 255, 150);
                border-radius: 25px;
                font-size: 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(150, 150, 150, 180);
                border: 2px solid rgba(255, 255, 255, 200);
            }
        """)
        
        # Mute/Unmute button
        self.mute_button = QPushButton("🔊", self)
        self.mute_button.setGeometry(60, 0, 50, 50)
        self.mute_button.clicked.connect(self.toggle_mute)
        self.mute_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 0, 0, 120);
                color: white;
                border: 2px solid rgba(255, 255, 255, 150);
                border-radius: 25px;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(50, 50, 50, 180);
                border: 2px solid rgba(255, 255, 255, 200);
            }
        """)
        
        # Close button
        self.close_button = QPushButton("✕", self)
        self.close_button.setGeometry(120, 0, 50, 50)
        self.close_button.clicked.connect(self.close_app)
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(200, 0, 0, 120);
                color: white;
                border: 2px solid rgba(255, 255, 255, 150);
                border-radius: 25px;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(255, 0, 0, 180);
                border: 2px solid rgba(255, 255, 255, 200);
            }
        """)
    
    def toggle_minimize(self):
        screen_geom = QApplication.primaryScreen().geometry()
        
        if self.is_minimized:
            # Expand
            self.resize(*self.expanded_size)
            self.move(screen_geom.width() - self.expanded_size[0] - 10, screen_geom.height() - 60)
            self.mute_button.show()
            self.close_button.show()
            self.minimize_button.setText("−")
            self.is_minimized = False
        else:
            # Minimize
            self.resize(*self.minimized_size)
            self.move(screen_geom.width() - self.minimized_size[0] - 10, screen_geom.height() - 60)
            self.mute_button.hide()
            self.close_button.hide()
            self.minimize_button.setText("+")
            self.is_minimized = True
    
    def toggle_mute(self):
        is_muted = self.audio_manager.toggle_mute()
        self.mute_button.setText("🔇" if is_muted else "🔊")
    
    def close_app(self):
        self.main_canvas.close()
        self.close()

# --- Main Canvas ---
class MultiPeepDesktopCanvas(QGraphicsView):
    def __init__(self, base_sprite_id:int, n_peeps:int, scale_factor: float = 1.0, nfo_path:str="./output/sprites.nfo", sprite_directory:str="./output/"):
        super().__init__()
        self.peeps: List[DesktopPeep] = []
        self.scale_factor = scale_factor
        
        # Initialize audio manager and start music
        self.audio_manager = AudioManager()
        self.audio_manager.play_music("RollerCoaster Tycoon - Merry go round music.mp3")
        
        # --- Window transparency / overlay settings ---
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput  # Restored for desktop interaction
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        # --- Fullscreen transparent scene ---
        screen_geom = QApplication.primaryScreen().geometry()
        self.setGeometry(screen_geom)
        self.scene = QGraphicsScene()
        self.scene.setSceneRect(QRectF(screen_geom))
        self.scene.setBackgroundBrush(Qt.GlobalColor.transparent)
        self.setScene(self.scene)
        self.setStyleSheet("background: transparent;")
        
        # Hide scrollbars always
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.screen_width = screen_geom.width()
        self.screen_height = screen_geom.height()

        # --- Add peeps ---
        for _ in range(n_peeps):
            peep = DesktopPeep(base_sprite_id, nfo_path, sprite_directory, scale_factor)
            self.peeps.append(peep)
            self.scene.addItem(peep.graphics_item)
            peep.setup(self.screen_width, self.screen_height)

        # --- Timer ---
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_peeps)
        self.timer.start(16)

        # --- Create separate control panel ---
        self.control_panel = ControlPanel(self.audio_manager, self)

        self.show()
    
    def create_control_buttons(self):
        # Mute/Unmute button
        self.mute_button = QPushButton("🔊", self)
        self.mute_button.setGeometry(10, self.screen_height - 50, 40, 40)
        self.mute_button.clicked.connect(self.toggle_mute)
        self.mute_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 0, 0, 100);
                color: white;
                border: 2px solid rgba(255, 255, 255, 100);
                border-radius: 20px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(50, 50, 50, 150);
            }
        """)
        
        # Close button
        self.close_button = QPushButton("✕", self)
        self.close_button.setGeometry(60, self.screen_height - 50, 40, 40)
        self.close_button.clicked.connect(self.close)
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(200, 0, 0, 100);
                color: white;
                border: 2px solid rgba(255, 255, 255, 100);
                border-radius: 20px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(255, 0, 0, 150);
            }
        """)
    
    def toggle_mute(self):
        is_muted = self.audio_manager.toggle_mute()
        self.mute_button.setText("🔇" if is_muted else "🔊")

    def update_peeps(self):
        for peep in self.peeps:
            peep.update(self.screen_width, self.screen_height)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        super().keyPressEvent(event)
    
    def closeEvent(self, event):
        # Stop music and close control panel when closing the application
        if hasattr(self, 'control_panel'):
            self.control_panel.close()
        self.audio_manager.stop_music()
        super().closeEvent(event)

# --- Main ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    base_sprite_ids = [11301, 6409, 6505]
    n_peeps = 10
    scale_factor = 1 # 2x scale - change this to control sprite size (1.0 = original, 2.0 = double, 0.5 = half, etc.)
    canvas = MultiPeepDesktopCanvas(base_sprite_ids, n_peeps, scale_factor)
    sys.exit(app.exec())