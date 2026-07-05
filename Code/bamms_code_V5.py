import RPi.GPIO as GPIO
import time
import csv
from datetime import datetime
import matplotlib.pyplot as plt
import adafruit_ina219
import board
import busio
import numpy as np
import os

# --- Set the output directory to /home/projects/ ---
output_dir = "/home/projects/"
log_file = os.path.join(output_dir, "motor_log.csv")  # Exporting CSV values for curve analysis
plot_file = os.path.join(output_dir, "motor_plot.png")  # Exporting plot for quick visual overview

# Ensure the output directory exists
os.makedirs(output_dir, exist_ok=True)

# --- Toggle for Sensing Capabilities ---
USE_SENSOR = None

# --- Setup INA219 ---
ina219 = None
i2c = None

# --- Safety function to reinitialize the current sensor if there is a crash --- 
def reset_i2c():
    """Reset the I2C bus and reinitialize INA219."""
    global i2c, ina219
    try:
        if i2c is not None:
            i2c.deinit()
            i2c = None
        if ina219 is not None:
            ina219 = None
        i2c = busio.I2C(board.SCL, board.SDA)
        ina219 = adafruit_ina219.INA219(i2c)
        print("I2C bus reset and INA219 reinitialized.")
        return True
    except Exception as e:
        print(f"Failed to reset I2C: {e}")
        return False

# --- Initialization and checking of current sensor --- 
def init_sensor():
    global USE_SENSOR, i2c, ina219
    if USE_SENSOR:
        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            ina219 = adafruit_ina219.INA219(i2c)
            print("INA219 initialized successfully.")
        except Exception as e:
            print(f"Failed to initialize INA219: {e}")
            reset_i2c()
            if ina219 is None:
                print("INA219 still not detected. Check wiring and I2C.")
                exit(1)

# --- Setup Pololu SMC (RC Mode) ---
GPIO.setmode(GPIO.BCM)
RC1_PIN = 18  # Motor control (PWM)
RC2_PIN = 23  # Dummy signal (1.5ms neutral) to trick Pololu SMC to interact with a DC motor instead of a servo

GPIO.setup(RC1_PIN, GPIO.OUT)
GPIO.setup(RC2_PIN, GPIO.OUT)

# Initialize PWM for RC signals at 50 Hz
PWM_FREQ = 50  # Standard frequency for servo motors, should not be changed
pwm_rc1 = GPIO.PWM(RC1_PIN, PWM_FREQ)
pwm_rc2 = GPIO.PWM(RC2_PIN, PWM_FREQ)
pwm_rc1.start(0)
pwm_rc2.start(0)
pwm_rc2.ChangeDutyCycle(7.5)  # 1.5ms neutral pulse

# --- Global Variables ---
voltage_data = []  # Stores voltage readings
current_data = []  # Stores current readings
time_data = []  # Stores time indices for plotting
smoothing_window = 5  # Smoothing over 5 points to iron out small voltage and current spikes

# --- Functions ---
def set_motor(speed_percent, direction="1"):
    """Set motor speed/direction via PWM on RC1."""
    if direction == "1":
        pulse_width_ms = 1.5 + (0.7 * (speed_percent / 100.0))  # 1.5ms-2.2ms
    elif direction == "2":
        pulse_width_ms = 1.5 - (1 * (speed_percent / 100.0))  # 1.5ms-0.5ms
    else:
        pulse_width_ms = 1.5  # Stop (1.5ms)
    duty_cycle = (pulse_width_ms / 20.0) * 100.0
    pwm_rc1.ChangeDutyCycle(duty_cycle)

def read_sensor(max_retries=5, retry_delay=0.01):
    """Read voltage (V) and current (A) from INA219 with retries."""
    if not USE_SENSOR:
        return None, None
    for attempt in range(max_retries):
        try:
            voltage = ina219.bus_voltage
            current = abs(ina219.current / 1000.0)  # Always positive
            return voltage, current
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"Failed to read sensor after {max_retries} attempts: {e}")
                reset_i2c()
                return None, None
            time.sleep(retry_delay)
    return None, None

