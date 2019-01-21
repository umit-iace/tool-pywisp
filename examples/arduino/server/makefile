# Arduino Make file. Refer to https://github.com/sudar/Arduino-Makefile

BOARD_TAG    	= uno

ifeq ($(OS),Windows_NT)
ARDUINO_DIR   	= /c/Arduino/
MONITOR_PORT	= com4

include $(USERPROFILE)/Documents/Arduino-Makefile/Arduino.mk

else
ARDUINO_DIR   	= /Applications/Arduino.app/Contents/Java

include $(HOME)/Documents/development/git/Arduino-Makefile/Arduino.mk

endif
