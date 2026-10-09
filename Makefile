ICON_SRC ?= $(HOME)/projects/assets/icons/regular
RESOURCE  = linscreencapture/linscreencapture.gresource
# Uses Xvfb when available, else the live display.
HEADLESS := $(shell command -v xvfb-run >/dev/null 2>&1 && echo 'xvfb-run -a -s "-screen 0 1600x1000x24"')

.PHONY: icons resources run test snapshot clean launcher unlauncher

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

# User-level menu entry "LinScreenCapture3" that runs this checkout (no install needed).
APPS   = $(HOME)/.local/share/applications
ICONS  = $(HOME)/.local/share/icons/hicolor
launcher: resources
	mkdir -p $(APPS) $(ICONS)/256x256/apps $(ICONS)/48x48/apps
	sed "s|@ROOT@|$(CURDIR)|g" data/linscreencapture3-dev.desktop.in > $(APPS)/linscreencapture3.desktop
	cp resources/icons/linscreencapture-256.png $(ICONS)/256x256/apps/linscreencapture3.png
	cp resources/icons/linscreencapture-48.png $(ICONS)/48x48/apps/linscreencapture3.png
	-update-desktop-database $(APPS) 2>/dev/null
	-gtk-update-icon-cache -q -t $(ICONS) 2>/dev/null
	@echo "Menu entry installed: $(APPS)/linscreencapture3.desktop"

unlauncher:
	rm -f $(APPS)/linscreencapture3.desktop $(ICONS)/256x256/apps/linscreencapture3.png $(ICONS)/48x48/apps/linscreencapture3.png
	-update-desktop-database $(APPS) 2>/dev/null