def log_data(voltage, current):
    if not USE_SENSOR:
        return
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"Logging: {timestamp}, {voltage:.2f} V, {current:.2f} A")
    with open(log_file, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, voltage, current])
    voltage_data.append(voltage)
    current_data.append(current)
    time_data.append(len(time_data))

def smooth_data(data, window_size=smoothing_window):
    if len(data) < window_size:
        return data
    return np.convolve(data, np.ones(window_size)/window_size, mode='valid')

def plot_data():
    if not USE_SENSOR or not voltage_data or not current_data:
        print("No sensor data to plot.")
        return
    if len(voltage_data) < smoothing_window:
        smoothed_voltage = voltage_data
        smoothed_current = current_data
        raw_voltage = voltage_data
        raw_current = current_data
        time_sliced = time_data
    else:
        smoothed_voltage = smooth_data(voltage_data)
        smoothed_current = smooth_data(current_data)
        raw_voltage = voltage_data
        raw_current = current_data
        time_sliced = time_data[smoothing_window-1:]

    plt.figure(figsize=(12, 6))
    ax1 = plt.gca()
    ax1.plot(time_sliced, smoothed_voltage, label="Voltage (V) - Smoothed", color="red", linewidth=2)
    ax1.plot(time_data, raw_voltage, label="Voltage (V) - Raw", color="red", alpha=0.5, linestyle='--', linewidth=1)
    ax1.set_xlabel("Time (samples)")
    ax1.set_ylabel("Voltage (V)", color="red")
    ax1.tick_params(axis='y', labelcolor="red")
    ax1.set_ylim(0, 12)

    ax2 = ax1.twinx()
    ax2.plot(time_sliced, smoothed_current, label="Current (A) - Smoothed", color="blue", linewidth=2)
    ax2.plot(time_data, raw_current, label="Current (A) - Raw", color="blue", alpha=0.5, linestyle='--', linewidth=1)
    ax2.set_ylabel("Current (A)", color="blue")
    ax2.tick_params(axis='y', labelcolor="blue")
    ax2.set_ylim(0, 5)

    if len(smoothed_voltage) > 0:
        ax1.annotate(f"{smoothed_voltage[-1]:.2f} V",
                    xy=(len(smoothed_voltage)-1, smoothed_voltage[-1]),
                    xytext=(len(smoothed_voltage)-1, smoothed_voltage[-1] + 0.2),
                    color="red", horizontalalignment='right')
    if len(smoothed_current) > 0:
        ax2.annotate(f"{smoothed_current[-1]:.2f} A",
                    xy=(len(smoothed_current)-1, smoothed_current[-1]),
                    xytext=(len(smoothed_current)-1, smoothed_current[-1] + 0.1),
                    color="blue", horizontalalignment='right')

    plt.title("Voltage and Current Over Time (Smoothed vs Raw)")
    plt.grid(True)
    plt.tight_layout()

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

    plt.savefig(plot_file, dpi=200, bbox_inches="tight")
    plt.close()

def clear_line():
    print("\033[2K\033[1A", end="", flush=True)

# --- Preset Functions for Mixing Mode ---
def lineseed_preset():
    print("\n--- Lineseed Preset ---")
    print("Settings: Alternate direction, 80% speed, 130 seconds mixing time.")
    mode = "2"
    direction = "1"
    speed = 80
    measurement_duration = 130
    
    print(f"Starting Lineseed mixing: Alternate direction, {speed}% speed, {measurement_duration} seconds...")
    start_time = time.time()
    last_direction_switch = start_time
    set_motor(speed, direction)
    
    try:
        while (time.time() - start_time) < measurement_duration:
            if mode == "2" and (time.time() - last_direction_switch) >= 10:
                direction = "2" if direction == "1" else "1"
                last_direction_switch = time.time()
                set_motor(speed, direction)
                direction_display = "forward" if direction == "1" else "backward"
                clear_line()
                print(f"Switched to {direction_display} direction.")
                time.sleep(0.5)
            
            remaining_time = max(0, measurement_duration - (time.time() - start_time))
            clear_line()
            print(f"Lineseed Mixing - Direction: {'forward' if direction == '1' else 'backward'} | Speed: {speed}% | Time left: {remaining_time:.1f}s\n", flush=True)
            time.sleep(0.01)
        
        print("\nLineseed mixing completed. Stopping motor...")
        set_motor(0)
        
        # Spin backward for 8 seconds
        print("Spinning motor backward for 8 seconds...")
        set_motor(speed, "2")
        backward_start = time.time()
        while (time.time() - backward_start) < 8:
            remaining_time = max(0, 8 - (time.time() - backward_start))
            clear_line()
            print(f"Backward Spin - Time left: {remaining_time:.1f}s\n", flush=True)
            time.sleep(0.01)
        set_motor(0)
        print("Backward spin completed.")
        
    except KeyboardInterrupt:
        print("\nStopping motor (user interrupted)...")
        set_motor(0)

