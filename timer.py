from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.clock import Clock
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.core.audio import SoundLoader
from kivy.core.text import Label as CoreLabel
import random
import time
import os
from glob import glob

# Generic image icon button to be used from kv
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.widget import Widget
from kivy.metrics import dp
from kivy.properties import StringProperty
from kivy.uix.image import Image

GardenSvgWidget = None
GardenSvgInstruction = None

class IconButton(ButtonBehavior, Widget):
    source = StringProperty('')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._icon = None  # used for Image or SvgWidget
        self._mode = 'none'  # 'widget', 'image', 'canvas', 'draw', or 'none'
        self._svg_group = None  # InstructionGroup when drawing Svg on canvas
        self._svg_obj = None
        self._tr = None
        self._sc = None
        # Fallback drawing
        self._draw_group = None
        self._draw_kind = None  # 'play', 'pause', 'reset'
        self.bind(size=self._relayout, pos=self._relayout)
        self.bind(source=self._reload_source)

    def on_kv_post(self, base_widget):
        # Ensure the initial icon is created once added from kv
        self._reload_source()

    def _clear_icon(self):
        # Remove any previous child widget
        if self._icon is not None:
            try:
                self.remove_widget(self._icon)
            except Exception:
                pass
            self._icon = None
        # Remove any previous canvas instructions
        if self._svg_group is not None:
            try:
                self.canvas.remove(self._svg_group)
            except Exception:
                pass
            self._svg_group = None
            self._svg_obj = None
            self._tr = None
            self._sc = None
        if self._draw_group is not None:
            try:
                self.canvas.after.remove(self._draw_group)
            except Exception:
                try:
                    self.canvas.remove(self._draw_group)
                except Exception:
                    pass
            self._draw_group = None
            self._draw_kind = None
        self._mode = 'none'

    def _infer_draw_kind(self, src: str):
        s = src.lower()
        if 'play' in s:
            return 'play'
        if 'pause' in s:
            return 'pause'
        if 'reset' in s or 'refresh' in s or 'reload' in s:
            return 'reset'
        if 'prev' in s or 'back' in s or 'left' in s:
            return 'prev'
        if 'next' in s or 'forward' in s or 'right' in s:
            return 'next'
        return 'play'

    def _reload_source(self, *args):
        self._clear_icon()
        src = self.source or ''
        try:
            if src.lower().endswith('.svg'):
                if GardenSvgWidget is not None:
                    # Preferred path: dedicated widget for svg
                    self._icon = GardenSvgWidget(filename=src)
                    self._icon.size_hint = (None, None)
                    self.add_widget(self._icon)
                    self._mode = 'widget'
                    self._relayout()
                    return
                elif GardenSvgInstruction is not None:
                    # Fallback path: draw Svg as canvas instructions with manual scaling
                    from kivy.graphics import InstructionGroup, PushMatrix, PopMatrix, Translate, Scale
                    self._svg_group = InstructionGroup()
                    self._tr = Translate(0, 0, 0)
                    self._sc = Scale(1.0, 1.0, 1.0)
                    self._svg_obj = GardenSvgInstruction(filename=src)
                    self._svg_group.add(PushMatrix())
                    self._svg_group.add(self._tr)
                    self._svg_group.add(self._sc)
                    self._svg_group.add(self._svg_obj)
                    self._svg_group.add(PopMatrix())
                    self.canvas.add(self._svg_group)
                    self._mode = 'canvas'
                    self._relayout()
                    return
                else:
                    # No SVG support; draw vector icon via canvas primitives
                    self._draw_kind = self._infer_draw_kind(src)
                    self._mode = 'draw'
                    self._relayout()
                    return
            # Raster image fallback (png/jpg)
            self._icon = Image(source=src, allow_stretch=True, keep_ratio=True)
            self._icon.size_hint = (None, None)
            self.add_widget(self._icon)
            self._mode = 'image'
            self._relayout()
        except Exception:
            # If loading fails, leave empty
            self._mode = 'none'

    def _relayout(self, *args):
        try:
            pad = dp(6)
        except Exception:
            pad = 6
        w = max(0, self.width - 2 * pad)
        h = max(0, self.height - 2 * pad)
        size = min(w, h)
        if self._mode in ('widget', 'image') and self._icon is not None:
            self._icon.size = (size, size)
            # Center inside self
            self._icon.pos = (self.x + (self.width - size) / 2.0, self.y + (self.height - size) / 2.0)
        elif self._mode == 'canvas' and self._svg_obj is not None and self._tr is not None and self._sc is not None:
            # Determine intrinsic SVG size
            try:
                sw = float(getattr(self._svg_obj, 'width', 0)) or 1.0
                sh = float(getattr(self._svg_obj, 'height', 0)) or 1.0
            except Exception:
                sw, sh = 100.0, 100.0
            scale = min((w / sw) if sw else 1.0, (h / sh) if sh else 1.0)
            # Center within the button rect
            tx = self.x + (self.width - (sw * scale)) / 2.0
            ty = self.y + (self.height - (sh * scale)) / 2.0
            # Apply transform
            try:
                self._sc.xyz = (scale, scale, 1)
            except Exception:
                try:
                    self._sc.x = scale; self._sc.y = scale; self._sc.z = 1
                except Exception:
                    pass
            try:
                self._tr.xyz = (tx, ty, 0)
            except Exception:
                try:
                    self._tr.x = tx; self._tr.y = ty; self._tr.z = 0
                except Exception:
                    pass
        elif self._mode == 'draw':
            # Draw simple vector icons as a fallback (white on transparent)
            from kivy.graphics import InstructionGroup, Color, Line, Triangle, Rectangle
            # Clear previous
            if self._draw_group is not None:
                try:
                    self.canvas.after.remove(self._draw_group)
                except Exception:
                    try:
                        self.canvas.remove(self._draw_group)
                    except Exception:
                        pass
                self._draw_group = None
            g = InstructionGroup()
            # Icon color (white)
            g.add(Color(1, 1, 1, 1))
            cx = self.x + self.width / 2.0
            cy = self.y + self.height / 2.0
            # Draw within centered square of side `size`
            left = cx - size / 2.0
            bottom = cy - size / 2.0
            right = cx + size / 2.0
            top = cy + size / 2.0
            # Add some inner padding for the glyph itself
            inner_pad = size * 0.15
            l = left + inner_pad
            r = right - inner_pad
            b = bottom + inner_pad
            t = top - inner_pad
            if self._draw_kind == 'play':
                # Right-pointing triangle
                g.add(Triangle(points=[l, b, l, t, r, (b + t) / 2.0]))
            elif self._draw_kind == 'pause':
                # Two vertical bars
                bar_w = (r - l) * 0.28
                gap = (r - l) * 0.18
                # Left bar
                g.add(Rectangle(pos=(l, b), size=(bar_w, t - b)))
                # Right bar
                g.add(Rectangle(pos=(l + bar_w + gap, b), size=(bar_w, t - b)))
            elif self._draw_kind == 'reset':
                # Circular arrow (arc + triangle head)
                radius = min(r - l, t - b) / 2.0
                from math import cos, sin, radians
                # Arc centered slightly left to leave room for arrow head
                arc_cx = cx - radius * 0.05
                arc_cy = cy
                start = 40
                end = 320
                g.add(Line(circle=(arc_cx, arc_cy, radius * 0.8, start, end), width=2))
                # Arrow head at approx end angle
                ang = radians(start)
                ax = arc_cx + radius * 0.8 * cos(ang)
                ay = arc_cy + radius * 0.8 * sin(ang)
                ah = radius * 0.28
                # Small triangular arrow head
                g.add(Triangle(points=[ax, ay, ax - ah * 0.9, ay + ah * 0.4, ax - ah * 0.1, ay + ah * 1.0]))
            elif self._draw_kind == 'prev':
                # Left-pointing chevron/triangle
                # Use a narrower inner padding to make it bolder
                g.add(Line(points=[r, b, l + (r - l) * 0.45, (b + t) / 2.0, r, t], width=2, cap='round', joint='round') )
            elif self._draw_kind == 'next':
                # Right-pointing chevron/triangle
                g.add(Line(points=[l, b, r - (r - l) * 0.45, (b + t) / 2.0, l, t], width=2, cap='round', joint='round'))
            # Push to canvas.after so it sits above the grey background
            self._draw_group = g
            try:
                self.canvas.after.add(self._draw_group)
            except Exception:
                self.canvas.add(self._draw_group)

