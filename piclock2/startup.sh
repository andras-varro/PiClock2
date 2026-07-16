#!/bin/bash
# Startup script for PiClock 2 (Python 3 / PyQt5 rewrite).
#
# Launched from ~/.config/autostart/PiClock.desktop, e.g.:
#   Exec=/bin/sh -c "/bin/sh ~/piclock2/startup.sh -m 15"
#
# Flags (mirror the original PiClock startup.sh):
#   -n | --no-sleep | --no-delay   start immediately
#   -d | --delay N                 sleep N seconds first
#   -m | --message-delay N         show a Now/Cancel dialog for N seconds
#   -s | --screen-log              log to the terminal instead of a file

cd "$HOME/piclock2" || exit 1

if [ -z "$DISPLAY" ]; then
	export DISPLAY=:0
fi

# Optional startup delay / cancel window so the desktop can settle.
DELAY="sleep 45"
case "$1" in
	-n|--no-sleep|--no-delay) DELAY=""; shift ;;
	-d|--delay) DELAY="sleep $2"; shift 2 ;;
	-m|--message-delay)
		DELAY='zenity --question --title "PiClock 2" --ok-label=Now --cancel-label=Cancel --timeout '"$2"' --text "Starting PiClock 2 in '"$2"' seconds" >/dev/null 2>&1'
		shift 2 ;;
esac
eval $DELAY
if [ $? -eq 1 ]; then
	echo "PiClock 2 cancelled"
	exit 0
fi

# Stop screen blanking / power management.
echo "Disabling screen blanking...."
xset s off
xset -dpms
xset s noblank

# Hide the mouse cursor.
if ! pgrep unclutter >/dev/null 2>&1; then
	unclutter >/dev/null 2>&1 &
fi

# The main app.
if [ "$1" = "-s" -o "$1" = "--screen-log" ]; then
	echo "Starting PiClock 2.... logging to screen."
	python3 -u main.py
else
	echo "Rotating log files...."
	rm -f piclock2.7.log
	for i in 6 5 4 3 2 1; do
		mv -f "piclock2.$i.log" "piclock2.$((i + 1)).log" >/dev/null 2>&1
	done
	echo "Starting PiClock 2.... logging to piclock2.1.log"
	python3 -u main.py >piclock2.1.log 2>&1
fi