def tapioca_meel_preset():
    print("\n--- Tapioca Meel Preset ---")
    
    # Step 1
    print("\nStep 1: Mix 20 grams of cold water with 10 grams of tapioca starch.")
    input("Press Enter when ready...")
    
    print("\nApplying: Alternate direction, 20% speed, 130 seconds...")
    mode = "2"
    direction = "1"
    speed = 20
    measurement_duration = 130
    
    start_time = time.time()
    last_direction_switch = start_time
    set_motor(speed, direction)
    
    try:
        while (time.time() - start_time) < measurement_duration:
            if mode == "2" and (time.time() - last_direction_switch) >= 10:
                direction = "2" if direction == "1" else "1"
                last_direction_switch = time.time()
                set_motor(speed, direction)
                direction_display = "forward" if direction == "1" else "backward"
                clear_line()
                print(f"Switched to {direction_display} direction.")
                time.sleep(0.5)
            
            remaining_time = max(0, measurement_duration - (time.time() - start_time))
            clear_line()
            print(f"Tapioca Meel Step 1 - Direction: {'forward' if direction == '1' else 'backward'} | Speed: {speed}% | Time left: {remaining_time:.1f}s\n", flush=True)
            time.sleep(0.01)
        
        print("\nStep 1 completed. Stopping motor...")
        set_motor(0)
        
    except KeyboardInterrupt:
        print("\nStopping motor (user interrupted)...")
        set_motor(0)
        return
    
    # Step 2
    print("\nStep 2: Add 80 grams of hot water.")
    input("Press Enter when ready...")
    
    print("\nApplying: Alternate direction, 20% speed for 60 seconds, then 40% speed for 70 seconds...")
    direction = "1"
    speed = 20
    measurement_duration = 60
    
    start_time = time.time()
    last_direction_switch = start_time
    set_motor(speed, direction)
    
    try:
        while (time.time() - start_time) < measurement_duration:
            if (time.time() - last_direction_switch) >= 10:
                direction = "2" if direction == "1" else "1"
                last_direction_switch = time.time()
                set_motor(speed, direction)
                direction_display = "forward" if direction == "1" else "backward"
                clear_line()
                print(f"Switched to {direction_display} direction.")
                time.sleep(0.5)
            
            remaining_time = max(0, measurement_duration - (time.time() - start_time))
            clear_line()
            print(f"Tapioca Meel Step 2 (20% speed) - Direction: {'forward' if direction == '1' else 'backward'} | Speed: {speed}% | Time left: {remaining_time:.1f}s\n", flush=True)
            time.sleep(0.01)
        
        print("\nSwitching to 40% speed for 70 seconds...")
        speed = 40
        measurement_duration = 70
        start_time = time.time()
        last_direction_switch = start_time
        set_motor(speed, direction)
        
        while (time.time() - start_time) < measurement_duration:
            if (time.time() - last_direction_switch) >= 10:
                direction = "2" if direction == "1" else "1"
                last_direction_switch = time.time()
                set_motor(speed, direction)
                direction_display = "forward" if direction == "1" else "backward"
                clear_line()
                print(f"Switched to {direction_display} direction.")
                time.sleep(0.5)
            
            remaining_time = max(0, measurement_duration - (time.time() - start_time))
            clear_line()
            print(f"Tapioca Meel Step 2 (40% speed) - Direction: {'forward' if direction == '1' else 'backward'} | Speed: {speed}% | Time left: {remaining_time:.1f}s\n", flush=True)
            time.sleep(0.01)
        
        print("\nStep 2 completed. Stopping motor...")
        set_motor(0)
        
    except KeyboardInterrupt:
        print("\nStopping motor (user interrupted)...")
        set_motor(0)
        return
    
    # Step 3
    print("\nStep 3: Add 28 grams of wood flour.")
    input("Press Enter when ready...")
    
    print("\nApplying: Alternate direction, 80% speed, 130 seconds...")
    direction = "1"
    speed = 80
    measurement_duration = 130
    
    start_time = time.time()
    last_direction_switch = start_time
    set_motor(speed, direction)
    
    try:
        while (time.time() - start_time) < measurement_duration:
            if (time.time() - last_direction_switch) >= 10:
                direction = "2" if direction == "1" else "1"
                last_direction_switch = time.time()
                set_motor(speed, direction)
                direction_display = "forward" if direction == "1" else "backward"
                clear_line()
                print(f"Switched to {direction_display} direction.")
                time.sleep(0.5)
            
            remaining_time = max(0, measurement_duration - (time.time() - start_time))
            clear_line()
            print(f"Tapioca Meel Step 3 - Direction: {'forward' if direction == '1' else 'backward'} | Speed: {speed}% | Time left: {remaining_time:.1f}s\n", flush=True)
            time.sleep(0.01)
        
        print("\nStep 3 completed. Stopping motor...")
        set_motor(0)
        
    except KeyboardInterrupt:
        print("\nStopping motor (user interrupted)...")
        set_motor(0)
        return
    
    # Step 4
    print("\nStep 4: Add 3 grams of xantham gum.")
    input("Press Enter when ready...")
    
    print("\nApplying: Alternate direction, 80% speed, 130 seconds...")
    direction = "1"
    speed = 80
    measurement_duration = 130
    
    start_time = time.time()
    last_direction_switch = start_time
    set_motor(speed, direction)
    
    try:
        while (time.time() - start_time) < measurement_duration:
            if (time.time() - last_direction_switch) >= 10:
                direction = "2" if direction == "1" else "1"
                last_direction_switch = time.time()
                set_motor(speed, direction)
                direction_display = "forward" if direction == "1" else "backward"
                clear_line()
                print(f"Switched to {direction_display} direction.")
                time.sleep(0.5)
            
            remaining_time = max(0, measurement_duration - (time.time() - start_time))
            clear_line()
            print(f"Tapioca Meel Step 4 - Direction: {'forward' if direction == '1' else 'backward'} | Speed: {speed}% | Time left: {remaining_time:.1f}s\n", flush=True)
            time.sleep(0.01)
        
        print("\nStep 4 completed. Stopping motor...")
        set_motor(0)
        
        # Spin backward for 8 seconds
        print("Spinning motor backward for 8 seconds...")
        set_motor(speed, "2")
        backward_start = time.time()
        while (time.time() - backward_start) < 8:
            remaining_time = max(0, 8 - (time.time() - backward_start))
            clear_line()
            print(f"Backward Spin - Time left: {remaining_time:.1f}s\n", flush=True)
            time.sleep(0.01)
        set_motor(0)
        print("Backward spin completed.")
        
    except KeyboardInterrupt:
        print("\nStopping motor (user interrupted)...")
        set_motor(0)