class DraftTimer(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", **kwargs)

        # Mode and round tracking
        self.mode = "Expert"
        self.current_round = 0
        self.pick_index = 0
        self.paused = False
        self.paused_remaining = None  # stores remaining seconds when user pauses

        # Sound suppression window (epoch seconds). When now < suppress_until, no tick/animal sounds.
        self.suppress_until = 0

        # Phase timing (wall-clock based)
        self.phase_start_ts = 0  # epoch seconds when current phase started
        self.phase_duration = 0  # seconds allocated to current phase

        # Prepare sound paths but avoid loading them synchronously here to prevent UI jank on first open (especially on Android).
        audio_files = []
        try:
            for pattern in ('*.mp3', '*.wav', '*.ogg'):
                audio_files.extend(glob(os.path.join('assets', pattern)))
        except Exception:
            audio_files = [
                os.path.join('assets', f) for f in [
                    'bark.mp3', 'bark.wav', 'meow.wav', 'bird.mp3', 'cow.wav',
                    'crow.mp3', 'duck.mp3', 'goat.mp3', 'horse.mp3', 'rooster.mp3',
                    'elephant.mp3', 'howl.mp3', 'lion.mp3', 'owl.mp3', 'seagulls.mp3', 'sheep.mp3'
                ]
            ]
        # Exclude tick sound and non-existing files; keep only file paths for lazy loading
        self.animal_sound_paths = [
            p for p in audio_files
            if os.path.basename(p).lower() != 'tick.wav' and os.path.isfile(p)
        ]
        # Cache for loaded Sound objects (path -> Sound)
        self._sound_cache = {}
        # Backward-compat list to hold loaded sounds when available (used for stopping any playing sounds)
        self.animal_sounds = []
        # Load the tick sound only (small, commonly used near zero)
        try:
            self.tick_sound = SoundLoader.load("assets/tick.wav")
        except Exception:
            self.tick_sound = None

        # Prepare sequences
        self.sequences = self.get_sequences()
        self.timer_event = None
        # Track a pending transition between phases to avoid duplications
        self.transition_event = None
        self.time_left = 0

        # UI: Top Booster, middle Pick, big Time, then compact mode spinner
        # Booster label (top)
        self.booster_label = Label(text="Booster 1", size_hint=(1, None))
        try:
            self.booster_label.height = dp(34)
            self.booster_label.font_size = '22sp'
        except Exception:
            self.booster_label.height = 34
        self.add_widget(self.booster_label)

        # Pick label (smaller, centered)
        self.pick_label = Label(text="", size_hint=(1, None))
        try:
            self.pick_label.height = dp(26)
            self.pick_label.font_size = '16sp'
        except Exception:
            self.pick_label.height = 26
        self.add_widget(self.pick_label)

        # Big time label (takes most of the space)
        self.time_label = Label(text="Ready", size_hint=(1, 1))
        # Auto-fit text with 10dp side margins when it's words; maximize when numeric countdown
        try:
            from kivy.metrics import sp
        except Exception:
            sp = lambda v: v

        def _is_numeric_text(t: str):
            t = t.strip()
            return len(t) > 0 and all(ch.isdigit() for ch in t)

        def _fit_label_font(label: Label, max_w: float, max_h: float, max_px: float, min_px: float = 10.0, measure_text: str = None):
            # Iteratively reduce font size until the texture of measure_text (or label.text) fits within max_w and max_h
            size = max_px if max_px and max_px > 0 else 10.0
            fitted = False
            # Use CoreLabel to measure text without altering the visible widget text and avoid flicker
            text_to_measure = measure_text if (measure_text is not None and len(measure_text) > 0) else label.text
            for _ in range(500):  # cap iterations with fine steps
                try:
                    cl = CoreLabel(text=text_to_measure, font_size=size)
                    cl.refresh()
                    tw, th = cl.texture.size if cl.texture else (0, 0)
                    if tw <= max_w and th <= max_h:
                        fitted = True
                        break
                except Exception:
                    break
                size -= 0.5  # finer decrement to avoid slight overflow
                if size <= min_px:
                    size = min_px
                    fitted = True
                    break
            # Apply a safety shrink to ensure we don't touch the edges due to rounding
            try:
                if fitted:
                    safe_size = max(min_px, size - 1.0)
                    label.font_size = safe_size
            except Exception:
                pass

        def _refit_all(*_):
            # Available width is this widget width minus side margins and a tiny safety pad
            try:
                margin = dp(28)
                safe_pad_w = dp(5)
                safe_pad_h = dp(4)
            except Exception:
                margin = 28
                safe_pad_w = 5
                safe_pad_h = 4
            max_w = max(0, self.width - 2 * margin - 2 * safe_pad_w)
            # Booster and Pick labels: fit within their own heights and available width
            for lbl in (self.booster_label, self.pick_label):
                try:
                    max_h = max(0, lbl.height * 0.90 - safe_pad_h)
                    # Start from a reasonable upper bound (in px)
                    max_px = max(12.0, min(sp(64), max_h))
                    _fit_label_font(lbl, max_w, max_h, max_px, min_px=sp(10))
                except Exception:
                    pass
            # Time label: if numeric, maximize; else fit like text
            try:
                max_w_time = max(0, self.width - 2 * margin - 2 * safe_pad_w)
                max_h_time = max(0, self.time_label.height * 0.90 - safe_pad_h)
                if _is_numeric_text(self.time_label.text):
                    # For numbers, allow a larger starting size (nearly fill height)
                    max_px = max(24.0, max_h_time)
                    # Measure against widest two-digit string to avoid overflow on glyph changes
                    _fit_label_font(self.time_label, max_w_time, max_h_time, max_px, min_px=sp(12), measure_text='88')
                else:
                    max_px = max(24.0, min(sp(160), max_h_time))
                    _fit_label_font(self.time_label, max_w_time, max_h_time, max_px, min_px=sp(12))
            except Exception:
                pass

        # Expose refit so other methods can call it without rebinding
        self._refit_all = _refit_all
        # Bind refit on size changes only (avoid per-second refit on numeric text updates)
        self.bind(size=_refit_all)
        self.time_label.bind(size=_refit_all)
        # Booster and Pick labels should also trigger refit on their changes
        self.booster_label.bind(size=_refit_all, text=_refit_all)
        self.pick_label.bind(size=_refit_all, text=_refit_all)
        # Add time label and perform initial fit
        self.add_widget(self.time_label)
        _refit_all()

        # Mode spinner (kept compact and below the time)
        self.spinner = Spinner(
            text="Expert",
            values=("Expert", "Regular", "Beginner", "Test"),
            size_hint=(1, None)
        )
        # Make the mode dial compact
        try:
            self.spinner.height = dp(36)
            self.spinner.font_size = '14sp'
        except Exception:
            self.spinner.height = 36
        self.spinner.bind(text=self.set_mode)
        self.add_widget(self.spinner)
        # Initialize spinner state (enabled on waiting page)
        try:
            self._update_spinner_state()
        except Exception:
            pass
        # Controls moved to kv: DraftTimerScreen now provides Play/Pause/Reset buttons

    def set_mode(self, spinner, text):
        self.mode = text
        self.sequences = self.get_sequences()
        self.reset_all(None)

    def get_sequences(self):
        expert = [50, 50, 45, 45, 40, 35, 30, 25, 20, 15, 10, 5, 5]
        regular = [60, 60, 55, 50, 45, 40, 35, 30, 25, 20, 15, 10, 5]
        beginner = [70, 70, 65, 65, 60, 55, 50, 40, 30, 20, 15, 10, 5]
        test = [1, 1, 1]
        return {
            "Expert": expert,
            "Regular": regular,
            "Beginner": beginner,
            "Test": test
        }

    def start_sequence(self, instance):
        # Start or resume sequence
        if self.timer_event:
            return
        # Ensure spinner reflects non-waiting state when resuming
        try:
            self._update_spinner_state()
        except Exception:
            pass
        if self.current_round > 0 and self.paused and self.phase_duration > 0:
            # Resume current phase from the exact paused remaining value
            remaining = self.paused_remaining if self.paused_remaining is not None else self.get_remaining()
            self.paused = False
            self.paused_remaining = None
            # Re-anchor start time so remaining stays the same
            self.phase_start_ts = time.time() - (self.phase_duration - int(remaining))
            # Refresh headers and current remaining
            try:
                self._update_headers()
                self.time_label.text = str(int(remaining))
            except Exception:
                pass
            self.timer_event = Clock.schedule_interval(self.update, 1)
            self.update(0)
            return
        # Fresh start
        self.current_round = 1
        self.pick_index = 0
        self.paused = False
        self.paused_remaining = None
        self.start_next_timer()

    def start_next_timer(self, dt=None):
        # Ensure no stray schedules/transitions from previous phase
        try:
            self._cancel_schedule()
        except Exception:
            pass
        # Ensure spinner dimmed while a timer phase is active
        try:
            self._update_spinner_state()
        except Exception:
            pass
        # Clear any transition guard as we are actively in a phase now
        try:
            self.transition_event = None
        except Exception:
            pass
        seq = self.sequences[self.mode]
        if self.pick_index < len(seq):
            # Pick timer
            self.phase_duration = int(seq[self.pick_index])
            self.phase_start_ts = time.time()
            self.pick_index += 1
            # Update headers and time display
            self._update_headers()
            self.time_label.text = str(self.phase_duration)
            self.timer_event = Clock.schedule_interval(self.update, 1)
            self.update(0)
        elif self.pick_index == len(seq):
            # 1-minute pick review
            self.phase_duration = 60
            self.phase_start_ts = time.time()
            self.pick_index += 1
            self._update_headers()
            self.time_label.text = str(self.phase_duration)
            self.timer_event = Clock.schedule_interval(self.update, 1)
            self.update(0)
        else:
            # Repeat sequence if rounds remain
            if self.current_round < 3:
                self.current_round += 1
                self.pick_index = 0
                self.start_next_timer()
            else:
                # Draft finished across all rounds
                try:
                    self.pick_label.text = "Draft Finished!"
                except Exception:
                    pass
                try:
                    self.time_label.text = "0"
                except Exception:
                    pass

    def get_remaining(self):
        # If user manually paused, freeze the remaining time regardless of wall-clock
        if self.paused and self.paused_remaining is not None:
            return int(self.paused_remaining)
        if self.phase_duration <= 0 or self.phase_start_ts <= 0:
            return 0
        remaining = int(self.phase_duration - (time.time() - self.phase_start_ts))
        return remaining

    def _phase_title(self):
        seq_len = len(self.sequences[self.mode])
        if self.pick_index == 0:
            return "Pick 1"
        if self.pick_index <= seq_len:
            return f"Pick {self.pick_index}"
        elif self.pick_index == seq_len + 1:
            return "Pick Review"
        return ""

    def _current_booster_iter(self):
        """Return the current Booster number (1..3).
        It should increment only after each full iteration of the picks array
        (i.e., after the Pick Review completes), not per pick.
        """
        try:
            # Before starting, show Booster 1
            if self.current_round <= 0:
                return 1
            # During picks and pick review of the current round, keep current_round
            return self.current_round
        except Exception:
            return 1

    def _update_headers(self):
        """Update Booster X and Pick Y/Pick Review labels."""
        try:
            booster = self._current_booster_iter()
            self.booster_label.text = f"Booster {booster}"
        except Exception:
            pass
        try:
            title = self._phase_title()
            self.pick_label.text = title if title else ""
        except Exception:
            pass

    def _cancel_schedule(self):
        if self.timer_event:
            try:
                self.timer_event.cancel()
            except Exception:
                pass
            self.timer_event = None
        # Also cancel any pending transition to the next phase
        if getattr(self, 'transition_event', None):
            try:
                self.transition_event.cancel()
            except Exception:
                pass
            self.transition_event = None

    def _update_spinner_state(self):
        try:
            waiting = (self.current_round <= 0)
            if hasattr(self, 'spinner') and self.spinner is not None:
                self.spinner.disabled = not waiting
                try:
                    self.spinner.opacity = 0.4 if not waiting else 1
                except Exception:
                    pass
        except Exception:
            pass

    def on_app_resume(self):
        # If not paused and a phase was running, reschedule updates
        if self.current_round > 0 and not self.paused and self.phase_duration > 0 and self.timer_event is None:
            self.timer_event = Clock.schedule_interval(self.update, 1)
            self.update(0)

    def update(self, dt):
        remaining = self.get_remaining()
        # Tick for last 3 seconds (unless suppressed)
        now = time.time()
        if remaining in (1, 2, 3) and self.tick_sound and now >= self.suppress_until:
            try:
                self.tick_sound.play()
            except Exception:
                pass
        if remaining > 0:
            # Update big time and keep headers as-is
            try:
                self.time_label.text = str(remaining)
            except Exception:
                pass
            return
        # Phase complete
        # Cancel active interval but don't clear any existing transition that might have been scheduled
        if self.timer_event:
            try:
                self.timer_event.cancel()
            except Exception:
                pass
            self.timer_event = None
        # Only schedule transition and play sound once
        if getattr(self, 'transition_event', None) is None:
            # Only play sound if not within suppression window
            if time.time() >= self.suppress_until:
                self.play_animal_sound()
            try:
                self.transition_event = Clock.schedule_once(self.start_next_timer, 2)  # 2-second break
            except Exception:
                # Fallback: call directly
                self.start_next_timer()

    def play_animal_sound(self):
        # If we have neither cached sounds nor paths, nothing to play
        if not getattr(self, 'animal_sound_paths', None) and not getattr(self, '_sound_cache', None):
            return
        # Stop any currently playing animal sounds to avoid overlap
        try:
            cache_vals = list(getattr(self, '_sound_cache', {}).values())
            for s in cache_vals:
                try:
                    if s is not None and getattr(s, 'status', None) == 'play':
                        s.stop()
                except Exception:
                    try:
                        s.stop()
                    except Exception:
                        pass
        except Exception:
            pass
        # Small safety to ensure tick sound doesn't overlap right at 0
        try:
            if self.tick_sound is not None:
                self.tick_sound.stop()
        except Exception:
            pass
        # Choose a random path and lazily load the sound if needed
        try:
            paths = getattr(self, 'animal_sound_paths', [])
            if not paths:
                return
            path = random.choice(paths)
            sound = None
            if path in self._sound_cache:
                sound = self._sound_cache.get(path)
            else:
                try:
                    sound = SoundLoader.load(path)
                except Exception:
                    sound = None
                if sound is not None:
                    self._sound_cache[path] = sound
                    # Maintain backward-compat list used elsewhere in code (if any)
                    try:
                        self.animal_sounds.append(sound)
                    except Exception:
                        pass
            if sound:
                sound.play()
        except Exception:
            # As a fallback (shouldn't normally hit), try any preloaded sounds list
            try:
                if self.animal_sounds:
                    s = random.choice(self.animal_sounds)
                    if s:
                        s.play()
            except Exception:
                pass

    # ---- Manual navigation helpers (prev/next) ----
    def _current_phase_info(self):
        """Return a tuple (kind, index) where kind is 'pick', 'review', or 'none'.
        For 'pick', index is zero-based within the sequence. For 'review', index is None.
        """
        try:
            if self.current_round <= 0 or self.pick_index <= 0:
                return ('none', None)
            seq_len = len(self.sequences[self.mode])
            if 1 <= self.pick_index <= seq_len:
                return ('pick', self.pick_index - 1)
            if self.pick_index == seq_len + 1:
                return ('review', None)
            return ('none', None)
        except Exception:
            return ('none', None)

    def has_prev_phase(self):
        kind, idx = self._current_phase_info()
        if kind == 'pick':
            if idx > 0:
                return True
            # idx == 0 -> previous round's review if exists
            return self.current_round > 1
        if kind == 'review':
            return True  # previous is last pick of this round
        return False

    def has_next_phase(self):
        if self.current_round <= 0:
            return False
        seq_len = len(self.sequences[self.mode])
        kind, idx = self._current_phase_info()
        if kind == 'pick':
            # next pick or review always exists within a round
            return True
        if kind == 'review':
            # next is next round if available
            return self.current_round < 3
        return False

    def _start_phase_by_upcoming_index(self, up_idx: int):
        """Start a phase immediately given its 'upcoming index'.
        up_idx in [0..len(seq)-1] -> picks; up_idx == len(seq) -> review.
        """
        try:
            self._cancel_schedule()
        except Exception:
            pass
        self.paused = False
        self.paused_remaining = None
        seq = self.sequences[self.mode]
        if up_idx < len(seq):
            self.phase_duration = int(seq[up_idx])
        else:
            self.phase_duration = 60  # review
        self.phase_start_ts = time.time()
        # As in start_next_timer, set pick_index to reflect started phase (human 1-based picks, review = len+1)
        self.pick_index = min(up_idx + 1, len(seq) + 1)
        # Update headers and time
        try:
            self._update_headers()
            self.time_label.text = str(self.phase_duration)
        except Exception:
            pass
        # Suppress immediate sounds caused by manual navigation
        try:
            self.suppress_until = time.time() + 1.0
        except Exception:
            self.suppress_until = 0
        # Schedule ticking
        self.timer_event = Clock.schedule_interval(self.update, 1)
        self.update(0)

    def go_next_phase(self):
        # Handle starting if not started yet
        if self.current_round <= 0:
            self.current_round = 1
            self._start_phase_by_upcoming_index(0)
            return
        kind, idx = self._current_phase_info()
        seq_len = len(self.sequences[self.mode])
        if kind == 'pick':
            if idx + 1 < seq_len:
                self._start_phase_by_upcoming_index(idx + 1)
            else:
                # move to review
                self._start_phase_by_upcoming_index(seq_len)
        elif kind == 'review':
            if self.current_round < 3:
                self.current_round += 1
                self._start_phase_by_upcoming_index(0)
            else:
                # Already at final review; do nothing
                return

    def go_prev_phase(self):
        if self.current_round <= 0:
            return
        kind, idx = self._current_phase_info()
        seq_len = len(self.sequences[self.mode])
        if kind == 'pick':
            if idx > 0:
                self._start_phase_by_upcoming_index(idx - 1)
            else:
                # First pick of round -> go to previous round's review if any
                if self.current_round > 1:
                    self.current_round -= 1
                    self._start_phase_by_upcoming_index(seq_len)
        elif kind == 'review':
            # Go to last pick of this round
            if seq_len > 0:
                self._start_phase_by_upcoming_index(seq_len - 1)

    def pause_timer(self, instance):
        # User-initiated pause: freeze remaining time exactly as seen
        self.paused_remaining = self.get_remaining()
        self.paused = True
        self._cancel_schedule()
        try:
            self._update_spinner_state()
        except Exception:
            pass

    def reset_all(self, instance):
        # Full reset of the timer state
        self._cancel_schedule()
        try:
            self.time_label.text = "Ready"
            # Refit once for non-numeric label to avoid stale font sizing
            if hasattr(self, '_refit_all') and callable(self._refit_all):
                self._refit_all()
        except Exception:
            pass
        self.time_left = 0
        self.pick_index = 0
        self.current_round = 0
        self.paused = False
        self.paused_remaining = None
        self.phase_start_ts = 0
        self.phase_duration = 0
        # Reset headers
        try:
            self.booster_label.text = "Booster 1"
            self.pick_label.text = ""
        except Exception:
            pass
        # Return spinner to enabled (waiting) state
        try:
            self._update_spinner_state()
        except Exception:
            pass

class DraftTimerApp(App):
    def build(self):
        return DraftTimer()

if __name__ == "__main__":
    DraftTimerApp().run()
