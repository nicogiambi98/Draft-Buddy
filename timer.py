from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.clock import Clock
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.core.audio import SoundLoader
import random

class DraftTimer(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", **kwargs)

        # Mode and round tracking
        self.mode = "Expert"
        self.current_round = 0
        self.pick_index = 0

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
        # Use icon-like glyphs for clarity on large buttons
        start_btn = Button(text="\u25B6", font_size='64sp', on_press=self.start_sequence)  # ▶
        pause_btn = Button(text="\u23F8", font_size='64sp', on_press=self.pause_timer)     # ⏸
        reset_btn = Button(text="\u21BB", font_size='64sp', on_press=self.reset_all)       # ↻
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
        if self.timer_event:
            return
        self.current_round = 1
        self.pick_index = 0
        self.start_next_timer()

    def start_next_timer(self, dt=None):
        seq = self.sequences[self.mode]
        if self.pick_index < len(seq):
            # Pick timer
            self.time_left = seq[self.pick_index]
            self.pick_index += 1
            self.label.text = f"Pick {self.pick_index} - {self.time_left}s"
            self.timer_event = Clock.schedule_interval(self.update, 1)
        elif self.pick_index == len(seq):
            # 1-minute build phase
            self.time_left = 60
            self.pick_index += 1
            self.label.text = f"Build Phase - {self.time_left}s"
            self.timer_event = Clock.schedule_interval(self.update, 1)
        else:
            # Repeat sequence if rounds remain
            if self.current_round < 3:
                self.current_round += 1
                self.pick_index = 0
                self.start_next_timer()
            else:
                self.label.text = "Draft Finished!"

    def update(self, dt):
        if self.time_left > 0:
            # Tick for last 3 seconds
            if self.time_left <= 3 and self.tick_sound:
                self.tick_sound.play()
            self.time_left -= 1
            self.label.text = self.label.text.split("-")[0] + f"- {self.time_left}s"
        else:
            self.pause_timer(None)
            self.play_animal_sound()
            Clock.schedule_once(self.start_next_timer, 2)  # 2-second break

    def play_animal_sound(self):
        if self.animal_sounds:
            sound = random.choice(self.animal_sounds)
            if sound:
                sound.play()

    def pause_timer(self, instance):
        if self.timer_event:
            self.timer_event.cancel()
            self.timer_event = None

    def reset_all(self, instance):
        self.pause_timer(None)
        self.label.text = "Ready"
        self.time_left = 0
        self.pick_index = 0
        self.current_round = 0

class DraftTimerApp(App):
    def build(self):
        return DraftTimer()

if __name__ == "__main__":
    DraftTimerApp().run()
