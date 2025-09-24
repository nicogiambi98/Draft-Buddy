from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.clock import Clock
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.core.audio import SoundLoader
import random
import time

class DraftTimer(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", **kwargs)

        # Mode and round tracking
        self.mode = "Expert"
        self.current_round = 0
        self.pick_index = 0
        self.paused = False

        # Phase timing (wall-clock based)
        self.phase_start_ts = 0  # epoch seconds when current phase started
        self.phase_duration = 0  # seconds allocated to current phase

        # Load sounds
        self.animal_sounds = [
            SoundLoader.load(f"assets/{name}.wav")
            for name in ["bark", "meow", "geese", "bird", "cow"]
        ]
        self.tick_sound = SoundLoader.load("assets/tick.wav")

        # Prepare sequences
        self.sequences = self.get_sequences()
        self.timer_event = None
        self.time_left = 0

        # UI
        self.label = Label(text="Select Mode & Start", font_size=48, size_hint=(1, 0.5))
        self.add_widget(self.label)

        self.spinner = Spinner(
            text="Expert",
            values=("Expert", "Regular", "Beginner"),
            size_hint=(1, 0.2)
        )
        self.spinner.bind(text=self.set_mode)
        self.add_widget(self.spinner)

        btn_layout = BoxLayout(size_hint=(1, 0.3))
        # Use ASCII-safe labels to ensure cross-platform support
        start_btn = Button(text=">", font_size='64sp', on_press=self.start_sequence)   # Play
        pause_btn = Button(text="||", font_size='64sp', on_press=self.pause_timer)     # Pause
        reset_btn = Button(text="R", font_size='64sp', on_press=self.reset_all)        # Reset
        for b in [start_btn, pause_btn, reset_btn]:
            btn_layout.add_widget(b)
        self.add_widget(btn_layout)

    def set_mode(self, spinner, text):
        self.mode = text
        self.sequences = self.get_sequences()
        self.reset_all(None)

    def get_sequences(self):
        expert = [50, 50, 50, 40, 40, 30, 30, 20, 20, 10, 10, 5, 5]
        regular = [55, 55, 55, 45, 45, 35, 35, 25, 25, 10, 10, 5, 5]
        beginner = [60, 60, 60, 50, 50, 40, 40, 30, 30, 15, 15, 5, 5]
        return {
            "Expert": expert,
            "Regular": regular,
            "Beginner": beginner
        }

    def start_sequence(self, instance):
        # Start or resume sequence
        if self.timer_event:
            return
        if self.current_round > 0 and self.paused and self.phase_duration > 0:
            # Resume current phase
            self.paused = False
            # Re-anchor start time so remaining stays the same
            remaining = self.get_remaining()
            self.phase_start_ts = time.time() - (self.phase_duration - remaining)
            self.timer_event = Clock.schedule_interval(self.update, 1)
            self.update(0)
            return
        # Fresh start
        self.current_round = 1
        self.pick_index = 0
        self.paused = False
        self.start_next_timer()

    def start_next_timer(self, dt=None):
        seq = self.sequences[self.mode]
        if self.pick_index < len(seq):
            # Pick timer
            self.phase_duration = int(seq[self.pick_index])
            self.phase_start_ts = time.time()
            self.pick_index += 1
            self.label.text = f"Pick {self.pick_index} - {self.phase_duration}s"
            self.timer_event = Clock.schedule_interval(self.update, 1)
            self.update(0)
        elif self.pick_index == len(seq):
            # 1-minute build phase
            self.phase_duration = 60
            self.phase_start_ts = time.time()
            self.pick_index += 1
            self.label.text = f"Build Phase - {self.phase_duration}s"
            self.timer_event = Clock.schedule_interval(self.update, 1)
            self.update(0)
        else:
            # Repeat sequence if rounds remain
            if self.current_round < 3:
                self.current_round += 1
                self.pick_index = 0
                self.start_next_timer()
            else:
                self.label.text = "Draft Finished!"

    def get_remaining(self):
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
            return "Build Phase"
        return ""

    def _cancel_schedule(self):
        if self.timer_event:
            try:
                self.timer_event.cancel()
            except Exception:
                pass
            self.timer_event = None

    def on_app_resume(self):
        # If not paused and a phase was running, reschedule updates
        if self.current_round > 0 and not self.paused and self.phase_duration > 0 and self.timer_event is None:
            self.timer_event = Clock.schedule_interval(self.update, 1)
            self.update(0)

    def update(self, dt):
        remaining = self.get_remaining()
        # Tick for last 3 seconds
        if remaining in (1, 2, 3) and self.tick_sound:
            try:
                self.tick_sound.play()
            except Exception:
                pass
        if remaining > 0:
            self.label.text = f"{self._phase_title()} - {remaining}s"
            return
        # Phase complete
        self._cancel_schedule()
        self.play_animal_sound()
        Clock.schedule_once(self.start_next_timer, 2)  # 2-second break

    def play_animal_sound(self):
        if self.animal_sounds:
            sound = random.choice(self.animal_sounds)
            if sound:
                sound.play()

    def pause_timer(self, instance):
        # User-initiated pause
        self.paused = True
        self._cancel_schedule()

    def reset_all(self, instance):
        self.pause_timer(None)
        self.label.text = "Ready"
        self.time_left = 0
        self.pick_index = 0
        self.current_round = 0
        self.paused = False
        self.phase_start_ts = 0
        self.phase_duration = 0

class DraftTimerApp(App):
    def build(self):
        return DraftTimer()

if __name__ == "__main__":
    DraftTimerApp().run()
