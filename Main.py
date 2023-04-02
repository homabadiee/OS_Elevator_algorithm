import sys
from functools import partial
from PyQt5.QtCore import QRect, QThread, QMutex, QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QWidget, QPushButton, QApplication, QLabel, QTextEdit, QVBoxLayout, QHBoxLayout, QLCDNumber
from ElevatorState import *
from ExternalRequest import *


# window size setting
UI_SIZE = QRect(200, 200, 450, 800)

ELEVATOR_NUM = 3
ELEVATOR_FLOORS = 15

TIME_PER_FLOOR = 1000
WAIT_TIME = 1500

external_requests = []
elevator_states = []
cur_floor = []
up_targets = []
down_targets = []
elev_direction = []

for elev in range(ELEVATOR_NUM):
    elevator_states.append(ElevatorState.idle)  # default idle
    cur_floor.append(1)  # Default is on the first floor
    up_targets.append([])
    down_targets.append([])
    elev_direction.append(Direction.up)  # Up by default


mutex = QMutex()

class Elevator(QThread):
    def __init__(self, elev_id):
        super().__init__()
        self.elevator_id = elev_id

    # move one floor
    def move(self, direction):
        if direction == Direction.up:
            elevator_states[self.elevator_id] = ElevatorState.going_up
        elif direction == Direction.down:
            elevator_states[self.elevator_id] = ElevatorState.going_down

        mutex.unlock()

        self.msleep(TIME_PER_FLOOR)

        mutex.lock()

        if direction == Direction.up:
            cur_floor[self.elevator_id] += 1
        elif direction == Direction.down:
            cur_floor[self.elevator_id] -= 1
        elevator_states[self.elevator_id] = ElevatorState.idle
        print(self.elevator_id, " is now in", cur_floor[self.elevator_id])


    def wait_target(self):
        elevator_states[self.elevator_id] = ElevatorState.wait
        mutex.unlock()
        self.msleep(WAIT_TIME)

        # lock back
        mutex.lock()


# LOOK algorithm
    def run(self):
        while True:
            mutex.lock()

            if elev_direction[self.elevator_id] == Direction.up:
                if up_targets[self.elevator_id] != []:
                    if up_targets[self.elevator_id][0] == cur_floor[self.elevator_id]:
                        self.wait_target()

                        if up_targets != []:
                            up_targets[self.elevator_id].pop(0)
                        for external_req in external_requests:
                            if external_req.target == cur_floor[self.elevator_id]:
                                external_req.state = ExternalRequestState.finished

                    elif up_targets[self.elevator_id][0] > cur_floor[self.elevator_id]:
                        self.move(Direction.up)

                # change the direction
                elif up_targets[self.elevator_id] == [] and down_targets[self.elevator_id] != []:
                    elev_direction[self.elevator_id] = Direction.down


            elif elev_direction[self.elevator_id] == Direction.down:
                if down_targets[self.elevator_id] != []:
                    if down_targets[self.elevator_id][0] == cur_floor[self.elevator_id]:
                        self.wait_target()

                        if down_targets != []:
                            down_targets[self.elevator_id].pop(0)
                        for external_req in external_requests:
                            if external_req.target == cur_floor[self.elevator_id]:
                                external_req.state = ExternalRequestState.finished

                    elif down_targets[self.elevator_id][0] < cur_floor[self.elevator_id]:
                        self.move(Direction.down)

                # change the direction
                elif down_targets[self.elevator_id] == [] and up_targets[self.elevator_id] != []:
                    elev_direction[self.elevator_id] = Direction.up

            mutex.unlock()


class Handler(QThread):
    def __init__(self):
        super().__init__()

    def run(self):
        while True:
            mutex.lock()  # prevent assigning same request to multiple elevator

            global external_requests

            for external_req in external_requests:
                if external_req.state == ExternalRequestState.unassigned:
                    min_distance = ELEVATOR_FLOORS + 1
                    target_id = -1
                    for i in range(ELEVATOR_NUM):
                        origin = cur_floor[i]
                        if elevator_states[i] == ElevatorState.going_up:
                            origin += 1
                        elif elevator_states[i] == ElevatorState.going_down:
                            origin -= 1

                        if elev_direction[i] == Direction.up:
                            targets = up_targets[i]
                        else:
                            targets = down_targets[i]


                        if targets == []:
                            distance = abs(origin - external_req.target)

                        elif elev_direction[i] == external_req.move_direction and \
                                ((external_req.move_direction == Direction.up and external_req.target >= origin) or
                                 (external_req.move_direction == Direction.down and external_req.target <= origin)):
                            distance = abs(origin - external_req.target)

                        else:
                            distance = abs(origin - targets[-1]) + abs(external_req.target - targets[-1])


                        if distance < min_distance:
                            min_distance = distance
                            target_id = i


                    if target_id != -1:
                        if cur_floor[target_id] == external_req.target:
                            if external_req.move_direction == Direction.up and external_req.target not in up_targets[
                                target_id] and elevator_states[target_id] != ElevatorState.going_up:
                                up_targets[target_id].append(external_req.target)
                                up_targets[target_id].sort()
                                print(up_targets)
                                external_req.state = ExternalRequestState.waiting

                            elif external_req.move_direction == Direction.down and external_req.target not in down_targets[
                                target_id] and elevator_states[target_id] != ElevatorState.going_down:
                                down_targets[target_id].append(external_req.target)
                                down_targets[target_id].sort(reverse=True)  # Descending order
                                print(down_targets)
                                external_req.state = ExternalRequestState.waiting

                        elif cur_floor[target_id] < external_req.target and external_req.target not in \
                                up_targets[target_id]:
                            up_targets[target_id].append(external_req.target)
                            up_targets[target_id].sort()
                            print(up_targets)
                            external_req.state = ExternalRequestState.waiting
                        elif cur_floor[target_id] > external_req.target and external_req.target not in down_targets[
                            target_id]:
                            down_targets[target_id].append(external_req.target)
                            down_targets[target_id].sort(reverse=True)  # Descending order
                            print(down_targets)
                            external_req.state = ExternalRequestState.waiting

            # remove completed tasks
            for task in external_requests:
                if task.state == ExternalRequestState.finished:
                    external_requests.remove(task)

            mutex.unlock()