def measuring_mode():
    global USE_SENSOR, voltage_data, current_data, time_data
    USE_SENSOR = True
    init_sensor()
    
    # CSV File initialization
    try:
        with open(log_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Time", "Voltage (V)", "Current (A)"])
        print(f"Log file initialized at: {log_file}")
    except Exception as e:
        print(f"Failed to initialize log file: {e}")
        exit(1)
    
    print("\n--- Measuring Mode ---")
    print("Settings: INA219 sensor enabled, single-direction (forward), 10 seconds.")
    
    mode = "1"
    direction = "1"
    speed = 62.5
    measurement_duration = 10
    
    start_time = time.time()
    set_motor(speed, direction)
    stall_count = 0
    logging_active = True
    
    try:
        while (time.time() - start_time) < measurement_duration:
            voltage, current = read_sensor()
            if voltage is not None and current is not None and logging_active:
                log_data(voltage, current)
                clear_line()
                remaining_time = max(0, measurement_duration - (time.time() - start_time))
                print(f"Voltage: {voltage:.2f} V | Current: {current:.2f} A | Time left: {remaining_time:.1f}s\n", flush=True)
                
                # Check for stall condition
                if current >= 3.1 and current <= 3.3:
                    stall_count += 1
                    if stall_count >= 3:
                        print("\nCurrent stalled at ~3.2 A. Stopping logging and motor...")
                        logging_active = False
                        set_motor(0)
                        break
                else:
                    stall_count = 0
            else:
                clear_line()
                remaining_time = max(0, measurement_duration - (time.time() - start_time))
                print(f"Time left: {remaining_time:.1f}s\n", flush=True)
            
            time.sleep(0.1)
        
        if (time.time() - start_time) >= measurement_duration:
            print("\nMeasurement duration completed. Stopping motor...")
            set_motor(0)
        
        # Spin backward for 5 seconds
        print("Spinning motor backward for 5 seconds...")
        set_motor(speed, "2")
        backward_start = time.time()
        while (time.time() - backward_start) < 5:
            remaining_time = max(0, 5 - (time.time() - backward_start))
            clear_line()
            print(f"Backward Spin - Time left: {remaining_time:.1f}s\n", flush=True)
            time.sleep(0.01)
        set_motor(0)
        print("Backward spin completed.")
        
        # Plot data
        plot_data()
        print(f"\nData logged to: {log_file}")
        print(f"Plot saved to: {plot_file}")
        
    except KeyboardInterrupt:
        print("\nStopping motor (user interrupted)...")
        set_motor(0)

# --- Main Script ---
def main():
    global USE_SENSOR, voltage_data, current_data, time_data
    
    print("Select mode:")
    print("1) Basic")
    print("2) Advanced")
    main_mode = input("Enter choice (1/2): ").strip()
    while main_mode not in ["1", "2"]:
        print("Invalid mode. Please enter '1' for Basic or '2' for Advanced.")
        main_mode = input("Enter choice (1/2): ").strip()
    
    if main_mode == "1":
        print("\nSelect Basic mode option:")
        print("1) Mixing")
        print("2) Measuring")
        basic_mode = input("Enter choice (1/2): ").strip()
        while basic_mode not in ["1", "2"]:
            print("Invalid option. Please enter '1' for Mixing or '2' for Measuring.")
            basic_mode = input("Enter choice (1/2): ").strip()
        
        if basic_mode == "1":
            USE_SENSOR = False
            print("\nSelect Mixing preset:")
            print("1) Lineseed")
            print("2) Tapioca Meel")
            preset = input("Enter choice (1/2): ").strip()
            while preset not in ["1", "2"]:
                print("Invalid preset. Please enter '1' for Lineseed or '2' for Tapioca Meel.")
                preset = input("Enter choice (1/2): ").strip()
            
            if preset == "1":
                lineseed_preset()
            else:
                tapioca_meel_preset()
        
        else:
            measuring_mode()
    
        # --- Inside the Advanced mode section of main() ---
    else:
        USE_SENSOR = input("Enable INA219 sensor? (y/n): ").strip().lower() == 'y'
        init_sensor()

        # CSV File initialization if sensor is used for data plotting
        if USE_SENSOR:
            try:
                with open(log_file, "w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(["Time", "Voltage (V)", "Current (A)"])
                print(f"Log file initialized at: {log_file}")
            except Exception as e:
                print(f"Failed to initialize log file: {e}")
                exit(1)

        # User inputs for mode and direction
        print("Select mode:")
        print("1) Single-direction")
        print("2) Alternating (10s forward, 10s backward)")
        mode = input("Enter choice (1/2): ").strip()
        while mode not in ["1", "2"]:
            print("Invalid mode. Please enter '1' or '2'.")
            mode = input("Enter choice (1/2): ").strip()

        if mode == "1":
            direction = input("Enter motor direction (forward = 1/backward = 2): ").strip()
            while direction not in ["1", "2"]:
                print("Invalid direction. Please enter '1' for forward or '2' for backward.")
                direction = input("Enter motor direction (forward = 1/backward = 2): ").strip()
        else:
            direction = "1"

        speed = float(input("Enter motor speed (0-100%): "))
        if not (0 <= speed <= 100):
            print("Invalid speed. Using 50%.")
            speed = 50

        # --- New: Ramp-up option ---
        use_ramp = input("Enable gradual ramp-up? (y/n): ").strip().lower() == 'y'
        ramp_time = 0
        if use_ramp:
            ramp_time = float(input("Enter ramp-up time (seconds): "))
            if ramp_time <= 0:
                print("Invalid ramp-up time. Using 2 seconds.")
                ramp_time = 2

        measurement_duration = float(input("Enter measurement duration (seconds): "))
        if measurement_duration <= 0:
            print("Invalid duration. Using 10 seconds.")
            measurement_duration = 10

        direction_display = "forward" if direction == "1" else "backward"
        print(f"\nStarting motor in {direction_display} direction at {speed}% speed for {measurement_duration} seconds...")
        if use_ramp:
            print(f"Ramping up to {speed}% over {ramp_time} seconds...")
        print("Press Ctrl+C to stop early.")

        start_time = time.time()
        set_motor(0, direction)  # Start at 0% speed
        last_direction_switch = start_time
        ramp_start_time = start_time

        try:
            while (time.time() - start_time) < measurement_duration:
                # --- Ramp-up logic ---
                current_time = time.time() - ramp_start_time
                if use_ramp and current_time < ramp_time:
                    # Calculate current speed based on ramp-up progress
                    ramp_progress = min(current_time / ramp_time, 1.0)
                    current_speed = speed * ramp_progress
                    set_motor(current_speed, direction)
                else:
                    set_motor(speed, direction)

                if mode == "2" and (time.time() - last_direction_switch) >= 10:
                    direction = "2" if direction == "1" else "1"
                    last_direction_switch = time.time()
                    set_motor(speed, direction)
                    direction_display = "forward" if direction == "1" else "backward"
                    clear_line()
                    print(f"Switched to {direction_display} direction.")
                    time.sleep(0.5)

                voltage, current = read_sensor()
                if USE_SENSOR and voltage is not None and current is not None:
                    log_data(voltage, current)
                    clear_line()
                    remaining_time = max(0, measurement_duration - (time.time() - start_time))
                    current_speed_display = speed if not use_ramp or current_time >= ramp_time else current_speed
                    print(f"Voltage: {voltage:.2f} V | Current: {current:.2f} A | Direction: {direction_display} | Speed: {current_speed_display:.1f}% | Time left: {remaining_time:.1f}s\n", flush=True)
                else:
                    clear_line()
                    remaining_time = max(0, measurement_duration - (time.time() - start_time))
                    current_speed_display = speed if not use_ramp or current_time >= ramp_time else current_speed
                    print(f"Direction: {direction_display} | Speed: {current_speed_display:.1f}% | Time left: {remaining_time:.1f}s\n", flush=True)

                time.sleep(0.01)

            print("\nMeasurement duration completed. Stopping motor...")
            set_motor(0)

            if USE_SENSOR:
                print("Spinning motor backward for 8 seconds...")
                set_motor(speed, "2")
                backward_start = time.time()
                while (time.time() - backward_start) < 8:
                    voltage, current = read_sensor()
                    if voltage is not None and current is not None:
                        log_data(voltage, current)
                        clear_line()
                        remaining_time = max(0, 8 - (time.time() - backward_start))
                        print(f"Backward Spin - Voltage: {voltage:.2f} V | Current: {current:.2f} A | Time left: {remaining_time:.1f}s\n", flush=True)
                    else:
                        clear_line()
                        remaining_time = max(0, 8 - (time.time() - backward_start))
                        print(f"Backward Spin - Time left: {remaining_time:.1f}s\n", flush=True)
                    time.sleep(0.01)
                set_motor(0)
                print("Backward spin completed.")

                plot_data()
                print(f"\nData logged to: {log_file}")
                print(f"Plot saved to: {plot_file}")

        except KeyboardInterrupt:
            print("\nStopping motor (user interrupted)...")
            set_motor(0)

        finally:
            print(f"Total samples: {len(time_data) if USE_SENSOR else 'N/A (sensor disabled)'}")
    
    # Cleanup
    pwm_rc1.ChangeDutyCycle(0)
    pwm_rc2.ChangeDutyCycle(0)
    pwm_rc1.stop()
    pwm_rc2.stop()
    GPIO.cleanup()

if __name__ == "__main__":
    main()