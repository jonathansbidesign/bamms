# Building Instructions

-Combine the 4 parts of the Raspberry Pi image, with 

    cat raspberry_pi_backup.img.gz.part* > raspberry_pi_backup.img.gz # Command for Linux and macOS
    copy /b raspberry_pi_backup.img.gz.part1 + raspberry_pi_backup.img.gz.part2 + raspberry_pi_backup.img.gz.part3 + raspberry_pi_backup.img.gz.part4 raspberry_pi_backup.img.gz # Command for Windows 


-Flash the Raspberry Pi image onto a blank, formatted Micro SD Card.

-Insert the SD Card in the Raspberry Pi.

-Load up the .3mf file in your slicer of choice, and make necessary modifications for your printing hardware (files are prepared for a BambuLab A1 Mini). Printing should take approximately 22 hours (referencing done for BambuLab A1 Mini), and should use approximately 689 grams of PLA.

-Follow assembly instructions from exploded view and technical drawings.

-An M3-12 screw must be added to the included threaded for the motor connector, to reduce wear and tear when in contact with the motor shaft.

-Perform electronic connections by following electronic schematics.

-CAD files can be modified using the .step file

-Python code can be modified using the .py file in this repository and on the Raspberry Pi's SD card

# Usage Instructions

-Power device on by plugging it in. Ensure all electronic connections are correct and secure.

-Choose between Advanced and Basic modes.

-In Advanced mode, all required information to be inputted is asked on-screen. The Advanced mode is primarily for developers. 

-In Basic mode, choose between Mixing and Measuring modes.

-In Mixing mode, securely connect the mixing effector to the motor connector. Choose your recipe.

-Follow on-screen instructions for mixing.

-In Measuring mode:

-You must first remove the mixed sample from the tank. 

-Place it into the material shaper, and press both halves to get a shaped sample. 

-Place sample in mixing tank. 

-Make sure the distance between the bottom of the lead screw and the bottom of the measuring plate is a few centimeters more than the height of the mixing tank. 

-Securely connect the measuring effector. 

-Add the measuring clamp on top, and lower it until not possible anymore. 

-Gently rotate the measuring clamp so it grabs onto the pegs on the mixing tank.

-Activate Measuring mode to perform measurement.


To offload on-device data from the Raspberry Pi, either perform an SSH connection, or connect the Raspberry Pi's Micro SD card to a computer.

#  Bill of Materials (around 161 euros)


-60W DC motor (e.g., JGB37-555 60W) (around 10 euros)

-Raspberry Pi (e.g., Raspberry Pi Zero 2) (around 80 euros)

-Motor-compatible motor driver (e.g., BT7960) (around 6 euros)

-Current sensor (e.g., ACS712, INA219) (around 3 euros)

-Analog-to-digital converter (ADS1115) (around 2 euros)

-60W, 12V power supply (e.g., Meanwell LPV-60-12) (around 40 euros)

-1 spool of PLA (total material usage should be around 698 grams) (around 20 euros)

-1 M3-12 screw