class ElevatorUi(QWidget):
    def __init__(self):
        super().__init__()

        self.floor_displayer = []
        self.inner_num_buttons = []
        self.outer_up_buttons = []
        self.outer_down_buttons = []
        self.timer = QTimer()

        self.set_UI()


    def set_UI(self):
        self.setWindowTitle("elevator simulator")
        self.setGeometry(UI_SIZE)

        h1 = QHBoxLayout()
        self.setLayout(h1)

        h2 = QHBoxLayout()
        h1.addLayout(h2)

        for i in range(ELEVATOR_NUM):
            v2 = QVBoxLayout()
            h2.addLayout(v2)
            floor_display = QLCDNumber()
            self.floor_displayer.append(floor_display)
            self.inner_num_buttons.append([])

            # internal number keys
            for j in range(ELEVATOR_FLOORS):
                button = QPushButton(str(ELEVATOR_FLOORS - j))
                button.setFixedSize(100, 25)
                button.clicked.connect(partial(self.inner_num_button_pushed, i, ELEVATOR_FLOORS - j))
                button.setStyleSheet("background-color : rgb(255,255,255)")
                self.inner_num_buttons[i].append(button)
                v2.addWidget(button)

        v3 = QVBoxLayout()
        h1.addLayout(v3)
        for i in range(ELEVATOR_FLOORS):
            h4 = QHBoxLayout()
            v3.addLayout(h4)
            label = QLabel(str(ELEVATOR_FLOORS - i))
            h4.addWidget(label)
            if i != 0:
                up_button = QPushButton()
                up_button.setIcon(QIcon('up.png'))
                up_button.setFixedSize(30, 30)
                up_button.clicked.connect(
                    partial(self.outer_button_pushed, ELEVATOR_FLOORS - i, Direction.up))
                self.outer_up_buttons.append(up_button)
                h4.addWidget(up_button)

            if i != ELEVATOR_FLOORS - 1:
                down_button = QPushButton()
                down_button.setIcon(QIcon('down.png'))
                down_button.setFixedSize(30, 30)
                down_button.clicked.connect(
                    partial(self.outer_button_pushed, ELEVATOR_FLOORS - i, Direction.down))
                self.outer_down_buttons.append(down_button)
                h4.addWidget(down_button)

        v1 = QVBoxLayout()
        h1.addLayout(v1)

        self.timer.setInterval(30)
        self.timer.timeout.connect(self.update)
        self.timer.start()

        self.show()


    def inner_num_button_pushed(self, elevator_id, floor):
        mutex.lock()

        # The same floor is not processed
        if floor == cur_floor[elevator_id]:
            mutex.unlock()
            return

        if floor > cur_floor[elevator_id] and floor not in up_targets[elevator_id]:
            up_targets[elevator_id].append(floor)
            up_targets[elevator_id].sort()
        elif floor < cur_floor[elevator_id] and floor not in down_targets[elevator_id]:
            down_targets[elevator_id].append(floor)
            down_targets[elevator_id].sort(reverse=True)  # Descending

        mutex.unlock()

        self.inner_num_buttons[elevator_id][ELEVATOR_FLOORS - floor].setStyleSheet("background-color : yellow")


    def outer_button_pushed(self, floor, move_state):
        mutex.lock()

        task = ExternalRequest(floor, move_state)

        if task not in external_requests:
            external_requests.append(task)

            if move_state == Direction.up:
                self.outer_up_buttons[ELEVATOR_FLOORS - floor - 1].setStyleSheet("background-color : yellow")

            elif elev_direction == Direction.down:
                self.outer_down_buttons[ELEVATOR_FLOORS - floor].setStyleSheet("background-color : yellow")

        mutex.unlock()

    def update(self):
        mutex.lock()
        for i in range(ELEVATOR_NUM):
            if elevator_states[i] == ElevatorState.wait:
                self.inner_num_buttons[i][ELEVATOR_FLOORS - cur_floor[i]].setStyleSheet("background-color : cyan")
            else:
                self.inner_num_buttons[i][ELEVATOR_FLOORS - cur_floor[i]].setStyleSheet("background-color : white")

        mutex.unlock()

        for button in self.outer_up_buttons:
            button.setStyleSheet("background-color : None")

        for button in self.outer_down_buttons:
            button.setStyleSheet("background-color : None")

        mutex.lock()
        for external_req in external_requests:
            if external_req.state != ExternalRequestState.finished:
                if external_req.move_direction == Direction.up:
                    self.outer_up_buttons[ELEVATOR_FLOORS - external_req.target - 1].setStyleSheet(
                        "background-color : pink")
                elif external_req.move_direction == Direction.down:
                    self.outer_down_buttons[ELEVATOR_FLOORS - external_req.target].setStyleSheet(
                        "background-color : pink")

        mutex.unlock()


if __name__ == '__main__':
    app = QApplication(sys.argv)

    handler = Handler()
    handler.start()

    elevators = []
    for i in range(ELEVATOR_NUM):
        elevators.append(Elevator(i))

    for elevator in elevators:
        elevator.start()

    e = ElevatorUi()
    sys.exit(app.exec_())