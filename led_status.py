import RPi.GPIO as GPIO

GREEN = 17
BLUE = 27
RED = 22

_initialized = False


def setup():
    global _initialized

    if _initialized:
        return

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    GPIO.setup(GREEN, GPIO.OUT)
    GPIO.setup(BLUE, GPIO.OUT)
    GPIO.setup(RED, GPIO.OUT)

    GPIO.output(GREEN, False)
    GPIO.output(BLUE, False)
    GPIO.output(RED, False)

    _initialized = True


def set_green(state: bool):
    GPIO.output(GREEN, state)


def set_blue(state: bool):
    GPIO.output(BLUE, state)


def set_red(state: bool):
    GPIO.output(RED, state)


def all_off():
    GPIO.output(GREEN, False)
    GPIO.output(BLUE, False)
    GPIO.output(RED, False)


def cleanup():
    all_off()
    GPIO.cleanup()