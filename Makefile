ICON_SRC ?= $(HOME)/projects/assets/icons/regular
RESOURCE  = linscreencapture/linscreencapture.gresource
# Uses Xvfb when available, else the live display.
HEADLESS := $(shell command -v xvfb-run >/dev/null 2>&1 && echo 'xvfb-run -a -s "-screen 0 1600x1000x24"')

.PHONY: icons resources run test snapshot clean

icons:
	python3 tools/sync_icons.py --source "$(ICON_SRC)"
	$(MAKE) resources

resources:
	glib-compile-resources --target $(RESOURCE) --sourcedir data --sourcedir linscreencapture/ui data/linscreencapture.gresource.xml

run: resources
	python3 -m linscreencapture

test: resources
	$(HEADLESS) python3 -m pytest -q

snapshot: resources
	$(HEADLESS) python3 tools/snapshot_shell.py

clean:
	rm -f $(RESOURCE)
